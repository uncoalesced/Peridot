# Changelog

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