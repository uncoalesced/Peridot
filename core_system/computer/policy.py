# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | COMPUTER USE POLICY
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""Safety policy for computer use, built from Settings.

check(action, context) raises ActionDenied with a reason. context is a dict
from the caller: "turn" (any hashable; the per-turn counter resets when it
changes), "approved" (the user approved this action, needed while
require_approval is on) and "app" (foreground app name, checked against
allowed_apps when that list is non-empty).
"""

import threading
from dataclasses import dataclass, field

from core_system.computer.actions import KeyPress
from core_system.computer.backend import ActionDenied

# Always denied, whatever the settings say: these escape the session or hand
# over the machine (Run dialog, lock, power menu, secure attention, task
# manager, close window).
BLOCKED_COMBOS = frozenset(frozenset(c) for c in (
    ("win", "r"), ("win", "l"), ("win", "x"), ("ctrl", "alt", "del"),
    ("ctrl", "shift", "esc"), ("alt", "f4"),
))


@dataclass
class ComputerPolicy:
    enabled: bool = False
    require_approval: bool = True
    allowed_apps: list = field(default_factory=list)
    max_actions_per_turn: int = 25
    redact_screens: bool = True  # placeholder: redaction lands with the real backend
    _turn: object = field(default=None, repr=False)
    _count: int = field(default=0, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def from_settings(cls):
        from core_system import settings  # lazy: keeps package import cheap
        return cls(
            enabled=bool(settings.get("computer.enabled")),
            require_approval=bool(settings.get("computer.require_approval")),
            allowed_apps=list(settings.get("computer.allowed_apps")),
            max_actions_per_turn=int(settings.get("computer.max_actions_per_turn")),
        )

    def check(self, action, context=None) -> None:
        ctx = context or {}
        if isinstance(action, KeyPress) and frozenset(action.keys) in BLOCKED_COMBOS:
            raise ActionDenied(f"Key combination {'+'.join(action.keys)} is always blocked")
        if not self.enabled:
            raise ActionDenied("Computer use is not enabled in Settings")
        app = ctx.get("app")
        if self.allowed_apps and app not in self.allowed_apps:
            raise ActionDenied(f"App {app!r} is not in computer.allowed_apps")
        if self.require_approval and not ctx.get("approved"):
            raise ActionDenied("Action needs user approval")
        with self._lock:
            turn = ctx.get("turn")
            if turn != self._turn:
                self._turn, self._count = turn, 0
            if self._count >= self.max_actions_per_turn:
                raise ActionDenied(f"Per-turn limit of {self.max_actions_per_turn} actions reached")
            self._count += 1
