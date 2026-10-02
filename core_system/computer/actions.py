# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | COMPUTER USE ACTIONS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""Immutable computer-use actions and the strict parser from model tool calls.

Model arguments are untrusted: from_tool_call() rejects unknown arguments,
wrong types (bool is never an int), negative coordinates, unknown buttons or
key names, over-long text and long waits with ValueError.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Union

MAX_TEXT = 2000
MAX_WAIT_S = 10.0
MAX_CLICKS = 3
MAX_SCROLL = 100
MAX_KEYS = 4
BUTTONS = frozenset({"left", "right", "middle"})

MODIFIER_KEYS = frozenset({"ctrl", "alt", "shift", "win"})
ALLOWED_KEYS = MODIFIER_KEYS | frozenset(
    [chr(c) for c in range(ord("a"), ord("z") + 1)]
    + [str(d) for d in range(10)]
    + [f"f{n}" for n in range(1, 13)]
    + ["enter", "esc", "tab", "space", "backspace", "del", "insert", "home", "end",
       "pageup", "pagedown", "up", "down", "left", "right", "capslock", "printscreen"]
)
KEY_ALIASES = {"control": "ctrl", "cmd": "win", "meta": "win", "super": "win",
               "return": "enter", "escape": "esc", "delete": "del"}


@dataclass(frozen=True)
class Screenshot:
    region: Optional[Tuple[int, int, int, int]] = None  # x, y, width, height


@dataclass(frozen=True)
class Click:
    x: int
    y: int
    button: str = "left"
    clicks: int = 1


@dataclass(frozen=True)
class MoveMouse:
    x: int
    y: int


@dataclass(frozen=True)
class Drag:
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class TypeText:
    text: str


@dataclass(frozen=True)
class KeyPress:
    keys: Tuple[str, ...]  # one combo, e.g. ("ctrl", "c")


@dataclass(frozen=True)
class Scroll:
    x: int
    y: int
    dx: int
    dy: int


@dataclass(frozen=True)
class Wait:
    seconds: float


Action = Union[Screenshot, Click, MoveMouse, Drag, TypeText, KeyPress, Scroll, Wait]


def _int(args, key, *, low=None, high=None, default=None):
    if key not in args:
        if default is None:
            raise ValueError(f"Missing argument: {key}")
        return default
    v = args[key]
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"{key} must be an integer")
    if low is not None and v < low:
        raise ValueError(f"{key} must be >= {low}")
    if high is not None and v > high:
        raise ValueError(f"{key} must be <= {high}")
    return v


def _coord(args, key):
    return _int(args, key, low=0)


def normalize_key(name) -> str:
    if not isinstance(name, str):
        raise ValueError("key names must be strings")
    k = name.strip().lower()
    k = KEY_ALIASES.get(k, k)
    if k not in ALLOWED_KEYS:
        raise ValueError(f"Key not allowed: {name!r}")
    return k


def _screenshot(a):
    region = a.get("region")
    if region is None:
        return Screenshot()
    if not isinstance(region, (list, tuple)) or len(region) != 4:
        raise ValueError("region must be [x, y, width, height]")
    r = dict(zip("xywh", region))
    return Screenshot((_coord(r, "x"), _coord(r, "y"), _int(r, "w", low=1), _int(r, "h", low=1)))


def _click(a):
    button = a.get("button", "left")
    if button not in BUTTONS:
        raise ValueError(f"button must be one of {sorted(BUTTONS)}")
    return Click(_coord(a, "x"), _coord(a, "y"), button,
                 _int(a, "clicks", low=1, high=MAX_CLICKS, default=1))


def _type(a):
    text = a.get("text")
    if not isinstance(text, str) or not text:
        raise ValueError("text must be a non-empty string")
    if len(text) > MAX_TEXT:
        raise ValueError(f"text longer than {MAX_TEXT} characters")
    return TypeText(text)


def _key(a):
    keys = a.get("keys")
    if isinstance(keys, str):
        keys = keys.split("+")
    if not isinstance(keys, (list, tuple)) or not 1 <= len(keys) <= MAX_KEYS:
        raise ValueError(f"keys must be a list of 1-{MAX_KEYS} key names")
    return KeyPress(tuple(normalize_key(k) for k in keys))


def _scroll(a):
    return Scroll(_coord(a, "x"), _coord(a, "y"),
                  _int(a, "dx", low=-MAX_SCROLL, high=MAX_SCROLL, default=0),
                  _int(a, "dy", low=-MAX_SCROLL, high=MAX_SCROLL, default=0))


def _wait(a):
    s = a.get("seconds")
    if isinstance(s, bool) or not isinstance(s, (int, float)):
        raise ValueError("seconds must be a number")
    if not 0 < s <= MAX_WAIT_S:
        raise ValueError(f"seconds must be in (0, {MAX_WAIT_S:g}]")
    return Wait(float(s))


# tool name -> (parser, allowed argument names)
PARSERS = {
    "computer_screenshot": (_screenshot, {"region"}),
    "computer_click": (_click, {"x", "y", "button", "clicks"}),
    "computer_move": (lambda a: MoveMouse(_coord(a, "x"), _coord(a, "y")), {"x", "y"}),
    "computer_drag": (lambda a: Drag(*(_coord(a, k) for k in ("x1", "y1", "x2", "y2"))),
                      {"x1", "y1", "x2", "y2"}),
    "computer_type": (_type, {"text"}),
    "computer_key": (_key, {"keys"}),
    "computer_scroll": (_scroll, {"x", "y", "dx", "dy"}),
    "computer_wait": (_wait, {"seconds"}),
}


def from_tool_call(name: str, args) -> Action:
    """Parse one model tool call into an Action; ValueError on anything off."""
    if name not in PARSERS:
        raise ValueError(f"Unknown computer tool: {name!r}")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ValueError("arguments must be an object")
    parser, allowed = PARSERS[name]
    extra = set(args) - allowed
    if extra:
        raise ValueError(f"Unexpected argument(s): {', '.join(sorted(extra))}")
    return parser(args)
