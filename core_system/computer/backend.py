# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | COMPUTER USE BACKENDS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""Screen/input backend interface. Only NullBackend exists in v1.6.0."""

from abc import ABC, abstractmethod


class ComputerUnavailable(RuntimeError):
    """No working backend on this machine / in this build."""


class ActionDenied(PermissionError):
    """The policy refused an action; str(e) is the reason shown to the model."""


class ComputerBackend(ABC):
    name = "abstract"
    available = False  # True only when the platform code loaded and works

    @abstractmethod
    def screen_size(self) -> tuple:
        """(width, height) of the primary screen in pixels."""

    @abstractmethod
    def screenshot(self, region=None) -> bytes:
        """PNG bytes of the screen, or of region (x, y, width, height)."""

    @abstractmethod
    def perform(self, action) -> None:
        """Execute one input action (anything but Screenshot)."""


class NullBackend(ComputerBackend):
    name = "null"
    MESSAGE = "Computer use backend not implemented yet (planned for v1.6.1-beta)"

    def screen_size(self):
        raise ComputerUnavailable(self.MESSAGE)

    def screenshot(self, region=None):
        raise ComputerUnavailable(self.MESSAGE)

    def perform(self, action):
        raise ComputerUnavailable(self.MESSAGE)


def get_backend() -> ComputerBackend:
    """The backend for this platform.

    Always NullBackend in v1.6.0. Planned: v1.6.1-beta a Win32 backend
    (GDI/BitBlt or PIL.ImageGrab capture, ctypes SendInput); v1.6.1 Linux X11
    and Wayland (xdg-desktop-portal) backends. Platform modules get imported
    here, lazily, so importing core_system.computer never touches them.
    """
    return NullBackend()
