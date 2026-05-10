# Peridot — Changelog
> Engineered by uncoalesced

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
