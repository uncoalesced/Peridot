# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | AGENT-WIRE ENGINE RUNNER
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Dispatches web and intelligence tool calls to the pulled agent-wire CLI.

Agent-wire runs as a standalone isolated tool in <BASE_DIR>/tools/agent-wire
(or system PATH). Zero vendored code inside Peridot, zero dependencies in
Peridot's venv. Fast, token-compressed (local profile <800 tokens), privacy
scrubbed, with prompt-injection defense.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent

try:
    from core_system.audit import ghost
except Exception:  # pragma: no cover
    ghost = None

WIRE_DIR = Path(BASE_DIR) / "tools" / "agent-wire"
_WIRE_BIN_CACHE: Optional[Path] = None


def _audit(level: str, message: str) -> None:
    if ghost is None:
        return
    try:
        getattr(ghost, level)(message)
    except Exception:
        pass


def get_wire_path(force_refresh: bool = False) -> Optional[Path]:
    """Finds the wire CLI executable in tools/agent-wire/venv or system PATH."""
    global _WIRE_BIN_CACHE
    if _WIRE_BIN_CACHE is not None and not force_refresh and _WIRE_BIN_CACHE.is_file():
        return _WIRE_BIN_CACHE

    # 1. Check Peridot isolated tools directory: tools/agent-wire/venv
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    bin_name = "wire.exe" if os.name == "nt" else "wire"
    local_wire = WIRE_DIR / "venv" / scripts_dir / bin_name
    if local_wire.is_file():
        _WIRE_BIN_CACHE = local_wire
        return local_wire

    # 2. Check system PATH
    which_wire = shutil.which("wire")
    if which_wire:
        p = Path(which_wire).resolve()
        if p.is_file():
            _WIRE_BIN_CACHE = p
            return p

    return None


def is_wire_available() -> bool:
    return get_wire_path() is not None


def run_wire(args: list[str], timeout: float = 35.0, input_text: Optional[str] = None) -> dict:
    """Executes a wire CLI command. Returns {'ok': bool, 'result': str, 'error': str}."""
    wire_exe = get_wire_path()
    if wire_exe is None:
        return {"ok": False, "result": "", "error": "agent-wire binary not found in tools/agent-wire or PATH"}

    wire_home = Path(BASE_DIR) / "storage" / ".wire"
    wire_home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["WIRE_HOME"] = str(wire_home)

    cmd = [str(wire_exe)] + args
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            shell=False,
            **kwargs,
        )
    except subprocess.TimeoutExpired:
        _audit("warning", f"[WIRE] Command timed out after {timeout}s: {' '.join(args[:3])}")
        return {"ok": False, "result": "", "error": f"agent-wire timed out after {timeout}s"}
    except Exception as exc:
        _audit("warning", f"[WIRE] Execution failed: {exc}")
        return {"ok": False, "result": "", "error": str(exc)}

    elapsed = time.monotonic() - started
    stdout = proc.stdout.strip() if proc.stdout else ""
    stderr = proc.stderr.strip() if proc.stderr else ""

    if proc.returncode != 0:
        err_msg = stderr or stdout or f"exited with code {proc.returncode}"
        _audit("warning", f"[WIRE] rc={proc.returncode} error: {err_msg[:200]}")
        return {"ok": False, "result": "", "error": err_msg}

    _audit("info", f"[WIRE] command {' '.join(args[:2])} ok {elapsed:.2f}s")
    return {"ok": True, "result": stdout, "error": ""}


def dispatch_wire_tool(name: str, arguments: dict) -> dict:
    """Dispatches web/intelligence tool calls to agent-wire with the local profile."""
    if name in ("web_search", "wire_search"):
        query = str(arguments.get("query", "")).strip()
        if not query:
            return {"ok": True, "result": "Error: query must be a non-empty string", "error": ""}
        limit = arguments.get("n", arguments.get("limit", 5))
        try:
            limit = max(1, min(10, int(limit)))
        except (ValueError, TypeError):
            limit = 5
        args = ["search", query, "--profile", "local", "--limit", str(limit)]
        searxng = arguments.get("searxng_url")
        if searxng:
            args.extend(["--searxng", str(searxng)])
        return run_wire(args, timeout=30.0)

    elif name in ("web_fetch", "wire_read"):
        url = str(arguments.get("url", "")).strip()
        if not url:
            return {"ok": True, "result": "Error: url must be a non-empty string", "error": ""}
        args = ["read", url, "--profile", "local"]
        return run_wire(args, timeout=30.0)

    elif name == "wire_research":
        topic = str(arguments.get("topic", "")).strip()
        if not topic:
            return {"ok": True, "result": "Error: topic must be a non-empty string", "error": ""}
        days = arguments.get("days", 14)
        try:
            days = max(1, min(90, int(days)))
        except (ValueError, TypeError):
            days = 14
        args = ["research", topic, "--days", str(days), "--depth", "quick", "--profile", "local"]
        return run_wire(args, timeout=60.0)

    elif name == "wire_cite":
        text = str(arguments.get("text", "")).strip()
        if not text:
            return {"ok": True, "result": "Error: text must be a non-empty string", "error": ""}
        args = ["cite", "-"]
        return run_wire(args, timeout=40.0, input_text=text)

    return {"ok": False, "result": "", "error": f"Unsupported agent-wire tool: {name}"}
