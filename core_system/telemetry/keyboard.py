# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | ZAT-SCS KEYSTROKE CADENCE SENSOR
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import os
import sys
import time
import logging

import numpy as np

logger = logging.getLogger("Peridot-ZAT")


def detect_session_type() -> str:
    """
    Classify the desktop session so ZAT-SCS knows whether a global keyboard
    hook is physically possible.

    Returns one of: "native" (Windows/macOS), "x11", "wayland", "headless".

    pynput's global listener is an X11 client. Under Wayland (the default
    session on Ubuntu 22.04+ and most Arch desktops) the compositor does not
    expose global input to unprivileged clients, so the listener either raises
    at import/start or silently records nothing.
    """
    if sys.platform in ("win32", "darwin"):
        return "native"

    session = (os.environ.get("XDG_SESSION_TYPE") or "").strip().lower()
    if session == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if session == "x11" or os.environ.get("DISPLAY"):
        return "x11"
    return "headless"


class KeyboardTracker:
    """
    Keystroke-cadence sensor feeding the f_c term of P(I_t).

    `available` is False when no global hook can be installed. Callers must
    zero the keyboard weight in that case rather than treating a permanently
    flat 0.0 cadence as genuine operator stillness.
    """

    def __init__(self):
        self.keystroke_timestamps = []
        self.listener = None
        self.session_type = detect_session_type()
        self.available = self.session_type in ("native", "x11")
        self.degradation_reason = None

        if not self.available:
            self.degradation_reason = (
                f"global keyboard hook unavailable under '{self.session_type}' session"
            )

    def start(self):
        if not self.available:
            logger.warning(
                "[ZAT-SCS] Keyboard telemetry DEGRADED: %s. "
                "P(I_t) falls back to audio-only sensing (keyboard weight = 0).",
                self.degradation_reason,
            )
            return False

        try:
            from pynput import keyboard  # imported lazily: binds to X11 at import time
        except Exception as e:
            self.available = False
            self.degradation_reason = f"pynput unavailable ({e})"
            logger.warning(
                "[ZAT-SCS] Keyboard telemetry DEGRADED: %s. "
                "P(I_t) falls back to audio-only sensing (keyboard weight = 0).",
                self.degradation_reason,
            )
            return False

        try:
            self.listener = keyboard.Listener(on_press=self._on_press)
            self.listener.start()
        except Exception as e:
            self.available = False
            self.degradation_reason = f"listener refused by display server ({e})"
            logger.warning(
                "[ZAT-SCS] Keyboard telemetry DEGRADED: %s. "
                "P(I_t) falls back to audio-only sensing (keyboard weight = 0).",
                self.degradation_reason,
            )
            return False

        logger.info("[ZAT-SCS] Keyboard telemetry online (session=%s).", self.session_type)
        return True

    def _on_press(self, key):
        self.keystroke_timestamps.append(time.time())
        if len(self.keystroke_timestamps) > 10:
            self.keystroke_timestamps.pop(0)

    def calculate_acceleration(self) -> float:
        if not self.available or len(self.keystroke_timestamps) < 2:
            return 0.0
        intervals = np.diff(self.keystroke_timestamps)
        avg_interval = np.mean(intervals) if len(intervals) > 0 else 1.0
        return min(1.0, 1.0 / (avg_interval + 1e-6))
