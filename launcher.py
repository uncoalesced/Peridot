import subprocess
import time
import sys
import os
import psutil


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

    # 1. Start the Server (The Brain)
    print(">> [1/2] Igniting Neural Engine (server.py)...")
    # Using pythonw on Windows to hide the server console window, or normal python if debugging
    server_cmd = [sys.executable, "server.py"]

    server_process = subprocess.Popen(
        server_cmd, cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    # Wait for server to spin up (Llama takes a few seconds to load VRAM)
    print(">> [WAIT] Loading Model into VRAM...")
    time.sleep(4)

    # 2. Start the Client (The UI)
    print(">> [2/2] Launching Interface (main.py)...")
    try:
        subprocess.run([sys.executable, "main.py"], check=True)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error running client: {e}")
    finally:
        # 3. Cleanup on Exit
        print(">> Shutting down Systems...")
        kill_proc_tree(server_process.pid)
        print(">> Neural Link Severed. Goodbye.")


if __name__ == "__main__":
    main()
