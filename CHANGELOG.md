# Changelog

## [v1.2.2] - 2026-03-14
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
**Name:** Peridot v1.2.1 Beta - Security changes, Patched memory leaks, and secured command routing

### Security
- **Localhost API Authentication:** Implemented dynamic API key generation (`auth.token`) and strict Bearer token authentication across all Flask endpoints to prevent unauthorized local processes from hijacking GPU resources.
- **Hardened System Directives:** Updated the core AI system prompt to establish a hard boundary against OS-level destruction. Peridot now explicitly refuses commands that attempt to delete system files, compromise host OS integrity, or exfiltrate sensitive data over the network, while maintaining uncensored operation for standard tasks.

### Added
- **True Hardware Telemetry:** Integrated `pynvml` (via `nvidia-ml-py`) into the VRAM State Machine to provide real-time NVIDIA GPU memory tracking and reporting.
- **Server Health Polling:** Added a `/health` endpoint to `server.py` to allow client processes to safely verify engine readiness before mounting the interface.

### Changed
- **WebSocket VRAM Hot-Swaps:** Completely removed legacy CLI subprocess polling for Folding@home. The VRAM State Machine now communicates directly with the FAH v8 client via local WebSockets (port 7396), achieving true zero-latency (21ms) hardware handoffs.
- **State Machine Localization:** Moved the medical research state manager entirely into `server.py`, directly coupling it to the LLM lifecycle. 
- **Command Routing:** Overhauled `command_router.py` to execute hardware requests via secure HTTP API calls rather than direct object manipulation.

### Fixed
- **Memory Leak Patch:** Fixed an unbounded array in `core.py` where chat history would scale infinitely and crash the application. Implemented a sliding context window that strictly retains only the last 10 messages (5 turns) to protect RAM/VRAM capacity.
- **Client Startup Crash:** Injected a `sys.path` override into `main.py` to resolve unpredictable "No module named X" import failures when spawned as a subprocess by the launcher.
- **Launcher Race Conditions:** Replaced arbitrary `time.sleep()` delays in `launcher.py` with robust endpoint polling, preventing the client from attempting to connect to a dead or loading server.
- **Subprocess Deadlocks:** Rerouted server `stdout` and `stderr` to a dedicated file (`logs/server.log`) to prevent application freezes caused by filled buffer pipes.