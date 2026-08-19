# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.5.4 | NEURAL ENGINE & INGESTION CORE
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import sys
import gc
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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from llama_cpp import Llama
from dotenv import load_dotenv
import functools

load_dotenv()

# --- PERIDOT CONFIGURATION ---
from config import (
    MODEL_PATH, GPU_LAYERS, MAX_TOKENS, CONTEXT_LENGTH, 
    TEMPERATURE, TOP_P, REPEAT_PENALTY, SERVER_HOST, SERVER_PORT, API_KEY,
    RESEARCH_IDLE_THRESHOLD, THREADS, BATCH_SIZE, INPUT_PATH, PROCESSED_PATH
)

# --- SOVEREIGNTY GATE ---
# config has already force-set offline mode; fail loud rather than boot an
# engine that could reach the network. Model fetches run in an isolated child
# process (python -m core_system.model_fetch), never in this one.
from core_system.model_fetch import assert_main_process_offline
assert_main_process_offline()

# --- CENTRALIZED PROMPT ENGINE ---
from core_system.prompting.constitution import get_model_format
from core_system.prompting.builder import build_full_context

# --- RAG SUBSYSTEM AND v1.5.4 CACHE IMPORTS ---
try:
    from core_system.audit import ghost
except ImportError:
    ghost = None

try:
    from core_system.telemetry import ledger
except ImportError:
    ledger = None

try:
    from core_system.memory.chat_ledger import get_chat_ledger
    chat_ledger = get_chat_ledger()
except ImportError as e:
    if ghost:
        try:
            ghost.warning(f"Chat Ledger offline. Session persistence disabled. Error: {e}")
        except Exception:
            pass
    chat_ledger = None

try:
    from core_system.memory.ephemeral_cache import EphemeralCache
    from core_system.memory.vault import PersistentVault
    from core_system.memory.embedder import embedder
    from core_system.rag_cache import AetherCache
    
    l1_cache = EphemeralCache()
    vault = PersistentVault()
    rag_cache = AetherCache(max_ram_items=50)
    if ghost:
        try:
            ghost.info("RAG Subsystem Online.")
        except Exception:
            pass
except Exception as e:
    # Deliberately broad: the RAG stack fails at *runtime* as well as at import
    # (a missing offline embedding model raises OSError/RuntimeError, not
    # ImportError). Inference must survive a degraded RAG subsystem -- pure LLM
    # mode is the documented fallback, a dead server is not.
    if ghost:
        try:
            ghost.warning(f"RAG Subsystem offline. Operating in pure LLM mode. Error: {e}")
        except Exception:
            pass
    print(f">> [WARN] RAG Subsystem offline, continuing in pure LLM mode: {e}")
    l1_cache = None
    vault = None
    rag_cache = None
    embedder = None

# --- KERNEL FSM IMPORTS ---
from core_system.kernel import SovereignKernel, KernelState

# --- ZAT-SCS IMPORTS ---
try:
    from core_system.telemetry.processor import PhysicalTelemetryEngine
    from core_system.telemetry.orchestration.fsm import SovereignGPUOrchestrator
    from core_system.telemetry.client.api import LlamaClient
    zat_available = True
except ImportError as e:
    if ghost:
        try: ghost.warning(f"[ZAT-SCS] Failed to load modules: {e}")
        except Exception: pass
    zat_available = False

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)
app = Flask(__name__)
CORS(app, origins=["http://127.0.0.1:5000", "http://localhost:5000"])
limiter = Limiter(get_remote_address, app=app, default_limits=["60 per minute"])

@app.errorhandler(429)
def ratelimit_handler(e):
    if ghost:
        try:
            ghost.warning(f"Rate limit exceeded: {e.description}")
        except Exception:
            pass
    return jsonify({"error": "Too Many Requests", "message": "Rate limit exceeded"}), 429

# --- RESOURCE ORCHESTRATION (FAH v8) ---
def get_vram_free() -> int:
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return info.free // 1024 // 1024
    except Exception:
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

# --- v1.5.4 KERNEL INTEGRATION (Delta Watchdog) ---
class PeridotProductionKernel(SovereignKernel):
    def _execute_vram_purge(self):
        if self.state == KernelState.PANIC:
            return
            
        if ghost:
            try: ghost.info("HARDWARE | Firing WebSocket SIGSTOP to FAH v8...")
            except Exception as e: pass
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
            free_vram_mb = info.free / (1024 ** 2)
            
            if reclaimed_mb > 10 or free_vram_mb > 200:
                cleared = True
                break
                
            time.sleep(0.1)
            timeout -= 1
            
        latency_ms = (time.time() - start_time) * 1000
        
        if cleared:
            log_msg = f"Hardware yielded. Free VRAM: {free_vram_mb:.0f}MB. Latency: {latency_ms:.0f}ms."
            if ghost:
                try: ghost.info(f">> {log_msg}")
                except Exception as e: pass
            if ledger: ledger.log_handoff(latency_ms, success=True)
            self.request_state_change(KernelState.INFERENCE, log_msg)
        else:
            fail_msg = f"VRAM LOCKOUT: Free VRAM critical at {free_vram_mb:.0f}MB. Threshold: 200MB."
            if ghost:
                try: ghost.error(f"[KERNEL PANIC] {fail_msg}")
                except Exception as e: pass
            if ledger: ledger.log_handoff(latency_ms, success=False)
            self.event_queue.put("FAH_HANG_DETECTED")
            self.state = KernelState.PANIC

kernel = PeridotProductionKernel()

# --- STATE MANAGEMENT ---
llm = None
last_activity_time = time.time()
research_allowed = False

# --- RAG DEGRADATION MONITORING ---
# Autonomous throttling for RAG retrieval to prevent NVMe I/O bottlenecks
current_retrieval_depth = 6  # Start at full depth
last_retrieval_latency_ms = 0
RETRIEVAL_LATENCY_THRESHOLD_MS = 100  # Throttle if retrieval exceeds 100ms
RECOVERY_RATE = 0.5  # Increase depth by this amount every successful fast retrieval
MAX_RETRIEVAL_DEPTH = 6
MIN_RETRIEVAL_DEPTH = 1

def idle_monitor():
    while True:
        elapsed = time.time() - last_activity_time
        if elapsed > RESEARCH_IDLE_THRESHOLD and research_allowed:
            with kernel.state_lock:
                if kernel.state == KernelState.IDLE:
                    if send_fah_command("fold"):
                        kernel.state = KernelState.FAH_ACTIVE
                        if ghost:
                            try: ghost.info(f"RESEARCH | Idle threshold met. VRAM allocated to FAH. (Free: {get_vram_free()}MB)")
                            except Exception as e: pass
        time.sleep(1)

def boot_engine():
    global llm
    print(f"\n{'='*50}")
    print("   PERIDOT NEURAL ENGINE (v1.5.4 SOVEREIGN KERNEL)")
    print(f"{'='*50}")
    
    if not MODEL_PATH.exists():
        print(f"[FATAL] Model not found at {MODEL_PATH}")
        sys.exit(1)
        
    model_mode = get_model_format(MODEL_PATH).upper()
    print(f"[SYSTEM] Engine architecture auto-detected: {model_mode}")

    kernel.start()
    send_fah_command("pause")

    try:
        llm = Llama(
            model_path=str(MODEL_PATH),
            n_ctx=CONTEXT_LENGTH,            
            n_threads=THREADS,          
            n_gpu_layers=GPU_LAYERS,      
            n_gpu=1 if GPU_LAYERS != 0 else 0,
            n_batch=BATCH_SIZE,          
            flash_attn=True,      
            verbose=False,       
        )
        print(f">> [SUCCESS] Peridot Brain Online. (Free VRAM: {get_vram_free()}MB)")
        threading.Thread(target=idle_monitor, daemon=True).start()
        
        if zat_available:
            zat_client = LlamaClient()
            zat_orchestrator = SovereignGPUOrchestrator(client=zat_client, kernel=kernel)
            zat_telemetry = PhysicalTelemetryEngine(orchestrator=zat_orchestrator)
            zat_telemetry.start()
            if ghost:
                try: ghost.info("[ZAT-SCS] Predictive preemption engine online.")
                except Exception: pass
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        print(f"[HINT] Active model: {MODEL_PATH.name}")
        print("[HINT] If the GGUF is rejected by llama.cpp (missing/unknown tensors), the file "
              "is incomplete or its architecture is unsupported by the pinned llama-cpp-python. "
              "Select another local model with the ACTIVE_MODEL_NAME env var, e.g. "
              "ACTIVE_MODEL_NAME=Qwen2.5-14B-Instruct-Q4_K_M.gguf")
        sys.exit(1)

inference_lock = threading.Lock()

def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or auth_header != f"Bearer {API_KEY}":
            return jsonify({"error": "Unauthorized. Invalid or missing API Key."}), 403
        return f(*args, **kwargs)
    return decorated

def queue_requests(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        with inference_lock:
            return f(*args, **kwargs)
    return decorated

# --- API ENDPOINTS ---
@app.route('/health', methods=['GET'])
def health_check():
    if llm is not None:
        return jsonify({"status": "online"}), 200
    return jsonify({"status": "booting"}), 503

@app.route("/ingest", methods=["POST"])
@require_auth
@limiter.limit("60 per minute")
def ingest_vault_nodes():
    if vault is None:
        return jsonify({"error": "RAG Vault offline."}), 500
    try:
        vault.ingest_directory()
        return jsonify({"status": "SUCCESS", "message": "Check engine console for ingestion telemetry."}), 200
    except Exception as e:
        if ghost:
            try: ghost.error(f"Ingestion Disrupted: {e}")
            except Exception as e2: pass
        return jsonify({"error": str(e)}), 500
    
@app.route("/ask", methods=["POST"])
@require_auth
@queue_requests
@limiter.limit("60 per minute")
def ask():
    global last_activity_time
    last_activity_time = time.time()

    data = request.json
    user_query = data.get("query", "")
    full_prompt = data.get("prompt", "")
    session_id = data.get("session_id", None)

    if not user_query or not full_prompt:
        user_query = data.get("command", "")
        full_prompt = user_query

    if not user_query:
        return jsonify({"response": "Empty prompt received."}), 400

    # Declare globals for RAG degradation monitoring
    global current_retrieval_depth, last_retrieval_latency_ms

    if chat_ledger is not None:
        history = chat_ledger.get_history(session_id, limit=6)
    else:
        history = []

    if kernel.state == KernelState.SPECULATIVE_PREPARED:
        if ghost:
            try: ghost.info("API | [ZAT-SCS] Predictive preemption hit! Bypassing VRAM purge.")
            except Exception: pass
        kernel.request_state_change(KernelState.INFERENCE, "ZAT-SCS direct generation.")
    else:
        if ghost:
            try: ghost.info("API | Received payload. Requesting hardware clearance...")
            except Exception as e: pass
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

    try:
        if l1_cache is not None:
            if ghost:
                try: ghost.info(f"VRAM_STATE | Action: ROUTING | Free: {get_vram_free()}MB")
                except Exception as e: pass
                
            cached_response = l1_cache.search(user_query)
            if cached_response:
                if ghost:
                    try: ghost.info("ROUTER | L1 Cache HIT. Bypassing GPU entirely.")
                    except Exception as e: pass
                return jsonify({"response": cached_response, "session_id": session_id})

        context_str = ""
        if vault is not None and embedder is not None:
            if ghost:
                try: ghost.info("ROUTER | L1 MISS. Searching Semantic Memory...")
                except Exception as e: pass

            try:
                query_vector = embedder.embed_query(user_query)
                retrieval_depth = min(
                    MAX_RETRIEVAL_DEPTH,
                    max(MIN_RETRIEVAL_DEPTH, int(current_retrieval_depth)),
                )

                # Apply autonomous RAG degradation policy based on retrieval latency
                retrieval_start_time = time.time()
                relevant_context = vault.search(query_vector, top_k=retrieval_depth)
                retrieval_latency_ms = (time.time() - retrieval_start_time) * 1000

                # Update global retrieval latency tracker
                global last_retrieval_latency_ms
                last_retrieval_latency_ms = retrieval_latency_ms

                # Log retrieval performance for monitoring
                if ghost:
                    try: ghost.info(f"ROUTER | Semantic retrieval completed in {retrieval_latency_ms:.1f}ms (depth: {current_retrieval_depth})")
                    except Exception as e: pass

                # Autonomous throttling: if retrieval is too slow, reduce depth for next query
                if retrieval_latency_ms > RETRIEVAL_LATENCY_THRESHOLD_MS:
                    # Reduce depth but don't go below minimum
                    current_retrieval_depth = max(MIN_RETRIEVAL_DEPTH, current_retrieval_depth - 2)
                    if ghost:
                        try: ghost.warning(f"ROUTER | RAG DEGRADATION ACTIVE: High latency detected. Reducing retrieval depth to {current_retrieval_depth}")
                        except Exception as e: pass
                else:
                    # Recovery: if retrieval is fast, gradually increase depth back to maximum
                    if current_retrieval_depth < MAX_RETRIEVAL_DEPTH:
                        current_retrieval_depth = min(MAX_RETRIEVAL_DEPTH, current_retrieval_depth + RECOVERY_RATE)

                if relevant_context:
                    context_segments = []
                    for idx, chunk in enumerate(relevant_context):
                        source_id = f"Vault_Chunk_{idx}"
                        context_segments.append(f"[SOURCE: {source_id}]: {chunk}")
                        if rag_cache is not None:
                            rag_cache.put(source_id, [1.0, 0.0])

                    context_str = "\n---\n".join(context_segments)
                    if len(context_str) > 8000:
                        context_str = context_str[:8000] + "\n...[CONTEXT TRUNCATED DUE TO MEMORY LIMITS]..."

                    if ghost:
                        try: ghost.info(f"ROUTER | MEMORY HIT. Injected {len(relevant_context)} blocks.")
                        except Exception as e: pass
                else:
                    if ghost:
                        try: ghost.info("ROUTER | MEMORY MISS. Proceeding raw.")
                        except Exception as e: pass
            except Exception as e:
                if ghost:
                    try: ghost.warning(f"ROUTER | RAG DEGRADATION: Semantic Memory Retrieval Failed ({e}). Bypassing injection.")
                    except Exception as e2: pass
                context_str = ""

        model_format = get_model_format(MODEL_PATH)

        if model_format == "llama3":
            target_stops = ["<|eot_id|>", "<|start_header_id|>", "<|im_end|>"]
        else:
            target_stops = ["<|im_end|>", "<|im_start|>"]

        final_prompt = build_full_context(
            rag_context=context_str,
            chat_history=history,
            current_prompt=user_query,
            model_format=model_format
        )

        start_time = time.time()
        
        try:
            prompt_tokens = len(llm.tokenize(final_prompt.encode("utf-8")))
            safe_max_tokens = CONTEXT_LENGTH - prompt_tokens - 10
            
            while safe_max_tokens < 128 and len(history) > 0:
                history.pop(0)
                final_prompt = build_full_context(
                    rag_context=context_str,
                    chat_history=history,
                    current_prompt=user_query,
                    model_format=model_format
                )
                prompt_tokens = len(llm.tokenize(final_prompt.encode("utf-8")))
                safe_max_tokens = CONTEXT_LENGTH - prompt_tokens - 10
                
        except Exception:
            safe_max_tokens = MAX_TOKENS
            
        if safe_max_tokens < 128:
            return jsonify({"response": "[SYSTEM ERROR] The conversation history and context have exceeded the AI's memory window, and could not be truncated safely. Please clear memory and start a new session."}), 400
            
        output = llm(
            final_prompt, 
            max_tokens=min(MAX_TOKENS, safe_max_tokens), 
            stop=target_stops, 
            temperature=TEMPERATURE,
            top_p=TOP_P,
            repeat_penalty=REPEAT_PENALTY,
            echo=False
        )
        elapsed_s = time.time() - start_time
        
        final_response = output["choices"][0]["text"].strip()
        
        if "[ANALYSIS]" not in final_response or "[KERNEL_RESPONSE]" not in final_response:
            final_response = f"[ANALYSIS]\nEnforced kernel formatting fallback.\n\n[KERNEL_RESPONSE]\n{final_response}"
        
        tokens_generated = output.get("usage", {}).get("completion_tokens", len(final_response.split()) * 1.3)
        tps = tokens_generated / elapsed_s if elapsed_s > 0 else 0
        
        if ghost:
            try: ghost.info(f"INFERENCE   | Tokens: {int(tokens_generated)} | Time: {elapsed_s:.2f}s | Speed: {tps:.2f} t/s")
            except Exception as e: pass
        
        if l1_cache is not None:
            l1_cache.add(user_query, final_response)
            
        if ledger: ledger.log_inference()
             
        return jsonify({"response": final_response, "session_id": session_id})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        if ghost:
            try: ghost.error(f"CRITICAL    | Component: server_ask_route | Error: {error_msg}")
            except Exception as e2: pass
        return jsonify({"response": "An internal error occurred during inference. Please check the engine terminal."}), 500
        
    finally:
        if ghost:
            try: ghost.info("API | Payload delivered. Releasing hardware lock...")
            except Exception as e: pass
        try:
            if 'llm' in globals() and llm:
                llm.reset()
        except Exception:
            pass
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        kernel.event_queue.put("INFERENCE_COMPLETE")

@app.route("/vram/reclaim", methods=["POST"])
@require_auth
def reclaim_vram():
    try:
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        if 'llm' in globals() and llm:
            try: llm.reset()
            except Exception as e: pass
        if ghost:
            try: ghost.info("HARDWARE | Manual VRAM Force-Reclaim triggered via UI.")
            except Exception as e: pass
        return jsonify({"status": "SUCCESS", "message": "VRAM successfully reclaimed."}), 200
    except Exception as e:
        if ghost:
            try: ghost.error(f"VRAM Reclaim Failed: {e}")
            except Exception as e2: pass
        return jsonify({"error": str(e)}), 500

@app.route("/telemetry/stability", methods=["GET"])
@require_auth
def get_stability_metrics():
    if ledger:
        data = ledger.generate_report()
        # Add current FSM state
        data["current_fsm_state"] = kernel.state.name
        return jsonify(data), 200
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