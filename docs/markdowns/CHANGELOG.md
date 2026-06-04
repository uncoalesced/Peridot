# Peridot - Changelog
> Engineered by uncoalesced


---


## [v1.5.0-STABLE] - 2026-06-03

**Name:** Peridot v1.5.0 STABLE - Sovereign Kernel Architecture & Split Tensor Allocation



### Core Engine Architecture & Hardware Arbitration



- **14B Model Pivot & Split Tensor Allocation:** Bypassed the planned 7B tier and transitioned the core inference weights to the high logic Qwen2.5-14B-Instruct-Q4_K_M to permanently resolve RAG hallucinations. `GPU_LAYERS` in `config.py` was adjusted to 20, safely splitting the 14B parameter load between the 8GB RTX 5050 GPU and Ryzen 7 CPU RAM.

- **Structural Watchdog Hardening & VRAM Purge:** Completely upgraded the `_execute_vram_purge` method inside the VRAM State Machine. Integrated direct NVIDIA driver querying via `pynvml` to calculate actual reclaimed physical bytes before allocating tensors, bypassing unreliable OS cache metrics.

- **FSM Panic Tuning & Hardware Ceiling:** Enforced a strict 7500MB FSM hard ceiling for display driver preservation. Lowered the VRAM purge safety threshold from 1.5GB to 200MB, preventing recursive 503 errors under the new 14B load. If the GPU fails to clear thresholds within a 2.0-second timeout, the FSM instantly trips a KERNEL PANIC.

- **System Prompt Hardening:** Re-engineered `build_system_prompt` to intercept RLHF conversational tropes. Injected explicit constraints forcing the model to refuse queries outside of provided RAG contexts, neutralizing knowledge-bleed defects.



### Interface & Operator UX



- **Multi-Tab Notebook Migration:** Replaced the legacy single-buffer UI with a `ttk.Notebook` framework, introducing three sectors:

  - CHAT MATRIX (text generation)

  - KERNEL VAULT (live RAG tracker)

  - SETTINGS (hardware configuration)

- **Control Console UI & Live Telemetry:** Deployed an industrial, low-overhead administrative dashboard fetching from the secured `/telemetry/stability` endpoint. Displays live FSM states, dynamic system health scores, total inferences, and panic counts.

- **Research Core Toggles:** Integrated UI control switches mapping to internal `/telemetry/enable` and `/research/disable` HTTP pathways, allowing operators to authorize or suspend Folding@Home cycles directly from the interface.

- **Hardware-Aware Model Swapper:** Engineered a dynamic directory scanner that evaluates local `.gguf` file sizes against the 8GB RTX 5050 VRAM envelope. Assigns runtime compatibility ratings (`[HIGH]`, `[MEDIUM]`, `[LOW/CRITICAL]`) and supports GUI hot-swapping through `config.py` rewriting.

- **144Hz Kinetic Scrolling:** Replaced Tkinter's default scroll behavior with a custom 5ms (200Hz) sub-pixel velocity decay loop for high  refresh rate rendering.



### Ingestion & RAG Pipeline



- **Standalone Command-Line Ingestion (`ingest_vault.py`):** Added an isolated CLI script to parse, chunk, embed, and commit files directly to the FAISS L2 database without touching the GUI. Embeddings are generated strictly through the CPU-bound Aether-Route.

- **Binary PDF & Deep Semantic Search:** Upgraded ingestion to dynamically decode binary PDF text layers via PyPDF2. Increased FAISS retrieval depth from `top_k=3` to `top_k=6` for denser multi-document context injection.

- **Sliding Window Chunking:** Replaced the legacy double-newline chunker with a strict character-clamped fragmentation system (<800 characters) to improve vector precision and reduce dilution.

- **Staging Cleanup Automation:** Processed files are automatically relocated from `input/` to `input/processed/` to prevent recursive re-ingestion and maintain a clean archive.



### Fixes, Optimizations & Repository Hygiene



- **AVX2 Matrix Restoration:** Reverted the Python environment to a stable NumPy 1.x baseline to resolve the fatal C-extension `_ARRAY_API` crash during vector initialization.

- **Live Buffer Search & UI Extraction:** Added a `Ctrl+F` real-time search overlay with highlight support and a `_copy_to_clipboard` function for instant Markdown extraction.

- **Global Instantiation Fix:** Patched a catastrophic `NameError` crash loop by explicitly instantiating `PeridotProductionKernel()` in the global scope before engine boot execution.

- **Git Integrity & Cleanup:** Updated `.gitignore` to block transient FAISS binary files (`aether_cold_storage.db`) from entering version control. Executed a cleanup sweep locking configuration, UI, and backend changes into the stable `origin/main` tree.

"""

---

## [v1.4.0-STABLE] - 2026-05-14
**Name:** Peridot v1.4.0 STABLE — TurboQuant Architecture & Sovereign Runtime Finalization

### Core Engine Architecture (TurboQuant)

- **Deprecated Legacy K-Quants:** Purged the default `Llama-3-8B-Instruct (Q4_K_M)` baseline due to unacceptable memory bus saturation (~6.6GB VRAM footprint) on 8GB hardware.
- **Integrated Importance Matrix (I-Quant) Support:** Shifted the primary inference engine to natively support `IQ3_XXS` and FP4 execution paths. Vaporized ~1.5GB of VRAM overhead while increasing deep-reasoning inference throughput.
- **Dual-Profile Bootstrapping:** Hardcoded two primary runtime profiles inside `config.py` for dynamic loading:
  - **Deep Thinker Profile:** `Llama-3-8B-Instruct (IQ3_XXS)` achieving **60.5 t/s** at ~4.5GB VRAM.
  - **Agile / Daily Driver Profile:** `Qwen 2.5 3B (Q4_K_M)` achieving **101.9 t/s** at ~2.7GB VRAM.
- **Thermal & Context Limits:** Locked the baseline context window to **8192 tokens** and dropped the default engine temperature to **0.1** to enforce strict, hallucination-resistant RAG document citation behavior.
- **Sliding Context Preservation:** Retained the lightweight sliding conversational window internally to preserve RAM stability during prolonged execution sessions.

### System Initialization & Security Perimeter

- **Setup Wizard Overhaul (`setup.py`):** Rewrote the installation pipeline into a hardware-aware deployment interface. The wizard now actively profiles GPU VRAM pools and dynamically recommends runtime profiles to prevent Out-Of-Memory (OOM) deployment failures.
- **Engine Tuning Interface:** Injected a dedicated initialization-stage tuning layer allowing operators to explicitly choose between:
  - Deep Thinker (maximum reasoning depth)
  - Agile / Daily Driver (maximum throughput)
- **Manual Matrix Override:** Added advanced profile bypass logic exposing raw runtime selection for unsupported or experimental hardware deployments.
- **Cryptographic Handshake Integration:** Completely abandoned the legacy static `config.json` authentication paradigm. System initialization is now locked behind a securely generated `.env` file containing a localized 16-byte hex `API_KEY`.
- **Air-Gap Enforcement:** The setup wizard now automatically injects:
  ```text
  HF_HUB_OFFLINE=1
  TRANSFORMERS_OFFLINE=1
  ```
  into the environment to permanently sever unauthorized HuggingFace telemetry and outbound network synchronization.
- **AGPL-3.0 Migration:** Upgraded the Peridot kernel licensing structure from MIT to AGPL-3.0 to preserve sovereign-source transparency across derivative deployments and hosted modifications.

### State-Machine & Medical Handoff (Folding@Home)

- **Zero-Latency Interrupt Protocol:** Finalized the WebSocket interrupt architecture. When a prompt hits the API, the Peridot kernel dispatches the Folding@Home pause payload in ~21ms and fully purges the VRAM allocation buffer in under 510ms.
- **Aggressive Idle Return:** Reduced the `RESEARCH_IDLE_THRESHOLD` to **30 seconds** to maximize distributed medical research contribution when the user is not actively generating tokens.
- **Aether-Route CPU Offloading:** Hardcoded the semantic embedding engine (`all-MiniLM-L6-v2`) to execute strictly on CPU/RAM resources (e.g., Ryzen 7 DDR5 memory footprint), preserving 100% of GPU VRAM for inference and Folding@Home transitions.
- **Persistent Research Arbitration:** Refined VRAM ownership logic to maintain deterministic hardware handoffs without requiring inference engine restarts.

### Performance

- **TurboQuant Throughput Validation:** Established the new stable benchmark baseline:
  - `Llama-3-8B-Instruct (IQ3_XXS)` → **60.5 tokens/sec**
  - `Qwen 2.5 3B (Q4_K_M)` → **101.9 tokens/sec**
- **Reduced VRAM Saturation:** Lowered active inference VRAM consumption from ~6.6GB to ~4.5GB under Deep Thinker mode.
- **Improved Tensor Allocation Stability:** Reduced CUDA allocation pressure during sustained inference + Folding@Home coexistence.
- **Enhanced Low-VRAM Runtime Reliability:** Optimized execution stability for systems operating below the 8GB VRAM threshold while preserving CPU-only fallback capability.

### Architecture

- **Aether-Route v1.4:** Expanded the routing layer with:
  - CPU-isolated semantic embedding
  - deterministic VRAM preservation
  - improved telemetry-aware execution
  - hardware-aware RAG arbitration
- **Inference Pipeline Refinement:** Refactored orchestration boundaries between:
  - embedding execution
  - tensor generation
  - VRAM arbitration
  - telemetry polling
- **Hardware-Aware Runtime Scaling:** Improved dynamic runtime behavior on:
  - constrained VRAM systems
  - Ryzen AI processors
  - CPU-only deployments
  - multitasking inference environments

### Security

- **Offline Enforcement Hardening:** Strengthened sovereign telemetry suppression by enforcing offline execution during setup initialization rather than post-launch configuration.
- **Expanded Authentication Isolation:** Refined `.env` handling to eliminate residual static credential dependencies.
- **Runtime Boundary Preservation:** Hardened subsystem isolation between:
  - telemetry
  - inference
  - RAG execution
  - GhostLogger auditing
  - Folding@Home orchestration

### Changed

- **README Overhaul:** Completely rebuilt repository documentation around the v1.4 STABLE runtime architecture, including:
  - TurboQuant execution profiles
  - sovereign network topology
  - VRAM allocation diagrams
  - hardware handoff visualization
  - Aether-Route topology mapping
- **Benchmark Visualization Infrastructure:** Added dedicated benchmark illustrations and engineering diagrams for performance validation and architecture transparency.
- **Stable Release Transition:** Removed beta-stage medical research warnings and finalized the sovereign runtime stack as the official v1.4 STABLE baseline.

---

## [v1.3.2-beta] - 2026-05-13
**Name:** Peridot v1.3.2 - Memory Deduplication, Meta-Citations & Sovereign Telemetry

### Security
- **Environment-Level Cryptography:** Migrated the `API_KEY` completely out of Python source code and into a localized `.env` file. Established `.env.example` and locked `.gitignore` to prevent automated scraping of the host's cryptographic handshake.
- **Client-Server Handshake Hardening:** Patched `core.py` to securely transmit explicit `Authorization: Bearer` headers during both standard inference and system shutdown operations.

### Added
- **Hash-Based Memory Deduplication:** Upgraded `vector_store.py` with a persistent `registry.json` tracking system. It now calculates SHA-256 hashes of all ingested files to prevent redundant vector embeddings and save CPU cycles.
- **Explicit Source Citations:** Engineered the RAG Context-Injection loop in `server.py` to dynamically tag semantic blocks with `[SOURCE: filename]`. The LLM is now structurally instructed to cite its specific documentary sources during generation.
- **Automated Ingestion Runner:** Shipped `index_all.py`, a dedicated ingestion script that automatically scans the `input/` zone, extracts text, checks the deduplication registry, and commits new data to the FAISS index.

### Changed
- **Sovereign Telemetry Override:** Forced the `sentence-transformers` and `huggingface_hub` libraries into strict offline mode via global environment variables (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`). This permanently silences network-check warnings and maintains a true air-gapped architecture.
- **Context Search Depth:** Increased the `vector_store` retrieval depth (`top_k=3`) to feed the LLM denser contextual clusters for more accurate multi-source answers.
- **Configuration Bootstrap:** Rewrote `config.py` to prioritize `load_dotenv()` before any secondary module imports, ensuring environment variables govern the entire kernel boot sequence.

### Fixed
- **403 Forbidden Handshake Failure:** Resolved a critical client-server desynchronization bug where `config.py` was generating conflicting `secrets.token_hex(16)` keys for independent processes. The key is now statically anchored to the `.env` file.
- **Flask Payload Rejection:** Fixed silent failures in the Neural Link by explicitly forcing the `"Content-Type": "application/json"` header in `requests.post()` calls originating from `core.py`.

---

## [v1.3.1-beta] - 2026-05-11
**Name:** Peridot v1.3.1 - Aether-Route Architecture & RAG Synchronization

### Added
- **Aether-Route (CPU Semantic Router):** Engineered a high-efficiency routing layer that offloads vectorization and intent classification to the Ryzen 7 CPU. This preserves VRAM on 4GB/6GB hardware by keeping the embedding matrix strictly in system RAM.
- **Split-Payload Architecture:** Implemented a decoupled communication protocol between `core.py` and `server.py`. The system now transmits an isolated query for semantic mapping and a full prompt for LLM ingestion, preventing chat history from corrupting vector search accuracy.
- **Unified Aether-Audit:** Integrated all RAG subsystems into the ghost auditing module, providing real-time telemetry on VRAM states, routing latency, and inference speeds.

### Changed
- **Server-Side Cache Centralization:** Stripped the duplicate L1 memory cache from `core.py` and centralized all caching logic within `server.py` to eliminate client-server race conditions and redundant CPU cycles.
- **Contextual Injection Logic:** Updated the RAG pipeline to prepend L2 Vault findings into the system instruction block rather than the user prompt, improving the LLM's adherence to retrieved document data.
- **CLI Ingestion Interface:** Overhauled `vault.py` with a standalone CLI entry point, enabling batch ingestion of the `input/` directory via `python core_system/memory/vault.py ingest`.

### Fixed
- **L1 Cache Signature Collision:** Resolved fatal `TypeError` crashes where the Router was passing incorrect argument counts to `EphemeralCache.add()` and `EphemeralCache.search()`.
- **GhostLogger Formatting Bug:** Fixed a system-wide crash caused by improper string formatting (`TypeError: not all arguments converted`) inside the ghost auditing calls.
- **The "Thermodynamics Loop":** Corrected a logic flaw where the router was embedding the entire conversational buffer, leading to 95%+ semantic overlap and causing the system to get stuck repeating previous cached answers.
- **Pathing Import Failures:** Injected absolute root discovery (`sys.path.insert`) into `vault.py` and `main.py` to resolve `ModuleNotFoundError` when running scripts from different terminal directories.
- **Windows File-Locking:** Implemented robust garbage collection and context management in the ingestion pipeline to ensure PDF file pointers are released immediately after vectorization.

### Optimized
- **Ryzen 7 250 AI Alignment:** Optimized the `all-MiniLM-L6-v2` embedding engine to utilize Ryzen multi-core efficiency, reducing query vectorization latency to <30ms.
- **Inference Telemetry:** Refined the benchmarking output to provide real-time tokens-per-second (tps) metrics and precise VRAM delta tracking during Aether-Route execution.

---

## [v1.3.0-beta] - 2026-03-30
**Name:** Peridot v1.3.0 - Dual-Tier Memory Engine & Sterile RAG Architecture

### Added
- **Dual-Tier Memory Engine:** Implemented Layer 1 Ephemeral RAM Cache for instant query interception and Layer 2 FAISS Persistent Vault for local PDF knowledge retrieval.
- **Sterile RAG Extraction (`_ask_ai_isolated`):** Engineered an isolated inference pipeline in `core.py` to bypass standard conversational memory, strictly preventing context poisoning and hallucinations when querying the L2 Vault.
- **Command Routing Subsystem:** Deployed `CommandRouter` to safely isolate system operations from standard LLM inference.
- **Dynamic Ingestion Command:** Added the `ingest` command to the router, allowing users to trigger PyMuPDF extraction and SentenceTransformer vectorization on the `input/` directory directly from the UI.
- **Silent Forensic Auditing (GhostLogger):** Implemented a non-blocking background logger in `core_system/audit.py` that writes to a 1MB rotating file without polluting the terminal UI.
- **API Authentication Middleware:** Secured the Neural Engine by implementing `@require_auth` with Bearer token validation across all operational endpoints.
- **Comprehensive Benchmark Suite:** Engineered custom stress-testing scripts for cold start metrics, VRAM handoff latency, memory stability, and L2 semantic search speed.

### Changed
- **Vault Intercept Logic:** Stripped the automatic PDF database search from the default conversational loop. The Vault is now strictly gated behind the explicit `vault [query]` command to preserve VRAM and conversation fluidity.
- **FAISS Semantic Threshold:** Relaxed the L2 distance threshold in `vault.py` from 1.5 to 1.85 to allow shorter, highly specific queries to successfully match with longer document chunks.
- **API Payload Structure:** Updated the core inference endpoint from `/chat` to `/ask` and modified the required JSON payload key from `"prompt"` to `"command"` to align with the v1.3 architecture.
- **Version String:** Bumped system designation from v1.2.1 BETA to v1.3 STABLE.

### Fixed
- **Context Poisoning Hallucinations:** Resolved the bug where the LLM would blend previous chat history with RAG extraction data by forcing sterile prompt injection.
- **Windows File-Locking Bug ([WinError 32]):** Fixed ingestion crashes by implementing strict context managers (`with fitz.open(...) as doc:`) and forced Python garbage collection to release OS-level file pointers after vectorization.
- **Hardware Architecture Collisions:** Hardcoded the Vault Embedding Engine (`all-MiniLM-L6-v2`) to run exclusively on the CPU, preventing `sm_120` architecture clashes with the GPU during LLM inference.
- **Benchmark Timeout Failures:** Rewrote the benchmarking suite to target the correct v1.3 endpoints, inject the required API keys, and account for the 8-billion parameter model load times during cold starts.
- **Logger Attribute Error:** Patched an upstream integration bug by aliasing the deprecated `.record()` method to the native `.info()` method inside `setup_ghost_logger`.

---

## [v1.2.2-beta] - 2026-03-14
**Name:** Peridot v1.2.2 - Empirical Benchmarking & Security Upgrades

### Security
- **RAM-Only Authentication (CWE-312 Mitigation):** Completely removed disk-based API key storage (`auth.token`). The kernel now generates ephemeral cryptographic keys in RAM via `os.environ` that evaporate upon shutdown.
- **Application-Layer Input Sanitization:** Implemented a pre-inference regex filter to destroy malicious code injection attempts (e.g., XSS payloads, `os.system` execution) before they reach the LLM.
- **Strict Path Traversal Blacklist:** The kernel now explicitly blocks attempts to read sensitive system directories (e.g., `C:\Windows\System32`, `/etc/`) and cryptographic material (e.g., `.ssh/id_rsa`, `.env`).
- **Subprocess Command Whitelisting:** Hardcoded the Medical Research (Folding@Home) WebSocket integration to strictly accept only `pause`, `unpause`, `finish`, and `shutdown` directives to prevent arbitrary command injection.
- **Timing-Attack Resistance:** Upgraded API authentication in `server.py` to use `secrets.compare_digest()` for Bearer token validation, preventing cryptographic timing attacks.
- **API Rate Limiting:** Enforced a strict 60 requests/minute limit per local IP address to mitigate local Denial-of-Service (DoS) and script-kiddie spam.
- **Constitution Fallback:** If `constitution.json` is missing or corrupted, the system safely defaults to a zero-trust state (`allow_file_read: False`).

### Added
- **Automated Penetration Testing:** Shipped `tests/security_tests.py`, an automated Red Team suite to barrage the local kernel and verify the containment field holds against actual payloads.
- **Empirical Benchmarking Suite:** Added `benchmarks/vram_test.py` and `benchmarks/inference_test.py` to measure precise hardware metrics rather than relying on estimates.
- **Security & Benchmark Policies:** Published `SECURITY.md` detailing the threat model and responsible disclosure, alongside `BENCHMARKING.md` for community hardware testing.
- **GhostLogger:** Integrated a zero-latency, asynchronous JSONL telemetry logger (`logs/ghost_audit.jsonl`) for tracking system state changes without blocking the main OS loop.
- **Security Logger:** Added a dedicated forensic logger (`logs/security.log`) to quietly record all blocked file accesses, rejected inputs, and authentication failures.

### Changed
- **Verified Hardware Metrics:** Replaced the estimated README hardware claims with empirical data tested on an RTX 5050: **6.55ms** VRAM hot-swap latency and **45-55 t/s** Llama-3 8B inference speed.

### Fixed
- **CodeQL CWE-312 Vulnerability:** Permanently patched clear-text storage of sensitive information by migrating the API key entirely to ephemeral RAM.

---

## [v1.2.1-beta] - 2026-03-10
**Name:** Peridot v1.2.1 - Security Changes, Patched Memory Leaks & Secured Command Routing

### Security
- **Localhost API Authentication:** Implemented dynamic API key generation (`auth.token`) and strict Bearer token authentication across all Flask endpoints to prevent unauthorized local processes from hijacking GPU resources.
- **Hardened System Directives:** Updated the core AI system prompt to establish a hard boundary against OS-level destruction. Peridot now explicitly refuses commands that attempt to delete system files, compromise host OS integrity, or exfiltrate sensitive data over the network, while maintaining uncensored operation for standard tasks.

### Added
- **True Hardware Telemetry:** Integrated `pynvml` (via `nvidia-ml-py`) into the VRAM State Machine to provide real-time NVIDIA GPU memory tracking and reporting.
- **Server Health Polling:** Added a `/health` endpoint to `server.py` to allow client processes to safely verify engine readiness before mounting the interface.

### Changed
- **WebSocket VRAM Hot-Swaps:** Completely removed legacy CLI subprocess polling for Folding@Home. The VRAM State Machine now communicates directly with the FAH v8 client via local WebSockets (port 7396), achieving true zero-latency (21ms) hardware handoffs.
- **State Machine Localization:** Moved the medical research state manager entirely into `server.py`, directly coupling it to the LLM lifecycle.
- **Command Routing:** Overhauled `command_router.py` to execute hardware requests via secure HTTP API calls rather than direct object manipulation.

### Fixed
- **Memory Leak Patch:** Fixed an unbounded array in `core.py` where chat history would scale infinitely and crash the application. Implemented a sliding context window that strictly retains only the last 10 messages (5 turns) to protect RAM/VRAM capacity.
- **Client Startup Crash:** Injected a `sys.path` override into `main.py` to resolve unpredictable "No module named X" import failures when spawned as a subprocess by the launcher.
- **Launcher Race Conditions:** Replaced arbitrary `time.sleep()` delays in `launcher.py` with robust endpoint polling, preventing the client from attempting to connect to a dead or loading server.
- **Subprocess Deadlocks:** Rerouted server `stdout` and `stderr` to a dedicated file (`logs/server.log`) to prevent application freezes caused by filled buffer pipes.
