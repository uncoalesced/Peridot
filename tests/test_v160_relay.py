"""v1.6.0 Sovereign Invocation Relay: lifecycle logic, lock, import weight, /health fields."""

import importlib
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core_system.invocation import relay as relay_mod  # noqa: E402
from test_agent3_rag_mtbf import (  # noqa: E402
    _STUBBED_MODULES,
    _drop_modules,
    _install_common_runtime_stubs,
)


class FakeChild:
    def __init__(self, pid):
        self.pid = pid
        self.returncode = None

    def poll(self):
        return self.returncode


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class RelayLogicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.req, self.quit = d / "relay.request", d / "relay.quit"
        self.clock = Clock()
        self.health = None  # what /health returns
        self.spawned, self.killed = [], []
        self.relay = relay_mod.Relay(
            health_fn=lambda: self.health,
            spawn_fn=self._spawn,
            kill_fn=self.killed.append,
            clock=self.clock,
            idle_timeout_fn=lambda: 300,
            request_file=self.req,
            quit_file=self.quit,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _spawn(self):
        child = FakeChild(4242 + len(self.spawned))
        self.spawned.append(child)
        return child

    def _own_healthy(self, idle_s, inflight=0):
        self.relay.ensure_server()
        self.health = {"ok": True, "status": "online", "pid": self.relay.child.pid,
                       "idle_s": idle_s, "inflight": inflight}

    def _idle_tick(self):
        self.clock.t += relay_mod.IDLE_CHECK_S
        self.relay.tick()

    def test_spawns_when_unhealthy_and_only_once(self):
        self.relay.ensure_server()
        self.relay.ensure_server()  # child still booting: no second spawn
        self.assertEqual(len(self.spawned), 1)
        self.assertEqual(self.relay.status(), "serving")

    def test_does_not_spawn_or_kill_foreign_server(self):
        self.health = {"ok": True, "pid": 999, "idle_s": 10_000, "inflight": 0}
        self.relay.ensure_server()
        self._idle_tick()
        self.assertEqual(self.spawned, [])
        self.assertEqual(self.killed, [])

    def test_kills_owned_server_when_idle(self):
        self._own_healthy(idle_s=300)
        self._idle_tick()
        self.assertEqual(self.killed, [4242])
        self.assertIsNone(self.relay.child)

    def test_keeps_server_when_busy_or_recent(self):
        self._own_healthy(idle_s=10_000, inflight=1)
        self._idle_tick()
        self.health["inflight"], self.health["idle_s"] = 0, 299
        self._idle_tick()
        self.assertEqual(self.killed, [])

    def test_idle_check_waits_for_interval(self):
        self._own_healthy(idle_s=10_000)
        self.clock.t += relay_mod.IDLE_CHECK_S - 1
        self.relay.tick()
        self.assertEqual(self.killed, [])

    def test_forgets_dead_child(self):
        self.relay.ensure_server()
        self.relay.child.returncode = 1
        self.relay.tick()
        self.assertIsNone(self.relay.child)
        self.assertEqual(self.killed, [])

    def test_request_file_ensures_server(self):
        self.req.touch()
        self.relay.tick()
        self.assertFalse(self.req.exists())
        self.assertEqual(len(self.spawned), 1)

    def test_quit_file_stops_and_shutdown_kills_owned(self):
        self.relay.ensure_server()
        self.quit.touch()
        self.relay.tick()
        self.assertFalse(self.quit.exists())
        self.assertTrue(self.relay.stopped.is_set())
        self.relay.shutdown()
        self.assertEqual(self.killed, [4242])

    def test_unload_now_without_child_is_noop(self):
        self.assertFalse(self.relay.unload_now())
        self.assertEqual(self.killed, [])


class RelayLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lock = Path(self.tmp.name) / "relay.lock"

    def tearDown(self):
        self.tmp.cleanup()

    def test_acquire_release(self):
        self.assertTrue(relay_mod.acquire_lock(self.lock))
        self.assertEqual(self.lock.read_text(), str(os.getpid()))
        relay_mod.release_lock(self.lock)
        self.assertFalse(self.lock.exists())

    def test_live_holder_blocks(self):
        self.lock.write_text("12345")
        self.assertFalse(relay_mod.acquire_lock(self.lock, alive_fn=lambda pid: True))
        self.assertEqual(self.lock.read_text(), "12345")

    def test_stale_lock_with_dead_pid_is_taken_over(self):
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        self.lock.write_text(str(dead.pid))
        self.assertFalse(relay_mod.pid_alive(dead.pid))
        self.assertTrue(relay_mod.acquire_lock(self.lock))
        self.assertEqual(self.lock.read_text(), str(os.getpid()))

    def test_reused_pid_of_non_relay_process_is_stale(self):
        self.assertFalse(relay_mod.pid_alive(os.getpid()))  # pytest is not a relay

    def test_corrupt_lock_is_taken_over(self):
        self.lock.write_text("not-a-pid")
        self.assertTrue(relay_mod.acquire_lock(self.lock))


class RelayImportTests(unittest.TestCase):
    def test_relay_import_stays_light(self):
        code = ("import sys; import core_system.invocation.relay; "
                "print([m for m in ('flask','torch','llama_cpp','server') if m in sys.modules])")
        out = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT,
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip().splitlines()[-1], "[]")

    @unittest.skipUnless(sys.platform == "win32", "Win32 tray")
    def test_tray_import_creates_nothing(self):
        tray = importlib.import_module("core_system.invocation.tray_win32")
        self.assertIsNone(tray._api)


class HealthFieldsTests(unittest.TestCase):
    def setUp(self):
        _drop_modules(*_STUBBED_MODULES)

    def tearDown(self):
        _drop_modules(*_STUBBED_MODULES)

    def test_health_reports_idle_inflight_pid_and_skips_itself(self):
        _install_common_runtime_stubs()
        server = importlib.import_module("server")
        server.llm = types.SimpleNamespace(is_loaded=True)

        server.request = types.SimpleNamespace(path="/ask", method="POST", environ={})
        server._track_request_start()
        body, status = server.health_check()
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "online")
        self.assertEqual(body["inflight"], 1)
        self.assertEqual(body["pid"], os.getpid())
        self.assertIsInstance(body["idle_s"], int)

        server._track_request_end()
        server._track_request_end()  # stream copy's second teardown: no double decrement
        self.assertEqual(server.health_check()[0]["inflight"], 0)

        server.request = types.SimpleNamespace(path="/health", method="GET", environ={})
        before = server._last_activity
        server._track_request_start()
        self.assertEqual(server._last_activity, before)
        self.assertEqual(server._inflight, 0)

        server.llm = None
        body, status = server.health_check()
        self.assertEqual(status, 503)
        self.assertEqual(set(body), {"status", "idle_s", "inflight", "pid", "model"})


if __name__ == "__main__":
    unittest.main()
