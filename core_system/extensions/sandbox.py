# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | PLUGIN SANDBOX
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Run one untrusted plugin tool function in a short-lived child interpreter.

Spawn pattern mirrors core_system/model_fetch.py::_spawn_fetch_child: JSON
payload on argv, shell=False, no console window, result as JSON on the last
stdout line. The child (sandbox_child.py) applies OS resource limits and an
audit-hook policy before importing the plugin.

policy = {"network": bool, "read_paths": [str], "write_paths": [str], "mem_mb": 512}
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from core_system.security import log_event

logger = logging.getLogger("Peridot-Sandbox")

try:
    from core_system.audit import ghost
except Exception:  # pragma: no cover - audit is optional at import time
    ghost = None

CHILD_PATH = Path(__file__).with_name("sandbox_child.py")

# Just enough environment for the interpreter to start; no user secrets.
_ENV_KEEP = {"SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "PATH", "LANG", "LC_ALL"}


def _audit(level: str, message: str) -> None:
    """GhostLogger is mandatory for new subsystems, but must never be fatal."""
    if ghost is None:
        return
    try:
        getattr(ghost, level)(message)
    except Exception:
        pass


def _result(ok: bool, result: str = "", error: str = "", denied: bool = False) -> dict:
    return {"ok": ok, "result": result, "error": error, "denied": denied}


def run_tool(plugin_dir: Path, entry: str, tool: str, args: dict, policy: dict,
             timeout: float = 30.0) -> dict:
    """Returns {"ok": bool, "result": str, "error": str, "denied": bool}."""
    plugin_dir = Path(plugin_dir).resolve()
    label = f"{plugin_dir.name}:{tool}"
    if not (plugin_dir / entry).resolve().is_relative_to(plugin_dir):
        _audit("warning", f"[SANDBOX] {label} rejected: entry escapes plugin dir")
        return _result(False, error="entry escapes plugin directory")

    payload = {
        "plugin_dir": str(plugin_dir),
        "entry": entry,
        "tool": tool,
        "args": args or {},
        "policy": policy or {},
        "timeout": timeout,
    }
    env = {k: v for k, v in os.environ.items() if k.upper() in _ENV_KEEP}
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    started = time.monotonic()
    try:
        # ponytail: payload rides on argv (~32K chars on Windows); move to stdin if tool args grow.
        proc = subprocess.run(  # nosec B603 - fixed argv, no shell
            [sys.executable, "-I", str(CHILD_PATH), json.dumps(payload)],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            **kwargs,
        )
    except subprocess.TimeoutExpired:
        _audit("warning", f"[SANDBOX] {label} timeout after {timeout}s")
        return _result(False, error="timeout")
    elapsed = time.monotonic() - started

    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    try:
        data = json.loads(lines[-1])
        if not isinstance(data, dict):
            raise ValueError("not an object")
    except (IndexError, ValueError):
        stderr_tail = (proc.stderr or "")[-500:]
        _audit("warning", f"[SANDBOX] {label} child failed rc={proc.returncode}: {stderr_tail!r}")
        return _result(False, error=f"sandbox child failed (rc={proc.returncode}): {stderr_tail}")

    out = _result(bool(data.get("ok")), str(data.get("result", "")), str(data.get("error", "")),
                  bool(data.get("denied")))
    meta = data.get("meta") or {}
    if out["denied"]:
        detail = f"{label} denials={meta.get('denials') or out['error']}"
        _audit("warning", f"[SANDBOX] PLUGIN_DENIED {detail}")
        try:
            log_event("PLUGIN_DENIED", detail, "WARNING")
        except Exception:
            logger.warning("PLUGIN_DENIED %s", detail)
    else:
        _audit("info", f"[SANDBOX] {label} ok={out['ok']} {elapsed:.2f}s {meta.get('limits', '')}")
    return out
