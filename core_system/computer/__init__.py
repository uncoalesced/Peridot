# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | COMPUTER USE (SCAFFOLD)
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Computer use: the model looks at the screen and drives mouse and keyboard.

Roadmap
-------
v1.6.0 (this): scaffold only. Typed actions with strict validation
    (actions.py), the backend interface plus a NullBackend that refuses
    everything (backend.py), the safety policy read from Settings (policy.py)
    and tool definitions + a handler (tools.py). OFF by default
    ("computer.enabled" is False) and NOT offered to the model:
    computer_tool_catalog() always returns [].
v1.6.1-beta: Win32 backend. Screenshots via GDI/BitBlt or PIL.ImageGrab,
    input via SendInput through ctypes. Tools wired into the tool loop behind
    the setting (tools.tool_catalog + dispatch, the same hook pattern as
    FILE_TOOL_HANDLERS). Per-action approval UI ("computer.require_approval").
v1.6.1: Linux X11 and Wayland-portal backends, region/window targeting,
    OCR / accessibility tree, session recording, policy UI.

Importing this package must stay cheap: no ctypes window/input calls and no
imaging libraries at import time. Backends load their platform code lazily.
"""

from core_system.computer.actions import Action, from_tool_call
from core_system.computer.backend import ActionDenied, ComputerBackend, ComputerUnavailable, get_backend
from core_system.computer.policy import ComputerPolicy
from core_system.computer.tools import computer_tool_catalog, handle

__all__ = [
    "Action", "ActionDenied", "ComputerBackend", "ComputerPolicy", "ComputerUnavailable",
    "computer_tool_catalog", "from_tool_call", "get_backend", "handle",
]
