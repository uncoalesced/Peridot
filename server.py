# Engineered by uncoalesced
# -----------------------------------------------------------------------------
# PERIDOT SERVER | Sovereign AI Kernel
# -----------------------------------------------------------------------------

import sys
import logging
import threading
import time
import os
import json
import websocket
import pynvml
from flask import Flask, request, jsonify
from flask_cors import CORS
from llama_cpp import Llama
from dotenv import load_dotenv

# CRITICAL FIX: Load the .env file BEFORE importing config
load_dotenv()

# --- RAG SUBSYSTEM IMPORTS ---
try:
    from core_system.audit import ghost
    from core_system.memory.ephemeral_cache import EphemeralCache
    from core_system.ingestion.vector_store import vector_store  # New Aether-Route CPU Memory
    
    l1_cache = EphemeralCache()
except ImportError as e:
    print(f"[WARN] RAG Subsystem offline. Operating in pure LLM mode. Error: {e}")
    l1_cache = None
    vector_store = None

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
            
            try:
                ghost.info(f"VRAM_STATE | Action: PURGE | Free: {get_vram_free()}MB | Latency: {elapsed_ms:.2f}ms")
            except Exception:
                pass

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

    send_fah_command("pause")

    try:
        llm = Llama(
            model_path=str(MODEL_PATH),
            n_ctx=8192,            
            n_threads=8,          
            n_gpu_layers=100,      
            n_batch=1024,          
            flash_attn=True,      
            verbose=True,         
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
        user_query = data.get("query", "")
        full_prompt = data.get("prompt", "")
        
        # Fallback for legacy commands if missing split payload
        if not user_query or not full_prompt:
            user_query = data.get("command", "")
            full_prompt = user_query
            
        if not user_query:
            return jsonify({"response": "Empty prompt received."}), 400

        # --- ROUTING LOGIC ---
        if l1_cache is not None:
            try:
                ghost.info(f"VRAM_STATE | Action: ROUTING | Free: {get_vram_free()}MB | Latency: 0.00ms")
            except Exception:
                pass
                
            # STEP 1: Check L1 RAM Cache
            cached_response = l1_cache.search(user_query)
            if cached_response:
                try:
                    ghost.info("ROUTER | L1 Cache HIT. Bypassing GPU entirely.")
                except Exception:
                    pass
                return jsonify({"response": cached_response})

        # STEP 2: Check Semantic Memory (Vector Store)
        if vector_store is not None:
            try:
                ghost.info("ROUTER | L1 MISS. Searching Semantic Memory...")
            except Exception:
                pass
            
            relevant_context = vector_store.search(user_query, top_k=2)
            
            if relevant_context:
                context_str = "\n".join([res['content'] for res in relevant_context])
                system_instruction = (
                    "<|start_header_id|>system<|end_header_id|>\n\n"
                    "You are the Peridot Sovereign Kernel. Use the following retrieved context "
                    "to answer the user query. If the context is irrelevant to the query, ignore it.\n\n"
                    f"RETRIEVED CONTEXT:\n{context_str}<|eot_id|>\n"
                )
                final_prompt = system_instruction + full_prompt
                
                try:
                    ghost.info(f"ROUTER | MEMORY HIT. Injected {len(relevant_context)} blocks into final prompt.")
                except Exception:
                    pass
            else:
                final_prompt = full_prompt
                try:
                    ghost.info("ROUTER | MEMORY MISS. No relevant documents found. Proceeding raw.")
                except Exception:
                    pass
        else:
            final_prompt = full_prompt

        # STEP 3: Final LLM Generation (Wakes up the GPU)
        start_time = time.time()
        output = llm(
            final_prompt, 
            max_tokens=MAX_TOKENS, 
            stop=["<|eot_id|>", "<|start_header_id|>", "assistant\n", "User:"], 
            temperature=TEMPERATURE,
            top_p=TOP_P,
            repeat_penalty=REPEAT_PENALTY,
            echo=False
        )
        elapsed_s = time.time() - start_time
        
        final_response = output["choices"][0]["text"].strip()
        
        # Extract metrics for the GhostLogger
        tokens_generated = output.get("usage", {}).get("completion_tokens", len(final_response.split()) * 1.3)
        tps = tokens_generated / elapsed_s if elapsed_s > 0 else 0
        
        try:
            ghost.info(f"INFERENCE  | Tokens: {int(tokens_generated)} | Time: {elapsed_s:.2f}s | Speed: {tps:.2f} t/s")
        except Exception:
            pass
        
        # STEP 4: Store new result in L1 Cache
        if l1_cache is not None:
            l1_cache.add(user_query, final_response)
            
        return jsonify({"response": final_response})
        
    except Exception as e:
        error_msg = str(e)
        print(f"LOG: Internal Inference Error - {error_msg}")
        try:
            ghost.error(f"CRITICAL   | Component: server_ask_route | Error: {error_msg}")
        except Exception:
            pass
        return jsonify({"response": "An internal error occurred during inference. Please check the engine terminal."}), 500

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