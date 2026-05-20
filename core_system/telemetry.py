# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.5 | STABILITY LEDGER
# Copyright (C) 2026 uncoalesced
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import json
import time
import threading
from pathlib import Path

class StabilityLedger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern: ensures only one ledger exists across all threads."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(StabilityLedger, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self, log_dir="logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_file = self.log_dir / "stability_metrics.json"
        self.boot_time = time.time()
        
        # The Baseline Infrastructure Metrics
        self.metrics = {
            "total_inferences": 0,
            "successful_handoffs": 0,
            "panics_triggered": 0,
            "total_handoff_latency_ms": 0.0,
            "average_handoff_latency_ms": 0.0,
            "vram_spikes_mitigated": 0
        }
        self._load_ledger()

    def _load_ledger(self):
        """Loads historical persistence to track lifetime kernel health."""
        if self.ledger_file.exists():
            try:
                with open(self.ledger_file, 'r') as f:
                    saved_metrics = json.load(f)
                    # Merge while ensuring new metric keys aren't lost
                    for k, v in saved_metrics.items():
                        if k in self.metrics:
                            self.metrics[k] = v
            except Exception as e:
                print(f"[LEDGER ERROR] Failed to read historical telemetry: {e}")

    def _save_ledger(self):
        """Atomic write to the SSD."""
        with self._lock:
            with open(self.ledger_file, 'w') as f:
                json.dump(self.metrics, f, indent=4)

    def log_handoff(self, latency_ms: float, success: bool):
        """Records the physical VRAM reclaim physics."""
        with self._lock:
            if success:
                self.metrics["successful_handoffs"] += 1
                self.metrics["total_handoff_latency_ms"] += latency_ms
                self.metrics["average_handoff_latency_ms"] = round(
                    self.metrics["total_handoff_latency_ms"] / self.metrics["successful_handoffs"], 2
                )
            else:
                self.metrics["panics_triggered"] += 1
        self._save_ledger()

    def log_inference(self):
        """Records successful payload execution."""
        with self._lock:
            self.metrics["total_inferences"] += 1
        self._save_ledger()

    def log_watchdog_mitigation(self):
        """Records when the FSM successfully blocked a phantom VRAM spike."""
        with self._lock:
            self.metrics["vram_spikes_mitigated"] += 1
        self._save_ledger()

    def generate_report(self):
        """Exports the SLA compliance dashboard data."""
        uptime_s = time.time() - self.boot_time
        total_attempts = self.metrics["successful_handoffs"] + self.metrics["panics_triggered"]
        reliability = 100.0 if total_attempts == 0 else (self.metrics["successful_handoffs"] / total_attempts) * 100

        return {
            "uptime_seconds": round(uptime_s, 2),
            "hardware_reliability_score": f"{reliability:.2f}%",
            "metrics": self.metrics
        }

# Global instance for the kernel to import
ledger = StabilityLedger()