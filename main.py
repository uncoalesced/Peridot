# -----------------------------------------------------------------------------
# PERIDOT CLIENT | Main Entry Point (Synchronized Ignition)
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import sys
import os
import time
import requests
from pathlib import Path

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

def wait_for_neural_engine(max_retries=45, delay=1.0):
    """
    Actively polls the FSM Kernel. 
    Locks the frontend boot sequence until the backend LLM is fully allocated in VRAM.
    """
    ghost.info("CLIENT | Scanning for Neural Engine heartbeat...")
    
    for i in range(max_retries):
        try:
            r = requests.get(f"{SERVER_URL}/health", timeout=2)
            if r.status_code == 200:
                ghost.info(f"CLIENT | Neural Link Established [Latency: {r.elapsed.total_seconds()*1000:.0f}ms]")
                return True
            elif r.status_code == 503:
                # The Flask server is up, but the Llama model is still loading into the GPU
                ghost.info(f"CLIENT | Engine Booting... Allocating Tensor Layers ({i+1}/{max_retries})")
        except requests.exceptions.ConnectionError:
            # The Flask server hasn't even bound to the port yet
            ghost.info(f"CLIENT | Awaiting Server Socket... ({i+1}/{max_retries})")
        except requests.exceptions.RequestException as e:
            ghost.warning(f"CLIENT | Handshake interrupted: {e}")
            
        time.sleep(delay)
        
    return False

def main():
    ghost.info("CLIENT | Initializing Peridot Sovereign Kernel Client...")

    # 1. Synchronized Server Handshake
    engine_online = wait_for_neural_engine()
    
    if not engine_online:
        ghost.error("CLIENT | FATAL: Neural Engine failed to boot within timeout limit. Aborting UI launch.")
        sys.exit(1)

    try:
        # 2. Load Core Logic
        core = PeridotCore()

        # 3. Load User Interface
        app = PeridotUI(core)

        # 4. Link User Interface back to Core
        core.ui = app

        # 5. Launch
        ghost.info("CLIENT | Hardware verified. Handing control to User Interface...")
        app.run()

    except KeyboardInterrupt:
        ghost.info("CLIENT | Manual Interruption Detected.")
        
    except Exception as e:
        ghost.error(f"CLIENT | CRITICAL FAILURE: {e}")
        import traceback
        traceback.print_exc()
        time.sleep(3)
        sys.exit(1)
        
    finally:
        # 6. Cleanup on Exit
        ghost.info("CLIENT | System Shutdown Successful.")
        sys.exit(0)

if __name__ == "__main__":
    main()