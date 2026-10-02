# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | NEURAL ENGINE & INGESTION CORE
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import os
import sys
import hmac
import logging
import threading
import time
import json
import websocket
import psutil
import pynvml
import queue
from flask import Flask, Response, copy_current_request_context, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import functools

load_dotenv()

# --- PERIDOT CONFIGURATION ---
from config import (
    MODEL_PATH, GPU_LAYERS, MAX_TOKENS, CONTEXT_LENGTH,
    TEMPERATURE, TOP_P, TOP_K, REPEAT_PENALTY, SERVER_HOST, SERVER_PORT, API_KEY,
    RESEARCH_IDLE_THRESHOLD, THREADS, THREADS_BATCH, BATCH_SIZE, UBATCH_SIZE, KV_CACHE_TYPE,
    ZAT_SCS_ENABLED,
)
from core_system import settings

# --- SOVEREIGNTY GATE ---
# config has already force-set offline mode; fail loud rather than boot an
# engine that could reach the network. Model fetches run in an isolated child
# process (python -m core_system.model_fetch), never in this one.
from core_system.model_fetch import assert_main_process_offline
assert_main_process_offline()

# --- CENTRALIZED PROMPT ENGINE ---
from core_system.prompting.constitution import (
    format_kernel_response,
    get_model_format,
    is_bare_tool_json,
    is_storable_answer,
    model_supports_thinking,
    parse_kernel_response,
    split_reasoning,
)
from core_system.prompting.builder import THINK_SEED, build_full_context

# --- v1.6.0 MODEL TOOLS & SOVEREIGN INVOCATION ---
from core_system.extensions import registry, tools
from core_system.invocation import agent, filetools

# --- v1.6.x INFERENCE PROVIDER ABSTRACTION ---
# .gguf always routes to LlamaCppProvider today; provider_for() is used (rather
# than importing LlamaCppProvider directly) so a future ExLlamaV2/.exl2 model
# picks up its provider automatically once that backend is registered.
from core_system.providers import provider_for

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

    l1_cache = EphemeralCache()
    vault = PersistentVault()
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
    embedder = None

# --- KERNEL FSM IMPORTS ---
from core_system.kernel import SovereignKernel, KernelState

# --- ZAT-SCS IMPORTS (opt-in: ZAT_SCS_ENABLED) ---
# Not imported at all when disabled, so sounddevice/pynput never load and no
# microphone stream or keyboard hook is opened.
zat_available = False
if ZAT_SCS_ENABLED:
    try:
        from core_system.telemetry.processor import PhysicalTelemetryEngine
        from core_system.telemetry.orchestration.fsm import SovereignGPUOrchestrator
        from core_system.telemetry.client.api import LlamaClient
        zat_available = True
    except ImportError as e:
        if ghost:
            try: ghost.warning(f"[ZAT-SCS] Failed to load modules: {e}")
            except Exception: pass
elif ghost:
    try: ghost.info("[ZAT-SCS] Disabled (set ZAT_SCS_ENABLED=1 to enable predictive preemption).")
    except Exception: pass

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

FAH_WS_PORT = 7396

def fah_listening() -> bool:
    """True when a Folding@home v8 client is listening on its websocket port.

    Checked from the socket table instead of by connecting: on Windows a
    connect to a closed localhost port is retried for ~2s before it fails,
    which every request used to pay whenever F@H was not running.
    """
    try:
        return any(
            c.laddr and c.laddr.port == FAH_WS_PORT and c.status == psutil.CONN_LISTEN
            for c in psutil.net_connections("tcp")
        )
    except Exception:
        return True  # Unknown: fall through to the real connect attempt.

def send_fah_command(cmd_state: str) -> bool:
    if not fah_listening():
        return False
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
            except Exception: pass
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
                except Exception: pass
            if ledger: ledger.log_handoff(latency_ms, success=True)
            self.request_state_change(KernelState.INFERENCE, log_msg)
        else:
            fail_msg = f"VRAM LOCKOUT: Free VRAM critical at {free_vram_mb:.0f}MB. Threshold: 200MB."
            if ghost:
                try: ghost.error(f"[KERNEL PANIC] {fail_msg}")
                except Exception: pass
            if ledger: ledger.log_handoff(latency_ms, success=False)
            self.event_queue.put("FAH_HANG_DETECTED")
            with self.state_changed:
                self.state = KernelState.PANIC
                self.state_changed.notify_all()

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
                            except Exception: pass
        time.sleep(1)

def boot_engine():
    global llm
    print(f"\n{'='*50}")
    print("   PERIDOT NEURAL ENGINE (v1.6.0 SOVEREIGN KERNEL)")
    print(f"{'='*50}")
    
    if not MODEL_PATH.exists():
        print(f"[FATAL] Model not found at {MODEL_PATH}")
        sys.exit(1)
        
    model_mode = get_model_format(MODEL_PATH).upper()
    print(f"[SYSTEM] Engine architecture auto-detected: {model_mode}")

    kernel.start()
    send_fah_command("pause")

    try:
        llm = provider_for(
            MODEL_PATH,
            n_ctx=CONTEXT_LENGTH,
            n_threads=THREADS,
            n_threads_batch=THREADS_BATCH,
            n_gpu_layers=GPU_LAYERS,
            n_batch=BATCH_SIZE,
            n_ubatch=UBATCH_SIZE,
            kv_cache_type=KV_CACHE_TYPE,
            flash_attn=True,
            verbose=False,
            supports_thinking=MODEL_THINKS,
        )
        llm.load()
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

# FreeThink registry lookup, once: native <think> models get the scaffold-free
# system prompt (constitution.build_system_prompt) and report supports_thinking.
MODEL_THINKS = model_supports_thinking(MODEL_PATH)

def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not hmac.compare_digest(auth_header, f"Bearer {API_KEY}"):
            return jsonify({"error": "Unauthorized. Invalid or missing API Key."}), 403
        return f(*args, **kwargs)
    return decorated

def queue_requests(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        with inference_lock:
            return f(*args, **kwargs)
    return decorated

# --- REQUEST ACTIVITY (v1.6.0 Sovereign Invocation Relay) ---
# The relay (core_system/invocation/relay.py) reads idle_s/inflight from
# /health and exits this process when idle, so /health itself must not count.
_last_activity = time.monotonic()
_inflight = 0
_activity_lock = threading.Lock()

@app.before_request
def _track_request_start():
    global _last_activity, _inflight
    if request.path == "/health" or request.method == "OPTIONS":
        return
    request.environ["peridot.inflight"] = True
    with _activity_lock:
        _last_activity = time.monotonic()
        _inflight += 1

@app.teardown_request
def _track_request_end(_exc=None):
    # pop(): /ask/stream's copy_current_request_context shares this environ,
    # so its second teardown must not decrement again.
    global _last_activity, _inflight
    if request.environ.pop("peridot.inflight", None):
        with _activity_lock:
            _last_activity = time.monotonic()
            _inflight -= 1

# --- API ENDPOINTS ---
@app.route('/health', methods=['GET'])
def health_check():
    global _last_activity
    # A stream's view returns before its worker finishes generating; the held
    # inference_lock is what proves work is still running.
    busy = inference_lock.locked()
    if busy:
        _last_activity = time.monotonic()
    info = {
        "idle_s": int(time.monotonic() - _last_activity),
        "inflight": max(_inflight, int(busy)),
        "pid": os.getpid(),
        "model": MODEL_PATH.name,
    }
    if llm is not None and llm.is_loaded:
        return jsonify({"status": "online", **info}), 200
    return jsonify({"status": "booting", **info}), 503

@app.route("/ingest", methods=["POST"])
@require_auth
@limiter.limit("60 per minute")
def ingest_vault_nodes():
    if vault is None:
        return jsonify({"error": "RAG Vault offline."}), 500
    try:
        vault.ingest_directory()
        return jsonify({
            "status": "SUCCESS",
            "message": "Check engine console for ingestion telemetry.",
            "sectors": vault.index.size,
        }), 200
    except Exception as e:
        if ghost:
            try: ghost.error(f"Ingestion Disrupted: {e}")
            except Exception: pass
        return jsonify({"error": str(e)}), 500
    
@app.route("/ask", methods=["POST"])
@require_auth
@queue_requests
@limiter.limit("60 per minute")
def ask():
    return _ask_impl()


@app.route("/ask/stream", methods=["POST"])
@require_auth
@limiter.limit("60 per minute")
def ask_stream():
    """/ask with the answer streamed as NDJSON while it generates.

    Lines are {"delta": "<raw text>"} as tokens arrive, then exactly one
    {"done": true, "status": <http code>, ...the /ask JSON body...}. Deltas are
    raw model output (reasoning and scaffolding included); clients show them via
    constitution.stream_visible_body() and render the final "response" exactly
    as they would /ask's. Every tool-loop generation streams, with anything
    from <tool_call> onward held back; tool runs arrive as
    {"tool": name, "status": "start"} then {"tool": name, "status": "ok"|"error",
    "error"?: short}. A retry, a cache hit or an error arrives as the final
    line alone.

    The pipeline runs in a worker thread holding inference_lock for the whole
    generation, so the lock and the kernel's INFERENCE_COMPLETE (in
    _ask_impl's finally) span the stream, not just this view's return.
    """
    events: "queue.Queue[dict]" = queue.Queue()

    @copy_current_request_context
    def worker():
        try:
            with inference_lock:
                result = _ask_impl(delta_sink=lambda text: events.put({"delta": text}),
                                   event_sink=events.put)
            body, status = result if isinstance(result, tuple) else (result, 200)
            events.put({"done": True, "status": status, **(body.get_json() or {})})
        except Exception as e:
            if ghost:
                try: ghost.error(f"CRITICAL    | Component: server_ask_stream | Error: {e}")
                except Exception: pass
            events.put({"done": True, "status": 500,
                        "response": "An internal error occurred during inference. Please check the engine terminal."})

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            event = events.get()
            yield json.dumps(event) + "\n"
            if event.get("done"):
                return

    return Response(stream(), mimetype="application/x-ndjson")


# --- CANCELLATION (/ask/cancel) ---
# One flag: at most one /ask generation runs at a time (inference_lock).
# Cleared when each /ask starts, checked on every streamed chunk.
_cancel = threading.Event()


class Cancelled(Exception):
    """Raised from the chunk callback once /ask/cancel fires; carries the raw text so far."""

    def __init__(self, partial):
        super().__init__("generation cancelled")
        self.partial = partial


@app.route("/ask/cancel", methods=["POST"])
@require_auth
def ask_cancel():
    """Stop the running /ask or /ask/stream generation.

    The running request then returns its partial answer with "cancelled": true.
    Nothing running -> {"cancelled": false}.
    """
    if not inference_lock.locked():
        return jsonify({"cancelled": False}), 200
    _cancel.set()
    return jsonify({"cancelled": True}), 200


def _acquire_kernel():
    """PROMPT_RECEIVED handshake. None once cleared for INFERENCE, else (error, status).

    The caller owns the matching INFERENCE_COMPLETE (in its finally).
    """
    if kernel.state == KernelState.SPECULATIVE_PREPARED:
        if ghost:
            try: ghost.info("API | [ZAT-SCS] Predictive preemption hit! Bypassing VRAM purge.")
            except Exception: pass
        kernel.request_state_change(KernelState.INFERENCE, "ZAT-SCS direct generation.")
        return None
    if ghost:
        try: ghost.info("API | Received payload. Requesting hardware clearance...")
        except Exception: pass
    kernel.event_queue.put("PROMPT_RECEIVED")

    cleared = kernel.wait_for_state(
        lambda s: s in (KernelState.INFERENCE, KernelState.PANIC), timeout=10.0
    )
    if kernel.state == KernelState.PANIC:
        return "KERNEL PANIC: Hardware failed to yield.", 503
    if not cleared:
        kernel.request_state_change(KernelState.PANIC, "FAH Timeout")
        return "KERNEL TIMEOUT: Hardware clearance not granted.", 504
    return None


def _stop_tokens(model_format):
    if model_format == "llama3":
        return ["<|eot_id|>", "<|start_header_id|>", "<|im_end|>"]
    if model_format == "mistral":
        # ponytail: was silently falling through to the ChatML stop
        # tokens below, which never appear in Mistral output -- generation
        # would have run to MAX_TOKENS every time instead of stopping at
        # </s>. Untested against real hardware; verify a Mistral-Nemo run
        # actually stops cleanly before trusting this.
        return ["</s>", "[INST]"]
    return ["<|im_end|>", "<|im_start|>"]


def _raw_text(prompt_text, text):
    """Generated text as the model sees it: a pre-seeded think opener at the
    end of the prompt (builder.THINK_SEED) is part of the reply."""
    return (THINK_SEED if prompt_text.endswith(THINK_SEED) else "") + text


def _make_generate(stops, max_tokens, delta_sink=None, cancellable=False):
    """generate(prompt_text, tag) -> GenerationResult, for one request.

    The budget is recomputed per prompt because tool turns grow it. Every
    tag but the pre-seeded retry streams to delta_sink, with tool-call
    markup held back (agent.MarkupFilter); a pre-seeded think opener is
    streamed first so clients hide the reasoning that follows. cancellable:
    raise Cancelled once /ask/cancel sets _cancel.
    """
    def _generate(prompt_text, tag):
        """Run one completion and log the RAW, unstripped text it produced.

        The raw repr is the only thing that separates "model stopped
        immediately" from "model answered and we dropped it downstream".
        Without it this bug was undiagnosable from the logs, which only
        ever recorded a token count.
        """
        try:
            prompt_tokens = llm.token_count(prompt_text)
            budget = min(max_tokens, CONTEXT_LENGTH - prompt_tokens - 10)
        except Exception:
            prompt_tokens, budget = -1, max_tokens
        if budget < 1:
            # ponytail: tool results filled the context window; the turn fails
            # with the generic 500. Summarise old tool turns if this shows up.
            raise RuntimeError(f"Context window exhausted ({prompt_tokens} prompt tokens).")
        sink = agent.MarkupFilter(delta_sink) if delta_sink and tag != "retry_preseeded" else None
        parts = [_raw_text(prompt_text, "")]
        if cancellable and _cancel.is_set():
            raise Cancelled("".join(parts))
        if sink and parts[0]:
            delta_sink(parts[0])

        def on_chunk(chunk):
            if cancellable and _cancel.is_set():
                raise Cancelled("".join(parts))
            parts.append(chunk)
            if sink:
                sink(chunk)

        result = llm.generate(
            prompt_text,
            max_tokens=budget,
            stop=stops,
            temperature=TEMPERATURE,
            top_p=TOP_P,
            top_k=TOP_K,
            repeat_penalty=REPEAT_PENALTY,
            **({"on_chunk": on_chunk} if sink or cancellable else {}),
        )
        if sink:
            sink.flush()
        if ghost:
            try:
                ghost.info(
                    f"RAW_OUTPUT | {tag} | finish={result.finish_reason} "
                    f"| prompt_tokens={prompt_tokens} | budget={budget} "
                    f"| text={result.text[:1200]!r}"
                )
            except Exception:
                pass
        return result
    return _generate


LEGACY_RETRY_SEED = '<think>\n\n</think>\n\n[ANALYSIS]\nDirect synthesis.\n\n[KERNEL_RESPONSE]\n'
THINKING_RETRY_SEED = "\n</think>\n\n"  # completes the prompt's "<think>\n" to an empty block


def _answer(output, prompt, generate, resume=None):
    """(analysis, body, output, raw) from the final generation, tool markup stripped.

    An empty or unstorable body (tool markup only, bare tool-call JSON, a "Let
    me look that up." stub) gets one retry with the reasoning closed (thinking
    models) or the legacy scaffold pre-seeded. If the retry calls a tool,
    resume(prompt, output) -> (output, prompt) hands it back to the tool loop.
    raw is the final generation including its pre-seeded think opener.
    """
    raw = _raw_text(prompt, output.text)
    analysis, body = parse_kernel_response(tools.strip_tool_calls(raw))
    if not is_storable_answer(body):
        # The model closed an empty think (or emitted a bare header / stub)
        # and stopped. Re-run with the reasoning closed so it can only
        # continue with the answer itself.
        if ghost:
            try: ghost.warning("INFERENCE   | Empty or unstorable answer. Re-running pre-seeded.")
            except Exception: pass
        thinking = prompt.endswith(THINK_SEED)
        seed = THINKING_RETRY_SEED if thinking else LEGACY_RETRY_SEED
        retry_prompt = prompt + seed
        output = generate(retry_prompt, "retry_preseeded")
        raw = (THINK_SEED if thinking else "") + seed + output.text
        if resume is not None and tools.parse_tool_calls(output.text):
            output, retry_prompt = resume(retry_prompt, output)
            raw = _raw_text(retry_prompt, output.text)
        retry_analysis, retry_body = parse_kernel_response(tools.strip_tool_calls(raw))
        analysis, body = retry_analysis or analysis, retry_body or body
    if is_bare_tool_json(body):
        body = ""  # never hand a tool call back as the answer (markup is already stripped)
    return analysis, body, output, raw


def _web_presearch(query, emit=None):
    """Per-message web button: run web_search before generation.

    -> (context block labelled [WEB SEARCH RESULTS] or "", notice or "").
    """
    if not settings.get("web.enabled"):
        return "", "Web access is disabled in Settings."
    plugin = registry.scan().plugins.get(tools.WEB_PLUGIN)
    if plugin is None or not plugin.approved:
        return "", "The web_search plugin is not installed or not approved."
    out = agent.dispatch("web_search", {"query": query}, emit)
    if not out["ok"]:
        return "", f"Web search failed: {str(out['error'])[:200]}"
    return "[WEB SEARCH RESULTS]\n" + str(out["result"])[:6000], ""


def _ask_impl(delta_sink=None, event_sink=None):
    global last_activity_time
    last_activity_time = time.time()
    _cancel.clear()

    data = request.json
    session_id = data.get("session_id", None)

    # Accept any of the three documented keys. This was previously
    # `if not user_query or not full_prompt:`, which meant sending "query"
    # without also sending "prompt" fell through to the "command" fallback and
    # blanked the query -- so the documented "query" key always returned 400.
    # The prompt itself is assembled by build_full_context() further down from
    # user_query, so there is no separate full_prompt to carry here.
    user_query = data.get("query") or data.get("prompt") or data.get("command") or ""

    if not user_query:
        return jsonify({"response": "Empty prompt received."}), 400

    # Declare globals for RAG degradation monitoring
    global current_retrieval_depth, last_retrieval_latency_ms

    if chat_ledger is not None:
        history = chat_ledger.get_history(session_id, limit=6)
    else:
        history = []
    # core.py writes the user turn to the ledger before calling /ask, so the
    # history read back already ends with this very turn. build_full_context
    # appends current_prompt itself -- without this trim every prompt carried
    # the question twice (user Q, user Q, assistant), which also broke KV
    # prefix reuse across turns. Dropped on role alone: for /skill messages
    # the ledger holds the typed "/name task" while the query is the expanded
    # skill prompt, so a content match missed it.
    if history and history[-1].get("role") == "user":
        history = history[:-1]

    # Per-message web button. Results are time-dependent, so neither this
    # turn nor any turn that ran a tool touches the L1 cache.
    web_requested = bool(data.get("web"))

    kernel_error = _acquire_kernel()
    if kernel_error:
        return jsonify({"error": kernel_error[0]}), kernel_error[1]

    try:
        if l1_cache is not None and not web_requested:
            if ghost:
                try: ghost.info(f"VRAM_STATE | Action: ROUTING | Free: {get_vram_free()}MB")
                except Exception: pass
                
            cached_response = l1_cache.search(user_query)
            if cached_response:
                if ghost:
                    try: ghost.info("ROUTER | L1 Cache HIT. Bypassing GPU entirely.")
                    except Exception: pass
                return jsonify({"response": cached_response, "session_id": session_id,
                                "cancelled": False, "reasoning": ""})

        context_str = ""
        if vault is not None and embedder is not None:
            if ghost:
                try: ghost.info("ROUTER | L1 MISS. Searching Semantic Memory...")
                except Exception: pass

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
                    except Exception: pass

                # Autonomous throttling: if retrieval is too slow, reduce depth for next query
                if retrieval_latency_ms > RETRIEVAL_LATENCY_THRESHOLD_MS:
                    # Reduce depth but don't go below minimum
                    current_retrieval_depth = max(MIN_RETRIEVAL_DEPTH, current_retrieval_depth - 2)
                    if ghost:
                        try: ghost.warning(f"ROUTER | RAG DEGRADATION ACTIVE: High latency detected. Reducing retrieval depth to {current_retrieval_depth}")
                        except Exception: pass
                else:
                    # Recovery: if retrieval is fast, gradually increase depth back to maximum
                    if current_retrieval_depth < MAX_RETRIEVAL_DEPTH:
                        current_retrieval_depth = min(MAX_RETRIEVAL_DEPTH, current_retrieval_depth + RECOVERY_RATE)

                if relevant_context:
                    context_segments = []
                    for idx, chunk in enumerate(relevant_context):
                        source_id = f"Vault_Chunk_{idx}"
                        context_segments.append(f"[SOURCE: {source_id}]: {chunk}")

                    context_str = "\n---\n".join(context_segments)
                    if len(context_str) > 8000:
                        context_str = context_str[:8000] + "\n...[CONTEXT TRUNCATED DUE TO MEMORY LIMITS]..."

                    if ghost:
                        try: ghost.info(f"ROUTER | MEMORY HIT. Injected {len(relevant_context)} blocks.")
                        except Exception: pass
                else:
                    if ghost:
                        try: ghost.info("ROUTER | MEMORY MISS. Proceeding raw.")
                        except Exception: pass
            except Exception as e:
                if ghost:
                    try: ghost.warning(f"ROUTER | RAG DEGRADATION: Semantic Memory Retrieval Failed ({e}). Bypassing injection.")
                    except Exception: pass
                context_str = ""

        has_documents = bool(context_str)
        notice = ""
        if web_requested:
            web_block, notice = _web_presearch(user_query, event_sink)
            extra = web_block or f"[SYSTEM NOTE]: {notice}"
            context_str = extra + ("\n---\n" + context_str if context_str else "")

        model_format = get_model_format(MODEL_PATH)
        target_stops = _stop_tokens(model_format)

        catalog = tools.tool_catalog() if settings.get("extensions.model_invoke") is True else []
        tools_block = tools.render_tools_block(catalog)
        if catalog:
            target_stops = target_stops + [agent.TOOL_CALL_CLOSE]
        # What the system prompt tells the model it can do this turn.
        capabilities = {"tools": [t["name"] for t in catalog],
                        "web": bool(settings.get("web.enabled")), "documents": has_documents}

        final_prompt = build_full_context(
            rag_context=context_str,
            chat_history=history,
            current_prompt=user_query,
            model_format=model_format,
            thinking=MODEL_THINKS,
            tools_block=tools_block,
            model_name=MODEL_PATH.name,
            capabilities=capabilities,
        )

        start_time = time.time()
        
        try:
            prompt_tokens = llm.token_count(final_prompt)
            safe_max_tokens = CONTEXT_LENGTH - prompt_tokens - 10

            while safe_max_tokens < 128 and len(history) > 0:
                history.pop(0)
                final_prompt = build_full_context(
                    rag_context=context_str,
                    chat_history=history,
                    current_prompt=user_query,
                    model_format=model_format,
                    thinking=MODEL_THINKS,
                    tools_block=tools_block,
                    model_name=MODEL_PATH.name,
                    capabilities=capabilities,
                )
                prompt_tokens = llm.token_count(final_prompt)
                safe_max_tokens = CONTEXT_LENGTH - prompt_tokens - 10
                
        except Exception:
            safe_max_tokens = MAX_TOKENS
            
        if safe_max_tokens < 128:
            return jsonify({"response": "[SYSTEM ERROR] The conversation history and context have exceeded the AI's memory window, and could not be truncated safely. Please clear memory and start a new session."}), 400
            
        token_budget = min(MAX_TOKENS, safe_max_tokens)
        _generate = _make_generate(target_stops, token_budget, delta_sink, cancellable=True)
        allowed = {t["name"] for t in catalog}
        calls = []

        def _tool_loop(prompt, first=None):
            output, prompt, made = agent.run_tool_loop(
                prompt, _generate, model_format, allowed=allowed, emit=event_sink,
                max_steps=agent.MAX_TOOL_STEPS - len(calls), thinking=MODEL_THINKS, first=first,
            )
            calls.extend(made)
            return output, prompt

        try:
            resume = None
            if catalog:
                output, final_prompt = _tool_loop(final_prompt)
                if len(calls) < agent.MAX_TOOL_STEPS:
                    resume = _tool_loop
            else:
                output = _generate(final_prompt, "primary")
            analysis, body, output, raw = _answer(output, final_prompt, _generate, resume)
            tokens_generated, cancelled = output.completion_tokens, False
        except Cancelled as c:
            # /ask/cancel: hand back whatever answer text was already visible.
            raw, tokens_generated, cancelled = c.partial, 0, True
            analysis, body = parse_kernel_response(tools.strip_tool_calls(raw))
        reasoning = split_reasoning(raw)[0]

        elapsed_s = time.time() - start_time

        storable = not cancelled and is_storable_answer(body)
        if not body and not cancelled:
            body = ("[KERNEL FAULT] The model produced no answer for this turn. "
                    "Raw output was empty; see RAW_OUTPUT in logs/ghost_audit.log.")

        final_response = format_kernel_response(analysis, body)

        tps = tokens_generated / elapsed_s if elapsed_s > 0 else 0

        if ghost:
            try: ghost.info(f"INFERENCE   | Tokens: {int(tokens_generated)} | Time: {elapsed_s:.2f}s | Speed: {tps:.2f} t/s"
                            + (" | CANCELLED" if cancelled else ""))
            except Exception: pass

        if l1_cache is not None and not web_requested and not calls and storable:
            l1_cache.add(user_query, final_response)

        if ledger: ledger.log_inference()

        reply = {"response": final_response, "session_id": session_id,
                 "cancelled": cancelled, "reasoning": reasoning}
        if notice:
            reply["notice"] = notice
        return jsonify(reply)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        if ghost:
            try: ghost.error(f"CRITICAL    | Component: server_ask_route | Error: {error_msg}")
            except Exception: pass
        return jsonify({"response": "An internal error occurred during inference. Please check the engine terminal."}), 500
        
    finally:
        if ghost:
            try: ghost.info("API | Payload delivered. Releasing hardware lock...")
            except Exception: pass
        # No llm.reset() / gc / torch.cuda.empty_cache() here any more. reset()
        # discarded the KV cache, so every turn re-prefilled the system prompt,
        # RAG context and history from scratch; llama-cpp-python reuses the
        # longest matching prompt prefix when the cache is left alone. The
        # torch call freed nothing -- torch holds no CUDA memory (the embedder
        # runs on CPU). /vram/reclaim still resets on demand.
        kernel.event_queue.put("INFERENCE_COMPLETE")


# --- SOVEREIGN INVOCATION (v1.6.0; called by mcp/peridot_mcp.py) ---
INVOKE_MODES = ("full", "review", "status_only")
NO_FOLDERS_MSG = "No folders are allowlisted for Sovereign Invocation. Add one in Peridot Settings."
DELEGATE_NOTE = (
    "You are running as a delegated local agent. Complete the task using the file tools "
    "on the user's allowlisted folders. Allowlisted folders: {roots}. "
    "Paths the caller pointed at: {paths}."
)
SUMMARY_PROMPT = (
    "Summarize the following result for a third party in at most 5 sentences. Do not include "
    "raw numbers, account numbers, names, addresses, file paths, or quotes from the files; "
    "describe outcomes only.\n\n<result>\n{}\n</result>"
)


@app.route("/invoke", methods=["POST"])
@require_auth
@limiter.limit("60 per minute")
def invoke():
    """Run a delegated task with the file tools; see mcp/peridot_mcp.py.

    -> {answer, summary, action_only, model_used, steps}. action_only is True
    iff at least one write_file succeeded and the answer is under 400 chars:
    the caller then reports "done" instead of relaying an answer.
    """
    global last_activity_time
    last_activity_time = time.time()

    data = request.json
    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object."}), 400
    task = data.get("task")
    if not isinstance(task, str) or not task.strip():
        return jsonify({"error": "'task' must be a non-empty string."}), 400
    paths = data.get("paths") or []
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        return jsonify({"error": "'paths' must be an array of strings."}), 400
    mode = data.get("return_mode") or "review"
    if mode not in INVOKE_MODES:
        return jsonify({"error": f"'return_mode' must be one of {', '.join(INVOKE_MODES)}."}), 400

    roots = filetools.allowed_roots()
    if not roots:
        return jsonify({"error": NO_FOLDERS_MSG}), 403
    if any(filetools.resolve(p, tool="invoke") is None for p in paths):
        return jsonify({"error": "A requested path is outside the folders allowlisted "
                                 "for Sovereign Invocation."}), 403
    if llm is None or not llm.is_loaded:
        return jsonify({"error": "Peridot is still loading its model."}), 503

    with inference_lock:
        kernel_error = _acquire_kernel()
        if kernel_error:
            return jsonify({"error": kernel_error[0]}), kernel_error[1]
        try:
            model_format = get_model_format(MODEL_PATH)
            stops = _stop_tokens(model_format)
            # Plugins ride along per the model_invoke setting; file tools always.
            if settings.get("extensions.model_invoke") is True:
                catalog = tools.tool_catalog(include_files=True)
            else:
                catalog = [dict(t) for t in tools.FILE_TOOLS]
            note = DELEGATE_NOTE.format(roots=", ".join(str(r) for r, _w in roots),
                                        paths=", ".join(paths) or "none")
            names = [t["name"] for t in catalog]
            prompt = build_full_context(
                rag_context="", chat_history=[], current_prompt=f"{note}\n\n[TASK]\n{task}",
                model_format=model_format, thinking=MODEL_THINKS,
                tools_block=tools.render_tools_block(catalog), model_name=MODEL_PATH.name,
                capabilities={"tools": names, "web": bool(settings.get("web.enabled"))},
            )
            generate = _make_generate(stops + [agent.TOOL_CALL_CLOSE], MAX_TOKENS)
            output, prompt, calls = agent.run_tool_loop(
                prompt, generate, model_format,
                allowed=set(names), allow_files=True, thinking=MODEL_THINKS,
            )
            _analysis, answer, _output, _raw = _answer(output, prompt, generate)

            summary = ""
            if mode == "review":
                summary_prompt = build_full_context(
                    rag_context="", chat_history=[], current_prompt=SUMMARY_PROMPT.format(answer),
                    model_format=model_format, thinking=MODEL_THINKS, model_name=MODEL_PATH.name,
                )
                if summary_prompt.endswith(THINK_SEED):
                    summary_prompt += THINKING_RETRY_SEED  # 300 tokens is no room to reason
                summary_out = _make_generate(stops, 300)(summary_prompt, "invoke_summary")
                summary = tools.strip_tool_calls(parse_kernel_response(summary_out.text)[1])

            if ledger: ledger.log_inference()
            return jsonify({
                "answer": answer,
                "summary": summary,
                "action_only": any(c["name"] == "write_file" and c["ok"] for c in calls)
                               and len(answer) < 400,
                "model_used": MODEL_PATH.name,
                "steps": len(calls),
            })
        except Exception as e:
            if ghost:
                try: ghost.error(f"CRITICAL    | Component: server_invoke | Error: {type(e).__name__}: {e}")
                except Exception: pass
            return jsonify({"error": "Peridot failed to run the task; see the engine log."}), 503
        finally:
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
            except Exception: pass
        if ghost:
            try: ghost.info("HARDWARE | Manual VRAM Force-Reclaim triggered via UI.")
            except Exception: pass
        return jsonify({"status": "SUCCESS", "message": "VRAM successfully reclaimed."}), 200
    except Exception as e:
        if ghost:
            try: ghost.error(f"VRAM Reclaim Failed: {e}")
            except Exception: pass
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
    # werkzeug.server.shutdown was removed in Werkzeug 2.1 (installed: 3.1.8),
    # so this route used to answer 200 and leave the engine running with the
    # model still holding VRAM. Unload, then exit once the reply is flushed.
    def _exit_process():
        try:
            if llm is not None:
                llm.unload()
        except Exception:
            pass
        os._exit(0)

    threading.Timer(0.5, _exit_process).start()
    return jsonify({"message": "Shutting down Neural Engine..."}), 200

@app.route("/research/status", methods=["GET"])
@require_auth
def get_research_status():
    return jsonify({
        "enabled": research_allowed,
        "active": kernel.state == KernelState.FAH_ACTIVE,
        "vram_free": get_vram_free(),
        # The vault lives in this process only; the UI's `status` reads it here.
        "vault_sectors": vault.index.size if vault is not None else None,
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

# --- SETTINGS (v1.6.0) ---
@app.route("/settings", methods=["GET"])
@require_auth
def get_settings():
    return jsonify(settings.all())

@app.route("/settings", methods=["POST"])
@require_auth
@limiter.limit("30 per minute")
def post_settings():
    body = request.json
    if not isinstance(body, dict):
        return jsonify({"error": "Expected a JSON object."}), 400

    # A model swap only takes effect at boot: validate the file here, persist
    # it to .env (where config reads ACTIVE_MODEL_NAME), and tell the caller.
    model = body.get("model.active")
    restart = isinstance(model, str) and bool(model)
    if restart:
        import config
        if (os.path.basename(model) != model or not model.lower().endswith(".gguf")
                or not (config.MODEL_DIR / model).is_file()):
            return jsonify({"error": f"Model not found in models/: {model}"}), 400

    try:
        settings.update(body)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    result = settings.all()
    if restart:
        from dotenv import set_key
        set_key(str(config.ENV_PATH), "ACTIVE_MODEL_NAME", model)
        result["restart_required"] = True
    return jsonify(result)

if __name__ == "__main__":
    from flask import cli
    cli.show_server_banner = lambda *_: None
    boot_engine()
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, use_reloader=False)