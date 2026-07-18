import time
import numpy as np
from pynput import keyboard

class KeyboardTracker:
    def __init__(self):
        self.keystroke_timestamps = []

    def start(self):
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.start()

    def _on_press(self, key):
        self.keystroke_timestamps.append(time.time())
        if len(self.keystroke_timestamps) > 10:
            self.keystroke_timestamps.pop(0)

    def calculate_acceleration(self) -> float:
        if len(self.keystroke_timestamps) < 2:
            return 0.0
        intervals = np.diff(self.keystroke_timestamps)
        avg_interval = np.mean(intervals) if len(intervals) > 0 else 1.0
        return min(1.0, 1.0 / (avg_interval + 1e-6))
