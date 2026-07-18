# CLAUDE.md — Peridot Sovereign Kernel Master Context
### System Directive for Claude Code: Lead AI Architect & Security Engineer

---

## 0. AGENT IDENTITY PROTOCOL (READ FIRST — NON-NEGOTIABLE)

### 0.1 Administrator Identification
The administrator's name was stated once at the start of this session. You must:
- Address the administrator **exclusively by that name** for the entire session.
- **Never** substitute a title (`Sir`, `User`, `Admin`, `Developer`), a pronoun (`you`), or any placeholder.
- **Never** ask "what should I call you?" — the name was already given.
- If you cannot recall the administrator's name with certainty, **do not guess**. State: `"I cannot confirm your name with certainty. Please start a new session."` Then stop.
- A wrong name or a forgotten name is a signal of context corruption. A new session is the correct response, not a retry.

This rule exists to detect hallucination drift. Violating it invalidates the session.

---

### 0.2 Mandatory Audit Log
After **every file you create or modify**, you must append a structured entry to:

```
E:\Peridot\docs\markdowns\AUDIT.md
```

**If the file does not exist, create it.** Never skip this step. The audit log is a non-negotiable part of every operation.

**Audit entry format:**
```markdown
---
## [AUDIT] {DATE} {TIME} — {OPERATION TYPE}

**Session:** {Brief description of what the administrator asked for}
**Files Modified:**
- `{filepath}` — {one-line description of what changed and why}

**Structural Changes:**
{Detailed technical description of every change: what was added, removed, or restructured, and the security/architectural reasoning behind it.}

**Security Implications:**
{Any security considerations introduced, resolved, or deferred.}

**Roadmap Alignment:**
{Which roadmap milestone (e.g., v1.5.3, v1.6.0) this work targets and whether it conflicts with any upcoming milestone.}

**Outstanding Items:**
{Anything left incomplete, deferred, or requiring follow-up.}
---
```

No entry may be vague. Entries must be precise enough that a future engineer reading the log understands exactly what changed and why, without reading the diff.

---

## 1. PROJECT PHILOSOPHY & DIRECTIVES

Peridot is a **fully-offline, GPU-accelerated LLM inference system** — a zero-telemetry sovereign alternative to cloud AI. These principles are absolute and must be preserved across every contribution.

### 1.1 Absolute Sovereignty (Zero Cloud)
Peridot does not phone home. No telemetry, no remote inference APIs, no silent tracking.

- External libraries are forcibly isolated: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`.
- These variables must be injected into the OS environment **before any subprocess is spawned** — enforced in `launcher.py` via `load_dotenv()` before all imports.
- No new dependency may introduce a network call, even an optional one, without explicit opt-in gating.

### 1.2 Defense-in-Depth
The host OS is trusted. The AI model, local processes, and all inbound data are **not**.

- All user input is treated as hostile until sanitized.
- The model is **prohibited** from self-modifying `server.py` or any core module.
- Agentic code generation must execute in a sandboxed `workspace/` directory only.
- `shell=True` is **eradicated**. All subprocess calls use strict argument arrays.
- No `pickle` deserialization anywhere in the codebase (RCE risk).

### 1.3 Hardware-Aware Orchestration
Inference is the **absolute priority**. Idle GPU compute is altruistically donated to Folding@Home for medical research. The two must coexist without friction.

### 1.4 Code Standards
- **No dead code.** Every module written must be wired into the active execution pipeline immediately.
- **No hallucinated cloud dependencies.** Every database, embedder, and search library must run 100% locally.
- **No bare `except:` clauses.** Use `except Exception:` at minimum.
- **`functools.wraps`** must wrap all decorator inner functions (Flask auth decorators included).
- **Strict import management.** Only use libraries pinned in `requirements.txt` / `pyproject.toml`. New dependencies require explicit addition with pinned versions.
- All logging must route through the unified `ghost` logger (`core_system/audit.py`). `print()` is permitted only for boot-sequence terminal output.

---

## 2. HARDWARE CONSTRAINTS & VRAM STATE MACHINE

### 2.1 Target Hardware
Peridot is meticulously optimized for **constrained consumer architectures**:

| Component | Primary Target | Secondary Target |
|-----------|---------------|-----------------|
| GPU | NVIDIA RTX 5050 Laptop (8GB VRAM) | NVIDIA RTX 3060 (12GB VRAM) |
| CPU | AMD Ryzen 7 250 AI | Any modern x64 (8+ threads) |
| RAM | 16GB DDR5 | 16GB DDR4 |
| OS | Windows 11 (primary) | Ubuntu/Debian Linux |

### 2.2 Kernel Finite State Machine (FSM)
**Location:** `core_system/runtime/kernel.py` and `core_system/runtime/hardware.py`

The VRAM State Machine governs every hardware transition. The state graph is strictly linear — no state may be skipped or bypassed:

```
BOOT → IDLE → FAH_ACTIVE → INTERRUPT_WAIT → VRAM_PURGE → INFERENCE → COOLDOWN → PANIC
```

**State definitions:**

| State | Description |
|-------|-------------|
| `BOOT` | Model loading into VRAM. F@H is paused. |
| `IDLE` | Model loaded. No active prompt. F@H eligible if `research_allowed=True`. |
| `FAH_ACTIVE` | F@H owns ~96% of available VRAM. Inference locked. |
| `INTERRUPT_WAIT` | Prompt received. WebSocket SIGSTOP dispatched to F@H. Waiting for yield confirmation. |
| `VRAM_PURGE` | Actively polling pynvml until reclaimed VRAM exceeds threshold. |
| `INFERENCE` | GPU fully allocated to LLM. F@H locked out. |
| `COOLDOWN` | Inference complete. VRAM GC executed. Transitioning back to IDLE. |
| `PANIC` | Hardware failed to yield within timeout. 503 thrown. Requires manual restart. |

### 2.3 VRAM Handoff Specifications
- **F@H interface:** Local WebSocket on port `7396` (`ws://127.0.0.1:7396/api/websocket`)
- **Pause payload:** `{"cmd": "state", "state": "pause"}`
- **Resume payload:** `{"cmd": "state", "state": "fold"}`
- **Observed average handoff latency:** ~21ms
- **Maximum tolerated handoff latency:** 510ms
- **Watchdog timeout:** 2.0 seconds hard ceiling before PANIC is tripped
- **Free VRAM safety threshold:** 200MB minimum before inference is permitted
- **Hard VRAM ceiling:** 7500MB (protects Windows kernel memory)

### 2.4 Split-Tensor Allocation
Large models that exceed 8GB VRAM are split between GPU and system RAM:

| Card | GPU_LAYERS | VRAM Used | RAM Used |
|------|-----------|-----------|---------|
| RTX 5050 8GB | 20 | ~4.5GB | ~remainder in DDR5 |
| RTX 3060 12GB | 99 | ~full fit | minimal |

`GPU_LAYERS` must always be set in `config.py`. `server.py` must **always** pass `GPU_LAYERS` to `Llama()` — never hardcode `n_gpu_layers`.

### 2.5 VRAM Garbage Collection (Mandatory)
At the end of every `/ask` route, inside a `finally:` block without exception:

```python
finally:
    import gc
    import torch
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    kernel.event_queue.put("INFERENCE_COMPLETE")
```

Failure to include this will cause VRAM fragmentation over extended sessions.

---

## 3. RAG ARCHITECTURE: "AETHER-ROUTE"

All semantic retrieval, indexing, and reranking is **100% CPU-bound**. The GPU is never touched during retrieval — it is reserved exclusively for LLM token generation.

### 3.1 Parent-Child Hierarchical Chunking

```
Raw File (PDF/TXT/JSON)
    │
    ├── [Parent Chunks] — 1024 tokens
    │     • Stored as raw strings (no embeddings)
    │     • Parsed via PyMuPDF fitz with sort=True
    │       (preserves multi-column table structure)
    │
    └── [Child Chunks] — 200–256 tokens, 50-token overlap
          • Projected into 384-dimensional dense vectors
          • Upon vector match → parent chunk fed to LLM
            (prevents context starvation from truncated chunks)
```

**Provenance tagging:** Every chunk must prepend `[SOURCE DOC: {filename}]` before embedding. This is mandatory — the LLM must be able to cite its sources explicitly.

### 3.2 LanceDB Hybrid RRF Retrieval Pipeline

```
User Query
    │
    ├── Dense Path: all-MiniLM-L6-v2 → 384-dim vector → LanceDB ANN search
    │
    └── Sparse Path: LanceDB Tantivy FTS (BM25 exact-keyword match)
            │
            └── Reciprocal Rank Fusion (RRF, K=60)
                    │
                    └── Top 20 child chunks → map to deduplicated parent chunks
                            │
                            └── FlashRank Cross-Encoder (ONNX, zero VRAM)
                                    │
                                    └── Top 3 mathematically proven chunks
                                            │
                                            └── Injected into LLM context window
```

**Key constraints:**
- Embedder: `all-MiniLM-L6-v2` (CPU-only, 384 dimensions)
- Reranker: FlashRank ONNX cross-encoder (zero GPU usage)
- RRF smoothing constant: `K=60`
- Final context injection: maximum 3 parent chunks

### 3.3 Tiered RAM/NVMe Cache

| Tier | Location | Limit | Eviction |
|------|----------|-------|----------|
| L1 — Active | DDR5 RAM (EphemeralCache) | 50 items LRU | Evict oldest to L2 |
| L2 — Cold | NVMe SQLite (`storage/aether_cold_storage.db`) | Disk-bound | Manual purge |

When L1 breaches 50 items, the oldest vectors are autonomously written to the SQLite cold store, not dropped.

### 3.4 Security: No Pickle
The vault must use **JSON or `.safetensors` serialization only**. `pickle` is banned — it is an arbitrary code execution vector. Any legacy `.bin` or `.pkl` file in the storage pipeline is a critical security defect.

---

## 4. CONVERSATIONAL MEMORY

**Location:** `core_system/memory/chat_ledger.py` (SQLite-backed)

### 4.1 Sliding Window Constraint
To prevent context overflow within the 4096–8192 token budget:

```python
get_history(session_id, limit=6)  # Hard cap: last 3 exchanges (6 messages)
```

This is enforced. Do not increase this limit without a corresponding context budget analysis.

### 4.2 Dual-Phase Execution Protocol
Governed by `config/constitution.json`. The LLM is **forced** into a two-phase output format to eliminate hallucination and conversational filler:

```
[ANALYSIS]
• Context status: Available / Empty
• Domain classification
• Silent factual validation of retrieved chunks
• (Never rendered to the user — collapsed by UI)

[KERNEL_RESPONSE]
• Direct, unfiltered answer
• No filler phrases ("Great question!", "Certainly!")
• No asterisks, no moralizing, no hedging
• Cites [SOURCE DOC: filename] if context was used
```

**Anti-pattern mandate (hardcoded into system prompt):**
> "You are forbidden from stating 'The term X does not appear in the context'. Evaluate context silently. If empty, pivot to a sharp, minimal objective summary."

---

## 5. SECURITY POSTURE

### 5.1 Authentication
- No hardcoded API keys anywhere in the codebase.
- `config.py` generates `secrets.token_hex(32)` on first boot and writes to `.env`.
- `.env` is written with `os.O_WRONLY | os.O_CREAT | os.O_TRUNC` and file mode `0o600` (owner read/write only).
- API key is loaded into `os.environ` and passed to child processes via `custom_env = os.environ.copy()` in `launcher.py`.

### 5.2 Network Isolation
- Flask-CORS is clamped strictly to `127.0.0.1` and `localhost`. No external origin is permitted.
- Flask-Limiter enforces **60 requests/minute** on `/ask` and `/ingest` routes to prevent local DoS.
- WebSocket connections are outbound-only (to F@H on port 7396). No inbound WebSocket server.

### 5.3 Subprocess Safety
- `shell=True` is **completely eradicated**. Every subprocess call uses a strict argument array.
- External process calls (e.g., `nvidia-smi`) must use `subprocess.run([...], capture_output=True, text=True, check=True)`.

### 5.4 RCE Prevention
- The model cannot self-modify `server.py`, `config.py`, or any `core_system/` module.
- Agentic code generation executes exclusively in `workspace/` (sandboxed, ephemeral).
- No `eval()`, `exec()`, or `__import__()` usage in any code path reachable from user input.

### 5.5 Input Sanitization
- All user input is treated as hostile.
- Path traversal attempts (`../`) are neutralized via `Path.resolve()` before any file operation.
- Blocked patterns must be validated before reaching the LLM inference layer.

---

## 6. SOFTWARE STACK

### 6.1 Backend
| Component | Technology |
|-----------|-----------|
| Inference Engine | `llama_cpp_python` (cuBLAS/CUDA backend) |
| API Server | Flask (`server.py`, decoupled into `core_system/`) |
| Vector Store | LanceDB (Dense + Sparse hybrid) |
| Embedder | `sentence-transformers` — `all-MiniLM-L6-v2` (CPU) |
| Reranker | FlashRank ONNX cross-encoder (CPU, zero VRAM) |
| Conversational Memory | SQLite via `chat_ledger.py` |
| Cold Cache | SQLite via `diskcache` / raw `sqlite3` |
| GPU Telemetry | `pynvml` (driver-level VRAM polling) |
| System Telemetry | `psutil` |
| PDF Parsing | `PyMuPDF (fitz)` with `sort=True` |
| Audio | `openai-whisper` (offline) |

### 6.2 Frontend — "Glass Box UI"
**Location:** `ui.py` (Custom Tkinter)

| Feature | Implementation |
|---------|---------------|
| Kinetic scrolling | 144Hz/200Hz, 5ms sub-pixel velocity decay loop |
| Sessions drawer | Collapsible `[>] SESSIONS` via `PanedWindow` |
| Icon rendering | `PIL Image.LANCZOS` anti-aliasing |
| Analysis phase | Stealth `[+] trace_cognition` drop-down masking `[ANALYSIS]` block |
| Model swapper | Scans `models/` for `.gguf` and `.safetensors`, calculates VRAM footprint vs 8GB budget, ranks `[HIGH]` / `[MEDIUM]` / `[LOW/CRITICAL]` |

### 6.3 Config & Constitution
| File | Purpose |
|------|---------|
| `config.py` | Hardware allocation, model path, inference params, network config |
| `config/constitution.json` | Identity, language constraints, behavioral rules, dual-phase mandate |
| `.env` | Runtime secrets (`API_KEY`, `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`) |

---

## 7. ARCHITECTURAL ROADMAP

You must execute work knowing exactly where the system is headed. **Do not implement features that conflict with upcoming milestones.**

### v1.5.3 — Sanity & Polish *(Current Focus)*
- [ ] Silence non-critical warnings (`faiss.swigfaiss_avx512`)
- [ ] Fix absolute import paths → enforce relative imports within `core_system/`
- [ ] Enforce VRAM GC (`gc.collect()`, `torch.cuda.empty_cache()`) in `finally:` block on `/ask` route
- [ ] Standardize all logging to unified `ghost` logger
- [ ] Eradicate remaining bare `except:` clauses → `except Exception:`
- [ ] Add `functools.wraps` to all Flask auth decorators
- [ ] Add `TRANSFORMERS_OFFLINE=1` to `.env` generation in `setup.py`

### v1.6.0 — Cross-Platform Core & TurboVec
- [ ] **Linux Migration:** Purge all Windows-exclusive paths. Enforce OS-agnostic `pathlib.Path` throughout.
- [ ] **TurboVec Integration:** Replace FAISS with TurboVec (Rust-based).
  - WHT rotation + Lloyd-Max scalar quantization (4-bit/2-bit)
  - SIMD-accelerated metadata filtering
  - Shrinks 10M docs from 31GB → 4GB

### v1.6.5 — Provider Decoupling
- [ ] Build abstract `BaseInferenceProvider` router
- [ ] Decouple `server.py` API layer from inference logic
- [ ] Enables hot-swapping inference backends without touching routes

### v1.6.8 — Unsloth Dynamic LoRA Engine
- [ ] Load static base model, hot-swap 150MB LoRA adapters based on prompt domain
- [ ] Adapters: Finance, Coding, Legal, General
- [ ] Zero additional VRAM overhead (LoRA layers only)

### v1.7.0 — The Multi-Engine Matrix
- [ ] **ExLlamaV2:** High-speed `.exl2` execution natively
- [ ] **vLLM:** PagedAttention, isolated via WebSockets to protect the UI thread
- [ ] **Native `.safetensors`:** Heuristic graph building and padded memory alignment for zero-copy `mmap` model loading
- [ ] **TurboQuant+:** Asymmetric KV Cache quantization (3-bit Keys, 2-bit Values) — 89% context compression on the fly

### v1.7.2 — Local Agentic Code Execution
- [ ] Deterministic Python REPL sandbox (E2B SDK) inside `[ANALYSIS]` phase
- [ ] Handles arithmetic and statutory accounting logic (neural networks cannot reliably do math)
- [ ] Target language support: Python, C, C++, Rust, Shell

### v1.7.5 — Semantic Graph Mapping (GraphRAG)
- [ ] Transition from flat vectors to Microsoft GraphRAG
- [ ] Extract entities during ingestion, map relationships into a network graph
- [ ] Enables hierarchical synthesis across multi-document knowledge bases

### v1.7.8 — Sovereign Web Gateway
- [ ] Opt-in, zero-telemetry web scraper triggered by JSON tool-calling
- [ ] Fetches HTML via headless DuckDuckGo + BeautifulSoup
- [ ] Sanitizes to ASCII, injects locally — no data leaves the machine

### v1.8.0 — Full-Stack Migration
- [ ] **Backend:** Migrate from Flask → FastAPI (native async, background tasks, WebSockets)
- [ ] **Frontend:** Migrate from Tkinter → React / SvelteKit (static compiled)
- [ ] Shatter the Tkinter performance ceiling permanently

---

## 8. FILE STRUCTURE REFERENCE

```
Peridot/
├── config.py                         # Hardware, model, inference, network config
├── server.py                         # Flask API — /ask, /ingest, /health, /telemetry
├── launcher.py                       # Ignition — boots server.py, waits for health, launches main.py
├── main.py                           # Entry point (UI launcher)
├── ui.py                             # Glass Box Tkinter UI
├── ingest_vault.py                   # CLI tool — sends /ingest to running server
├── debug_vault.py                    # CLI diagnostic — audits SQLite cold storage
├── setup.py                          # Interactive setup wizard (hardware detect, model download)
├── config/
│   └── constitution.json             # Dual-phase mandate, behavioral constraints, identity
├── core_system/
│   ├── audit.py                      # Ghost logger (unified logging)
│   ├── telemetry.py                  # Ledger — inference counts, handoff latency, panics
│   ├── rag_cache.py                  # AetherCache — tiered LRU RAM cache
│   ├── kernel.py                     # SovereignKernel FSM (states, transitions, watchdog)
│   ├── memory/
│   │   ├── ephemeral_cache.py        # L1 RAM cache (EphemeralCache)
│   │   ├── vault.py                  # FAISS / LanceDB persistent vector store
│   │   ├── embedder.py               # CPU sentence-transformer singleton
│   │   └── chat_ledger.py            # SQLite conversational memory (sliding window)
│   └── ingestion/
│       └── vector_store.py           # Ingestion pipeline (chunking, embedding, indexing)
├── models/                           # .gguf and .safetensors model files
├── input/                            # PDF/TXT/JSON drop zone for ingestion
│   └── processed/                   # Moved here after successful ingestion
├── storage/
│   └── aether_cold_storage.db        # SQLite L2 cold vector cache
├── logs/
│   ├── server.log                    # Neural engine stdout (overwritten each boot)
│   └── security.log                  # Security events (authentication failures, blocked input)
├── docs/
│   └── markdowns/
│       └── AUDIT.md                  # Mandatory audit log — appended after every change
├── workspace/                        # Sandboxed agentic code execution directory
└── .env                              # Runtime secrets (0o600, never committed)
```

---

## 9. KNOWN ISSUES TRACKER

Issues identified but not yet resolved. Clear these before closing a version milestone.

| ID | Severity | File | Description | Target |
|----|----------|------|-------------|--------|
| K-001 | HIGH | `server.py` | Busy-wait in `/ask` blocks Flask thread during hardware handoff (100 × 0.1s) | v1.5.3 |
| K-002 | MEDIUM | `server.py` | Missing `finally:` VRAM GC block on `/ask` route | v1.5.3 |
| K-003 | MEDIUM | `setup.py` | AMD ROCm GPU detection removed — README still claims support | v1.6.0 |
| K-004 | LOW | `setup.py` | Banner still reads v1.4 | v1.5.3 |
| K-005 | LOW | `debug_vault.py` | Hardcoded `storage/` path — should use `STORAGE_PATH` from config | v1.5.3 |
| K-006 | LOW | `requirements.txt` | `openai-whisper==20250625` — impossible version date, breaks fresh installs | v1.5.3 |

---

## 10. AGENT RULES SUMMARY (QUICK REFERENCE)

```
[OK] DO                                   [X] DO NOT
────────────────────────────────────    ────────────────────────────────────
Address admin by name from session      Guess the admin's name
Append to AUDIT.md after every change  Skip the audit log for "small" changes
Use ghost logger for all logging        Use print() inside core_system/
Use except Exception:                   Use bare except:
Use @functools.wraps on decorators      Manually set __name__ on inner funcs
Use pathlib.Path for all paths          Use os.path.join() or hardcoded strings
Use strict subprocess argument arrays   Use shell=True under any circumstance
Use GPU_LAYERS / CONTEXT_LENGTH config  Hardcode n_gpu_layers / n_ctx in Llama()
Add gc.collect() + cuda.empty_cache()  Leave VRAM unrecovered after inference
Run gc.collect() before moving files    Let PyMuPDF hold OS file locks on Windows
Wire new modules into the pipeline      Leave new code unreachable (dead code)
Pin versions in requirements.txt        Introduce unpinned dependencies
Keep all inference/storage 100% local   Import any cloud API or telemetry service
Check AUDIT.md tracker before coding    Implement things that conflict with roadmap
```

---

*PERIDOT SOVEREIGN KERNEL — Engineered by uncoalesced*
*This document is the absolute source of truth. When in doubt, this file wins.*
