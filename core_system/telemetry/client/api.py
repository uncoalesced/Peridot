import requests
from core_system.telemetry.config.settings import SERVER_HOST, SERVER_PORT
from core_system.audit import ghost

class LlamaClient:
    def __init__(self):
        self.base_url = f"http://{SERVER_HOST}:{SERVER_PORT}"

    def restore_slot(self, slot_id=0) -> bool:
        try:
            r = requests.post(f"{self.base_url}/slots/{slot_id}/restore", json={}, timeout=5.0)
            if r.status_code == 200:
                ghost.info(f"[ZAT-SCS | CLIENT] Speculative restore executed for slot {slot_id}.")
                return True
            return False
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            ghost.error("[ZAT-SCS | CLIENT | OFFLINE] local llama-server is unreachable. Speculative restore bypassed.")
            return False
