# -----------------------------------------------------------------------------
# PERIDOT CLIENT | Main Entry Point
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import logging
import sys
import os
import urllib.request
import urllib.error
import time

# --- INTERNAL MODULES ---
# We wrap this in a try-block to catch if dependencies are missing (like torch)
try:
    from core import PeridotCore
    from ui import PeridotUI
except ImportError as e:
    print(f"[FATAL] System Integrity Failure: Could not import core modules.")
    print(f"Make sure you have activated the virtual environment (venv).")
    print(f"Error Details: {e}")
    sys.exit(1)

# --- CONFIGURATION ---
SERVER_URL = "http://127.0.0.1:5000"
LOG_FILE = "logs/peridot.log"

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),  # Fix: UTF-8 for Windows
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("SYSTEM")


def check_server_status():
    """Checks if the Brain (server.py) is online using standard libraries."""
    try:
        # Replaced 'requests' with 'urllib' to remove external dependency
        with urllib.request.urlopen(SERVER_URL, timeout=0.5) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, ConnectionRefusedError):
        return False
    except Exception:
        return False


def main():
    logger.info("Initializing Peridot Sovereign Kernel...")

    # 1. Server Handshake
    if check_server_status():
        logger.info("Neural Link Established [OK]")
    else:
        logger.info("Neural Link Status: [WAITING] (Engine may still be loading)")

    try:
        # 2. Initialize Core Logic
        # This loads memory, ethics, research module, and command router
        core = PeridotCore()

        # 3. Initialize User Interface
        # We pass the core to the UI so buttons can trigger logic
        app = PeridotUI(core)

        # 4. Link UI back to Core
        # This allows Core to print to the screen (e.g., "Research Started")
        core.ui = app

        # 5. Launch
        logger.info("Handing control to User Interface...")
        app.run()

    except KeyboardInterrupt:
        logger.info("Manual Interrupt Detected.")

    except Exception as e:
        logger.critical(f"CRITICAL FAILURE: {e}", exc_info=True)
        # Keep window open briefly if it crashed immediately so user can see error
        time.sleep(3)
        sys.exit(1)

    finally:
        # 6. Cleanup on Exit
        logger.info("System Shutdown.")
        sys.exit(0)


if __name__ == "__main__":
    main()
