# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.5 | NEURAL ENGINE
# Copyright (C) 2026 uncoalesced
# 
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import sys
import logging
import threading
import time
import os
import json
import websocket
import pynvml
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
from llama_cpp import Llama
from dotenv import load_dotenv

load_dotenv()

# --- PERIDOT CONFIGURATION ---
from config import (
    MODEL_PATH, GPU_LAYERS, MAX_TOKENS, CONTEXT_LENGTH, 
    TEMPERATURE, TOP_P, REPEAT_PENALTY, SERVER_HOST, SERVER_PORT, API_KEY,
    RESEARCH_IDLE_THRESHOLD, THREADS, BATCH_SIZE
)

# --- DYNAMIC TRANSLATION LAYER ---
def get_model_format():
    model_name = MODEL_PATH.name.lower()
    if "llama" in model_name: return "llama3"
    elif "qwen" in model_name: return "chatml"
    else: return "chatml" 

# --- CONSTITUTION BOOTSTRAP ---
CONSTITUTION_PATH = Path("constitution.json")
CONSTITUTION = {}
if CONSTITUTION_PATH.exists():
    try:
        with open(CONSTITUTION_PATH, "r") as f:
            CONSTITUTION = json.load(f)
        print("[KERNEL] Sovereign Constitution Loaded.")
    except Exception as e:
        print(f"[FATAL] Constitution parsing failed: {e}")
        sys.exit(1)
else:
    print("[WARN] constitution.json not found. Operating without identity bounds.")

def build_system_prompt(context_str="", model_format="chatml"):
    p = CONSTITUTION.get("personality", {})
    rules = CONSTITUTION.get("hard_rules", [])
    anti_patterns = p.get("anti_patterns", [])

    if model_format == "llama3":
        sys_start = "<|start_header_id|>system<|end_header_id|>\n\n"
        sys_end = "<|eot_id|>\n"
        user_start = "<|start_header_id|>user<|end_header_id|>\n\n"
    else:
        sys_start = "<|im_start|>system\n"
        sys_end = "<|im_end|>\n"
        user_start = "<|im_start|>user\n"

    sys_prompt = sys_start
    sys_prompt += f"IDENTITY: {p.get('identity_enforcement', 'You are Peridot.')}\n"
    sys_prompt += f"TONE & VOICE: {p.get('tone', '')} {p.get('voice', '')}\n"
    sys_prompt += f"EXPLANATION STYLE: {p.get('explanation_style', '')}\n"
    sys_prompt += f"REFUSAL STYLE: {p.get('refusal_style', '')}\n\n"

    if rules:
        sys_prompt += "HARD RULES:\n- " + "\n- ".join(rules) + "\n\n"

    if anti_patterns:
        sys_prompt += "ANTI-PATTERNS (CRITICAL - DO NOT DO THESE):\n- " + "\n- ".join(anti_patterns) + "\n\n"

    if context_str:
        sys_prompt += (
            "RAG DIRECTIVE: You have access to local file context. "
            "CRITICAL: If the retrieved context is irrelevant to the user's prompt, "
            "IGNORE THE CONTEXT COMPLETELY. ONLY cite a source if it contains the explicit answer.\n\n"
            f"RETRIEVED CONTEXT:\n{context_str}\n"
        )

    sys_prompt += sys_end + user_start
    return sys_prompt

# --- RAG SUBSYSTEM & v1.5 CACHE IMPORTS ---
try:
    from core_system.audit import ghost
except ImportError:
    ghost = None

try:
    from core_system.telemetry import ledger
except ImportError:
    ledger = None

try:
    from core_system.memory.ephemeral_cache import EphemeralCache
    from core_system.memory.vault import PersistentVault
    from core_system.memory.embedder import embedder
    from core_system.rag_cache import AetherCache
    
    l1_cache = EphemeralCache()
    vault = PersistentVault()
    rag_cache = AetherCache(max_ram_items=50)
    print("[SYSTEM] RAG Subsystem Online.")
except ImportError as e:
    print(f"[WARN] RAG Subsystem offline. Operating in pure LLM mode. Error: {e}")
    l1_cache = None
    vault = None
    rag_cache = None
    embedder = None

# --- KERNEL FSM IMPORTS ---
from core_system.kernel import SovereignKernel, KernelState

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)
app = Flask(__name__)
CORS(app)

# --- RESOURCE ORCHESTRATION (FAH v8 WebSockets) ---
def get_vram_free() -> int:
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return info.free // 1024 // 1024
    except:
        return 0

def send_fah_command(cmd_state: str) -> bool:
    try:
        ws = websocket.create_connection("ws://127.0.0.1:7396/api/websocket", timeout=2.0)
        payload = json.dumps({"cmd": "state", "state": cmd_state})
        ws.send(payload)
        ws.close()
        return True
    except Exception:
        return False

# --- v1.5 KERNEL INTEGRATION (Delta Watchdog) ---
class PeridotProductionKernel(SovereignKernel):
    def _execute_vram_purge(self):
        print("[HARDWARE] Firing WebSocket SIGSTOP to FAH v8...")
        start_time = time.time()
        
        initial_info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
        initial_vram_mb = initial_info.used / (1024 ** 2)
        
        send_fah_command("pause")
        
        timeout = 20
        cleared = False
        reclaimed_mb = 0
        current_vram_mb = initial_vram_mb
        
        while timeout > 0:
            info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
            current_vram_mb = info.used / (1024 ** 2)
            reclaimed_mb = initial_vram_mb - current_vram_mb
            
            if reclaimed_mb > 500 or current_vram_mb < 7200:
                cleared = True
                break
                
            time.sleep(0.1)
            timeout -= 1
            
        latency_ms = (time.time() - start_time) * 1000
        
        if cleared:
            log_msg = f"Hardware yielded. Reclaimed: {reclaimed_mb:.0f}MB. Total Load: {current_vram_mb:.0f}MB. Latency: {latency_ms:.0f}ms."
            print(f">> {log_msg}")
            if ledger: ledger.log_handoff(latency_ms, success=True)
            self.request_state_change(KernelState.INFERENCE, log_msg)
        else:
            fail_msg = f"VRAM LOCKOUT: Reclaimed {reclaimed_mb:.0f}MB. Load stuck at {current_vram_mb:.0f}MB. Threshold: 7200MB."
            print(f"[KERNEL PANIC] {fail_msg}")
            if ledger: ledger.log_handoff(latency_ms, success=False)
            self.event_queue.put("FAH_HANG_DETECTED")

kernel = PeridotProductionKernel()

# --- STATE MANAGEMENT ---
llm = None
last_activity_time = time.time()
research_allowed = False

def idle_monitor():
    global last_activity_time
    while True:
        elapsed = time.time() - last_activity_time
        if elapsed > RESEARCH_IDLE_THRESHOLD and research_allowed:
            with kernel.state_lock:
                if kernel.state == KernelState.IDLE:
                    if send_fah_command("fold"):
                        kernel.state = KernelState.FAH_ACTIVE
                        print(f"\n[Peridot-Research] Idle threshold met. VRAM allocated to FAH. (Free: {get_vram_free()}MB)")
        time.sleep(1)

def boot_engine():
    global llm
    print(f"\n{'='*50}")
    print("   PERIDOT NEURAL ENGINE (v1.5 SOVEREIGN KERNEL)")
    print(f"{'='*50}")
    
    if not MODEL_PATH.exists():
        print(f"[FATAL] Model not found at {MODEL_PATH}")
        sys.exit(1)
        
    model_mode = get_model_format().upper()
    print(f"[SYSTEM] Engine architecture auto-detected: {model_mode}")

    kernel.start()
    send_fah_command("pause")

    try:
        llm = Llama(
            model_path=str(MODEL_PATH),
            n_ctx=CONTEXT_LENGTH,            
            n_threads=THREADS,          
            n_gpu_layers=GPU_LAYERS,      
            n_batch=BATCH_SIZE,          
            flash_attn=True,      
            verbose=False,       
        )
        print(f">> [SUCCESS] Peridot Brain Online. (Free VRAM: {get_vram_free()}MB)")
        threading.Thread(target=idle_monitor, daemon=True).start()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        sys.exit(1)

# --- SECURITY ---
def require_auth(f):
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or auth_header != f"Bearer {API_KEY}":
            return jsonify({"error": "Unauthorized. Invalid or missing API Key."}), 403
        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated

# --- API ENDPOINTS ---
@app.route('/health', methods=['GET'])
def health_check():
    if llm is not None:
        return jsonify({"status": "online"}), 200
    return jsonify({"status": "booting"}), 503

@app.route("/ask", methods=["POST"])
@require_auth
def ask():
    global last_activity_time
    last_activity_time = time.time()

    data = request.json
    user_query = data.get("query", "")
    full_prompt = data.get("prompt", "")
    
    if not user_query or not full_prompt:
        user_query = data.get("command", "")
        full_prompt = user_query
        
    if not user_query:
        return jsonify({"response": "Empty prompt received."}), 400

    print(f"\n[API] Received payload. Requesting hardware clearance...")
    kernel.event_queue.put("PROMPT_RECEIVED")
    
    timeout = 100
    while kernel.state != KernelState.INFERENCE:
        if kernel.state == KernelState.PANIC:
            return jsonify({"error": "KERNEL PANIC: Hardware failed to yield."}), 503
        time.sleep(0.1)
        timeout -= 1
        if timeout <= 0:
            kernel.request_state_change(KernelState.PANIC, "FAH Timeout")
            return jsonify({"error": "KERNEL TIMEOUT: Hardware clearance not granted."}), 504

    # --- ROUTING LOGIC ---
    try:
        if l1_cache is not None:
            if ghost:
                try: ghost.info(f"VRAM_STATE | Action: ROUTING | Free: {get_vram_free()}MB")
                except: pass
                
            cached_response = l1_cache.search(user_query)
            if cached_response:
                if ghost:
                    try: ghost.info("ROUTER | L1 Cache HIT. Bypassing GPU entirely.")
                    except: pass
                kernel.event_queue.put("INFERENCE_COMPLETE")
                return jsonify({"response": cached_response})

        context_str = ""
        # CRITICAL FIX: The backend now correctly routes vector searches through vault.py instead of the deleted vector_store.py
        if vault is not None and embedder is not None:
            if ghost:
                try: ghost.info("ROUTER | L1 MISS. Searching Semantic Memory...")
                except: pass
            
            # Convert user query to vector natively
            query_vector = embedder.embed_query(user_query)
            # Search PersistentVault
            relevant_context = vault.search(query_vector, top_k=3)
            
            if relevant_context:
                context_segments = []
                for idx, chunk in enumerate(relevant_context):
                    source_id = f"Vault_Chunk_{idx}"
                    context_segments.append(f"[SOURCE: {source_id}]: {chunk}")
                    if rag_cache is not None:
                        rag_cache.put(source_id, [1.0, 0.0])
                
                context_str = "\n---\n".join(context_segments)
                if ghost:
                    try: ghost.info(f"ROUTER | MEMORY HIT. Injected {len(relevant_context)} blocks.")
                    except: pass
            else:
                if ghost:
                    try: ghost.info("ROUTER | MEMORY MISS. Proceeding raw.")
                    except: pass

        # --- DYNAMIC INFERENCE ASSEMBLY ---
        model_format = get_model_format()
        
        if model_format == "llama3":
            assistant_start = "<|eot_id|>\n<|start_header_id|>assistant<|end_header_id|>\n"
            target_stops = ["<|eot_id|>", "<|start_header_id|>"]
        else:
            assistant_start = "<|im_end|>\n<|im_start|>assistant\n"
            target_stops = ["<|im_end|>", "<|im_start|>"]

        final_prompt = build_system_prompt(context_str, model_format) + full_prompt + assistant_start

        # --- LLM GENERATION ---
        start_time = time.time()
        output = llm(
            final_prompt, 
            max_tokens=MAX_TOKENS, 
            stop=target_stops, 
            temperature=TEMPERATURE,
            top_p=TOP_P,
            repeat_penalty=REPEAT_PENALTY,
            echo=False
        )
        elapsed_s = time.time() - start_time
        
        final_response = output["choices"][0]["text"].strip()
        
        tokens_generated = output.get("usage", {}).get("completion_tokens", len(final_response.split()) * 1.3)
        tps = tokens_generated / elapsed_s if elapsed_s > 0 else 0
        
        if ghost:
            try: ghost.info(f"INFERENCE  | Tokens: {int(tokens_generated)} | Time: {elapsed_s:.2f}s | Speed: {tps:.2f} t/s")
            except: pass
        
        if l1_cache is not None:
            l1_cache.add(user_query, final_response)
            
        if ledger: ledger.log_inference()
            
        return jsonify({"response": final_response})
        
    except Exception as e:
        error_msg = str(e)
        print(f"[FATAL] Internal Inference Error - {error_msg}")
        if ghost:
            try: ghost.error(f"CRITICAL   | Component: server_ask_route | Error: {error_msg}")
            except: pass
        return jsonify({"response": "An internal error occurred during inference. Please check the engine terminal."}), 500
        
    finally:
        print("[API] Payload delivered. Releasing hardware lock...")
        kernel.event_queue.put("INFERENCE_COMPLETE")

@app.route("/telemetry/stability", methods=["GET"])
@require_auth
def get_stability_metrics():
    if ledger:
        return jsonify(ledger.generate_report()), 200
    return jsonify({"error": "Telemetry Ledger Offline"}), 503

@app.route("/shutdown", methods=["POST"])
@require_auth
def shutdown():
    send_fah_command("pause")
    kernel.event_queue.put("SHUTDOWN")
    shutdown_func = request.environ.get('werkzeug.server.shutdown')
    if shutdown_func:
        shutdown_func()
    return jsonify({"message": "Shutting down Neural Engine..."}), 200

@app.route("/research/status", methods=["GET"])
@require_auth
def get_research_status():
    global research_allowed
    return jsonify({
        "enabled": research_allowed, 
        "active": kernel.state == KernelState.FAH_ACTIVE,
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
    send_fah_command("pause")
    if kernel.state == KernelState.FAH_ACTIVE:
        kernel.request_state_change(KernelState.IDLE, "Research disabled via UI.")
    return jsonify({"status": "disabled"})

if __name__ == "__main__":
    from flask import cli
    cli.show_server_banner = lambda *_: None
    boot_engine()
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, use_reloader=False)