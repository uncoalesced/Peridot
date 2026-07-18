"""Pytest safeguards for offline, headless CI runs."""

from __future__ import annotations

import os
import sys
import types


os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


class _NVMLError(Exception):
    """Test-only stand-in for pynvml.NVMLError."""


class _MemoryInfo:
    total = 0
    free = 0
    used = 0


class _UtilizationRates:
    gpu = 0
    memory = 0


def _install_fake_pynvml() -> None:
    fake = types.ModuleType("pynvml")
    fake.NVMLError = _NVMLError
    fake.NVML_TEMPERATURE_GPU = 0
    fake.nvmlInit = lambda: None
    fake.nvmlShutdown = lambda: None
    fake.nvmlDeviceGetCount = lambda: 0
    fake.nvmlDeviceGetHandleByIndex = lambda index: object()
    fake.nvmlDeviceGetMemoryInfo = lambda handle: _MemoryInfo()
    fake.nvmlDeviceGetUtilizationRates = lambda handle: _UtilizationRates()
    fake.nvmlDeviceGetTemperature = lambda handle, sensor: 0
    fake.nvmlDeviceGetPowerUsage = lambda handle: 0
    fake.nvmlDeviceGetName = lambda handle: b"pytest-no-gpu"
    sys.modules["pynvml"] = fake


try:
    import pynvml  # type: ignore[import-not-found]

    try:
        pynvml.nvmlInit()
        pynvml.nvmlShutdown()
    except Exception:
        _install_fake_pynvml()
except Exception:
    _install_fake_pynvml()