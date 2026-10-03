# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN INVOCATION RELAY | On-Demand Engine Owner (v1.6.0)
# Copyright (C) 2026 uncoalesced
#
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------
# Idle-cheap background process: starts server.py when a cloud agent needs it
# and exits it after invocation.idle_unload_s of inactivity. Process exit is the
# only reliable way to hand the VRAM back (Folding@Home uses it otherwise).
#
#   relay.py                  run (tray on Windows, headless elsewhere)
#   relay.py --ensure-server  start a relay if none, and make sure the server is up
#   relay.py --headless       never show a tray icon
#   relay.py --quit           ask the running relay to stop
#
# Must stay light: stdlib + psutil + config + settings + audit only. No flask,
# torch, llama_cpp or server import here (tests/test_v160_relay.py checks).

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import psutil  # noqa: E402

from config import BASE_DIR, LOG_PATH, SERVER_HOST, SERVER_PORT, STORAGE_PATH  # noqa: E402
from core_system import settings  # noqa: E402

try:
    from core_system.audit import ghost
except Exception:  # logging must never stop the relay
    ghost = None

POLL_S = 1.0          # request/quit file poll
IDLE_CHECK_S = 30.0   # /health idle check while we own a server
HEALTH_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/health"
LOCK_FILE = Path(STORAGE_PATH) / "relay.lock"
REQUEST_FILE = Path(STORAGE_PATH) / "relay.request"
QUIT_FILE = Path(STORAGE_PATH) / "relay.quit"


def _log(level, msg):
    try:
        getattr(ghost, level)(f"[RELAY] {msg}")
    except Exception:
        pass


def kill_proc_tree(pid):
    """Same as launcher.kill_proc_tree (not imported: launcher pulls in requests + config)."""
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass


def http_health(url=HEALTH_URL, timeout=2.0):
    """/health JSON plus "ok" (HTTP 200), or None when nothing answers."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return {**json.loads(r.read() or b"{}"), "ok": r.status == 200}
    except urllib.error.HTTPError as e:  # 503 = booting, still a server
        try:
            body = json.loads(e.read() or b"{}")
        except Exception:
            body = {}
        return {**body, "ok": False}
    except Exception:
        return None


def spawn_server():
    LOG_PATH.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    with open(LOG_PATH / "relay_server.log", "ab") as log:
        return subprocess.Popen(
            [sys.executable, str(BASE_DIR / "server.py")],
            cwd=str(BASE_DIR), stdin=subprocess.DEVNULL, stdout=log,
            stderr=subprocess.STDOUT, creationflags=flags,
        )


def _idle_timeout():
    return settings.get("invocation.idle_unload_s")


class Relay:
    """Owns at most one server.py child. Never kills a server it did not spawn."""

    def __init__(self, health_fn=http_health, spawn_fn=spawn_server, kill_fn=kill_proc_tree,
                 clock=time.monotonic, idle_timeout_fn=_idle_timeout,
                 request_file=REQUEST_FILE, quit_file=QUIT_FILE):
        self.health_fn, self.spawn_fn, self.kill_fn = health_fn, spawn_fn, kill_fn
        self.clock, self.idle_timeout_fn = clock, idle_timeout_fn
        self.request_file, self.quit_file = Path(request_file), Path(quit_file)
        self.child = None
        self.stopped = threading.Event()
        self._lock = threading.RLock()  # tray thread vs relay loop
        self._last_idle_check = clock()

    def status(self):
        return "serving" if self.child is not None else "idle"

    def _owns(self, pid):
        if self.child is None or pid is None:
            return False
        if pid == self.child.pid:
            return True
        # A venv python.exe on Windows is a launcher stub that runs the real
        # interpreter as its child, so the serving pid can be a descendant.
        try:
            return any(c.pid == pid for c in psutil.Process(self.child.pid).children(recursive=True))
        except psutil.Error:
            return False

    def ensure_server(self):
        with self._lock:
            if self.child is not None and self.child.poll() is None:
                return  # ours, still booting or serving
            if self.health_fn() is not None:
                return  # someone else's server (launcher / user): use it, never own it
            self.child = self.spawn_fn()
            self._last_idle_check = self.clock()
            _log("info", f"Started server.py (pid {self.child.pid}).")

    def unload_now(self, reason="requested"):
        with self._lock:
            if self.child is None:
                return False
            pid, self.child = self.child.pid, None
            self.kill_fn(pid)
            _log("info", f"Stopped server.py (pid {pid}): {reason}. VRAM released.")
            return True

    def check_idle(self):
        with self._lock:
            if self.child is None:
                return
            h = self.health_fn()
            if not h or not h.get("ok") or not self._owns(h.get("pid")):
                return
            timeout = self.idle_timeout_fn()
            if h.get("inflight", 0) == 0 and h.get("idle_s", 0) >= timeout:
                self.unload_now(f"idle {h.get('idle_s')}s >= {timeout}s")

    def request_quit(self):
        self.stopped.set()

    def tick(self):
        if _take(self.quit_file):
            _log("info", "Quit requested.")
            self.request_quit()
            return
        if _take(self.request_file):
            self.ensure_server()
        with self._lock:
            if self.child is not None and self.child.poll() is not None:
                _log("warning", f"server.py (pid {self.child.pid}) exited on its own (code {self.child.returncode}).")
                self.child = None
        now = self.clock()
        if now - self._last_idle_check >= IDLE_CHECK_S:
            self._last_idle_check = now
            self.check_idle()

    def run(self):
        while not self.stopped.is_set():
            try:
                self.tick()
            except Exception as e:  # one bad poll must not kill the relay
                _log("error", f"Tick failed: {e}")
            self.stopped.wait(POLL_S)

    def shutdown(self):
        self.request_quit()
        self.unload_now("relay shutting down")


def _take(path):
    """Consume a signal file; True if it was there."""
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return path.exists()


def pid_alive(pid):
    """True if pid is a live relay. A reused pid running something else is stale."""
    try:
        proc = psutil.Process(pid)
        if proc.status() == psutil.STATUS_ZOMBIE:
            return False
        return any(p.replace("\\", "/").endswith("invocation/relay.py") for p in proc.cmdline())
    except psutil.AccessDenied:
        return True  # cannot inspect: assume it is live rather than double-run
    except (psutil.Error, ValueError):
        return False


def _lock_holder(lock_file):
    try:
        return int(Path(lock_file).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def acquire_lock(lock_file=LOCK_FILE, alive_fn=pid_alive):
    """Single-instance lock: storage/relay.lock holds the owner's pid."""
    lock_file = Path(lock_file)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            pid = _lock_holder(lock_file)
            if pid is not None and pid != os.getpid() and alive_fn(pid):
                return False
            # ponytail: two relays clearing the same stale lock can race here;
            # both need a crashed predecessor first, and the loser exits on retry.
            lock_file.unlink(missing_ok=True)
            continue
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()))
        return True
    return False


def release_lock(lock_file=LOCK_FILE):
    if _lock_holder(lock_file) == os.getpid():
        Path(lock_file).unlink(missing_ok=True)


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Peridot Sovereign Invocation Relay")
    ap.add_argument("--ensure-server", action="store_true", help="make sure server.py is running")
    ap.add_argument("--headless", action="store_true", help="no tray icon")
    ap.add_argument("--quit", action="store_true", help="stop the running relay")
    args = ap.parse_args(argv)

    holder = _lock_holder(LOCK_FILE)
    running = holder is not None and holder != os.getpid() and pid_alive(holder)
    if args.quit:
        if running:
            _touch(QUIT_FILE)
        return 0

    if not acquire_lock():
        if args.ensure_server:
            _touch(REQUEST_FILE)  # the running relay polls it every POLL_S
        return 0

    # Signals left over from a relay that is gone must not hit this one.
    _take(QUIT_FILE)
    _take(REQUEST_FILE)
    relay = Relay()
    _log("info", f"Relay up (pid {os.getpid()}).")
    try:
        if args.ensure_server:
            relay.ensure_server()
        if sys.platform == "win32" and not args.headless:
            from core_system.invocation import tray_win32
            tray_win32.run(relay)
        else:
            try:
                relay.run()
            except KeyboardInterrupt:
                pass
    finally:
        relay.shutdown()
        release_lock()
        _log("info", "Relay down.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
