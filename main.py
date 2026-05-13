# -----------------------------------------------------------------------------
# PERIDOT CLIENT | Main Entry Point
# Copyright (C) 2026 uncoalesced
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import sys
import os
import time
import requests
from pathlib import Path

# CRITICAL FIX: Force Python to recognize the current directory as the root path.
# This completely eliminates "No module named X" errors during subprocess launches.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- INTERNAL MODULES ---
try:
    from core_system.audit import ghost
    from core import PeridotCore
    from ui import PeridotUI
    from config import SERVER_HOST, SERVER_PORT
except ImportError as e:
    print(f"\n[FATAL] System Integrity Failure: Could not import core modules.")
    print(f"Error Details: {e}")
    print("Ensure 'core.py' and 'ui.py' are correctly updated.")
    sys.exit(1)

# --- CONFIGURATION ---
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

def check_server_status():
    """Checks if the Neural Engine (server.py) is online using the health endpoint."""
    try:
        r = requests.get(f"{SERVER_URL}/health", timeout=1)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False

def main():
    ghost.info("CLIENT | Initializing Peridot Sovereign Kernel Client...")

    # 1. Server Handshake
    if check_server_status():
        ghost.info("CLIENT | Neural Link Established [OK]")
    else:
        ghost.info("CLIENT | Neural Link Status: [WAITING] (Engine may still be loading)")

    try:
        # 2. Initialize Core Logic
        core = PeridotCore()

        # 3. Initialize User Interface
        app = PeridotUI(core)

        # 4. Link UI back to Core
        core.ui = app

        # 5. Launch
        ghost.info("CLIENT | Handing control to User Interface...")
        app.run()

    except KeyboardInterrupt:
        ghost.info("CLIENT | Manual Interrupt Detected.")
        
    except Exception as e:
        ghost.error(f"CLIENT | CRITICAL FAILURE: {e}")
        time.sleep(3)
        sys.exit(1)
        
    finally:
        # 6. Cleanup on Exit
        ghost.info("CLIENT | System Shutdown.")
        sys.exit(0)

if __name__ == "__main__":
    main()