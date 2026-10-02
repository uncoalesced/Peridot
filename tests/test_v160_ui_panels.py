# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | v1.6.0 UI PANELS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""
v1.6.0 client panels: Extensions tab, WEB / SEARCH toggles, ATTACH, settings
sections, tool-call chips, and the core.py side (tool events, web flag,
settings helpers). Static and pure checks never open a window; the live check
builds one withdrawn and skips without a display.
"""

import ast
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import core
import ui

UI_SRC = (Path(__file__).resolve().parent.parent / "ui.py").read_text(encoding="utf-8")
UI_TREE = ast.parse(UI_SRC)
TK_CALLS = {"config", "configure", "itemconfig", "insert", "delete", "see", "pack", "grid",
            "update_value", "after", "tag_add", "tag_remove", "update", "update_idletasks",
            "select", "set", "mark_set", "clipboard_append"}


def _functions(name):
    return [n for n in ast.walk(UI_TREE)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]


def _tk_calls(fn):
    return sorted({n.func.attr for n in ast.walk(fn)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr in TK_CALLS})


# --- static -------------------------------------------------------------------

def test_new_worker_code_never_touches_widgets():
    fns = (_functions("task") + _functions("on_tool") + _functions("on_notice")
           + _functions("_extensions_snapshot")
           + _functions("_ingest_pdfs"))
    assert len(fns) >= 12
    for fn in fns:
        assert _tk_calls(fn) == [], f"{fn.name} at line {fn.lineno}"


def test_settings_only_change_through_post_settings():
    # The server is the sole settings writer; the UI never writes locally.
    assert "local_settings.update" not in UI_SRC
    assert "registry.approve(" not in UI_SRC and "registry.revoke(" not in UI_SRC


# --- pure helpers ---------------------------------------------------------------

def test_format_attachment_plain():
    block = ui.format_attachment("notes.md", "hello\n")
    assert block == "File: notes.md\n```md\nhello\n```\n"


def test_format_attachment_truncates_with_note():
    block = ui.format_attachment("big.txt", "x" * 50, limit=10)
    assert "x" * 10 + "\n```" in block and "x" * 11 not in block
    assert "[truncated: showing the first 10 characters]" in block


def test_format_attachment_longer_fence_when_text_has_fences():
    block = ui.format_attachment("r.md", "a\n```py\nb\n```\n")
    assert block.startswith("File: r.md\n````md\n") and block.rstrip().endswith("````")


def test_read_attachment_classifies(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "Makefile").write_text("all:\n\techo hi\n", encoding="utf-8")
    (tmp_path / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    assert ui.read_attachment(str(tmp_path / "a.pdf")) == ("pdf", None)
    assert ui.read_attachment(str(tmp_path / "a.py")) == ("text", "print(1)\n")
    assert ui.read_attachment(str(tmp_path / "Makefile"))[0] == "text"
    kind, why = ui.read_attachment(str(tmp_path / "a.png"))
    assert kind == "unsupported" and "a.png" in why


@pytest.mark.parametrize("approved, expected", [
    ({}, "Needs approval"),
    (None, "Needs approval"),
    ({"p": "abc"}, "Approved"),
    ({"p": "old"}, "Changed since approval"),
    ({"other": "abc"}, "Needs approval"),
])
def test_plugin_status(approved, expected):
    assert ui.plugin_status("p", "abc", approved) == expected


def test_perm_summary_and_mcp_command(tmp_path):
    assert ui.perm_summary({"network": True, "files": "none"}) == "network: yes, files: none"
    assert ui.perm_summary({"network": False, "files": "allowlist"}) == "network: no, files: allowlist"
    cmd = ui.mcp_setup_command(tmp_path, "py.exe")
    assert cmd == f'claude mcp add peridot -- "py.exe" "{tmp_path / "mcp" / "peridot_mcp.py"}"'
    assert ui.venv_python(tmp_path)  # no venv there: falls back to sys.executable


# --- core.py: stream consumer, web flag, settings helpers ------------------------

class _FakeStream:
    def __init__(self, events):
        self.lines = [json.dumps(e) for e in events]
        self.status_code = 200

    def raise_for_status(self):
        pass

    def iter_lines(self, decode_unicode=True):
        yield from self.lines


def _bare_core():
    return core.PeridotCore.__new__(core.PeridotCore)


def test_stream_consumer_tool_events_and_web_flag(monkeypatch):
    sent = {}

    def fake_post(url, json=None, **kw):
        sent.update(url=url, payload=json)
        return _FakeStream([
            {"delta": "Let me "}, {"delta": "check."},
            {"tool": "web_search", "status": "start"},
            {"tool": "web_search", "status": "ok"},
            {"tool": "web_fetch", "status": "error", "error": "timeout"},
            {"delta": " Done."},
            {"done": True, "status": 200, "response": "FINAL", "notice": "web off"},
        ])

    monkeypatch.setattr(core.requests, "post", fake_post)
    deltas, tools, notices = [], [], []
    out = _bare_core()._send_to_server("q", session_id="s1", on_delta=deltas.append,
                                       on_tool=lambda *a: tools.append(a), web=True,
                                       on_notice=notices.append)
    assert out == "FINAL" and notices == ["web off"]
    assert sent["url"] == core.STREAM_URL
    assert sent["payload"] == {"query": "q", "session_id": "s1", "web": True}
    assert tools == [("web_search", "start", None), ("web_search", "ok", None),
                     ("web_fetch", "error", "timeout")]
    # Text streamed before a tool call is flushed before the call is reported.
    assert deltas and deltas[-1].startswith("Let me check.")


def test_stream_consumer_throttles_visible_body(monkeypatch):
    calls = []
    real = core.stream_visible_body
    monkeypatch.setattr(core, "stream_visible_body", lambda raw: calls.append(1) or real(raw))
    monkeypatch.setattr(core.requests, "post", lambda *a, **k: _FakeStream(
        [{"delta": "x"}] * 500 + [{"done": True, "response": "ok"}]))
    assert _bare_core()._send_to_server("q", on_delta=lambda v: None) == "ok"
    assert 1 <= len(calls) < 50  # not once per token


def test_no_web_key_unless_armed(monkeypatch):
    sent = {}
    monkeypatch.setattr(core.requests, "post", lambda url, json=None, **kw: (
        sent.update(payload=json), _FakeStream([{"done": True, "response": "r"}]))[1])
    _bare_core()._send_to_server("q", on_delta=lambda v: None)
    assert "web" not in sent["payload"]


def test_non_stream_ask_passes_web_and_notice(monkeypatch):
    sent, notices = {}, []

    class Resp:
        body = {"response": "R", "notice": "Web search is disabled."}

        def raise_for_status(self):
            pass

        def json(self):
            return self.body

    monkeypatch.setattr(core.requests, "post", lambda url, json=None, **kw: (
        sent.update(url=url, payload=json), Resp())[1])
    assert _bare_core()._send_to_server("q", web=True, on_notice=notices.append) == "R"
    assert sent["url"] == core.AI_SERVER_URL and sent["payload"]["web"] is True
    assert notices == ["Web search is disabled."]
    Resp.body = {"response": "R"}  # no notice field: callback not called
    _bare_core()._send_to_server("q", on_notice=notices.append)
    assert len(notices) == 1


def test_respond_to_input_threads_web_and_on_tool(monkeypatch):
    c = _bare_core()
    c.command_router = SimpleNamespace(command_registry={})
    seen = {}

    def fake_send(query, session_id=None, on_delta=None, on_tool=None, web=False, on_notice=None,
                  on_final=None):
        seen.update(query=query, on_tool=on_tool, web=web, on_notice=on_notice)
        return "[KERNEL_RESPONSE]\nok"

    ledger = SimpleNamespace(add_message=lambda *a: None, get_session=lambda sid: {"title": "x"})
    c.current_session_id, c.chat_ledger, c.logger = "s", ledger, core.logger
    monkeypatch.setattr(c, "_send_to_server", fake_send)
    tool_cb, notice_cb = object(), object()
    assert c.respond_to_input("hello", on_delta=lambda v: None, on_tool=tool_cb, web=True,
                              on_notice=notice_cb)
    assert seen == {"query": "hello", "on_tool": tool_cb, "web": True, "on_notice": notice_cb}


def test_settings_helpers_never_raise(monkeypatch):
    monkeypatch.setattr(core, "SETTINGS_URL", "http://127.0.0.1:1/settings")
    assert "error" in core.get_settings()
    assert "error" in core.post_settings({"web.enabled": True})

    class Resp:
        def __init__(self, code, body):
            self.status_code, self._body = code, body

        def json(self):
            if self._body is None:
                raise ValueError("not json")
            return self._body

    monkeypatch.setattr(core.requests, "request", lambda *a, **k: Resp(400, {"error": "bad key"}))
    assert core.post_settings({"x": 1}) == {"error": "bad key"}
    monkeypatch.setattr(core.requests, "request", lambda *a, **k: Resp(502, None))
    assert core.get_settings()["error"].startswith("HTTP 502")
    monkeypatch.setattr(core.requests, "request", lambda *a, **k: Resp(200, {"web.enabled": True}))
    assert core.get_settings() == {"web.enabled": True}


# --- live check (needs a display) ------------------------------------------------

class _FakeCore:
    def __init__(self):
        self.calls = []

    def respond_to_input(self, text, on_delta=None, on_tool=None, web=False, on_notice=None,
                         on_final=None):
        self.calls.append((text, web))
        on_notice("Web search is unavailable right now.")
        return "[KERNEL_RESPONSE]\nok"


SETTINGS = {"web.enabled": True, "web.searxng_url": "", "extensions.model_invoke": False,
            "allow.folders": [{"path": "C:\\data", "write": True}],
            "invocation.idle_unload_s": 600, "invocation.review_timeout_s": 90,
            "plugins.approved": {}}


_CORE = _FakeCore()


@pytest.fixture
def live_ui(peridot_ui):  # shared session window, see tests/conftest.py
    peridot_ui.core = _CORE
    return peridot_ui


def _drain(app):
    while not app._ui_queue.empty():
        fn, args = app._ui_queue.get_nowait()
        fn(*args)


def test_panels_exist(live_ui):
    app = live_ui
    tabs = [app.notebook.tab(t, "text") for t in app.notebook.tabs()]
    assert any("EXTENSIONS" in t for t in tabs) and len(tabs) == 4
    for name in ("btn_attach", "btn_search", "btn_web", "skills_tree", "plugins_tree",
                 "folder_list", "searxng_entry", "btn_install_web", "ext_errors"):
        assert hasattr(app, name), name


def test_settings_and_extensions_render(live_ui):
    app = live_ui
    app._apply_settings({"error": "offline"})  # silent no-op without a label
    app._apply_settings(SETTINGS)
    assert app.web_enabled and app.btn_web.cget("text") == "WEB: ON"
    assert app.folder_list.get(0).strip() == "[RW] C:\\data"
    assert app.idle_min_var.get() == "10" and app.review_s_var.get() == "90"
    assert app.model_invoke_var.get() is False

    app._apply_extensions({
        "skills": [("summarise", "Summarise text")],
        "plugins": {"web_search": {"name": "web_search", "version": "1.0.0", "description": "d",
                                   "permissions": {"network": True, "files": "none"},
                                   "tools": ["web_search"], "hash": "h",
                                   "status": "Changed since approval"}},
        "errors": ["plugins/bad: tools must be a non-empty list"],
        "settings": SETTINGS, "web_installed": False,
    })
    assert app.plugins_tree.item("web_search", "values")[2] == "Changed since approval"
    assert "bad" in app.ext_errors.get(0)
    assert app.btn_install_web.winfo_manager() == "pack"

    app.skills_tree.selection_set("summarise")
    app._use_skill()
    assert app.entry.get("1.0", "end-1c") == "/summarise "
    app.entry.delete("1.0", "end")


def test_search_arms_one_message_only(live_ui):
    app = live_ui
    app._apply_settings(SETTINGS)
    app._toggle_web_armed()
    assert app.web_armed and app.btn_search.cget("text") == "[x] SEARCH"
    app.entry.insert("1.0", "look this up")
    app.handle_input()
    deadline = time.time() + 5
    while not app.core.calls and time.time() < deadline:
        time.sleep(0.01)
    assert app.core.calls[-1] == ("look this up", True)
    assert not app.web_armed and app.btn_search.cget("text") == "[ ] SEARCH"
    while app._ui_queue.empty() and time.time() < deadline:
        time.sleep(0.01)
    _drain(app)  # runs _finish
    assert not app.is_processing
    app.root.update()  # the notice is posted with after(0), once the reply is drawn
    text = app.chat.get("1.0", "end")
    assert text.rstrip().endswith("> look this up\nok\n\n>> Web search is unavailable right now.")


def test_tool_chips_sit_above_the_stream(live_ui):
    app = live_ui
    chat = app.chat
    app.is_processing = True
    chat.mark_set("stream_start", "end-1c")
    chat.mark_gravity("stream_start", "left")
    pending = {"text": None, "streamed": False, "shown": None, "placeholder": False}
    app._stream_state = pending

    def flush(text):
        pending["text"] = text
        app._flush_stream(pending)
        return chat.get("stream_start", "end-1c")

    app._add_tool_chip("web_search", "start")
    assert flush("Hel") == "\nHel"
    app._add_tool_chip("web_search", "ok")
    assert flush("Hello") == "\nHello"           # still append-only after a chip
    app._add_tool_chip("web_fetch", "error", "timeout")  # no start event seen
    assert flush("Rewritten") == "\nRewritten"   # replace keeps the chips
    text = chat.get("1.0", "end")
    assert "[tool] web_search ... ok\n" in text
    assert "[tool] web_fetch ... error: timeout\n" in text
    assert text.index("[tool] web_search") < text.index("[tool] web_fetch") < text.index("Rewritten")

    app._finish("Final answer")
    text = chat.get("1.0", "end")
    assert "[tool] web_search ... ok" in text and "Final answer" in text and "Rewritten" not in text
    app._add_tool_chip("late", "start")  # after finish: ignored
    assert "late" not in chat.get("1.0", "end")
