# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.5 | NEURAL ENGINE (FSM)
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

load_dotenv()

# --- RAG SUBSYSTEM & v1.5 CACHE IMPORTS ---
try:
    from core_system.audit import ghost
    from core_system.memory.ephemeral_cache import EphemeralCache
    from core_system.ingestion.vector_store import vector_store
    from core_system.rag_cache import AetherCache # v1.5 LRU Cache
    
    l1_cache = EphemeralCache()
    rag_cache = AetherCache(max_ram_items=50) # System RAM limit enforcement
except ImportError as e:
    print(f"[WARN] RAG Subsystem offline. Operating in pure LLM mode. Error: {e}")
    l1_cache = None
    vector_store = None
    rag_cache = None

# --- KERNEL FSM IMPORTS ---
from core_system.kernel import SovereignKernel, KernelState

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

# --- v1.5 KERNEL INTEGRATION (Binding Network to FSM) ---
class PeridotProductionKernel(SovereignKernel):
    def _execute_vram_purge(self):
        """Overrides FSM with actual hardware WebSockets and dynamic VRAM limits."""
        print("[HARDWARE] Firing WebSocket SIGSTOP to FAH v8...")
        send_fah_command("pause")
        
        timeout = 20  # 2.0 seconds maximum wait time
        cleared = False
        
        while timeout > 0:
            info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
            used_vram_mb = info.used / (1024 ** 2)
            
            # 8GB RTX 5050 ceiling is ~8000MB. 
            # If we are below 7500MB, we have enough headroom for the Llama 3 attention window.
            if used_vram_mb < 7500:
                cleared = True
                break
                
            time.sleep(0.1)
            timeout -= 1
            
        if cleared:
            self.request_state_change(KernelState.INFERENCE, f"Hardware cleared. Load: {used_vram_mb:.0f} MB.")
        else:
            self.event_queue.put("FAH_HANG_DETECTED")

kernel = PeridotProductionKernel()

# --- STATE MANAGEMENT ---
llm = None
last_activity_time = time.time()
research_allowed = False  # Default to False (Opt-In Security)

def idle_monitor():
    """v1.5 Idle Monitor linked to the FSM."""
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
    """Loads the Llama-3 model into VRAM and ignites FSM."""
    global llm
    print(f"\n{'='*50}")
    print("   PERIDOT NEURAL ENGINE (v1.5 SOVEREIGN KERNEL)")
    print(f"{'='*50}")
    
    if not MODEL_PATH.exists():
        print(f"[FATAL] Model not found at {MODEL_PATH}")
        sys.exit(1)

    # Ignite the v1.5 Central Nervous System
    kernel.start()

    # Force hardware clear for LLM instantiation
    send_fah_command("pause")

    try:
        llm = Llama(
            model_path=str(MODEL_PATH),
            n_ctx=8192,            
            n_threads=8,          
            n_gpu_layers=100,      
            n_batch=1024,          
            flash_attn=True,      
            verbose=False, # Suppress llama.cpp verbosity for cleaner kernel logs         
        )
        print(f">> [SUCCESS] Peridot Brain Online. (Free VRAM: {get_vram_free()}MB)")
        threading.Thread(target=idle_monitor, daemon=True).start()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        sys.exit(1)

# --- SECURITY & AUTHENTICATION ---
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

    # --- THE v1.5 FSM HARDWARE LOCK ---
    print(f"\n[API] Received payload. Requesting hardware clearance...")
    kernel.event_queue.put("PROMPT_RECEIVED")
    
    timeout = 100 # 10 seconds max wait for FAH to yield its memory
    while kernel.state != KernelState.INFERENCE:
        if kernel.state == KernelState.PANIC:
            return jsonify({"error": "KERNEL PANIC: Hardware failed to yield. Inference aborted."}), 503
        time.sleep(0.1)
        timeout -= 1
        if timeout <= 0:
            kernel.request_state_change(KernelState.PANIC, "FAH Timeout")
            return jsonify({"error": "KERNEL TIMEOUT: Hardware clearance not granted."}), 504

    # --- ROUTING LOGIC ---
    try:
        if l1_cache is not None:
            try: ghost.info(f"VRAM_STATE | Action: ROUTING | Free: {get_vram_free()}MB")
            except: pass
                
            cached_response = l1_cache.search(user_query)
            if cached_response:
                try: ghost.info("ROUTER | L1 Cache HIT. Bypassing GPU entirely.")
                except: pass
                return jsonify({"response": cached_response})

        if vector_store is not None:
            try: ghost.info("ROUTER | L1 MISS. Searching Semantic Memory...")
            except: pass
            
            relevant_context = vector_store.search(user_query, top_k=3)
            
            if relevant_context:
                context_segments = []
                for res in relevant_context:
                    source_id = res.get('source', 'Unknown')
                    context_segments.append(f"[SOURCE: {source_id}]: {res['content']}")
                    
                    # v1.5 LRU Cache Integration: Push accessed chunks into System RAM cache
                    if rag_cache is not None:
                        rag_cache.put(source_id, [1.0, 0.0]) # Tracks active state for SSD eviction
                
                context_str = "\n---\n".join(context_segments)
                
                system_instruction = (
                    "<|start_header_id|>system<|end_header_id|>\n\n"
                    "You are the Peridot Sovereign Kernel. You have access to the user's private documents. "
                    "Use the provided context to answer the query. ALWAYS cite the specific source filename "
                    "in your response if you use information from it. If the context is irrelevant, answer normally.\n\n"
                    f"RETRIEVED CONTEXT:\n{context_str}<|eot_id|>\n"
                )
                final_prompt = system_instruction + full_prompt
                try: ghost.info(f"ROUTER | MEMORY HIT. Injected {len(relevant_context)} blocks with citations.")
                except: pass
            else:
                final_prompt = full_prompt
                try: ghost.info("ROUTER | MEMORY MISS. Proceeding raw.")
                except: pass
        else:
            final_prompt = full_prompt

        # --- LLM GENERATION ---
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
        
        tokens_generated = output.get("usage", {}).get("completion_tokens", len(final_response.split()) * 1.3)
        tps = tokens_generated / elapsed_s if elapsed_s > 0 else 0
        
        try: ghost.info(f"INFERENCE  | Tokens: {int(tokens_generated)} | Time: {elapsed_s:.2f}s | Speed: {tps:.2f} t/s")
        except: pass
        
        if l1_cache is not None:
            l1_cache.add(user_query, final_response)
            
        return jsonify({"response": final_response})
        
    except Exception as e:
        error_msg = str(e)
        print(f"[FATAL] Internal Inference Error - {error_msg}")
        try: ghost.error(f"CRITICAL   | Component: server_ask_route | Error: {error_msg}")
        except: pass
        return jsonify({"response": "An internal error occurred during inference. Please check the engine terminal."}), 500
        
    finally:
        # --- FSM UNLOCK (MANDATORY) ---
        print("[API] Payload delivered. Releasing hardware lock...")
        kernel.event_queue.put("INFERENCE_COMPLETE")

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