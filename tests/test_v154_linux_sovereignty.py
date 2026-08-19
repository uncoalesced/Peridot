# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
v1.5.4 regression coverage: Linux session detection, the offline sovereignty
lock, and the provisional GPU layer pin.

Runs headless -- no GPU, no display server, no network.
"""

import os
import sys
import subprocess
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402  -- must be imported first; sets the sovereignty lock
from core_system.security import is_file_safe, is_model_download_safe  # noqa: E402
from core_system.model_fetch import assert_main_process_offline, download_model  # noqa: E402
from core_system.telemetry.keyboard import KeyboardTracker, detect_session_type  # noqa: E402
from core_system.telemetry.config.settings import WEIGHT_KEY, WEIGHT_AUD  # noqa: E402


# -----------------------------------------------------------------------------
# 1. LINUX SESSION DETECTION / WAYLAND DEGRADATION
# -----------------------------------------------------------------------------

@pytest.fixture
def linux_session(monkeypatch):
    """Force the detector down the Linux branch with a clean session env."""
    monkeypatch.setattr(sys, "platform", "linux")
    for var in ("XDG_SESSION_TYPE", "WAYLAND_DISPLAY", "DISPLAY"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_detects_wayland_from_session_type(linux_session):
    linux_session.setenv("XDG_SESSION_TYPE", "wayland")
    assert detect_session_type() == "wayland"


def test_detects_wayland_from_display_socket(linux_session):
    """Some Arch/sway setups leave XDG_SESSION_TYPE unset."""
    linux_session.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert detect_session_type() == "wayland"


def test_detects_x11(linux_session):
    linux_session.setenv("XDG_SESSION_TYPE", "x11")
    linux_session.setenv("DISPLAY", ":0")
    assert detect_session_type() == "x11"


def test_detects_headless(linux_session):
    assert detect_session_type() == "headless"


def test_windows_always_native(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert detect_session_type() == "native"


def test_wayland_tracker_is_unavailable_and_does_not_raise(linux_session):
    linux_session.setenv("XDG_SESSION_TYPE", "wayland")
    tracker = KeyboardTracker()
    assert tracker.available is False
    assert "wayland" in tracker.degradation_reason
    # start() must degrade, never raise, and never install a listener.
    assert tracker.start() is False
    assert tracker.listener is None
    assert tracker.calculate_acceleration() == 0.0


def test_headless_tracker_is_unavailable(linux_session):
    tracker = KeyboardTracker()
    assert tracker.available is False
    assert tracker.start() is False


def test_wayland_zeroes_keyboard_weight_in_p_i(linux_session):
    """
    The core requirement: under Wayland, P(I_t) must run audio-only with
    WEIGHT_KEY dropped to 0, not merely receive a flat 0.0 cadence.
    """
    linux_session.setenv("XDG_SESSION_TYPE", "wayland")
    from core_system.telemetry.processor import PhysicalTelemetryEngine

    class _NullOrchestrator:
        def __init__(self):
            self.seen = []

        def evaluate_probability(self, p):
            self.seen.append(p)

    class _FakeAudio:
        def start(self):
            pass

        def get_envelope(self):
            return 1.0

    engine = PhysicalTelemetryEngine(orchestrator=_NullOrchestrator())
    engine.audio_tracker = _FakeAudio()
    engine._loop = lambda: None  # do not spawn the 10Hz daemon in tests
    engine.start()

    assert engine.weight_key == 0.0, "Keyboard weight must be zeroed under Wayland"
    assert engine.weight_aud == WEIGHT_AUD, "Audio weight must be preserved"

    # Even with a saturated keyboard signal, only the audio term contributes.
    engine.key_tracker.keystroke_timestamps = [0.0, 0.001, 0.002]
    p = engine.tick()
    assert p == pytest.approx(WEIGHT_AUD, abs=1e-6)


def test_x11_preserves_keyboard_weight(linux_session):
    """Under X11 the weight stays intact even if pynput itself is absent."""
    linux_session.setenv("XDG_SESSION_TYPE", "x11")
    linux_session.setenv("DISPLAY", ":0")
    tracker = KeyboardTracker()
    assert tracker.available is True
    assert tracker.session_type == "x11"
    # WEIGHT_KEY is a real, non-zero contribution on a supported session.
    assert WEIGHT_KEY > 0


def test_audio_failure_degrades_instead_of_crashing(linux_session):
    """No mic on a headless box must not take the telemetry engine down."""
    linux_session.setenv("XDG_SESSION_TYPE", "x11")
    linux_session.setenv("DISPLAY", ":0")
    from core_system.telemetry.processor import PhysicalTelemetryEngine

    class _NullOrchestrator:
        def evaluate_probability(self, p):
            pass

    class _BrokenAudio:
        def start(self):
            raise OSError("no default input device")

        def get_envelope(self):
            return 0.0

    engine = PhysicalTelemetryEngine(orchestrator=_NullOrchestrator())
    engine.audio_tracker = _BrokenAudio()
    engine.key_tracker.start = lambda: True  # skip the real X11 hook
    engine._loop = lambda: None
    engine.start()

    assert engine.weight_aud == 0.0


@pytest.fixture
def no_portaudio(monkeypatch):
    """
    Simulate a stock Debian 12 / Arch box with no portaudio19-dev.

    Note we never import the real sounddevice here: on a host where PortAudio
    is genuinely missing, the partially-initialised cffi module destabilises
    later native DLL loads (PyMuPDF faults) inside the same interpreter.
    """
    import builtins
    real_import = builtins.__import__

    def _no_portaudio(name, *args, **kwargs):
        if name == "sounddevice":
            raise OSError("PortAudio library not found")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_portaudio)
    monkeypatch.delitem(sys.modules, "sounddevice", raising=False)


def test_missing_portaudio_does_not_raise(no_portaudio):
    """
    sounddevice raises OSError (not ImportError) when libportaudio is absent,
    which server.py's `except ImportError` guard would miss. The sensor must
    swallow it locally so a stock Debian box without portaudio19-dev still boots.
    """
    from core_system.telemetry.audio import AudioTracker

    tracker = AudioTracker()
    assert tracker.start() is False  # degrades, never raises
    assert tracker.available is False
    assert tracker.get_envelope() == 0.0
    assert "PortAudio" in tracker.degradation_reason


def test_audio_import_failure_zeroes_audio_weight(linux_session, no_portaudio):
    linux_session.setenv("XDG_SESSION_TYPE", "x11")
    linux_session.setenv("DISPLAY", ":0")
    from core_system.telemetry.audio import AudioTracker
    from core_system.telemetry.processor import PhysicalTelemetryEngine

    class _NullOrchestrator:
        def evaluate_probability(self, p):
            pass

    engine = PhysicalTelemetryEngine(orchestrator=_NullOrchestrator())
    engine.audio_tracker = AudioTracker()
    engine.key_tracker.start = lambda: True
    engine._loop = lambda: None
    engine.start()

    assert engine.audio_tracker.available is False
    assert engine.weight_aud == 0.0


def test_no_sensors_leaves_p_i_flat(linux_session, no_portaudio):
    """Wayland + no mic: P(I_t) must stay 0 so preemption never misfires."""
    linux_session.setenv("XDG_SESSION_TYPE", "wayland")
    from core_system.telemetry.audio import AudioTracker
    from core_system.telemetry.processor import PhysicalTelemetryEngine

    class _NullOrchestrator:
        def evaluate_probability(self, p):
            pass

    engine = PhysicalTelemetryEngine(orchestrator=_NullOrchestrator())
    engine.audio_tracker = AudioTracker()
    engine._loop = lambda: None
    engine.start()

    assert engine.weight_key == 0.0
    assert engine.weight_aud == 0.0
    assert engine.tick() == 0.0


# -----------------------------------------------------------------------------
# 2. SOVEREIGNTY LOCK / SUBPROCESS-ISOLATED DOWNLOAD
# -----------------------------------------------------------------------------

def test_config_forces_offline_mode():
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    assert_main_process_offline()


def test_offline_lock_survives_a_hostile_dotenv(tmp_path, monkeypatch):
    """
    A .env that says HF_HUB_OFFLINE=0 must not be able to re-open the network:
    config.py force-sets the flag after load_dotenv().
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "API_KEY=deadbeef\nHF_HUB_OFFLINE=0\nTRANSFORMERS_OFFLINE=0\n",  # pragma: allowlist secret
        encoding="utf-8",
    )
    child_env = dict(os.environ)
    child_env.pop("HF_HUB_OFFLINE", None)
    child_env.pop("TRANSFORMERS_OFFLINE", None)

    proc = subprocess.run(
        [sys.executable, "-c",
         "import os, sys; sys.path.insert(0, r'%s'); import config;"
         "print(os.environ['HF_HUB_OFFLINE'], os.environ['TRANSFORMERS_OFFLINE'])"
         % str(Path(__file__).parent.parent)],
        cwd=str(tmp_path),
        env=child_env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines()[-1] == "1 1"


def test_assert_main_process_offline_rejects_online(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    with pytest.raises(RuntimeError, match="Sovereignty violation"):
        assert_main_process_offline()


def test_download_child_gets_online_env_but_parent_does_not(monkeypatch, tmp_path):
    """
    The one place HF_HUB_OFFLINE=0 may exist is the fetch child's environment.
    Assert that contract without touching the network.
    """
    captured = {}

    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs["env"]
        captured["shell"] = kwargs.get("shell")
        (tmp_path / "model.gguf").write_bytes(b"stub")
        return _Result()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    result = download_model("Qwen/Qwen3-27B-GGUF", "model.gguf", tmp_path)

    assert result == tmp_path / "model.gguf"
    assert captured["env"]["HF_HUB_OFFLINE"] == "0"
    assert captured["env"]["TRANSFORMERS_OFFLINE"] == "0"
    assert captured["shell"] is False
    assert captured["cmd"][0] == sys.executable
    # Parent process is untouched.
    assert os.environ["HF_HUB_OFFLINE"] == "1"


def test_download_rejected_before_any_subprocess(monkeypatch, tmp_path):
    """Security layer must block first: no child is ever spawned."""
    def _boom(*a, **k):
        raise AssertionError("subprocess spawned despite security rejection")

    monkeypatch.setattr(subprocess, "run", _boom)
    with pytest.raises(PermissionError):
        download_model("Qwen/Qwen3", "../../../etc/cron.d/pwn", tmp_path)
    with pytest.raises(PermissionError):
        download_model("evil; rm -rf /", "model.gguf", tmp_path)


# -----------------------------------------------------------------------------
# 3. CROSS-PLATFORM PATH BLACKLIST
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("bad_path", [
    "C:\\Windows\\System32\\cmd.exe",
    "c:/windows/system32/config/sam",
    "/etc/shadow",
    "/etc/passwd",
    "/root/.ssh/id_ed25519",
    "/boot/vmlinuz",
    "/proc/self/environ",
])
def test_sensitive_paths_blocked_on_any_host(bad_path):
    """These must be blocked whether the suite runs on Windows or the Linux CI."""
    allowed, _ = is_file_safe(bad_path)
    assert allowed is False, f"{bad_path} was not blocked"


@pytest.mark.parametrize("ok_path", [
    "research_paper.pdf",
    "input/processed/chapter1.txt",
    "models/Qwen3.8-27B-UD-Q2_K_XL.gguf",
])
def test_operator_paths_allowed(ok_path):
    allowed, _ = is_file_safe(ok_path)
    assert allowed is True, f"{ok_path} was wrongly blocked"


@pytest.mark.parametrize("secret", [".ssh/id_rsa", "some/dir/.env", "auth.token"])
def test_credential_files_blocked_with_either_separator(secret):
    assert is_file_safe(secret)[0] is False
    assert is_file_safe(secret.replace("/", "\\"))[0] is False


def test_model_download_destination_confined(tmp_path):
    assert is_model_download_safe("Qwen/Qwen3-GGUF", "m.gguf", tmp_path)[0] is True
    assert is_model_download_safe("Qwen/Qwen3-GGUF", "..", tmp_path)[0] is False
    assert is_model_download_safe("Qwen/Qwen3-GGUF", "a/b.gguf", tmp_path)[0] is False


# -----------------------------------------------------------------------------
# 4. PROVISIONAL GPU LAYER PIN
# -----------------------------------------------------------------------------

QWEN_27B = "Qwen3.8-27B-UD-Q2_K_XL.gguf"


def test_default_model_is_qwen_27b():
    """The pin is only meaningful if it matches the shipped default."""
    assert config.ACTIVE_MODEL_NAME == QWEN_27B or "ACTIVE_MODEL_NAME" in os.environ


def test_qwen_27b_has_a_provisional_pin():
    assert QWEN_27B in config._PROVISIONAL_GPU_LAYERS
    pinned = config._PROVISIONAL_GPU_LAYERS[QWEN_27B]
    assert 0 < pinned < 99, "Provisional pin must be a partial offload, not full-GPU"


def test_provisional_pin_is_lower_than_the_unvalidated_heuristic():
    """
    Guards the whole point of the pin: the auto-heuristic was tuned on 4-bit
    8B-14B models and reads high for a 2-bit 27.8B. If a future edit makes the
    pin the looser of the two, boot safety is gone.
    """
    model_mb = 10700   # measured size of the shipped Q2_K_XL file
    vram_mb = 8151     # RTX 5050 Laptop, the validated reference GPU
    heuristic = config._calculate_gpu_layers(model_mb, vram_mb)
    assert config._PROVISIONAL_GPU_LAYERS[QWEN_27B] <= heuristic


def test_cpu_only_host_still_gets_zero_layers():
    """No VRAM must win over the pin, or a CPU-only box tries to offload."""
    assert config._calculate_gpu_layers(10700, 0) == 0


def test_gpu_layers_env_override_wins(tmp_path):
    child_env = dict(os.environ)
    child_env["GPU_LAYERS"] = "7"
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, r'%s'); import config; print(config.GPU_LAYERS)"
         % str(Path(__file__).parent.parent)],
        env=child_env, capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines()[-1] == "7"
