# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | v1.6.1 COMPUTER USE SCAFFOLD TESTS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""core_system/computer: parsing, policy, catalog gating, handler, import cost."""

import subprocess
import sys
from pathlib import Path

import pytest

from core_system import settings
from core_system.computer import actions, tools
from core_system.computer.actions import (
    Click, Drag, KeyPress, MoveMouse, Screenshot, Scroll, TypeText, Wait, from_tool_call,
)
from core_system.computer.backend import ActionDenied, ComputerUnavailable, NullBackend, get_backend
from core_system.computer.policy import ComputerPolicy

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def store(tmp_path):
    settings.set_path(tmp_path / "settings.json")
    yield
    settings.set_path(tmp_path / "unused.json")


@pytest.fixture
def logs(monkeypatch):
    seen = []
    monkeypatch.setattr(tools, "_log", lambda event, detail, severity="INFO": seen.append((event, detail)))
    return seen


# --- parsing -----------------------------------------------------------------

@pytest.mark.parametrize("name,args,expected", [
    ("computer_screenshot", {}, Screenshot()),
    ("computer_screenshot", None, Screenshot()),
    ("computer_screenshot", {"region": [0, 0, 100, 50]}, Screenshot((0, 0, 100, 50))),
    ("computer_click", {"x": 10, "y": 20}, Click(10, 20)),
    ("computer_click", {"x": 0, "y": 0, "button": "right", "clicks": 2}, Click(0, 0, "right", 2)),
    ("computer_move", {"x": 5, "y": 6}, MoveMouse(5, 6)),
    ("computer_drag", {"x1": 1, "y1": 2, "x2": 3, "y2": 4}, Drag(1, 2, 3, 4)),
    ("computer_type", {"text": "hello"}, TypeText("hello")),
    ("computer_key", {"keys": ["Control", "C"]}, KeyPress(("ctrl", "c"))),
    ("computer_key", {"keys": "ctrl+shift+t"}, KeyPress(("ctrl", "shift", "t"))),
    ("computer_scroll", {"x": 1, "y": 1, "dy": -3}, Scroll(1, 1, 0, -3)),
    ("computer_wait", {"seconds": 10}, Wait(10.0)),
    ("computer_wait", {"seconds": 0.5}, Wait(0.5)),
])
def test_parse_valid(name, args, expected):
    assert from_tool_call(name, args) == expected


@pytest.mark.parametrize("name,args", [
    ("computer_nope", {}),
    ("computer_click", "x=1"),
    ("computer_click", {"x": 1}),
    ("computer_click", {"x": -1, "y": 0}),
    ("computer_click", {"x": 1.5, "y": 0}),
    ("computer_click", {"x": True, "y": 0}),
    ("computer_click", {"x": 1, "y": 1, "button": "side"}),
    ("computer_click", {"x": 1, "y": 1, "clicks": 4}),
    ("computer_click", {"x": 1, "y": 1, "extra": 1}),
    ("computer_screenshot", {"region": [0, 0, 0, 10]}),
    ("computer_screenshot", {"region": [0, 0, 10]}),
    ("computer_type", {"text": ""}),
    ("computer_type", {"text": "a" * (actions.MAX_TEXT + 1)}),
    ("computer_type", {"text": 5}),
    ("computer_key", {"keys": []}),
    ("computer_key", {"keys": ["ctrl", "launch_missiles"]}),
    ("computer_key", {"keys": ["a", "b", "c", "d", "e"]}),
    ("computer_scroll", {"x": 1, "y": 1, "dy": 1000}),
    ("computer_wait", {"seconds": 0}),
    ("computer_wait", {"seconds": 11}),
    ("computer_wait", {"seconds": "1"}),
])
def test_parse_invalid(name, args):
    with pytest.raises(ValueError):
        from_tool_call(name, args)


def test_actions_are_frozen():
    with pytest.raises(Exception):
        Click(1, 2).x = 3


def test_text_at_cap_is_accepted():
    assert from_tool_call("computer_type", {"text": "a" * actions.MAX_TEXT}).text


# --- policy ------------------------------------------------------------------

def _on(**kw):
    return ComputerPolicy(enabled=True, require_approval=False, **kw)


def test_policy_denies_when_disabled():
    with pytest.raises(ActionDenied, match="not enabled"):
        ComputerPolicy().check(Click(1, 1))


def test_policy_from_default_settings_is_off(store):
    p = ComputerPolicy.from_settings()
    assert (p.enabled, p.require_approval, p.allowed_apps, p.max_actions_per_turn) == (False, True, [], 25)


@pytest.mark.parametrize("keys", [("win", "r"), ("r", "win"), ("ctrl", "alt", "del"), ("alt", "f4")])
def test_policy_always_denies_blocked_combos(keys):
    with pytest.raises(ActionDenied, match="always blocked"):
        _on().check(KeyPress(keys))


def test_blocked_combo_via_alias_is_denied():
    action = from_tool_call("computer_key", {"keys": ["Control", "Alt", "Delete"]})
    with pytest.raises(ActionDenied, match="always blocked"):
        _on().check(action)


def test_policy_allows_plain_combo():
    _on().check(KeyPress(("ctrl", "c")))


def test_policy_requires_approval():
    p = ComputerPolicy(enabled=True)
    with pytest.raises(ActionDenied, match="approval"):
        p.check(Click(1, 1))
    p.check(Click(1, 1), {"approved": True})


def test_policy_allowed_apps():
    p = _on(allowed_apps=["notepad.exe"])
    with pytest.raises(ActionDenied, match="allowed_apps"):
        p.check(Click(1, 1), {"app": "cmd.exe"})
    p.check(Click(1, 1), {"app": "notepad.exe"})


def test_policy_per_turn_cap_resets_on_new_turn():
    p = _on(max_actions_per_turn=3)
    for _ in range(3):
        p.check(Click(1, 1), {"turn": 1})
    with pytest.raises(ActionDenied, match="limit of 3"):
        p.check(Click(1, 1), {"turn": 1})
    p.check(Click(1, 1), {"turn": 2})


# --- backend -----------------------------------------------------------------

def test_null_backend_raises():
    b = get_backend()
    assert isinstance(b, NullBackend) and not b.available
    for call in (b.screen_size, b.screenshot, lambda: b.perform(Click(1, 1))):
        with pytest.raises(ComputerUnavailable, match="v1.6.1-beta"):
            call()


# --- catalog + handler -------------------------------------------------------

def test_catalog_empty_by_default(store):
    assert tools.computer_tool_catalog() == []


def test_catalog_empty_even_when_enabled_without_backend(store):
    settings.update({"computer.enabled": True})
    assert tools.computer_tool_catalog() == []


def test_catalog_offered_with_enabled_policy_and_working_backend():
    class Live(NullBackend):
        available = True
    names = {t["name"] for t in tools.computer_tool_catalog(_on(), Live())}
    assert names == tools.COMPUTER_TOOL_NAMES == set(actions.PARSERS)


def test_handle_not_enabled_by_default(store, logs):
    out = tools.handle("computer_click", {"x": 1, "y": 1})
    assert out["ok"] is False and "not enabled" in out["error"]
    assert logs and logs[-1][0] == "COMPUTER_DENIED"


def test_handle_not_implemented_when_enabled(store, logs):
    settings.update({"computer.enabled": True, "computer.require_approval": False})
    out = tools.handle("computer_screenshot", {}, {"turn": "t"})
    assert out["ok"] is False and "not implemented" in out["error"]
    assert logs[-1][0] == "COMPUTER_ACTION"


def test_handle_invalid_args_logged(logs):
    out = tools.handle("computer_click", {"x": -5, "y": 1})
    assert out["ok"] is False and "Invalid" in out["error"]
    assert logs[-1][0] == "COMPUTER_DENIED"


def test_handle_does_not_log_typed_text(store, logs):
    tools.handle("computer_type", {"text": "hunter2"})
    assert all("hunter2" not in detail for _, detail in logs)


def test_handle_writes_security_log(store, monkeypatch):
    from core_system import security
    events = []
    monkeypatch.setattr(security, "log_event", lambda *a: events.append(a))
    tools.handle("computer_wait", {"seconds": 1})
    assert events and events[-1][0] == "COMPUTER_DENIED"


# --- import cost -------------------------------------------------------------

def test_import_pulls_in_no_heavy_or_input_modules():
    code = (
        "import sys, core_system.computer\n"
        "bad = [m for m in ('PIL', 'ctypes', 'numpy', 'torch', 'Xlib', 'pyautogui', 'config')"
        " if m in sys.modules]\n"
        "print(','.join(bad))\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == ""
