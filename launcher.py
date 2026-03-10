import subprocess
import time
import sys
import os
import psutil
import requests
import secrets

# SECURITY: Generate ephemeral API key in RAM before anything else loads.
# This prevents CWE-312 Clear-Text Storage vulnerabilities on the disk.
os.environ["PERIDOT_AUTH_TOKEN"] = secrets.token_hex(16)

from config import SERVER_HOST, SERVER_PORT, LOG_PATH

def kill_proc_tree(pid, including_parent=True):
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
    print(">> Initializing Peridot Sovereign Kernel...")

    # Pass the RAM-injected environment variables to our child processes
    custom_env = os.environ.copy()

    print(">> [1/2] Igniting Neural Engine (server.py)...")
    server_cmd = [sys.executable, "server.py"]
    
    try:
        server_log = open(LOG_PATH / "server.log", "a")
        server_process = subprocess.Popen(
            server_cmd, cwd=os.getcwd(), stdout=server_log, stderr=server_log, env=custom_env
        )
    except Exception as e:
        print(f"FATAL: Inference server failed to start: {e}")
        sys.exit(1)

    print(">> [WAIT] Verifying VRAM and API health...")
    health_url = f"http://{SERVER_HOST}:{SERVER_PORT}/health"
    
    server_ready = False
    for _ in range(30):
        try:
            r = requests.get(health_url, timeout=1)
            if r.status_code == 200:
                server_ready = True
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)

    if not server_ready:
        print("ERROR: Server failed to start or timed out.")
        kill_proc_tree(server_process.pid)
        sys.exit(1)

    print(">> [2/2] Launching Interface (main.py)...")
    try:
        # Launch UI with the secure RAM token
        subprocess.run([sys.executable, "main.py"], check=True, env=custom_env)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error running client: {e}")
    finally:
        print(">> Shutting down Systems...")
        kill_proc_tree(server_process.pid)
        
        # Clean up any leftover token files from the old architecture
        token_path = LOG_PATH / "auth.token"
        if token_path.exists():
            try:
                token_path.unlink()
            except Exception as e:
                pass
                
        print(">> Neural Link Severed. Goodbye.")

if __name__ == "__main__":
    main()