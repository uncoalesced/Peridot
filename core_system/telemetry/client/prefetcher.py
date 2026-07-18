import threading
from core_system.telemetry.client.api import LlamaClient

class ContextStreamingEngine:
    def __init__(self):
        self.client = LlamaClient()

    def speculative_restore_async(self):
        t = threading.Thread(target=self._run_restore, daemon=True)
        t.start()

    def _run_restore(self):
        self.client.restore_slot(slot_id=0)
