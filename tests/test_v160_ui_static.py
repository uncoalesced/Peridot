# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | v1.6.0 UI CHECKS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""
Guards for the v1.6.0 UI polish/perf pass (ui.py):

  * every #RRGGBB lives in the palette block,
  * the window icon path points at a real file,
  * worker-thread code never touches Tk widgets directly (ui_call only),
  * the streaming diff is append-only when it can be,
  * the `clear` command goes through ui_call on the real `chat` widget.

The static checks never open a window. The one live check builds the window
withdrawn and is skipped when Tk has no display.
"""

import ast
import re
from pathlib import Path

import pytest

import ui
from core_system.command_router import CommandRouter

UI_SRC = (Path(__file__).resolve().parent.parent / "ui.py").read_text(encoding="utf-8")
UI_TREE = ast.parse(UI_SRC)

# Calls that mutate or query Tk state; none may appear in worker-thread code.
TK_CALLS = {"config", "configure", "itemconfig", "insert", "delete", "see",
            "update_value", "after", "tag_add", "tag_remove", "update", "update_idletasks"}


def _functions(name):
    return [n for n in ast.walk(UI_TREE)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]


def _tk_calls(fn):
    return sorted({n.func.attr for n in ast.walk(fn)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr in TK_CALLS})


def test_hex_colours_only_inside_palette_block():
    lines = UI_SRC.splitlines()
    start = lines.index("# --- PALETTE ---")
    end = lines.index("# --- END PALETTE ---")
    stray = [(i + 1, line.strip()) for i, line in enumerate(lines)
             if re.search(r"#[0-9A-Fa-f]{6}\b", line) and not start < i < end]
    assert not stray, f"hex colours outside the palette block: {stray}"


def test_brand_palette_values():
    assert (ui.LIME, ui.BLACK, ui.GRAPE, ui.MINT, ui.TAUPE) == (
        "#00FF19", "#000000", "#5F5AA2", "#EFF9F0", "#A18276")


def test_icon_path_exists_and_is_cwd_independent():
    assert ui.ICON_PATH.is_absolute()
    assert ui.ICON_PATH.is_file(), ui.ICON_PATH


@pytest.mark.parametrize("name", ["_read_telemetry", "_telemetry_worker"])
def test_telemetry_worker_never_touches_widgets(name):
    (fn,) = _functions(name)
    assert _tk_calls(fn) == []


def test_worker_thread_bodies_never_touch_widgets():
    # Every nested `task`/`on_delta` closure runs off the Tk thread, as does
    # _voice_thread; they must hand off through ui_call/display_system_message.
    fns = _functions("task") + _functions("on_delta") + _functions("_voice_thread")
    assert len(fns) >= 6
    for fn in fns:
        assert _tk_calls(fn) == [], f"{fn.name} at line {fn.lineno}"


def test_old_per_poll_thread_and_main_thread_posts_are_gone():
    assert not _functions("_poll_backend_telemetry")
    assert not _functions("_update_stats")
    for name in ("_toggle_research", "_force_reclaim_vram"):
        (fn,) = _functions(name)
        src = ast.get_source_segment(UI_SRC, fn)
        assert "threading.Thread" in src, f"{name} posts on the Tk thread"
    (copy,) = _functions("_copy_to_clipboard")
    assert "update()" not in ast.get_source_segment(UI_SRC, copy)
    (adjust,) = _functions("_adjust_input_height")
    assert "update_idletasks()" not in ast.get_source_segment(UI_SRC, adjust)


@pytest.mark.parametrize("displayed, new, expected", [
    (None, "Hello", ("replace", "Hello")),
    ("Hel", "Hello", ("append", "lo")),
    ("Hello", "Hello", ("append", "")),
    ("[ANALYSIS] thinking", "Answer", ("replace", "Answer")),
    ("Hello world", "Hello", ("replace", "Hello")),
    ("", "abc", ("append", "abc")),
])
def test_stream_suffix(displayed, new, expected):
    assert ui._stream_suffix(displayed, new) == expected


class _RecordingUI:
    def __init__(self):
        self.calls = []
        self.chat = object()  # the real attribute name; chat_display never existed

    def ui_call(self, fn, *args):
        self.calls.append(fn.__name__)

    def clear_chat(self):
        raise AssertionError("must be queued via ui_call, not called on the worker")

    def print_logo(self):
        raise AssertionError("must be queued via ui_call, not called on the worker")


def test_clear_command_queues_through_ui_call():
    class Core:
        ui = _RecordingUI()

    result = CommandRouter(core=Core()).route("clear")
    assert Core.ui.calls == ["clear_chat", "print_logo"]
    assert result.startswith("[SYSTEM] Screen cleared")


# --- live check (needs a display) -------------------------------------------

@pytest.fixture
def live_ui(peridot_ui):  # shared session window, see tests/conftest.py
    peridot_ui.core = None
    return peridot_ui


def test_window_builds_and_streams_append_only(live_ui):
    app = live_ui
    app.root.update_idletasks()
    chat = app.chat

    deletes = []
    real_delete = chat.delete
    chat.delete = lambda *a: (deletes.append(a), real_delete(*a))

    app.is_processing = True
    chat.mark_set("stream_start", "end-1c")
    chat.mark_gravity("stream_start", "left")
    pending = {"text": None, "streamed": False, "shown": None, "placeholder": False}
    app._stream_state = pending

    def flush(text):
        pending["text"] = text
        app._flush_stream(pending)
        return chat.get("stream_start", "end-1c")

    assert flush("") == "\n>> reasoning..."
    assert flush("Hel") == "\nHel"            # placeholder replaced
    n = len(deletes)
    assert flush("Hello") == "\nHello"        # appended
    assert flush("Hello there") == "\nHello there"
    assert len(deletes) == n, "append path must not delete/redraw"
    assert flush("Rewritten") == "\nRewritten"  # shrink/rewrite -> full replace
    assert len(deletes) == n + 1

    app._finish("Final answer")
    assert "Final answer" in chat.get("1.0", "end")
    assert "Rewritten" not in chat.get("1.0", "end")


def test_input_height_tracks_lines(live_ui):
    app = live_ui
    app.root.update_idletasks()
    app.entry.insert("1.0", "a\nb\nc")
    app._adjust_input_height()
    assert int(app.entry.cget("height")) == 3
    app.entry.delete("1.0", "end")
    app._adjust_input_height()
    assert int(app.entry.cget("height")) == 1
