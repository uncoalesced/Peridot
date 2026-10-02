"""v1.6.0 Sovereign Invocation MCP server (mcp/peridot_mcp.py).

No network beyond a loopback http.server owned by the test, no Tk windows.
"""

import importlib.util
import json
import os
import subprocess
import sys
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "mcp" / "peridot_mcp.py"

_spec = importlib.util.spec_from_file_location("peridot_mcp_under_test", SCRIPT)
pm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pm)


class FakeClient:
    def __init__(self, response=None, up=True, error=None, api_key="k"):
        self.response = response or {}
        self.up = up
        self.error = error
        self.api_key = api_key
        self.payloads = []

    def ensure_server(self):
        return self.up

    def invoke(self, payload, timeout=None):
        self.payloads.append(payload)
        if self.error:
            raise self.error
        return self.response


def call(args, client, approver=None):
    msg = {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
           "params": {"name": "peridot_invoke", "arguments": args}}
    resp = pm.handle_message(msg, client=client, approver=approver)
    assert resp["id"] == 7
    return resp["result"]


def text_of(result):
    return result["content"][0]["text"]


RESP = {"answer": "RAW ANSWER", "summary": "short summary", "action_only": False,
        "model_used": "m", "steps": 2}


# --------------------------------------------------------------------------- handshake

@pytest.mark.parametrize("requested,expected", [
    ("2025-06-18", "2025-06-18"),
    ("2025-03-26", "2025-03-26"),
    ("2024-11-05", "2024-11-05"),
    ("1999-01-01", "2025-06-18"),
    (None, "2025-06-18"),
])
def test_initialize_version_negotiation(requested, expected):
    resp = pm.handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                              "params": {"protocolVersion": requested, "capabilities": {}}})
    res = resp["result"]
    assert res["protocolVersion"] == expected
    assert res["capabilities"] == {"tools": {}}
    assert res["serverInfo"] == {"name": "peridot-sovereign-invocation", "version": "1.6.0"}
    assert "private" in res["instructions"]


def test_notifications_get_no_response():
    assert pm.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert pm.handle_message({"jsonrpc": "2.0", "method": "notifications/cancelled",
                              "params": {"requestId": 3}}) is None


def test_ping():
    assert pm.handle_message({"jsonrpc": "2.0", "id": "p", "method": "ping"}) == \
        {"jsonrpc": "2.0", "id": "p", "result": {}}


def test_tools_list_schema():
    tools = pm.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert [t["name"] for t in tools] == ["peridot_invoke"]
    schema = tools[0]["inputSchema"]
    assert schema["required"] == ["task"]
    props = schema["properties"]
    assert props["return_mode"]["enum"] == ["full", "review", "status_only"]
    assert props["return_mode"]["default"] == "review"
    assert props["paths"]["items"] == {"type": "string"}
    assert "ignored" in props["model"]["description"].lower()


def test_unknown_method_and_invalid_request():
    resp = pm.handle_message({"jsonrpc": "2.0", "id": 3, "method": "resources/list"})
    assert resp["error"]["code"] == -32601
    assert pm.handle_message({"id": 4, "method": "ping"})["error"]["code"] == -32600
    assert pm.handle_message([1, 2])["error"]["code"] == -32600
    resp = pm.handle_message({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                              "params": {"name": "nope", "arguments": {}}})
    assert resp["error"]["code"] == -32602


# --------------------------------------------------------------------------- tools/call

def test_full_returns_answer_and_forwards_payload():
    client = FakeClient(RESP)
    res = call({"task": "sum my bank csv", "paths": ["C:/x"], "return_mode": "full",
                "model": "foo"}, client)
    assert res == {"content": [{"type": "text", "text": "RAW ANSWER"}], "isError": False}
    assert client.payloads == [{"task": "sum my bank csv", "return_mode": "full",
                                "paths": ["C:/x"], "model": "foo"}]


def test_action_only_returns_status_text():
    res = call({"task": "rename files", "return_mode": "full"},
               FakeClient(dict(RESP, action_only=True)))
    assert text_of(res) == pm.DONE_TEXT and res["isError"] is False


def test_status_only_never_returns_data():
    res = call({"task": "t", "return_mode": "status_only"}, FakeClient(RESP))
    assert text_of(res) == pm.DONE_TEXT
    res = call({"task": "t", "return_mode": "status_only"},
               FakeClient(error=pm.InvokeError("secret path C:/private", 500)))
    assert res["isError"] is True and "secret" not in text_of(res)


def test_review_approve_returns_edited_text():
    seen = {}

    def approver(summary, task, timeout_s):
        seen.update(summary=summary, task=task)
        return "approve", "edited by user"

    res = call({"task": "t"}, FakeClient(RESP), approver)  # default mode = review
    assert text_of(res) == "edited by user" and res["isError"] is False
    assert seen == {"summary": "short summary", "task": "t"}


def test_review_deny():
    res = call({"task": "t", "return_mode": "review"}, FakeClient(RESP),
               lambda *a: ("deny", ""))
    assert text_of(res) == pm.DECLINED_TEXT and res["isError"] is False
    assert "RAW ANSWER" not in text_of(res)


def test_server_unreachable_is_error():
    res = call({"task": "t", "return_mode": "full"}, FakeClient(up=False))
    assert res["isError"] is True


def test_http_error_is_error():
    res = call({"task": "t", "return_mode": "full"},
               FakeClient(error=pm.InvokeError("forbidden path", 403)))
    assert res["isError"] is True and "403" in text_of(res)


def test_bad_arguments_are_tool_errors():
    assert call({"task": ""}, FakeClient(RESP))["isError"] is True
    assert call({"task": "t", "return_mode": "loud"}, FakeClient(RESP))["isError"] is True
    assert call({"task": "t", "paths": "C:/x"}, FakeClient(RESP))["isError"] is True


def test_client_unreachable_launches_relay_then_gives_up(tmp_path):
    def dead_opener_open(*a, **k):
        raise urllib.error.URLError("refused")

    opener = type("O", (), {"open": staticmethod(dead_opener_open)})()
    launches = []
    client = pm.PeridotClient(base_url="http://127.0.0.1:9", api_key="k", opener=opener,
                              home=tmp_path, launcher=lambda: launches.append(1) or True,
                              startup_wait_s=0.05, poll_s=0.01)
    res = call({"task": "t", "return_mode": "full"}, client)
    assert res["isError"] is True and launches == [1]
    with pytest.raises(pm.InvokeError):
        client.invoke({"task": "t"})


def test_missing_relay_does_not_launch(tmp_path):
    client = pm.PeridotClient(home=tmp_path, api_key="k")
    assert client.launch_relay() is False


# --------------------------------------------------------------------------- .env

def test_parse_env(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "\n"
        "API_KEY=\"abc#123\"\n"
        "SERVER_HOST='0.0.0.0'\n"
        "SERVER_PORT=5055 # trailing comment\n"
        "export OTHER = plain value\n"
        "NOEQUALS\n",
        encoding="utf-8",
    )
    vals = pm.parse_env(env)
    assert vals == {"API_KEY": "abc#123", "SERVER_HOST": "0.0.0.0",  # pragma: allowlist secret
                    "SERVER_PORT": "5055", "OTHER": "plain value"}
    client = pm.PeridotClient(home=tmp_path)
    assert client.base_url == "http://127.0.0.1:5055"  # wildcard bind -> loopback
    assert client.api_key == "abc#123"  # pragma: allowlist secret
    assert pm.parse_env(tmp_path / "missing.env") == {}


# --------------------------------------------------------------------------- end to end

class _FakePeridot(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, {"ok": True}) if self.path == "/health" else self._send(404, {"error": "nf"})

    def do_POST(self):
        if self.path != "/invoke":
            return self._send(404, {"error": "nf"})
        if self.headers.get("Authorization") != "Bearer e2e-key":
            return self._send(401, {"error": "unauthorized"})
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self._send(200, {"answer": f"local answer to: {req['task']}", "summary": "s",
                         "action_only": False, "model_used": "fake", "steps": 1})


def test_stdio_end_to_end(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakePeridot)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        (tmp_path / ".env").write_text(
            f"SERVER_HOST=127.0.0.1\nSERVER_PORT={server.server_address[1]}\n"
            "API_KEY='e2e-key'  # quoted\n", encoding="utf-8")  # pragma: allowlist secret
        env = dict(os.environ, PERIDOT_HOME=str(tmp_path), PERIDOT_PYTHON=sys.executable,
                   PYTHONIOENCODING="utf-8")
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                        "clientInfo": {"name": "pytest", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "peridot_invoke",
                        "arguments": {"task": "count my receipts \u00e9", "return_mode": "full"}}},
            "not json",
        ]
        stdin = "\n".join(m if isinstance(m, str) else json.dumps(m) for m in msgs) + "\n"
        proc = subprocess.run([sys.executable, str(SCRIPT)], input=stdin.encode("utf-8"),
                              capture_output=True, env=env, timeout=60)
    finally:
        server.shutdown()
    lines = [json.loads(ln) for ln in proc.stdout.decode("utf-8").splitlines() if ln.strip()]
    by_id = {m.get("id"): m for m in lines}
    assert len(lines) == 3, proc.stderr.decode(errors="replace")
    assert by_id[1]["result"]["protocolVersion"] == "2025-03-26"
    assert by_id[None]["error"]["code"] == -32700
    result = by_id[2]["result"]
    assert result["isError"] is False, result
    assert result["content"][0]["text"] == "local answer to: count my receipts \u00e9"
