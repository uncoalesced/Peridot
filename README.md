<div align="center">

```
██████╗ ███████╗██████╗ ██╗██████╗  ██████╗ ████████╗
██╔══██╗██╔════╝██╔══██╗██║██╔══██╗██╔═══██╗╚══██╔══╝
██████╔╝█████╗  ██████╔╝██║██║  ██║██║   ██║   ██║   
██╔═══╝ ██╔══╝  ██╔══██╗██║██║  ██║██║   ██║   ██║   
██║     ███████╗██║  ██║██║██████╔╝╚██████╔╝   ██║   
╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝╚═════╝  ╚═════╝    ╚═╝   
```

### `SOVEREIGN LOCAL AI KERNEL — v1.5.0 STABLE`

### `Sovereign Kernel Architecture & Split Tensor Allocation`

[![STATUS](https://img.shields.io/badge/STATUS-STABLE-00ff88?style=for-the-badge&labelColor=0a0a0a)](https://github.com/uncoalesced/Peridot/releases)
[![PLATFORM](https://img.shields.io/badge/PLATFORM-WINDOWS-0078D4?style=for-the-badge&labelColor=0a0a0a)](docs/markdowns/COMMUNITY_INSTALL.md)
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

Peridot is a sovereign local AI kernel engineered to execute entirely on operator owned hardware without external dependency, cloud inference, telemetry collection or remote orchestration.

The runtime combines:

- Local LLM inference
- Permission gated execution
- Split Tensor Allocation
- Dynamic VRAM arbitration
- Hardware aware telemetry routing
- Local Retrieval Augmented Generation (RAG)
- Asynchronous forensic auditing
- Immutable logging infrastructure

Unlike cloud first AI platforms, Peridot was architected around:

- Deterministic local execution
- Transparent orchestration
- Operator sovereignty
- Hardware aware optimization
- Zero telemetry dependency

Most AI assistants are surveillance infrastructure with a chat interface.

Peridot is the opposite.

Peridot was built around a simple principle:

```text
The user owns the machine.
Therefore the user controls the intelligence running on it.
```

Unlike cloud first assistants, Peridot does not:

- Transmit prompts externally
- Require external inference APIs
- Rely on cloud orchestration
- Force locked safety layers
- Hide execution behavior from the operator

Every subsystem is locally inspectable, locally auditable, and locally controllable.

> **Development Note**
>
> Peridot's runtime architecture, telemetry systems, security infrastructure, inference pipeline, orchestration layers, setup wizard, VRAM state machine, and kernel logic are human engineered.
>
> AI-generated code is used exclusively inside the `benchmarking/` suite for telemetry automation and validation tooling.

```text
┌─────────────────────────────────────────────────────────┐
│ USER INPUT                                              │
│    │                                                    │
│    ▼                                                    │
│ SECURITY GATE                                           │
│ • Input Sanitization                                    │
│ • File Access Blacklist                                 │
│ • Path Traversal Prevention                             │
│    │                                                    │
│    ▼                                                    │
│ PERMISSION LAYER                                        │
│ • constitution.json                                     │
│ • Function Call Authorization                           │
│    │                                                    │
│    ▼                                                    │
│ AETHER-ROUTE v1.5                                       │
│ • Hardware-Aware Telemetry                              │
│ • Semantic Routing                                      │
│ • Dynamic VRAM Arbitration                              │
│ • CPU-Offloaded Embedding Pipeline                      │
│ • Local RAG Pipeline                                    │
│    │                                                    │
│    ▼                                                    │
│ INFERENCE ENGINE                                        │
│ • Qwen2.5-14B-Instruct-Q4_K_M                           │
│ • Split-Tensor Allocation                               │
│ • llama-cpp-python + cuBLAS                             │
│ • localhost:5000 (local-only)                           │
│ • ~39 tokens/sec sustained inference                    │
│    │                                                    │
│    ▼                                                    │
│ GHOSTLOGGER                                             │
│ • Asynchronous Security Auditing                        │
│ • Tamper-Evident Logging                                │
│ • Forensic Event Persistence                            │
│    │                                                    │
│    ▼                                                    │
│ AUDIT LAYER                                             │
│ • SHA-256 Verified                                      │
│ • Append-Only Logging                                   │
│ • Security Event Isolation                              │
└─────────────────────────────────────────────────────────┘
```

---

# `> PERFORMANCE`

Measured on real hardware. No overclocking. No cherry picked runs.

### Test Hardware

- **GPU:** NVIDIA GeForce RTX 5050 Laptop (8GB VRAM)
- **CPU:** AMD Ryzen 7 250 AI
- **Model:** Qwen2.5-14B-Instruct-Q4_K_M

---

## Split-Tensor Allocation

Peridot v1.5.0 STABLE standardizes on a single production inference architecture.

```text
Qwen2.5-14B-Instruct-Q4_K_M
```

Instead of aggressively reducing model size to fit inside VRAM boundaries, Peridot now uses Split Tensor Allocation.

Tensor weights are dynamically distributed across GPU VRAM and system RAM.

This allows Peridot to deploy substantially larger reasoning models on consumer hardware while preserving:

- Stable inference execution
- RAG grounding accuracy
- Long context consistency
- Reduced hallucination rates
- Improved multi-document reasoning

The legacy 3B execution path was retired as the primary engine after repeated parameter-starvation failures, knowledge bleed events and degraded RAG performance under complex retrieval workloads.

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

## Benchmark Visualization

<div align="center">

![Benchmark Speed Chart](assets/benchmarks/benchmark_speed_chart.png)

</div>

---

## VRAM Allocation Map

Peridot v1.5 aggressively manages memory allocation to support large-parameter inference without compromising operating system stability.

<div align="center">

![VRAM Allocation](assets/benchmarks/benchmark_vram_chart.png)

</div>

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

## Structural Watchdog Hardening & FSM Tuning

Peridot v1.5 introduces a hardened finite state memory controller designed specifically for large model execution on constrained VRAM hardware.

The kernel now enforces:

```text
7500MB Physical VRAM Ceiling
```

to preserve display driver stability during sustained tensor workloads.

Additional safeguards include:

- Direct NVIDIA driver interrogation through `pynvml`
- Physical VRAM validation
- Reduced purge threshold (200MB)
- FSM-controlled memory recovery
- Phantom VRAM mitigation

---

## KERNEL PANIC Guarantee

Peridot no longer trusts operating system cache metrics when reclaiming VRAM.

The finite state machine verifies physical byte recovery directly from the NVIDIA driver.

If Folding@Home fails to yield memory within a strict:

```text
2.0 Second Timeout
```

the kernel triggers:

```text
KERNEL PANIC
```

The active prompt is discarded.

The allocation path is aborted.

The fault is isolated.

Host operating system stability is preserved.

<div align="center">

![VRAM State Machine](assets/benchmarks/hardware_handoff_sequence.png)

</div>

---

# `> SECURITY`

Peridot implements a hardened defense in depth architecture engineered to protect the inference runtime from malicious prompts, unauthorized file access, unsafe subprocess execution, prompt injection attacks, and privilege escalation attempts.

The kernel assumes:

```text
All input is potentially hostile until validated otherwise
```

Security boundaries are enforced before the inference layer is permitted to interact with:

- The filesystem
- Subprocess execution
- Network interfaces
- External resources
- Privileged runtime operations

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

## System Prompt Hardening

Peridot v1.5 introduces a redesigned system prompt architecture engineered specifically to combat knowledge bleed and context drift.

The `build_system_prompt()` pathway now injects explicit contextual constraints into every generation cycle.

The objective is simple:

```text
If information does not exist in retrieved context,
the model should not invent it.
```

The hardened prompt architecture actively suppresses:

- RLHF conversational drift
- Unsupported factual extrapolation
- Cross-document contamination
- Retrieval bypass attempts
- Context abandonment

This substantially improves:

- RAG grounding accuracy
- Citation fidelity
- Multi-document reasoning
- Contextual obedience

while reducing hallucination rates under heavy retrieval workloads.

---

## File Access Blacklist

The kernel actively blocks access to sensitive files and restricted directories before the inference layer is permitted to interact with the host filesystem.

### Blocked Files

- `.env`
- `.ssh/id_rsa`
- `passwords.txt`
- `auth.token`

### Blocked Directories

- `C:\Windows\`
- `/etc/`
- `/root/`
- `/boot/`

Path traversal attacks such as:

```text
../../../etc/passwd
```

are automatically neutralized through path normalization and permission validation before file execution paths are resolved.

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

Peridot v1.5 introduces a redesigned operator interface engineered around transparency, observability, and separation of responsibilities.

Unlike traditional chat-first interfaces, the Glass Box UI exposes runtime state directly to the operator.

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

KERNEL VAULT provides real-time visibility into the retrieval subsystem.

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

The v1.5 interface introduces a custom scrolling engine designed for high refresh-rate displays.

Features include:

- 5ms sub pixel velocity decay
- Smooth inertial movement
- High refresh rate optimization
- Reduced scroll latency

for large conversations and document-heavy workloads.

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

<div align="center">

![Aether-Route Topology](assets/illustrations/aether_route_topology.png)

</div>

---

## **2. Aether Route RAG Pipeline**

Peridot's retrieval infrastructure was substantially redesigned for v1.5.

---

### Standalone CLI Ingestion

A dedicated ingestion utility:

```text
ingest_vault.py
```

allows operators to parse, chunk, embed and index content directly into the FAISS database.

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

**Community Builds:** Maintained by contributors. Community deployment documentation may lag behind stable runtime architecture revisions. See [`COMMUNITY_INSTALL.md`](docs/markdowns/COMMUNITY_INSTALL.md).

---

# `> INSTALLATION`

## Prerequisites

```text
OS:      Windows 10/11 (64-bit)
GPU:     NVIDIA RTX Series Recommended
Python:  3.11
Storage: ~10GB Free (SSD Recommended)
RAM:     16GB Recommended
```

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
[████████████████████] v1.5           Linux Support
[░░░░░░░░░░░░░░░░░░░░] v1.6           Updated and more efficient RAG and Ingestion system
[░░░░░░░░░░░░░░░░░░░░] v1.7           AMD GPU Support (ROCm)
[░░░░░░░░░░░░░░░░░░░░] v2.0           macOS Support (Apple Silicon)
```

**Current Focus (v1.5.0 STABLE)**

Autonomous RAG degradation policies, 24-hour MTBF stress testing under Split-Tensor Allocation workloads, and expanded sovereign UI observability.

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

<div align="center">

![Sovereign Network Diagram](assets/illustrations/sovereign_network_diagram.png)

</div>

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

`PERIDOT` · `SOVEREIGN AI KERNEL` · `v1.5.0 STABLE`

**Engineered by [uncoalesced](https://github.com/uncoalesced)**

*Your hardware. Your model. Your rules.*

</div> 