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
import pynvml
from flask import Flask, request, jsonify
from flask_cors import CORS
from llama_cpp import Llama

# --- PERIDOT CONFIGURATION ---
from config import (
    MODEL_PATH, GPU_LAYERS, MAX_TOKENS, CONTEXT_LENGTH, 
    TEMPERATURE, TOP_P, REPEAT_PENALTY, SERVER_HOST, SERVER_PORT, API_KEY,
    RESEARCH_IDLE_THRESHOLD
)

# Configure Logging
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)
app = Flask(__name__)
CORS(app)

# --- STATE MANAGEMENT ---
llm = None
last_activity_time = time.time()
research_active = False
research_allowed = False  # Default to False (Opt-In Security)
research_lock = threading.Lock()

# Initialize Hardware Monitoring
try:
    pynvml.nvmlInit()
except Exception as e:
    print(f"[WARN] Failed to initialize NVML (VRAM tracking disabled): {e}")

# --- SECURITY & AUTHENTICATION ---

def require_auth(f):
    """Decorator to enforce strict API Key authentication."""
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or auth_header != f"Bearer {API_KEY}":
            return jsonify({"error": "Unauthorized. Invalid or missing API Key."}), 403
        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated

# --- RESOURCE ORCHESTRATION (FAH v8 WebSockets) ---

def get_vram_free() -> int:
    """Returns free VRAM in MB directly from the NVIDIA driver."""
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return info.free // 1024 // 1024
    except:
        return 0

def send_fah_command(cmd_state: str) -> bool:
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
    except Exception as e:
        return False

def start_research():
    """Wakes FAH via WebSocket."""
    global research_active, last_activity_time
    with research_lock:
        if not research_active:
            if send_fah_command("fold"):
                research_active = True
                print(f"\n[Peridot-Research] - SUCCESS - Idle threshold reached. VRAM allocated to Research. (Free: {get_vram_free()}MB)")
            else:
                last_activity_time = time.time()

def kill_research():
    """Pauses FAH via WebSocket to purge VRAM."""
    global research_active
    with research_lock:
        if research_active:
            print("\n[Peridot-Research] - INFO - Prompt Detected. Sending WebSocket VRAM purge signal...")
            start_time = time.time()
            send_fah_command("pause")
            research_active = False
            elapsed_ms = (time.time() - start_time) * 1000
            print(f"[Peridot-Research] - SUCCESS - VRAM Cleared in {elapsed_ms:.2f}ms. (Free: {get_vram_free()}MB)")

def idle_monitor():
    """Watches the clock in the background."""
    global last_activity_time
    while True:
        elapsed = time.time() - last_activity_time
        if elapsed > RESEARCH_IDLE_THRESHOLD and not research_active and research_allowed:
            start_research()
        time.sleep(1)

def boot_engine():
    """Loads the Llama-3 model into VRAM."""
    global llm
    print(f"\n{'='*50}")
    print("   PERIDOT NEURAL ENGINE (VRAM STATE MACHINE)")
    print(f"{'='*50}")
    
    if not MODEL_PATH.exists():
        print(f"[FATAL] Model not found at {MODEL_PATH}")
        sys.exit(1)

    # Initialize state by pausing FAH in case it's currently running
    send_fah_command("pause")

    try:
        llm = Llama(
            model_path=str(MODEL_PATH),
            n_ctx=CONTEXT_LENGTH,
            n_threads=8, # Optimized for 8-core CPUs
            n_gpu_layers=GPU_LAYERS,
            verbose=False,
        )
        print(f">> [SUCCESS] Peridot Brain Online. (Free VRAM: {get_vram_free()}MB)")
        threading.Thread(target=idle_monitor, daemon=True).start()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        sys.exit(1)

# --- API ENDPOINTS ---

@app.route('/health', methods=['GET'])
def health_check():
    """Unauthenticated endpoint for launcher.py to verify server status."""
    if llm is not None:
        return jsonify({"status": "online"}), 200
    return jsonify({"status": "booting"}), 503

@app.route("/ask", methods=["POST"])
@require_auth
def ask():
    global last_activity_time
    last_activity_time = time.time()

    # Ensure GPU is empty before inference starts
    kill_research() 

    try:
        data = request.json
        full_prompt = data.get("command", "")
        
        output = llm(
            full_prompt, 
            max_tokens=MAX_TOKENS, 
            stop=["User:", "<|eot_id|>"], 
            temperature=TEMPERATURE,
            top_p=TOP_P,
            repeat_penalty=REPEAT_PENALTY
        )
        return jsonify({"response": output["choices"][0]["text"]})
    except Exception as e:
        print(f"LOG: Internal Inference Error - {e}")
        return jsonify({"response": "An internal error occurred during inference. Please try again."}), 500

@app.route("/shutdown", methods=["POST"])
@require_auth
def shutdown():
    kill_research()
    shutdown_func = request.environ.get('werkzeug.server.shutdown')
    if shutdown_func:
        shutdown_func()
    return jsonify({"message": "Shutting down Neural Engine..."}), 200

# --- RESEARCH CONTROL ENDPOINTS ---

@app.route("/research/status", methods=["GET"])
@require_auth
def get_research_status():
    global research_active, research_allowed
    return jsonify({
        "enabled": research_allowed, 
        "active": research_active,
        "vram_free": get_vram_free()
    })

@app.route("/research/enable", methods=["POST"])
@require_auth
def enable_research():
    global research_allowed
    research_allowed = True
    return jsonify({"status": "enabled"})

@app.route("/research/disable", methods=["POST"])
@require_auth
def disable_research():
    global research_allowed
    research_allowed = False
    kill_research()
    return jsonify({"status": "disabled"})

if __name__ == "__main__":
    from flask import cli
    cli.show_server_banner = lambda *_: None
    boot_engine()
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, use_reloader=False)