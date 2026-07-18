import time
import math
from core_system.telemetry.config.settings import LAMBDA_DECAY, WEIGHT_KEY, WEIGHT_AUD, TELEMETRY_HZ
from core_system.telemetry.keyboard import KeyboardTracker
from core_system.telemetry.audio import AudioTracker

class PhysicalTelemetryEngine:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.key_tracker = KeyboardTracker()
        self.audio_tracker = AudioTracker()
        self.p_i = 0.0
        self.last_event_time = time.time()

    def start(self):
        self.key_tracker.start()
        self.audio_tracker.start()
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
        self.p_i = min(1.0, (self.p_i * decay_factor) + (WEIGHT_KEY * f_c) + (WEIGHT_AUD * g_a))
        
        self.orchestrator.evaluate_probability(self.p_i)
        return self.p_i
