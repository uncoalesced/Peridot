"""Peridot Sovereign Invocation -- MCP server over stdio.

Lets cloud agents (Claude Code, Codex CLI, Gemini CLI, any MCP client)
delegate private-data jobs to the user's local Peridot model. Raw data never
leaves the machine: only the final answer (full), a user-approved summary
(review) or a status line (status_only) is returned to the caller.

Standalone by design: imports nothing from Peridot, talks to it over HTTP.
Transport: newline-delimited JSON-RPC 2.0 on stdin/stdout. stdout carries
protocol messages only; every log line goes to stderr.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

SERVER_NAME = "peridot-sovereign-invocation"
SERVER_VERSION = "1.6.0"
SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
LATEST_VERSION = SUPPORTED_VERSIONS[0]

INVOKE_TIMEOUT_S = 900
STARTUP_WAIT_S = 180
APPROVAL_TIMEOUT_S = 120
RETURN_MODES = ("full", "review", "status_only")

DONE_TEXT = "Peridot completed the task."
DECLINED_TEXT = "The user declined to share Peridot's result."

HERE = Path(__file__).resolve().parent

INSTRUCTIONS = (
    "Peridot is the user's private, local AI running on their own machine. "
    "Use the peridot_invoke tool whenever a task needs the user's private data: "
    "personal files, financial records, health, messages, notes, credentials-adjacent "
    "material, or anything in the user's local folders. Peridot reads that data "
    "locally and returns only a result, so raw data never reaches you. Describe the "
    "job in plain language; do not ask the user to paste private data into this chat."
)

TOOL = {
    "name": "peridot_invoke",
    "title": "Peridot (local, private)",
    "description": (
        "Run a task on the user's local Peridot model, which can read the user's "
        "allowlisted folders on their own machine. The data stays local; only the "
        "result comes back. Results may be summarized or redacted, and in 'review' "
        "mode the user must approve (and may edit) what is shared before you see it. "
        "Use this for anything touching private, financial or personal data."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "What Peridot should do, in plain language.",
            },
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional files/folders to focus on (must be inside the user's allowlist).",
            },
            "return_mode": {
                "type": "string",
                "enum": list(RETURN_MODES),
                "default": "review",
                "description": (
                    "full: return Peridot's answer. review (default): the user approves/edits "
                    "a summary first. status_only: return only whether the task completed."
                ),
            },
            "model": {
                "type": "string",
                "description": "Optional local model name. Ignored in v1.6.0 (Peridot uses its configured model).",
            },
        },
        "required": ["task"],
        "additionalProperties": False,
    },
}


def log(*parts) -> None:
    print("[peridot-mcp]", *parts, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- config

def parse_env(path) -> dict:
    """Tiny .env parser: KEY=VALUE, optional `export`, quotes, # comments."""
    out: dict = {}
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[7:].strip()
        val = val.strip()
        if val[:1] in ("'", '"'):
            end = val.find(val[0], 1)
            val = val[1:end] if end != -1 else val[1:]
        else:
            hash_at = val.find(" #")
            if hash_at != -1:
                val = val[:hash_at].rstrip()
        if key:
            out[key] = val
    return out


def peridot_home() -> Path:
    env = os.environ.get("PERIDOT_HOME")
    return Path(env).expanduser().resolve() if env else HERE.parent


def python_exe() -> str:
    """PERIDOT_PYTHON, else Peridot's own venv, else this interpreter.

    The agent that spawns this bridge runs it with whatever `python` is on its
    PATH, which usually lacks Peridot's dependencies (flask, llama_cpp). The
    Relay starts the server with the interpreter it was given, so prefer the venv.
    """
    env = os.environ.get("PERIDOT_PYTHON")
    if env:
        return env
    venv = peridot_home() / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(venv) if venv.is_file() else sys.executable


# --------------------------------------------------------------------------- HTTP client

class InvokeError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class PeridotClient:
    """HTTP client for the Peridot server. Everything is injectable for tests."""

    def __init__(self, base_url=None, api_key=None, opener=None, home=None,
                 launcher=None, startup_wait_s=STARTUP_WAIT_S, poll_s=1.0):
        self.home = Path(home) if home else peridot_home()
        env = parse_env(self.home / ".env")
        if base_url is None:
            host = env.get("SERVER_HOST") or os.environ.get("SERVER_HOST") or "127.0.0.1"
            if host in ("0.0.0.0", "::", ""):
                host = "127.0.0.1"
            port = env.get("SERVER_PORT") or os.environ.get("SERVER_PORT") or "5000"
            base_url = f"http://{host}:{port}"
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key if api_key is not None else env.get("API_KEY", "")
        # No proxies: requests to the local server must never be routed off-box.
        self.opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.launcher = launcher or self.launch_relay
        self.startup_wait_s = startup_wait_s
        self.poll_s = poll_s

    def health(self) -> bool:
        try:
            with self.opener.open(self.base_url + "/health", timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def launch_relay(self) -> bool:
        relay = self.home / "core_system" / "invocation" / "relay.py"
        if not relay.is_file():
            log("relay not found:", relay)
            return False
        kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                        "stderr": subprocess.DEVNULL, "cwd": str(self.home), "close_fds": True}
        if os.name == "nt":
            kwargs["creationflags"] = (subprocess.DETACHED_PROCESS
                                       | subprocess.CREATE_NEW_PROCESS_GROUP
                                       | subprocess.CREATE_NO_WINDOW)
        else:
            kwargs["start_new_session"] = True
        try:
            subprocess.Popen([python_exe(), str(relay), "--ensure-server"], **kwargs)
        except OSError as exc:
            log("relay launch failed:", exc)
            return False
        log("launched relay; waiting for Peridot to come up")
        return True

    def ensure_server(self) -> bool:
        if self.health():
            return True
        if not self.launcher():
            return False
        deadline = time.monotonic() + self.startup_wait_s
        while time.monotonic() < deadline:
            time.sleep(self.poll_s)
            if self.health():
                return True
        return False

    def invoke(self, payload: dict, timeout: float = INVOKE_TIMEOUT_S) -> dict:
        req = urllib.request.Request(
            self.base_url + "/invoke",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            try:
                msg = json.loads(exc.read() or b"{}").get("error") or exc.reason
            except Exception:
                msg = exc.reason
            raise InvokeError(str(msg), exc.code) from None
        except (urllib.error.URLError, OSError) as exc:
            raise InvokeError(f"Peridot server unreachable ({exc})") from None
        try:
            data = json.loads(body)
        except ValueError:
            raise InvokeError("Peridot returned a non-JSON response") from None
        if not isinstance(data, dict):
            raise InvokeError("Peridot returned an unexpected response")
        return data


# --------------------------------------------------------------------------- approval

def run_approval(summary: str, task: str, timeout_s: int = APPROVAL_TIMEOUT_S):
    """Show the Tk approval dialog in a subprocess. Returns (decision, text)."""
    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        proc = subprocess.run(
            [python_exe(), str(HERE / "approve.py")],
            input=json.dumps({"summary": summary, "task": task, "timeout_s": timeout_s}),
            capture_output=True, text=True, encoding="utf-8",
            timeout=timeout_s + 30, **kwargs,
        )
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        result = json.loads(lines[-1]) if lines else {}
    except Exception as exc:  # crash, timeout, bad output -> deny
        log("approval dialog failed:", exc)
        return "deny", ""
    if result.get("decision") == "approve":
        return "approve", str(result.get("text", ""))
    return "deny", ""


# --------------------------------------------------------------------------- tool

def _text_result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def call_peridot_invoke(args: dict, client=None, approver=None) -> dict:
    task = args.get("task")
    if not isinstance(task, str) or not task.strip():
        return _text_result("'task' must be a non-empty string.", True)
    paths = args.get("paths")
    if paths is not None and (not isinstance(paths, list)
                              or not all(isinstance(p, str) for p in paths)):
        return _text_result("'paths' must be an array of strings.", True)
    mode = args.get("return_mode") or "review"
    if mode not in RETURN_MODES:
        return _text_result(f"'return_mode' must be one of {', '.join(RETURN_MODES)}.", True)
    model = args.get("model")

    client = client or PeridotClient()
    if not client.api_key:
        return _text_result("Peridot API_KEY not found in Peridot's .env; start Peridot once to create it.", True)
    if not client.ensure_server():
        return _text_result("Peridot is not running and could not be started. Start Peridot and retry.", True)

    payload: dict = {"task": task, "return_mode": mode}
    if paths:
        payload["paths"] = paths
    if isinstance(model, str) and model:
        payload["model"] = model  # ignored server-side in v1.6.0
    try:
        data = client.invoke(payload)
    except InvokeError as exc:
        if mode == "status_only":
            code = f" (HTTP {exc.status})" if exc.status else ""
            return _text_result(f"Peridot failed to complete the task{code}.", True)
        prefix = f"Peridot error (HTTP {exc.status}): " if exc.status else "Peridot error: "
        return _text_result(prefix + str(exc)[:300], True)

    if mode == "status_only" or data.get("action_only"):
        return _text_result(DONE_TEXT)
    answer = str(data.get("answer") or "")
    if mode == "full":
        return _text_result(answer)
    summary = str(data.get("summary") or answer)
    decision, text = (approver or run_approval)(summary, task, APPROVAL_TIMEOUT_S)
    if decision == "approve":
        return _text_result(text)
    return _text_result(DECLINED_TEXT)


# --------------------------------------------------------------------------- JSON-RPC

def _error(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _ok(msg_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def handle_message(msg, client=None, approver=None):
    """Handle one decoded JSON-RPC message. Returns a response dict, or None."""
    if not isinstance(msg, dict):
        return _error(None, -32600, "Invalid Request")
    is_notification = "id" not in msg
    msg_id = msg.get("id")
    method = msg.get("method")
    if method is None and ("result" in msg or "error" in msg):
        return None  # a response to a request we never send; ignore
    if msg.get("jsonrpc") != "2.0" or not isinstance(method, str) \
            or not (is_notification or isinstance(msg_id, (str, int))):
        return _error(msg_id if isinstance(msg_id, (str, int)) else None, -32600, "Invalid Request")
    if is_notification:
        return None  # notifications/initialized, notifications/cancelled, ...

    params = msg.get("params") or {}
    if not isinstance(params, dict):
        return _error(msg_id, -32602, "Invalid params")

    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_VERSIONS else LATEST_VERSION
        return _ok(msg_id, {
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return _ok(msg_id, {})
    if method == "tools/list":
        return _ok(msg_id, {"tools": [TOOL]})
    if method == "tools/call":
        if params.get("name") != TOOL["name"]:
            return _error(msg_id, -32602, f"Unknown tool: {params.get('name')}")
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            return _error(msg_id, -32602, "Invalid params: arguments must be an object")
        try:
            return _ok(msg_id, call_peridot_invoke(args, client, approver))
        except Exception as exc:  # never kill the server over one call
            log("tools/call crashed:", repr(exc))
            return _ok(msg_id, _text_result("Peridot invocation failed unexpectedly.", True))
    return _error(msg_id, -32601, f"Method not found: {method}")


def main() -> None:
    out = sys.stdout.buffer
    sys.stdout = sys.stderr  # any stray print() must not corrupt the protocol stream
    lock = threading.Lock()

    def send(resp) -> None:
        if resp is None:
            return
        data = json.dumps(resp, ensure_ascii=False).encode("utf-8") + b"\n"
        with lock:
            out.write(data)
            out.flush()

    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            send(_error(None, -32700, "Parse error"))
            continue
        if isinstance(msg, dict) and msg.get("method") == "tools/call" and "id" in msg:
            # Long-running (up to 15 min): run off the read loop so pings still answer.
            # Non-daemon, so in-flight results are still written after stdin closes.
            threading.Thread(target=lambda m=msg: send(handle_message(m))).start()
        else:
            send(handle_message(msg))


if __name__ == "__main__":
    main()
