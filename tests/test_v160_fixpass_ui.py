# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | v1.6.0 FIX-PASS UI CHECKS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""
Input row redesign (ATTACH | SEARCH | MIC | SEND/STOP), the message queue,
the hardware-aware model swap, launcher pid-file cleanup, the reasoning
toggle, and the core.py side (ledger guard, reasoning/cancelled plumbing).
Live checks share the session window from tests/conftest.py.
"""

import threading
import time
from types import SimpleNamespace

import pytest

import core
import launcher
import ui


# --- message queue (pure) ---------------------------------------------------------

def test_message_queue_fifo_cancel_and_ids():
    q = ui.MessageQueue()
    a = q.enqueue("first", web=True)
    b = q.enqueue("second")
    c = q.enqueue("third")
    assert len(q) == 3 and a < b < c
    assert q.cancel(b) is True and q.cancel(b) is False
    assert [i["text"] for i in q.items()] == ["first", "third"]
    assert q.pop_next() == {"id": a, "text": "first", "web": True}
    assert q.pop_next()["text"] == "third"
    assert q.pop_next() is None and len(q) == 0


def test_queue_preview_truncates_and_flattens():
    assert ui.queue_preview("short\n  text") == "short text"
    long = "x" * 60
    assert ui.queue_preview(long) == "x" * 40 + "…"


# --- model choices (pure) -----------------------------------------------------------

def test_model_fit_bands():
    assert ui.model_fit(5.0, 8.0) == "fits in VRAM"        # 5*1.1+0.5 = 6.0
    assert ui.model_fit(10.0, 8.0) == "partial offload"    # 11.5 <= 16
    assert ui.model_fit(20.0, 8.0) == "CPU-heavy"
    assert ui.model_fit(1.0, 0) == "CPU-heavy"             # no GPU


def _sized(path, size):
    with open(path, "wb") as f:
        f.truncate(size)


def test_model_choices_lists_only_gguf(tmp_path):
    _sized(tmp_path / "b-model.gguf", int(5.9 * 1024 ** 3))
    _sized(tmp_path / "a-small.GGUF", 1024 ** 3)
    _sized(tmp_path / "weights.safetensors", 1024)
    (tmp_path / "notes.txt").write_text("x")
    choices = ui.model_choices(tmp_path, 6.0)  # 5.9 GB needs ~7.0 GB
    assert [name for _, name in choices] == ["a-small.GGUF", "b-model.gguf"]
    assert choices[1][0] == "b-model.gguf  ·  5.9 GB  ·  partial offload"
    assert choices[0][0] == "a-small.GGUF  ·  1.0 GB  ·  fits in VRAM"
    assert ui.model_choices(tmp_path / "missing", 8.0) == []


# --- model swap orchestration (pure) ------------------------------------------------

class _Engine:
    """Scripted engine: health answers until /shutdown, then after `boot_s` polls."""

    def __init__(self, boot_s=3, stops=True, settings_error=None, exit_code=None, model="new.gguf"):
        self.posts, self.up, self.stops = [], True, stops
        self.boot_s, self.settings_error, self.exit_code, self.model = boot_s, settings_error, exit_code, model
        self.spawned = False
        self.polls = 0

    def post(self, path, body):
        self.posts.append((path, body))
        if path == "/settings" and self.settings_error:
            return {"error": self.settings_error}
        if path == "/shutdown" and self.stops:
            self.up = False
        return {}

    def health(self):
        if self.spawned:
            self.polls += 1
            if self.polls >= self.boot_s:
                return 200, {"model": self.model}
            return 503, {}
        return (200, {}) if self.up else None

    def spawn(self):
        self.spawned = True
        return SimpleNamespace(poll=lambda: self.exit_code)


def _swap(engine, **kw):
    status = []
    result = ui.run_model_swap("new.gguf", post=engine.post, spawn=engine.spawn,
                               health=engine.health, sleep=lambda s: None,
                               on_status=status.append, **kw)
    return result, status


def test_model_swap_happy_path():
    eng = _Engine(boot_s=3)
    (status, model), lines = _swap(eng)
    assert (status, model) == ("ok", "new.gguf")
    assert eng.posts == [("/settings", {"model.active": "new.gguf"}), ("/shutdown", None)]
    assert lines == ["Loading new.gguf… 1s", "Loading new.gguf… 2s", "Loading new.gguf… 3s"]


def test_model_swap_reports_health_model_and_falls_back_to_name():
    assert _swap(_Engine(model="other.gguf"))[0] == ("ok", "other.gguf")
    assert _swap(_Engine(model=None))[0] == ("ok", "new.gguf")


def test_model_swap_rejected_never_shuts_down():
    eng = _Engine(settings_error="Model not found in models/: new.gguf")
    assert _swap(eng)[0] == ("rejected", "Model not found in models/: new.gguf")
    assert [p for p, _ in eng.posts] == ["/settings"] and not eng.spawned


def test_model_swap_old_engine_never_stops():
    eng = _Engine(stops=False)
    status, why = _swap(eng, stop_timeout=3)[0]
    assert status == "failed" and "still answered" in why and not eng.spawned


def test_model_swap_boot_crash_and_timeout():
    assert _swap(_Engine(exit_code=1))[0] == ("failed", "the engine exited during boot (code 1)")
    status, why = _swap(_Engine(boot_s=999), load_timeout=5)[0]
    assert status == "failed" and "5s" in why


def test_tail_lines(tmp_path):
    log = tmp_path / "server.log"
    log.write_text("".join(f"line {i}\n" for i in range(30)))
    assert ui.tail_lines(log, 3) == "line 27\nline 28\nline 29"
    assert ui.tail_lines(tmp_path / "missing.log") == ""


# --- launcher pid-file cleanup ------------------------------------------------------

def test_launcher_kills_pidfile_server_only(tmp_path, monkeypatch):
    killed = []
    cmdlines = {101: ["python.exe", "server.py"], 202: ["notepad.exe"]}
    monkeypatch.setattr(launcher, "kill_proc_tree", killed.append)
    monkeypatch.setattr(launcher.psutil, "Process",
                        lambda pid: SimpleNamespace(cmdline=lambda: cmdlines[pid]))
    pid_file = tmp_path / "server.pid"

    pid_file.write_text("101")
    assert launcher.kill_pidfile_server(pid_file) is True
    assert killed == [101] and not pid_file.exists()

    pid_file.write_text("202")  # stale pid reused by something else
    assert launcher.kill_pidfile_server(pid_file) is False
    assert killed == [101] and not pid_file.exists()

    assert launcher.kill_pidfile_server(pid_file) is False  # no file


# --- core.py --------------------------------------------------------------------

def _ledger_core(add_message):
    c = core.PeridotCore.__new__(core.PeridotCore)
    c.current_session_id, c.logger = "s", core.logger
    c.chat_ledger = SimpleNamespace(add_message=add_message, get_session=lambda sid: {"title": "x"})
    return c


def test_core_skips_ledger_write_when_not_storable(monkeypatch):
    rows = []
    c = _ledger_core(lambda *a: rows.append(a))
    monkeypatch.setattr(c, "_send_to_server", lambda **kw: "[KERNEL_RESPONSE]\nI cannot.")
    monkeypatch.setattr(core, "is_storable_answer", lambda text: False)
    c._ask_ai_with_memory("hi")
    assert [r[1] for r in rows] == ["user"]
    monkeypatch.setattr(core, "is_storable_answer", lambda text: True)
    c._ask_ai_with_memory("hi")
    assert [r[1] for r in rows] == ["user", "user", "assistant"]


def test_core_passes_reasoning_when_ledger_accepts_it(monkeypatch):
    rows = []

    def add_message(session_id, role, content, reasoning=None):
        rows.append((role, content, reasoning))

    c = _ledger_core(add_message)
    finals = []

    def fake_send(on_final=None, **kw):
        on_final({"reasoning": "thought", "cancelled": False})
        return "[KERNEL_RESPONSE]\nanswer"

    monkeypatch.setattr(c, "_send_to_server", fake_send)
    monkeypatch.setattr(core, "is_storable_answer", None)
    c._ask_ai_with_memory("q", on_final=finals.append)
    assert rows[-1] == ("assistant", "answer", "thought")
    assert finals == [{"reasoning": "thought", "cancelled": False}]


def test_send_to_server_reports_reasoning_and_cancelled(monkeypatch):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "partial", "reasoning": "hmm", "cancelled": True}

    monkeypatch.setattr(core.requests, "post", lambda *a, **k: Resp())
    finals = []
    c = core.PeridotCore.__new__(core.PeridotCore)
    assert c._send_to_server("q", on_final=finals.append) == "partial"
    assert finals == [{"reasoning": "hmm", "cancelled": True}]


def test_post_cancel_never_raises(monkeypatch):
    monkeypatch.setattr(core, "CANCEL_URL", "http://127.0.0.1:1/ask/cancel")
    assert core.post_cancel() is False
    resp = SimpleNamespace(status_code=200, json=lambda: {"cancelled": True})
    monkeypatch.setattr(core.requests, "post", lambda *a, **k: resp)
    assert core.post_cancel() is True
    resp.json = lambda: ["not a dict"]
    assert core.post_cancel() is False


# --- live (shared window) ---------------------------------------------------------

class _GatedCore:
    """respond_to_input blocks until `gate` is set; reports reasoning + STOP."""

    def __init__(self):
        self.calls, self.gate, self.ears = [], threading.Event(), None

    def respond_to_input(self, text, on_delta=None, on_tool=None, web=False, on_notice=None,
                         on_final=None):
        self.calls.append((text, web))
        self.gate.wait(5)
        on_final({"reasoning": f"thinking about {text}", "cancelled": text == "first"})
        return f"[KERNEL_RESPONSE]\nreply to {text}"


@pytest.fixture
def live_ui(peridot_ui):
    peridot_ui.core = _GatedCore()
    yield peridot_ui
    peridot_ui.core.gate.set()


def _drain(app, until, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        while not app._ui_queue.empty():
            fn, args = app._ui_queue.get_nowait()
            fn(*args)
        app.root.update()
        if until():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached")


def _grid_col(widget):
    return int(widget.grid_info()["column"])


def test_input_row_order_and_alignment(live_ui):
    app = live_ui
    row = [app.entry, app.btn_attach, app.btn_search, app.btn_mic, app.btn_send]
    assert [_grid_col(w) for w in row] == [0, 1, 2, 3, 4]
    assert {w.grid_info()["row"] for w in row} == {row[0].grid_info()["row"]}
    assert all(w.grid_info()["sticky"] == "nesw" for w in row)
    buttons = row[1:]
    assert {str(b.cget("font")) for b in buttons} == {ui.FONT_BUTTON}
    assert {str(b.cget("padx")) for b in buttons} == {str(ui.PAD_L)}
    assert {int(b.cget("highlightthickness")) for b in buttons} == {1}
    assert app.btn_mic.cget("text") == "MIC" and not app.btn_mic.cget("image")


def test_hover_lights_border_and_send_fills(live_ui):
    app = live_ui
    for btn in (app.btn_attach, app.btn_search, app.btn_mic, app.btn_send):
        assert btn.bind("<Enter>") and btn.bind("<Leave>")
    app._hover_button(app.btn_mic, True)
    assert app.btn_mic.cget("highlightbackground").upper() == ui.LIME
    assert app.btn_mic.cget("fg").upper() == ui.LIME
    app._hover_button(app.btn_mic, False)
    assert app.btn_mic.cget("fg").upper() == ui.MINT
    assert app.btn_mic.cget("highlightbackground").upper() == ui.BORDER

    assert app.btn_send.cget("fg").upper() == ui.LIME
    app._hover_button(app.btn_send, True)
    assert (app.btn_send.cget("bg").upper(), app.btn_send.cget("fg").upper()) == (ui.LIME, ui.BLACK)
    app._hover_button(app.btn_send, False)
    assert app.btn_send.cget("bg").upper() == ui.SURFACE


def test_send_becomes_stop_queue_drains_and_reasoning_renders(live_ui):
    app = live_ui
    app.entry.delete("1.0", "end")
    app.entry.insert("1.0", "first")
    app.handle_input()
    assert app.is_processing and app.btn_send.cget("text") == "STOP"
    assert app.btn_send.cget("fg").upper() == ui.RED

    for text in ("second", "third"):
        app.entry.insert("1.0", text)
        app.handle_input()
    assert app.entry.get("1.0", "end-1c") == ""
    assert [i["text"] for i in app._queue.items()] == ["second", "third"]
    assert app.queue_strip.winfo_manager() == "grid"
    labels = [w.cget("text") for w in app.queue_strip.winfo_children() if isinstance(w, ui.tk.Label)]
    assert labels[0] == "Queued (2):"

    app._cancel_queued(app._queue.items()[1]["id"])  # [x] on "third"
    assert [i["text"] for i in app._queue.items()] == ["second"]

    app.core.gate.set()
    _drain(app, lambda: len(app.core.calls) == 2 and not app.is_processing)
    assert [c[0] for c in app.core.calls] == ["first", "second"]
    assert app.btn_send.cget("text") == "SEND" and len(app._queue) == 0
    assert app.queue_strip.winfo_manager() == ""

    text = app.chat.get("1.0", "end")
    assert "reply to first (stopped)" in text and "reply to second\n" in text
    assert text.index("reply to first") < text.index("> second") < text.index("reply to second")
    heads = [w for name in app.chat.window_names()
             for w in app.root.nametowidget(name).winfo_children()
             if isinstance(w, ui.tk.Label) and w.cget("text") == "[+] reasoning"]
    assert len(heads) >= 2
    heads[-1].toggle()  # the <Button-1> handler; a withdrawn window gets no clicks
    assert heads[-1].cget("text") == "[-] reasoning"
    heads[-1].toggle()
    assert heads[-1].cget("text") == "[+] reasoning"


def test_stop_posts_cancel_off_the_tk_thread(live_ui, monkeypatch):
    app = live_ui
    seen = threading.Event()
    threads = []
    monkeypatch.setattr(ui.core_api, "post_cancel",
                        lambda: (threads.append(threading.current_thread()), seen.set(), True)[-1])
    app.is_processing = True
    app._set_send_mode(True)
    try:
        app.btn_send.invoke()
        assert seen.wait(5)
        assert threads[0] is not threading.main_thread()
        assert app.btn_send.cget("state") == "disabled"
    finally:
        app.is_processing = False
        app._set_send_mode(False)
    assert app.btn_send.cget("state") == "normal" and app.btn_send.cget("text") == "SEND"


def test_reasoning_toggle_only_with_reasoning(live_ui):
    app = live_ui
    app.clear_chat()
    app._parse_and_write_ai("[KERNEL_RESPONSE]\nplain answer")
    assert not app.chat.window_names()
    app._parse_and_write_ai("[KERNEL_RESPONSE]\nanswer", reasoning="  because  ")
    (name,) = app.chat.window_names()
    texts = [w.cget("text") for w in app.root.nametowidget(name).winfo_children()
             if isinstance(w, ui.tk.Label)]
    assert texts == ["[+] reasoning"]
    app._parse_and_write_ai("[ANALYSIS] inline plan [KERNEL_RESPONSE] body")  # non-thinking model
    assert len(app.chat.window_names()) == 2
    app.clear_chat()


def test_model_dropdown_lists_only_gguf(live_ui, tmp_path, monkeypatch):
    app = live_ui
    _sized(tmp_path / "pick.gguf", 1024 ** 3)
    _sized(tmp_path / "skip.safetensors", 1024)
    monkeypatch.setattr(ui, "MODEL_DIR", tmp_path)
    monkeypatch.setattr(ui, "TOTAL_VRAM_GB", 8.0)
    app._populate_models()
    assert list(app.model_dropdown["values"]) == ["pick.gguf  ·  1.0 GB  ·  fits in VRAM"]
    assert app.available_models_map == {"pick.gguf  ·  1.0 GB  ·  fits in VRAM": "pick.gguf"}

    monkeypatch.setattr(ui, "MODEL_DIR", tmp_path / "empty")
    app._populate_models()
    assert "[ERROR]" in app.model_dropdown["values"][0] and app.available_models_map == {}


def test_swap_done_refreshes_label_and_reenables(live_ui):
    app = live_ui
    app._swapping = True
    app.btn_swap.config(state="disabled")
    app._swap_done("new.gguf", "ok", "loaded.gguf")
    assert not app._swapping and app.btn_swap.cget("state") == "normal"
    assert app.lbl_current_model.cget("text").strip() == "loaded.gguf"
    app._swap_done("new.gguf", "failed", "timeout", "boom")
    _drain(app, lambda: "boom" in app.chat.get("1.0", "end"))
    assert app.lbl_status.cget("text") == "FSM: ENGINE OFFLINE"
