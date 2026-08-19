<div align="center">

```
██████╗ ███████╗██████╗ ██╗██████╗  ██████╗ ████████╗
██╔══██╗██╔════╝██╔══██╗██║██╔══██╗██╔═══██╗╚══██╔══╝
██████╔╝█████╗  ██████╔╝██║██║  ██║██║   ██║   ██║   
██╔═══╝ ██╔══╝  ██╔══██╗██║██║  ██║██║   ██║   ██║   
██║     ███████╗██║  ██║██║██████╔╝╚██████╔╝   ██║   
╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝╚═════╝  ╚═════╝    ╚═╝   
```

### `SOVEREIGN LOCAL AI KERNEL — v1.5.4 STABLE`

### `PERIDOT SOVEREIGN KERNEL v1.5.4-STABLE [ZAT-SCS]`

[![STATUS](https://img.shields.io/badge/STATUS-STABLE-00ff88?style=for-the-badge&labelColor=0a0a0a)](https://github.com/uncoalesced/Peridot/releases)
[![PLATFORM](https://img.shields.io/badge/PLATFORM-WINDOWS_%7C_LINUX-0078D4?style=for-the-badge&labelColor=0a0a0a)](docs/markdowns/COMMUNITY_INSTALL.md)
[![PRIVACY](https://img.shields.io/badge/PRIVACY_AIR_GAPPED-ff4444?style=for-the-badge&labelColor=0a0a0a)](docs/markdowns/SECURITY.md)

<br>

[![LICENSE](https://img.shields.io/badge/LICENSE-MIT-ff5f25?style=for-the-badge&labelColor=0a0a0a)](LICENSE)
[![Python](https://img.shields.io/badge/PYTHON-3.11-4fc3f7?style=for-the-badge&labelColor=0a0a0a)](https://python.org)

<br>

**Engineered by [uncoalesced](https://github.com/uncoalesced)**

*GPU-accelerated, air-gapped sovereign AI runtime with defense in depth security and hardware aware orchestration.*  
*Zero telemetry. Zero cloud dependency. Absolute user sovereignty.*

</div>

---

# `> OVERVIEW`

Peridot v1.5.4-STABLE is a sovereign local AI kernel engineered for fully offline inference, hardware-aware GPU arbitration and predictive context preparation on operator owned systems. v1.5.4 adds native Linux support (Debian 12, Ubuntu 22.04+, Arch) alongside the existing Windows runtime, and closes a real sovereignty gap where the offline flags could be silently reopened by a stale `.env`.

ZAT-SCS stands for Zero-Overhead Active Telemetry and Speculative Context Streaming. It is the flagship v1.5.3 update: a predictive preemption layer that monitors physical interaction signals before a prompt is submitted, prepares the GPU and context path in advance, and removes the normal prefill delay when the operator commits a query during the prepared state.

The v1.5.3 telemetry path runs a 10Hz Physical Telemetry Engine as a background daemon thread. It fuses two local only signals:

- Keyboard typing frequency f(C), measured by the isolated pynput keystroke monitor through a sliding timestamp window.
- Microphone RMS envelope g(A), measured by the non-blocking sounddevice InputStream acoustic tracker.

These signals are converted into the speculative interaction probability P(I_t). The decay-acceleration model raises probability during active typing or acoustic engagement and decays it during idle periods:

```text
P(I_t) = min(1.0, P(I_t-1) * e^(-lambda * dt) + w_key * f(C) + w_aud * g(A))
```

When P(I_t) >= 0.65, the finite state machine transitions into:

```text
KernelState.SPECULATIVE_PREPARED
```

That transition prepares the inference path before the prompt reaches `/ask`:

1. Distributed Folding@Home compute is throttled to 10 percent SM capacity through CUDA MPS where available.
2. `GGML_CUDA_ENABLE_UNIFIED_MEMORY=1` is exported so model weights can be pre-mapped into physical page tables through Unified Virtual Memory.
3. A non-blocking loopback REST call is issued to `/slots/0/restore` to prefetch the active session KV cache without freezing the telemetry loop.

If the operator submits a prompt while the kernel is already in `SPECULATIVE_PREPARED`, the `/ask` endpoint bypasses the normal preemption and prefill latency phase. The request is routed directly into generation from the prepared state, allowing token streaming to begin at generation-speed limits instead of waiting for a cold VRAM handoff and context prefill cycle.

Peridot still retains the original sovereign constraints: local inference, permission-gated execution, Split Tensor Allocation, dynamic VRAM arbitration, local RAG, asynchronous forensic auditing and operator controlled research participation.

```text
+---------------------------------------------------------+
| USER INPUT                                              |
|    |                                                    |
|    v                                                    |
| SECURITY GATE                                           |
| - Input Sanitization                                    |
| - File Access Blacklist                                 |
| - Path Traversal Prevention                             |
|    |                                                    |
|    v                                                    |
| PERMISSION LAYER                                        |
| - constitution.json                                     |
| - Function Call Authorization                           |
|    |                                                    |
|    v                                                    |
| ZAT-SCS TELEMETRY LOOP                                  |
| - 10Hz Physical Telemetry Engine                        |
| - Keyboard f(C) + Acoustic RMS g(A)                     |
| - P(I_t) speculative probability                        |
|    |                                                    |
|    v                                                    |
| SPECULATIVE PREPARED STATE                              |
| - CUDA MPS 10 percent background throttle               |
| - UVM weight pre-mapping                                |
| - Async /slots/0/restore KV cache prefetch              |
|    |                                                    |
|    v                                                    |
| AETHER-ROUTE v1.5.3                                     |
| - Semantic Routing                                      |
| - Dynamic VRAM Arbitration                              |
| - CPU-Offloaded Embedding Pipeline                      |
| - Local RAG Pipeline                                    |
|    |                                                    |
|    v                                                    |
| /ask PREFILL BYPASS ROUTE                               |
| - Direct generation from prepared state                 |
| - Qwen2.5-14B-Instruct-Q4_K_M                           |
| - Split-Tensor Allocation, GPU_LAYERS = 20              |
|    |                                                    |
|    v                                                    |
| GHOSTLOGGER AND STABILITY LEDGER                        |
+---------------------------------------------------------+
```

---

# `> PERFORMANCE`

Measured on real hardware. No overclocking. No cherry picked runs.

### Test Hardware

- **GPU:** NVIDIA GeForce RTX 5050 Laptop (8GB VRAM)
- **CPU:** AMD Ryzen 7 250 AI
- **Model:** Qwen2.5-14B-Instruct-Q4_K_M

---

## ZAT-SCS Telemetry Daemon

Peridot v1.5.3 adds a high frequency telemetry daemon that runs independently from prompt submission and inference generation. The daemon is launched as a background thread by the Physical Telemetry Engine after the server boots and continuously samples local interaction signals at 10Hz.

The daemon lifecycle is intentionally isolated:

1. `KeyboardTracker.start()` mounts the pynput listener and stores the latest keystroke timestamps in a bounded sliding window.
2. `AudioTracker.start()` opens a sounddevice input stream and updates a smoothed microphone RMS envelope without blocking the main loop.
3. `PhysicalTelemetryEngine.tick()` runs every 100ms, reads f(C) and g(A), applies temporal decay and forwards P(I_t) to the GPU orchestrator.
4. `SovereignGPUOrchestrator.evaluate_probability()` transitions the kernel into `SPECULATIVE_PREPARED` when the probability crosses 0.65.

The release model is:

```text
P(I_t) = min(1.0, P(I_t-1) * e^(-lambda * dt) + w_key * f(C) + w_aud * g(A))
TELEMETRY_HZ = 10
SPECULATIVE_THRESHOLD = 0.65
LAMBDA_DECAY = 0.1
WEIGHT_KEY = 0.45
WEIGHT_AUD = 0.35
```

---

## Validated Runtime Baseline

```text
GPU:          RTX 5050 Laptop (8GB)
CPU:          Ryzen 7 250 AI
Model:        Qwen2.5-14B-Instruct-Q4_K_M
Throughput:   ~39 tokens/sec
Execution:    Fully Local
```

---

## Dynamic VRAM Arbitration

Dynamic GPU resource arbitration between Folding@Home and active inference execution.

### Measured Runtime Behavior

- **WebSocket Interrupt Dispatch:** ~21ms
- **Full VRAM Purge + Handoff:** <510ms
- **Inference Priority:** Absolute

### Technical Implementation

When a user query enters the inference queue:

1. Peridot dispatches a WebSocket pause signal
2. Folding@Home begins VRAM release
3. Physical memory reclamation is validated
4. Tensor allocation proceeds
5. Generation begins

This allows Peridot to maintain:

- Uninterrupted inference responsiveness
- Persistent distributed medical research
- Stable VRAM reclamation
- Deterministic hardware transitions

Inference execution always takes priority.

---

## Speculative Context Restoration Pipeline

Peridot v1.5.3 extends the FSM with an asynchronous context restoration path for speculative prompt preparation. When telemetry pushes the kernel into `KernelState.SPECULATIVE_PREPARED`, the orchestrator launches the context streaming path without blocking the 10Hz monitoring loop.

The speculative restoration sequence is:

1. `SovereignGPUOrchestrator` receives P(I_t) >= 0.65 and requests the prepared state.
2. The kernel applies the ZAT-SCS transition hooks.
3. CUDA MPS background capacity is reduced to 10 percent where Linux MPS control is available.
4. Unified Virtual Memory pre-mapping is enabled with `GGML_CUDA_ENABLE_UNIFIED_MEMORY=1`.
5. `ContextStreamingEngine.speculative_restore_async()` starts a daemon thread.
6. `LlamaClient.restore_slot(slot_id=0)` posts to the loopback llama-server endpoint `/slots/0/restore` with timeout and connection-failure isolation.

This keeps speculative KV cache restoration non-blocking. If the loopback llama-server slot endpoint is offline or slow, the exception path is contained and the sensory loop continues operating.

## Split-Tensor Runtime Guardrails

The validated v1.5.3 inference target is:

```text
Model:        Qwen2.5-14B-Instruct-Q4_K_M
GPU:          RTX 5050 Laptop GPU, 8GB VRAM
CPU:          Ryzen 7 250 AI
GPU_LAYERS:   20
Allocation:   Split Tensor Allocation across VRAM and system RAM
```

Peridot does not attempt to force the entire 14B model into an 8GB VRAM envelope. The stable split configuration keeps a safe GPU layer budget and allows the remainder of the tensor load to execute through system RAM, preserving reasoning quality while avoiding catastrophic CUDA allocation failures.

The FSM retains a 200MB free VRAM clearance threshold on 8GB targets. If Folding@Home or any background workload cannot yield the required physical memory before timeout, inference is aborted rather than risking a display driver crash.


---

# `> SOVEREIGN MULTI-SESSION MEMORY`

Peridot v1.5.1 introduced a local SQLite-backed conversational ledger in `core_system/memory/chat_ledger.py`. The ledger gives the kernel durable, multi-session chat continuity without external accounts, cloud storage, or remote profile synchronization.

The ledger persists two local tables:

```text
sessions(session_id, title, created_at, updated_at)
messages(id, session_id, role, content, timestamp)
```

Session CRUD supports creating new conversations, listing recent sessions, updating titles, retrieving session metadata, and deleting a session with cascading message cleanup. Each `/ask` request may carry a `session_id`; the server uses that value to retrieve recent turns and return continuity metadata to the client.

The runtime injects history through a six-turn sliding window:

```text
get_history(session_id, limit=6)
```

The ledger fetches up to twelve recent messages, reverses them back into chronological order, deduplicates consecutive identical role/content pairs and hands the result to the prompt builder for ChatML-style context assembly. This prevents unbounded chat growth while preserving enough local conversational state for stable follow-up prompts.

---

## Input Sanitization

All prompts are sanitized before entering the inference pipeline.

Blocked patterns include:

```python
<script>         # XSS attacks
eval()           # Arbitrary code execution
os.system()      # Shell injection
__import__       # Python import abuse
subprocess.      # Subprocess exploitation
```

Malicious prompts are rejected before execution and logged asynchronously through GhostLogger.

Security violations are isolated to:

```text
logs/ghost_audit.log
```

---

## Cryptographic Handshake Architecture

Peridot abandons static credential configuration entirely.

The runtime generates:

- Localized `.env` authentication
- Ephemeral API keys
- Isolated environment authentication boundaries
- Offline execution enforcement

during setup initialization.

The setup wizard additionally enforces:

```text
HF_HUB_OFFLINE=1
```

to sever unauthorized HuggingFace telemetry routing at the environment level.

No API key files are committed to repositories.

No cloud authorization exists.

No remote trust assumptions exist.

---

## Stable v1.5 Milestone Ledger

The stable v1.5 line consolidated Peridot around local persistence, hardened ingestion and predictive hardware orchestration.

### v1.5.1-STABLE

v1.5.1 delivered the operator facing stability layer and local conversation persistence:

- Multi-tab UI migration with dedicated Chat, Vault and Settings workspaces.
- Glass Box operator visibility for runtime state, research controls and telemetry endpoints.
- 360Hz Kinetic Scrolling and custom themed ttk.Combobox styling for the operator interface.
- SQLite chat ledger integration for session CRUD, message logging and six turn sliding history injection.
- 256-bit API key generation through `secrets.token_hex(32)` and loopback CORS restriction.

### v1.5.2-STABLE

v1.5.2 stabilized memory safety and document ingestion:

- Insecure pickle metadata deserialization was removed from the vault path and replaced with JSON metadata serialization.
- PyMuPDF was promoted into the layout preserving extraction pipeline with `fitz` and `sort=True` to preserve tables, columns and balance-sheet style geometry.
- Each embedded chunk receives an inline `[SOURCE DOC: filename]` citation brand before vector insertion.
- Dynamic VRAM splitting heuristics and context overflow clamps reduce OOM and 400-response failures under dense RAG workloads.

### v1.5.3-STABLE [ZAT-SCS]

v1.5.3 adds predictive preemption and speculative context streaming:

- The 10Hz Physical Telemetry Engine computes P(I_t) from keyboard f(C) and acoustic RMS g(A).
- P(I_t) >= 0.65 transitions the kernel into `KernelState.SPECULATIVE_PREPARED`.
- CUDA MPS throttles background distributed compute to 10 percent SM capacity during speculative preparation.
- `GGML_CUDA_ENABLE_UNIFIED_MEMORY=1` enables Unified Virtual Memory weight pre-mapping.
- The loopback `/slots/0/restore` call prefetches llama-server slot state asynchronously.
- The `/ask` route detects the speculative prepared state and bypasses the preemption and prefill phase when possible.

### v1.5.4-STABLE

v1.5.4 adds Linux support and closes a real sovereignty gap:

- Native Linux support (Debian 12, Ubuntu 22.04+, Arch). Session type (`x11`/`wayland`/`headless`/`native`) is detected at boot; under Wayland, `pynput`'s global keyboard hook cannot receive input by design, so the ZAT-SCS keyboard term degrades to zero rather than crashing or silently going stale.
- `HF_HUB_OFFLINE` and `TRANSFORMERS_OFFLINE` are now force-locked to `1` immediately after `.env` is loaded — a hand-edited or stale `.env` can no longer reopen outbound traffic. Model downloads route through a subprocess-isolated child process that is the only part of the system ever granted network access.
- Default model briefly promoted to `Qwen3.8-27B-UD-Q2_K_XL.gguf`, then **reverted** to `Qwen2.5-14B-Instruct-Q4_K_M.gguf`. The 27B cannot be loaded by the pinned `llama-cpp-python` 0.3.23: the GGUF declares an MTP (multi-token prediction) head at block 64 via `qwen35.nextn_predict_layers`, which the runtime builds as a standard hybrid layer and then rejects for a missing SSM tensor. The file is valid - a byte-exact re-download fails identically - so this is a runtime support gap, not corruption. Unblocked by a newer llama.cpp; deferred to v1.6.x. See CHANGELOG.md for the full analysis.
- Test suite expanded from 11 to 50 tests; a platform-relative path-blacklist bug affecting both Windows and Linux sensitive-directory checks was found and fixed.

---

## GhostLogger

GhostLogger is Peridot's asynchronous forensic auditing subsystem.

It functions as a silent observer operating independently from the primary inference and UI execution paths.

GhostLogger intercepts and records:

- Authentication failures
- Unauthorized file access attempts
- Malicious prompt injections
- Constitution validation failures
- Blocked subprocess calls
- Runtime security violations
- Kernel panic events
- VRAM arbitration faults

without interrupting inference execution.

### Design Goals

GhostLogger was engineered around three priorities:

```text
Persistence
Isolation
Forensic Integrity
```

Even if the UI or inference engine experiences sustained load, GhostLogger continues operating independently to preserve a persistent forensic trail for auditing and security analysis.

For full threat model documentation and disclosure policy, see [`SECURITY.md`](docs/markdowns/SECURITY.md).

---

# `> GLASS BOX UI & OPERATOR INTERFACE`

Peridot v1.5 introduces a redesigned operator interface engineered around transparency, observability and separation of responsibilities.

Unlike traditional chat first interfaces, the Glass Box UI exposes runtime state directly to the operator.

The objective is simple:

```text
Nothing important should happen silently.
```

---

## CHAT MATRIX

CHAT MATRIX serves as the primary generation environment.

This workspace is responsible for:

- Local inference
- Prompt execution
- Conversation management
- Context rendering
- Markdown formatting
- Code generation

The interface remains isolated from background telemetry processing to ensure UI responsiveness remains independent of inference workload.

---

## KERNEL VAULT

KERNEL VAULT provides real time visibility into the retrieval subsystem.

Operators can observe:

- Active document ingestion
- Retrieved context chunks
- Vector database activity
- Retrieval performance
- RAG state transitions

This provides direct visibility into what information entered the generation pipeline.

The objective is to eliminate black-box retrieval behavior.

---

## SETTINGS

SETTINGS consolidates kernel configuration into a dedicated control surface.

Operators can manage:

- Model selection
- Hardware preferences
- Research participation
- Runtime parameters
- Security settings
- Telemetry controls

without modifying configuration files manually.

---

## Control Console & Live Telemetry

The Glass Box UI includes a dedicated control console backed by:

```text
/telemetry/stability
```

The console continuously exposes:

- FSM state
- Health score
- Active model
- VRAM utilization
- Memory pressure
- Panic count
- Research status

without overwhelming the operator with unnecessary diagnostic noise.

---

## Hardware Aware Model Swapper

Peridot dynamically scans available `.gguf` models and evaluates them against available hardware resources.

The swapper can:

- Detect local models
- Estimate memory requirements
- Validate VRAM compatibility
- Prevent unsupported deployments

before runtime initialization occurs.

---

## 144Hz Kinetic Scrolling

The v1.5 interface introduces a custom scrolling engine designed for high refresh rate displays.

Features include:

- 5ms sub pixel velocity decay
- Smooth inertial movement
- High refresh rate optimization
- Reduced scroll latency

for large conversations and document heavy workloads.

---

## Live Search & Markdown Extraction

The interface includes:

```text
CTRL + F
```

real-time search functionality.

Additional tooling provides:

- Instant markdown extraction
- Code block isolation
- Rapid content navigation
- Search result highlighting

across large conversations.

---

## Research Core Controls

Research participation remains fully optional.

Dedicated controls expose:

```text
/research/enable
/research/disable
```

allowing operators to explicitly opt into or opt out of distributed medical research workloads.

Peridot never requires Folding@Home participation.

Research contribution remains voluntary.

---

# `> ARCHITECTURE`

Peridot is engineered as a layered sovereign runtime composed of isolated but composable subsystems.

Each module can:

- Operate independently
- Be expanded individually
- Be disabled without collapsing the kernel
- Communicate through controlled execution boundaries

The architecture intentionally prioritizes:

```text
Transparency
Security
Deterministic Local Execution
```

over abstraction-heavy orchestration.

---

# `> CORE ARCHITECTURE & FEATURE MATRIX`

## **1. Aether Route RAG Topology**

Peridot v1.5 permanently isolates semantic retrieval workloads away from tensor generation resources.

The architecture intentionally separates:

- Embedding generation
- Semantic indexing
- Retrieval orchestration

from active inference execution.

Workloads are routed toward:

- CPU resources
- DDR5 system memory
- Ryzen AI acceleration paths

while preserving GPU memory for inference execution.

This separation reduces:

- VRAM starvation
- Allocation contention
- Retrieval latency spikes
- Inference instability

during sustained workloads.


---

## **2. Aether Route RAG Pipeline**

Peridot's retrieval infrastructure was substantially redesigned for v1.5.

---

### Standalone CLI Ingestion

A dedicated ingestion utility:

```text
ingest_vault.py
```

allows operators to parse, chunk, embed and index content directly into the TurboVec index.

All ingestion workloads remain CPU bound to protect inference resources.

---

### Binary PDF Extraction

Peridot now supports binary PDF text layer extraction using:

```text
PyPDF2
```

allowing direct ingestion of research papers, textbooks, manuals and technical documentation.

---

### Sliding Window Chunking

Documents are fragmented using strict character clamped chunking.

```text
< 800 Characters
```

This prevents vector dilution while improving retrieval precision across large source documents.

---

### Deep Semantic Search

Retrieval depth has been increased from:

```text
top_k = 3
```

to:

```text
top_k = 6
```

allowing denser context reconstruction and improved multi-document reasoning.

---

### Aether Cache

Peridot introduces a tiered caching architecture designed to protect 16GB systems during large ingestion workloads.

Tier 1:

```text
DDR5 RAM
```

Stores active retrieval context for zero-latency access.

Tier 2:

```text
NVMe SQLite Persistence
```

Stores aged vectors and infrequently accessed data.

This architecture minimizes:

- Page faults
- Memory thrashing
- Retrieval latency spikes

during sustained ingestion workloads.

---

### TurboVec / TurboQuant

Peridot does not depend on a third-party vector database. Retrieval runs on **TurboVec**, a Rust-backed vector index (`core_system/memory/turbovec_index.py`) built specifically for this kernel, with a pure-Python fallback when the native extension isn't available.

TurboVec uses **TurboQuant** — Peridot's own quantization architecture, applied consistently across the kernel since v1.4.0 — to compress stored vectors to 4-bit precision, claiming roughly 16x lower memory footprint than an uncompressed FAISS index at comparable retrieval accuracy. Persistence is safetensors-based; no `pickle` is used anywhere in the vault path. Chunk IDs remain stable across deletions, so the index doesn't need a full rebuild after routine document removal.

This is sovereign infrastructure, not a wrapper around someone else's hosted or telemetry-bearing vector store — no external vector database dependency exists anywhere in Peridot, by design.

---

## **3. Optimized Local Inference Engine**

The inference layer is engineered specifically for:

- Constrained VRAM systems
- Sustained tensor workloads
- Ryzen/NVIDIA hybrid systems
- Low overhead local execution
- Long session runtime stability
- Distributed compute coexistence

Unlike previous releases, v1.5 standardizes on a single production inference architecture rather than multiple competing execution profiles.

The objective is consistency.

The operator should receive the same reasoning quality, retrieval fidelity and runtime behavior regardless of workload complexity.

---

### GGUF Runtime

Built on:

```text
llama-cpp-python
```

with:

```text
cuBLAS Acceleration
```

allowing large quantized models to remain practical on consumer hardware.

The runtime remains:

- Fully local
- Fully inspectable
- Hardware aware
- Air gapped

with no external inference dependencies.

---

### Split Tensor Allocation

The defining architectural change of v1.5 is Split Tensor Allocation.

Rather than forcing the entire model into GPU memory, Peridot dynamically distributes tensor weights across:

- GPU VRAM
- System RAM

This allows significantly larger reasoning models to operate on hardware that would traditionally be considered VRAM constrained.

Benefits include:

- Larger parameter budgets
- Improved reasoning depth
- Reduced hallucination frequency
- Increased RAG fidelity
- Greater hardware utilization efficiency

without requiring cloud infrastructure.

---

## `[01] - Inference Engine`

Core inference runtime:

```text
Primary Model:   Qwen2.5-14B-Instruct-Q4_K_M
Backend:         llama-cpp-python + cuBLAS
Endpoint:        localhost:5000 (local-only)
Context:         8192 tokens (sliding window)
Temperature:     0.1
Execution:       Fully Local
```

### Why Qwen2.5-14B?

Peridot's previous architecture relied on smaller parameter count models to preserve VRAM overhead.

While performant, these models demonstrated limitations under complex retrieval workloads:

- Knowledge bleed
- Context drift
- Circular reasoning failures
- Multi-document hallucinations

The transition to Qwen2.5-14B-Instruct-Q4_K_M significantly improves:

- Retrieval fidelity
- Long context reasoning
- Citation accuracy
- Multi-document synthesis
- Instruction adherence

while remaining deployable on validated 8GB hardware through Split Tensor Allocation.

---

## `[02] - Medical Research Module (Folding@Home Integration)`

When idle, Peridot can allocate unused GPU resources toward distributed medical research through Folding@Home.

Participation is:

```text
Optional
Voluntary
Operator Controlled
```

Research workloads are never mandatory.

Peridot functions identically with Folding@Home disabled.

---

### Idle State

```text
GPU Utilization:  <5%
Action:           Folding@Home activated
Research:         Cancer, Alzheimer's, Parkinson's
```

---

### Active State

```text
User Query Detected
Action:           WebSocket Pause Signal Dispatched
Interrupt:        ~21ms
Full Handoff:     <510ms
Inference:        Priority
```

---

### Runtime Characteristics

- Opt-in only
- Fully auditable
- Zero restart overhead
- Dynamic VRAM arbitration
- Inference priority execution
- Transparent runtime tracking
- Aggressive idle return logic

---

### Commands

```text
research enable
research disable
research status
```

---

# `> HARDWARE SUPPORT`

| Tier | Hardware | Configuration | Expected Performance |
|:-----|:---------|:--------------|:--------------------:|
| ✅ **Validated Baseline** | NVIDIA RTX 5050 (8GB) + Ryzen 7 250 AI | Split-Tensor Allocation | **~39 t/s** |
| ✅ **Full Support** | NVIDIA RTX 4050+ (8GB+) | Split-Tensor Allocation | High |
| ✅ **Full Support** | NVIDIA RTX 5060 / 5070 / 5080 | Split-Tensor Allocation | Very High |
| ⚙️ **CPU Fallback** | Modern x64 CPUs | CPU Only | 10–20 t/s |
| ⚠️ **Lite Mode** | AMD Radeon 680M / 780M | Lite | 8–15 t/s |
| ⚠️ **Lite Mode** | Intel Iris Xe | Lite | 5–10 t/s |
| 🛠️ **Community** | AMD RX 6000 / 7000 Series | ROCm (Linux) | Experimental |
| 🛠️ **Community** | Intel Arc A750 / A770 | Vulkan | Experimental |

Peridot is optimized for modern NVIDIA hardware but remains operational across a wide range of deployment environments.

The validated baseline for v1.5 is:

```text
RTX 5050 8GB
Ryzen 7 250 AI
Qwen2.5-14B-Instruct-Q4_K_M
```

using Split Tensor Allocation.

CPU only execution paths remain fully supported at reduced throughput.

**Linux:** Debian 12, Ubuntu 22.04+ and Arch are supported as of v1.5.4. The code path is correct in principle and covered by automated tests, but GPU-accelerated inference has not yet been validated on real Linux hardware — no GPU-equipped Linux machine was available during that release cycle. Treat Linux GPU inference as untested, not unsupported.

**Community Builds:** Maintained by contributors. Community deployment documentation may lag behind stable runtime architecture revisions. See [`COMMUNITY_INSTALL.md`](docs/markdowns/COMMUNITY_INSTALL.md).

---

# `> INSTALLATION`

## Prerequisites

```text
OS:      Windows 10/11 (64-bit), or Debian 12 / Ubuntu 22.04+ / Arch (Linux)
GPU:     NVIDIA RTX Series Recommended
Python:  3.11
Storage: ~10GB Free (SSD Recommended)
RAM:     16GB Recommended
```

Linux operators: see [`COMMUNITY_INSTALL.md`](docs/markdowns/COMMUNITY_INSTALL.md) for system dependencies (including `portaudio19-dev`, required for the acoustic telemetry sensor) and the Wayland degradation matrix before running setup.

---

## Setup

### 1. Clone Repository

```bash
git clone https://github.com/uncoalesced/Peridot.git
cd Peridot
```

---

### 2. Create Virtual Environment

```bash
python -m venv venv
.\venv\Scripts\activate
```

---

### 3. Run Setup Wizard

Peridot includes an interactive hardware-aware setup wizard.

The wizard automatically:

- Detects installed hardware
- Profiles available VRAM
- Validates compatibility
- Configures security boundaries
- Generates cryptographic authentication
- Enables offline execution controls
- Downloads runtime weights
- Installs runtime dependencies

```bash
python setup.py
```

---

### Hardware Detection

The setup wizard automatically detects:

```text
Operating System
CPU
System RAM
GPU Vendor
GPU VRAM
CUDA Availability
```

and selects the most appropriate deployment pathway.

---

### Security Initialization

During setup the kernel generates:

```text
.env Authentication
Ephemeral API Keys
Offline Execution Controls
```

and enforces:

```text
HF_HUB_OFFLINE=1
```

to prevent unauthorized HuggingFace telemetry routing.

---

### Runtime Weight Installation

The setup wizard manages:

- Model acquisition
- Dependency installation
- CUDA binding
- Runtime validation

before the kernel is permitted to launch.

---

### Manual Matrix Override

Advanced operators may bypass automatic recommendations and manually expose available deployment profiles.

This mode is intended for:

- Testing
- Benchmarking
- Development
- Experimental hardware

---

### Launching The Kernel

After setup completes:

```bash
python launcher.py
```

The kernel will initialize using the configured runtime environment.

---

# `> ROADMAP`

```text
[████████████████████] v1.2 BETA      Security Hardening + Benchmarking
[████████████████████] v1.3 BETA      RAG Engine (Document Analysis)
[████████████████████] v1.4.0 STABLE  TurboQuant Architecture
[████████████████████] v1.5.4 STABLE  Linux Support (code-complete; GPU unvalidated on Linux)
[░░░░░░░░░░░░░░░░░░░░] v1.6.x         Multi-engine inference (ExLlamaV2, vLLM), episodic memory
[░░░░░░░░░░░░░░░░░░░░] v1.7.x         FreeThink reasoning, sandboxed agentic REPL, sovereign web gateway
[░░░░░░░░░░░░░░░░░░░░] v1.8.x         Optional local WebUI, artifact system
```

**Current Focus (v1.6.x)**

Multi-engine inference behind a shared provider abstraction, each model in its own child process, plus infrastructure for Peridot's own episodic self-improvement memory — both built on the existing TurboVec index rather than any external vector database.

---

# `> PHILOSOPHY`

Peridot exists because the AI industry's default assumption is that **your data belongs to them**.

It does not.

Every design decision reflects a single principle:

```text
The user is sovereign.
```

That means:
- no telemetry without explicit consent
- no autonomous action without permission
- no hidden cloud inference
- no unremovable execution boundaries
- no ethical guardrails that cannot be modified by the operator

The `config/constitution.json` system ships with sensible defaults.

You can:
- make them stricter
- make them looser
- remove them entirely

That decision belongs to the user, not the developer.


**This is what AI should look like.**

For our full philosophical reasoning, see [`PHILOSOPHY.md`](docs/markdowns/PHILOSOPHY.md).

---

# `> LICENSE & DISCLAIMER`

**License:** MIT License

Clone it.

Fork it.

Modify it.

Commercialize it.

Build on it.

Break it.

Improve it.

Peridot exists to be studied, audited, modified and expanded by its operators.

**Disclaimer:** Peridot is experimental software. The operator assumes responsibility for all commands executed, hardware utilization and generated content. Provided as is without warranty of any kind.

---

<div align="center">

`PERIDOT` · `SOVEREIGN AI KERNEL` · `v1.5.4 STABLE`

**Engineered by [uncoalesced](https://github.com/uncoalesced)**

*Your hardware. Your model. Your rules.*

</div> 
