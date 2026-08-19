import time
import math
import logging
from core_system.telemetry.config.settings import LAMBDA_DECAY, WEIGHT_KEY, WEIGHT_AUD, TELEMETRY_HZ
from core_system.telemetry.keyboard import KeyboardTracker
from core_system.telemetry.audio import AudioTracker

logger = logging.getLogger("Peridot-ZAT")

class PhysicalTelemetryEngine:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.key_tracker = KeyboardTracker()
        self.audio_tracker = AudioTracker()
        self.p_i = 0.0
        self.last_event_time = time.time()
        # Sensor weights are resolved at start(), once we know which sensors
        # actually came online on this host.
        self.weight_key = WEIGHT_KEY
        self.weight_aud = WEIGHT_AUD

    def start(self):
        self.key_tracker.start()
        if not self.key_tracker.available:
            # Wayland / headless: a global keyboard hook is impossible, so a
            # flat 0.0 cadence is a missing signal, not operator stillness.
            # Drop its weight entirely and run P(I_t) audio-only.
            self.weight_key = 0.0
            logger.warning(
                "[ZAT-SCS] P(I_t) degraded to audio-only "
                "(session=%s, reason=%s). WEIGHT_KEY %.2f -> 0.00.",
                self.key_tracker.session_type,
                self.key_tracker.degradation_reason,
                WEIGHT_KEY,
            )

        try:
            self.audio_tracker.start()
            audio_ok = getattr(self.audio_tracker, "available", True)
        except Exception as e:
            audio_ok = False
            logger.warning("[ZAT-SCS] Audio telemetry raised on start: %s", e)

        if not audio_ok:
            # No PortAudio / no input device: the acoustic term is a missing
            # signal, not silence. Drop its weight the same way we drop the
            # keyboard term under Wayland.
            self.weight_aud = 0.0
            logger.warning(
                "[ZAT-SCS] Audio telemetry unavailable (%s). WEIGHT_AUD %.2f -> 0.00.",
                getattr(self.audio_tracker, "degradation_reason", "unknown"), WEIGHT_AUD,
            )

        if self.weight_key == 0.0 and self.weight_aud == 0.0:
            logger.warning(
                "[ZAT-SCS] No physical sensors online. Speculative preemption "
                "is inert; inference falls back to standard prefill latency."
            )

        self.last_event_time = time.time()
        self._loop()

    def _loop(self):
        import threading
        def _run():
            while True:
                self.tick()
                time.sleep(1.0 / TELEMETRY_HZ)
        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def tick(self) -> float:
        current_time = time.time()
        dt = current_time - self.last_event_time
        self.last_event_time = current_time

        f_c = self.key_tracker.calculate_acceleration()
        g_a = self.audio_tracker.get_envelope()

        decay_factor = math.exp(-LAMBDA_DECAY * dt)
        self.p_i = min(1.0, (self.p_i * decay_factor) + (self.weight_key * f_c) + (self.weight_aud * g_a))

        self.orchestrator.evaluate_probability(self.p_i)
        return self.p_i
