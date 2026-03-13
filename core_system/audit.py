"""
PERIDOT SOVEREIGN KERNEL | GHOST LOGGER
Module: core_system/audit.py
Description: Silent, non-blocking, asynchronous audit trail for security and state changes.
Zero console output. Zero performance impact.
"""

import json
import time
import threading
from pathlib import Path

# Adjust path dynamically to ensure it always hits the Peridot root
BASE_DIR = Path(__file__).parent.parent
LOG_PATH = BASE_DIR / "logs"
LOG_PATH.mkdir(exist_ok=True)

class GhostLogger:
    def __init__(self):
        self.audit_file = LOG_PATH / "ghost_audit.jsonl"
        self.lock = threading.Lock()
        
    def record(self, action: str, entity: str, meta: dict = None):
        """
        Silently writes an event to the audit file in the background.
        
        Args:
            action: The event type (e.g., 'SECURITY_BLOCK', 'VRAM_PURGE', 'LLM_QUERY')
            entity: What triggered it (e.g., 'User', 'WebSocket', 'System')
            meta: Dictionary of additional context.
        """
        def _write_silently():
            with self.lock:
                payload = {
                    "timestamp": time.time(),
                    "action": action,
                    "entity": entity,
                    "meta": meta or {}
                }
                try:
                    with open(self.audit_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(payload) + "\n")
                except Exception:
                    # Absolute silence. If file I/O fails, do not crash or spam the terminal.
                    pass 
        
        # Spawn a daemon thread to handle the I/O so the main OS loop never pauses
        threading.Thread(target=_write_silently, daemon=True).start()

# Global instance to be imported across the kernel
ghost = GhostLogger()