# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | COMPUTER USE TOOLS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""Model-facing computer tools and their handler.

Not wired into the tool loop in v1.6.0. The single v1.6.1-beta integration
point is core_system/extensions/tools.py: tool_catalog() extends its list with
computer_tool_catalog(), and dispatch routes names in COMPUTER_TOOL_NAMES to
handle(name, arguments, context), the same hook pattern as FILE_TOOL_HANDLERS.
"""

import base64

from core_system.computer.actions import Screenshot, from_tool_call
from core_system.computer.backend import ActionDenied, ComputerUnavailable, get_backend
from core_system.computer.policy import ComputerPolicy


def _obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


_INT = {"type": "integer", "minimum": 0}
_XY = {"x": _INT, "y": _INT}

COMPUTER_TOOLS = [
    {"name": "computer_screenshot", "description": "Capture the screen (optionally a region) as PNG.",
     "parameters": _obj({"region": {"type": "array", "items": {"type": "integer"},
                                    "minItems": 4, "maxItems": 4,
                                    "description": "[x, y, width, height]"}})},
    {"name": "computer_click", "description": "Click at screen coordinates.",
     "parameters": _obj({**_XY, "button": {"type": "string", "enum": ["left", "right", "middle"]},
                         "clicks": {"type": "integer", "minimum": 1, "maximum": 3}}, ("x", "y"))},
    {"name": "computer_type", "description": "Type text at the current focus.",
     "parameters": _obj({"text": {"type": "string", "maxLength": 2000}}, ("text",))},
    {"name": "computer_key", "description": "Press one key combination, e.g. [\"ctrl\", \"c\"].",
     "parameters": _obj({"keys": {"type": "array", "items": {"type": "string"},
                                  "minItems": 1, "maxItems": 4}}, ("keys",))},
    {"name": "computer_scroll", "description": "Scroll at screen coordinates by dx/dy notches.",
     "parameters": _obj({**_XY, "dx": {"type": "integer"}, "dy": {"type": "integer"}}, ("x", "y"))},
    {"name": "computer_move", "description": "Move the mouse pointer.",
     "parameters": _obj(_XY, ("x", "y"))},
    {"name": "computer_drag", "description": "Drag with the left button from (x1,y1) to (x2,y2).",
     "parameters": _obj({"x1": _INT, "y1": _INT, "x2": _INT, "y2": _INT},
                        ("x1", "y1", "x2", "y2"))},
    {"name": "computer_wait", "description": "Wait up to 10 seconds for the screen to settle.",
     "parameters": _obj({"seconds": {"type": "number", "exclusiveMinimum": 0, "maximum": 10}},
                        ("seconds",))},
]
COMPUTER_TOOL_NAMES = frozenset(t["name"] for t in COMPUTER_TOOLS)


def _out(ok, result="", error=""):
    return {"ok": ok, "result": result, "error": error}


def _log(event, detail, severity="INFO"):
    # Both imported lazily: audit pulls in config (and numpy via gguf), and
    # security creates logs/ on import; the package import stays stdlib-only.
    try:
        from core_system.audit import ghost
        ghost.info(f"[COMPUTER] {event} {detail}")
    except Exception:
        pass
    try:
        from core_system import security
        security.log_event(event, detail, severity)
    except Exception:
        pass


_shared_policy = ComputerPolicy()


def _settings_policy():
    """One process-wide policy so the per-turn counter survives between calls;
    its knobs are re-read from Settings every time."""
    fresh = ComputerPolicy.from_settings()
    for f in ("enabled", "require_approval", "allowed_apps", "max_actions_per_turn"):
        setattr(_shared_policy, f, getattr(fresh, f))
    return _shared_policy


def computer_tool_catalog(policy=None, backend=None) -> list:
    """Tool definitions offered to the model: [] unless enabled AND a backend works."""
    policy = policy or ComputerPolicy.from_settings()
    backend = backend or get_backend()
    if not (policy.enabled and backend.available):
        return []
    return [dict(t) for t in COMPUTER_TOOLS]


def handle(name, arguments, context=None, *, policy=None, backend=None) -> dict:
    """Parse, policy-check and perform one computer tool call. Never raises."""
    try:
        action = from_tool_call(name, arguments)
    except ValueError as e:
        _log("COMPUTER_DENIED", f"{name} invalid: {e}", "WARNING")
        return _out(False, error=f"Invalid {name} call: {e}")
    kind = type(action).__name__  # TypeText may carry a password: log the type only
    try:
        (policy or _settings_policy()).check(action, context)
    except ActionDenied as e:
        _log("COMPUTER_DENIED", f"{kind}: {e}", "WARNING")
        return _out(False, error=str(e))
    backend = backend or get_backend()
    _log("COMPUTER_ACTION", f"{kind} via {backend.name}")
    try:
        if isinstance(action, Screenshot):
            png = backend.screenshot(action.region)
            return _out(True, base64.b64encode(png).decode("ascii"))
        backend.perform(action)
        return _out(True, "done")
    except ComputerUnavailable as e:
        return _out(False, error=str(e))
    except Exception as e:
        _log("COMPUTER_ACTION", f"{kind} failed: {e}", "WARNING")
        return _out(False, error=f"{name} failed: {e}")
