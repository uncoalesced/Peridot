# -----------------------------------------------------------------------------
# PERIDOT GHOST LOGGER | High-Performance Silent Audit Subsystem
# Copyright (C) 2026 uncoalesced
#
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import os
import threading
from datetime import datetime
from pathlib import Path

# Try to get centralized log path from config, fallback to local 'logs'
try:
    from config import LOG_PATH
except ImportError:
    LOG_PATH = Path("logs")

class GhostLogger:
    """
    PERIDOT GHOST LOGGER
    Ultra-lightweight, zero-terminal-output, thread-safe logger.
    Functions independently of the Python 'logging' module to ensure 
    zero interference with other system logs and maximum performance.
    """
    def __init__(self, log_name="ghost_audit.log", max_bytes=1024*1024):
        self.log_path = LOG_PATH / log_name
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        self.propagate = False # Mock attribute for compatibility
        
        # Ensure log directory exists silently
        try:
            self.log_path.parent.mkdir(exist_ok=True)
        except Exception:
            pass

    def _rotate_if_needed(self):
        """Maintains a single .old backup to prevent disk bloat."""
        if self.log_path.exists() and self.log_path.stat().st_size > self.max_bytes:
            backup = self.log_path.with_suffix(".old")
            try:
                if backup.exists():
                    os.remove(backup)
                os.rename(self.log_path, backup)
            except Exception:
                pass 

    def _write(self, level, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"{timestamp} | [{level}] | {message}\n"
        with self._lock:
            try:
                self._rotate_if_needed()
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(entry)
            except Exception:
                # Ghost logger must never crash the main application
                pass

    def info(self, message): self._write("INFO", message)
    def warning(self, message): self._write("WARNING", message)
    def error(self, message): self._write("ERROR", message)
    def critical(self, message): self._write("CRITICAL", message)
    def debug(self, message): self._write("DEBUG", message)
    def record(self, message): self._write("AUDIT", message)
    
    # Compatibility methods for logging.Logger surface area
    def setLevel(self, level): pass
    def addHandler(self, handler): pass
    def hasHandlers(self): return True
    def clearHandlers(self): pass

# Global singleton instance
ghost = GhostLogger()

def setup_ghost_logger():
    """Returns the global GhostLogger instance."""
    return ghost

# Exported aliases
ghost_log = ghost

if __name__ == "__main__":
    # Internal validation
    ghost.info("GhostLogger: System check.")
    ghost.record("GhostLogger: Audit protocol initialized.")
