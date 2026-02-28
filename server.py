# -----------------------------------------------------------------------------
# PERIDOT SERVER | Sovereign AI Kernel
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import sys
import logging
import threading
import time
import os
import json
import websocket  # Requires: pip install websocket-client
from flask import Flask, request, jsonify
from llama_cpp import Llama

# --- CONFIGURATION ---
MODEL_PATH = "models/brain.gguf"
CONTEXT_SIZE = 2048
N_GPU_LAYERS = 33  # RTX 5050 Engaged
N_THREADS = 8  # Ryzen 7 Optimization

# TEST SETTINGS
IDLE_THRESHOLD = 600

# --- STATE MANAGEMENT ---
last_activity_time = time.time()
research_active = False
research_allowed = True  # Master switch for UI control
research_lock = threading.Lock()

# Configure Logging
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)
app = Flask(__name__)

# --- RESOURCE ORCHESTRATION ---


def send_fah_command(cmd_state):
    """Fires WebSocket JSON commands directly into the FAH v8 backend."""
    try:
        # FAH v8 uses port 7396 with WebSockets
        ws = websocket.create_connection(
            "ws://127.0.0.1:7396/api/websocket", timeout=2.0
        )
        payload = json.dumps({"cmd": "state", "state": cmd_state})
        ws.send(payload)
        ws.close()
        return True
    except Exception:
        return False


def start_research():
    """Wakes FAH via WebSocket."""
    global research_active, last_activity_time

    with research_lock:
        if not research_active:
            # 'fold' is the v8 command to unpause
            if send_fah_command("fold"):
                research_active = True
                print(
                    "\n[Peridot-Research] - SUCCESS - Idle threshold reached. VRAM allocated to Research."
                )
            else:
                last_activity_time = time.time()


def kill_research():
    """Pauses FAH via WebSocket to purge VRAM."""
    global research_active
    with research_lock:
        if research_active:
            print(
                "\n[Peridot-Research] - INFO - Prompt Detected. Sending VRAM purge signal..."
            )
            send_fah_command("pause")
            research_active = False
            print("[Peridot-Research] - SUCCESS - VRAM Cleared for Inference.")


def idle_monitor():
    """Watches the clock in the background."""
    while True:
        elapsed = time.time() - last_activity_time
        if elapsed > IDLE_THRESHOLD and not research_active and research_allowed:
            start_research()
        time.sleep(1)


# --- MODEL LOADING ---

try:
    print(f"\n{'='*50}")
    print("   PERIDOT NEURAL ENGINE (VRAM STATE MACHINE)")
    print(f"{'='*50}")

    # Initialize state by pausing FAH in case it's currently running
    send_fah_command("pause")

    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=CONTEXT_SIZE,
        n_threads=N_THREADS,
        n_gpu_layers=N_GPU_LAYERS,
        verbose=False,
    )
    print(">> [SUCCESS] Peridot Brain Online.")
    threading.Thread(target=idle_monitor, daemon=True).start()

except Exception as e:
    print(f"\n[FATAL ERROR] {e}")
    sys.exit(1)

# --- API ENDPOINTS ---


@app.route("/ask", methods=["POST"])
def ask():
    global last_activity_time
    last_activity_time = time.time()

    kill_research()  # Ensure GPU is empty before inference starts

    try:
        data = request.json
        full_prompt = data.get("command", "")
        output = llm(full_prompt, max_tokens=1024, stop=["User:"], temperature=0.7)
        return jsonify({"response": output["choices"][0]["text"]})
    except Exception as e:
        # Print the full error to your local terminal for your own debugging
        print(f"LOG: Internal Inference Error - {e}")

        # Return a safe, generic message to the external user
        return (
            jsonify(
                {
                    "response": "An internal error occurred during inference. Please try again."
                }
            ),
            500,
        )


@app.route("/shutdown", methods=["POST"])
def shutdown():
    kill_research()
    os._exit(0)


# --- RESEARCH CONTROL ENDPOINTS ---


@app.route("/research/status", methods=["GET"])
def get_research_status():
    global research_active, research_allowed
    return jsonify({"enabled": research_allowed, "active": research_active})


@app.route("/research/enable", methods=["POST"])
def enable_research():
    global research_allowed
    research_allowed = True
    return jsonify({"status": "enabled"})


@app.route("/research/disable", methods=["POST"])
def disable_research():
    global research_allowed
    research_allowed = False
    kill_research()
    return jsonify({"status": "disabled"})


if __name__ == "__main__":
    from flask import cli

    cli.show_server_banner = lambda *_: None
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
