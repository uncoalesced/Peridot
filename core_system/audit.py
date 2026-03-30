# -----------------------------------------------------------------------------
# PERIDOT GHOST LOGGER | Silent Audit Subsystem
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

# Ensure the logs directory exists silently
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
GHOST_LOG_PATH = LOG_DIR / "ghost_audit.log"

def setup_ghost_logger():
    """Initializes a completely silent, file-only logger."""
    ghost = logging.getLogger("GhostLogger")
    ghost.setLevel(logging.INFO)
    
    # CRITICAL: Prevent logs from bubbling up to the terminal (stdout)
    ghost.propagate = False
    
    # Clear any existing handlers to prevent duplicate entries
    if ghost.hasHandlers():
        ghost.handlers.clear()
        
    # Rotating file handler: Caps at 1MB, keeps exactly 1 backup. No disk bloat.
    file_handler = RotatingFileHandler(
        GHOST_LOG_PATH, maxBytes=1024 * 1024, backupCount=1
    )
    
    # Clean, forensic formatting
    formatter = logging.Formatter(
        '%(asctime)s | [%(levelname)s] | %(message)s', 
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    ghost.addHandler(file_handler)
    return ghost

# Export the active instance
ghost_log = setup_ghost_logger()

# --- Usage Example (Do not run this block when imported) ---
if __name__ == "__main__":
    ghost_log.info("GhostLogger initialized. This will not appear in the terminal.")
    ghost_log.warning("Silent warning recorded.")