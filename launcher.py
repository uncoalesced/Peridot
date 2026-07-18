#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.5.3 | IGNITION LAUNCHER
# Copyright (C) 2026 uncoalesced
# 
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import subprocess
import time
import sys
import os
import psutil
import requests
from dotenv import load_dotenv

# 1. ENVIRONMENT BOOTSTRAP
load_dotenv()

from config import SERVER_HOST, SERVER_PORT, LOG_PATH

def kill_proc_tree(pid, including_parent=True):
    """Sovereign protocol to forcibly terminate all child threads."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.kill()
        if including_parent:
            parent.kill()
    except psutil.NoSuchProcess:
        pass

def main():
    print("==================================================")
    print("  PERIDOT SOVEREIGN KERNEL v1.5.3 | INITIATING BOOT ")
    print("==================================================")

    custom_env = os.environ.copy()

    print(">> [1/2] Igniting Neural Engine (server.py)...")
    server_cmd = [sys.executable, "server.py"]
    
    try:
        LOG_PATH.mkdir(parents=True, exist_ok=True)
        server_log_path = LOG_PATH / "server.log"
        
        server_log = open(server_log_path, "w") 
        server_process = subprocess.Popen(
            server_cmd, cwd=os.getcwd(), stdout=server_log, stderr=subprocess.STDOUT, env=custom_env
        )
    except Exception as e:
        print(f"[FATAL] Inference server failed to start: {e}")
        sys.exit(1)

    print(">> [WAIT] Allocating VRAM and verifying API health...")
    health_url = f"http://{SERVER_HOST}:{SERVER_PORT}/health"
    
    server_ready = False
    
    for _ in range(120):
        if server_process.poll() is not None:
            print("\n[SYSTEM ERROR] Neural Engine crashed during boot sequence.")
            break

        try:
            r = requests.get(health_url, timeout=1)
            if r.status_code == 200:
                server_ready = True
                break
        except requests.exceptions.RequestException:
            pass
        
        time.sleep(1)
        sys.stdout.write(".")
        sys.stdout.flush()

    print("")

    if not server_ready:
        print("[ERROR] Engine failed to establish Neural Link.")
        try:
            with open(server_log_path, "r") as f:
                lines = f.readlines()
                print("\n--- CRASH LOG DUMP ---")
                print("".join(lines[-10:]))
                print("----------------------\n")
        except Exception:
            pass
        kill_proc_tree(server_process.pid)
        sys.exit(1)

    print(">> [2/2] Launching Interface (main.py)...")
    try:
        subprocess.run([sys.executable, "main.py"], check=True, env=custom_env)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[ERROR] Client interface execution failed: {e}")
    finally:
        print("\n>> Shutting down Kernel Subsystems...")
        kill_proc_tree(server_process.pid)
        
        token_path = LOG_PATH / "auth.token"
        if token_path.exists():
            try:
                token_path.unlink()
            except Exception:
                pass
                
        print(">> Neural Link Severed. Hardware released. Goodbye.")

if __name__ == "__main__":
    main()