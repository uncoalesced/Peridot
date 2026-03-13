# -----------------------------------------------------------------------------
# PERIDOT CLIENT | Main Entry Point
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import sys
import os

# CRITICAL FIX: Force Python to recognize the current directory as the root path.
# This completely eliminates "No module named X" errors during subprocess launches.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import time
import requests

# --- INTERNAL MODULES ---
try:
    from core import PeridotCore
    from ui import PeridotUI
    from config import SERVER_HOST, SERVER_PORT, LOG_PATH
except ImportError as e:
    print(f"\n[FATAL] System Integrity Failure: Could not import core modules.")
    print(f"Error Details: {e}")
    print("Ensure 'research.py', 'core.py', and 'ui.py' are in the root directory.")
    sys.exit(1)

# --- CONFIGURATION ---
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
LOG_FILE = LOG_PATH / "peridot.log"

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("Peridot.Client")

def check_server_status():
    """Checks if the Neural Engine (server.py) is online using the health endpoint."""
    try:
        r = requests.get(f"{SERVER_URL}/health", timeout=1)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False

def main():
    logger.info("Initializing Peridot Sovereign Kernel Client...")

    # 1. Server Handshake
    if check_server_status():
        logger.info("Neural Link Established [OK]")
    else:
        logger.info("Neural Link Status: [WAITING] (Engine may still be loading)")

    try:
        # 2. Initialize Core Logic
        core = PeridotCore()

        # 3. Initialize User Interface
        app = PeridotUI(core)

        # 4. Link UI back to Core
        core.ui = app

        # 5. Launch
        logger.info("Handing control to User Interface...")
        app.run()

    except KeyboardInterrupt:
        logger.info("Manual Interrupt Detected.")
        
    except Exception as e:
        logger.critical(f"CRITICAL FAILURE: {e}", exc_info=True)
        time.sleep(3)
        sys.exit(1)
        
    finally:
        # 6. Cleanup on Exit
        logger.info("System Shutdown.")
        sys.exit(0)

if __name__ == "__main__":
    main()