"""SovereignKernel FSM: state-change signalling and the cooldown path.

NVML is stubbed so this runs without a GPU (CI is ubuntu, no CUDA).
"""
import threading
import time

import pytest

from core_system import kernel as kernel_mod
from core_system.kernel import KernelState, SovereignKernel


@pytest.fixture
def kernel(monkeypatch):
    monkeypatch.setattr(kernel_mod.pynvml, "nvmlInit", lambda: None)
    monkeypatch.setattr(kernel_mod.pynvml, "nvmlDeviceGetHandleByIndex", lambda i: object())
    monkeypatch.setattr(kernel_mod.pynvml, "nvmlDeviceGetName", lambda h: "stub-gpu")
    k = SovereignKernel()
    yield k
    k.is_running = False


def test_wait_for_state_wakes_on_transition(kernel):
    kernel.request_state_change(KernelState.IDLE, "test")
    threading.Timer(0.05, kernel.request_state_change, (KernelState.INFERENCE, "test")).start()

    start = time.perf_counter()
    assert kernel.wait_for_state(lambda s: s == KernelState.INFERENCE, timeout=2.0)
    # Woken by the notify, not a poll interval: well under the old 100ms tick.
    assert time.perf_counter() - start < 0.5


def test_wait_for_state_times_out(kernel):
    kernel.request_state_change(KernelState.IDLE, "test")
    assert not kernel.wait_for_state(lambda s: s == KernelState.INFERENCE, timeout=0.05)


def test_inference_complete_returns_to_idle_without_delay(kernel):
    kernel.request_state_change(KernelState.INFERENCE, "test")
    loop = threading.Thread(target=kernel.orchestrator_loop, daemon=True)
    loop.start()
    # orchestrator_loop first moves to IDLE (boot); wait for that, then re-enter INFERENCE.
    assert kernel.wait_for_state(lambda s: s == KernelState.IDLE, timeout=1.0)
    kernel.request_state_change(KernelState.INFERENCE, "test")

    start = time.perf_counter()
    kernel.event_queue.put("INFERENCE_COMPLETE")
    assert kernel.wait_for_state(lambda s: s == KernelState.IDLE, timeout=3.0)
    # Used to include a fixed time.sleep(2) in COOLDOWN.
    assert time.perf_counter() - start < 0.5
