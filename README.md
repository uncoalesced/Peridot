<div align="center">

```text
██████╗ ███████╗██████╗ ██╗██████╗  ██████╗ ████████╗
██╔══██╗██╔════╝██╔══██╗██║██╔══██╗██╔═══██╗╚══██╔══╝
██████╔╝█████╗  ██████╔╝██║██║  ██║██║   ██║   ██║
██╔═══╝ ██╔══╝  ██╔══██╗██║██║  ██║██║   ██║   ██║
██║     ███████╗██║  ██║██║██████╔╝╚██████╔╝   ██║
╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝╚═════╝  ╚═════╝    ╚═╝
```

### `SOVEREIGN AI KERNEL — v1.3.1 BETA`

[![STATUS](https://img.shields.io/badge/STATUS-OPERATIONAL-00ff88?style=for-the-badge&labelColor=0a0a0a)](https://github.com/uncoalesced/Peridot)
[![PLATFORM](https://img.shields.io/badge/PLATFORM-WINDOWS_GPU-4fc3f7?style=for-the-badge&labelColor=0a0a0a)](https://github.com/uncoalesced/Peridot)
[![PRIVACY](https://img.shields.io/badge/PRIVACY-AIR_GAPPED-ff4444?style=for-the-badge&labelColor=0a0a0a)](https://github.com/uncoalesced/Peridot)
[![LICENSE](https://img.shields.io/badge/LICENSE-MIT-f9e642?style=for-the-badge&labelColor=0a0a0a)](LICENSE)
[![Python](https://img.shields.io/badge/PYTHON-3.11-4fc3f7?style=for-the-badge&labelColor=0a0a0a)](https://python.org)

<br>

> **⚠️ BETA RELEASE**  
> Medical research orchestration and ARPM validation framework under active testing. [Report issues →](https://github.com/uncoalesced/Peridot/issues)

<br>

**Engineered by [uncoalesced](https://github.com/uncoalesced)**

*GPU-accelerated, air-gapped sovereign AI runtime with defense-in-depth security and hardware-aware orchestration.*  
*Zero telemetry. Zero cloud dependency. Absolute user sovereignty.*

<br>

</div>

---

# `> OVERVIEW`

Peridot is a sovereign local AI kernel engineered to execute entirely on user-owned hardware without external dependency, cloud inference, telemetry collection, or remote orchestration.

The runtime combines:
- Local LLM inference
- Permission-gated execution
- Dynamic VRAM arbitration
- Hardware-aware telemetry routing
- Local Retrieval-Augmented Generation (RAG)
- Asynchronous forensic auditing
- Immutable logging infrastructure

Most AI assistants are surveillance infrastructure with a chat interface. Peridot is the opposite.

Peridot was built around a simple principle:

```text
The user owns the machine.
Therefore the user controls the intelligence running on it.
```

Unlike cloud-first assistants, Peridot does not:
- transmit prompts externally
- require external inference APIs
- rely on cloud orchestration
- force locked safety layers
- hide execution behavior from the operator

Every subsystem is locally inspectable, locally auditable, and locally controllable.

> **Development Note**  
> Peridot's core runtime architecture, telemetry systems, security infrastructure, inference pipeline, orchestration layers, and kernel logic are 100% human engineered.
>
> AI-generated code is used exclusively inside the `\benchmarking` suite for telemetry automation and validation tooling.

```text
┌─────────────────────────────────────────────────────────┐
│  USER INPUT                                             │
│     │                                                   │
│     ▼                                                   │
│  SECURITY GATE                                          │
│  • Input Sanitization                                   │
│  • File Access Blacklist                                │
│  • Path Traversal Prevention                            │
│     │                                                   │
│     ▼                                                   │
│  PERMISSION LAYER                                       │
│  • constitution.json                                    │
│  • Function Call Authorization                          │
│     │                                                   │
│     ▼                                                   │
│  AETHER-ROUTE v1.3                                      │
│  • Hardware-Aware Telemetry                             │
│  • Semantic Routing                                     │
│  • Dynamic VRAM Arbitration                             │
│  • Local RAG Pipeline                                   │
│     │                                                   │
│     ▼                                                   │
│  INFERENCE ENGINE                                       │
│  • Llama-3-8B-Instruct (Q4_K_M)                         │
│  • llama-cpp-python + cuBLAS                            │
│  • localhost:5000 (air-gapped)                          │
│  • 43–55 tokens/sec sustained                           │
│     │                                                   │
│     ▼                                                   │
│  GHOSTLOGGER                                            │
│  • Asynchronous Security Auditing                       │
│  • Tamper-Evident Logging                               │
│  • Forensic Event Persistence                           │
│     │                                                   │
│     ▼                                                   │
│  AUDIT LAYER                                            │
│  • SHA-256 Verified                                     │
│  • Append-Only Logging                                  │
│  • Security Event Isolation                             │
└─────────────────────────────────────────────────────────┘
```

---

### File Access Blacklist

The kernel actively blocks access to sensitive files and restricted directories before the inference layer is permitted to interact with the host filesystem.

**Blocked Files**
- `.env`
- `.ssh/id_rsa`
- `passwords.txt`
- `auth.token`

**Blocked Directories**
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

### Ephemeral API Authentication

Peridot uses a RAM-resident ephemeral authentication architecture designed to eliminate persistent credential exposure.

API keys are:
- generated cryptographically at runtime
- stored exclusively in process memory
- destroyed automatically during shutdown
- never serialized to disk

**Security Features**
- Zero disk footprint (`CWE-312` mitigation)
- `secrets.compare_digest()` timing-attack protection
- Environment-isolated token storage
- Automatic teardown and cleanup routines

No API key files are ever written to disk.

---

### Intra-Process Authentication Pipeline

Internal subsystem authentication is orchestrated through a secure intra-process environment pipeline.

Benchmarking utilities and auxiliary kernel modules dynamically retrieve:

```text
PERIDOT_AUTH_TOKEN
```

directly from the active runtime environment using controlled `psutil` process inspection.

This architecture exists specifically to preserve:
- air-gapped execution
- ephemeral credential handling
- zero-config subsystem communication
- non-persistent authentication boundaries

without introducing disk-based synchronization or plaintext token storage.

---

### Rate Limiting

The local inference API enforces strict request throttling:

```text
60 requests per minute per client IP
```

This prevents:
- local denial-of-service conditions
- runaway automation loops
- abusive subprocess flooding
- inference starvation under sustained misuse

---

### Subprocess Command Whitelisting

Medical research integration (`Folding@home`) operates under a hardcoded execution whitelist.

```python
ALLOWED_COMMANDS = ("pause", "unpause", "finish", "shutdown")
```

Any command outside the approved execution boundary is:
- rejected immediately
- isolated from execution
- logged by GhostLogger as a security violation

---

# `> SECURITY`

Peridot implements a hardened defense-in-depth architecture engineered to protect the inference runtime from malicious prompts, unauthorized file access, unsafe subprocess execution, and privilege escalation attempts.

The kernel assumes:
```text
all input is potentially hostile until validated otherwise
```

Security boundaries are enforced before the inference layer is permitted to interact with:
- the filesystem
- subprocess execution
- network interfaces
- external resources
- privileged runtime operations

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
logs/security.log
```

---

## Constitution Validation

Peridot's permission architecture is governed through:

```text
constitution.json
```

If the configuration becomes corrupted, unavailable, or malformed, the kernel automatically falls back to a locked-down safe mode.

```json
{
  "allow_file_read": false,
  "allow_file_write": false,
  "allow_code_execute": false,
  "allow_web_fetch": false
}
```

No privileged operation is permitted without explicit user authorization.

The permission layer is intentionally user-controlled:
- restrictions can be tightened
- restrictions can be relaxed
- restrictions can be removed entirely

The operator remains sovereign over runtime behavior.

---

## Hardware-Aware Security Isolation

Peridot's telemetry architecture was specifically engineered to avoid unnecessary CUDA context initialization during monitoring operations.

The runtime:
- uses direct `pynvml` polling
- bypasses heavyweight PyTorch initialization
- prevents VRAM starvation caused by telemetry overhead
- isolates monitoring from inference execution

CPU telemetry additionally implements:
- `wmic` fallbacks
- registry query fallback logic
- Ryzen-aware polling routines

to bypass inconsistent Windows 11 hardware reporting behavior.

---

## GhostLogger

GhostLogger is Peridot's asynchronous forensic auditing subsystem.

It functions as a silent observer operating independently from the primary inference and UI execution paths.

GhostLogger intercepts and records:
- authentication failures
- unauthorized file access attempts
- malicious prompt injections
- constitution validation failures
- blocked subprocess calls
- runtime security violations

without interrupting inference execution.

### Design Goals

GhostLogger was engineered around three priorities:

```text
Persistence
Isolation
Forensic Integrity
```

### Operational Characteristics

- Runs on an isolated execution thread
- Continues auditing during heavy inference load
- Preserves event continuity during runtime stress
- Maintains tamper-evident forensic logging
- Separates security events from standard audit activity

Even if the UI or inference engine experiences sustained load, GhostLogger continues operating independently to preserve a persistent forensic trail for auditing and security analysis.

For full threat model documentation and disclosure policy, see:
```text
SECURITY.md
```

---

# `> PERFORMANCE`

Measured on real hardware. No overclocking. No cherry-picked runs.

**Test Hardware**
- **GPU:** NVIDIA GeForce RTX 5050 Laptop (8GB VRAM)
- **CPU:** AMD Ryzen 7 250 AI
- **Model:** Llama-3-8B-Instruct (Q4_K_M quantization)

---

## Inference Benchmarks

> Benchmarking methodology and tooling documentation are available in:
>
> ```text
> benchmarking/BENCHMARKING.md
> ```

| Task | Output Tokens | Throughput |
|:-----|:-------------:|:----------:|
| Short Response (chat) | ~50 tokens | **~55 t/s** |
| Medium Response (logic) | ~150 tokens | **~50 t/s** |
| Long Response (creative) | ~512 tokens | **~43 t/s** |

**Measured sustained throughput:** `43–55 tokens/sec`

**Cold start:** ~6.2 seconds (model load into VRAM)

---

## VRAM Handoff Benchmarks

Dynamic GPU resource arbitration between Folding@home and active inference execution.

**Measured Latencies**
- **VRAM Hot-Swap:** 6.55 ms (pause command → VRAM freed)
- **Post-Handoff Inference:** ~50 t/s sustained (no degradation)

### Technical Implementation

When a user query enters the inference queue:
1. Peridot dispatches a WebSocket pause signal
2. Folding@home releases active VRAM allocation
3. The inference engine immediately reclaims tensor memory
4. Generation begins without requiring runtime restart

This allows Peridot to maintain:
- uninterrupted inference responsiveness
- zero restart overhead
- persistent research contribution while idle

Inference execution always takes priority.

---

# `> ARCHITECTURE`

Peridot is engineered as a layered sovereign runtime composed of isolated but composable subsystems.

Each module can:
- operate independently
- be expanded individually
- be disabled without collapsing the kernel
- communicate through controlled execution boundaries

The architecture intentionally prioritizes:
```text
Transparency
Security
Deterministic Local Execution
```

over abstraction-heavy orchestration.

---

## Core Architecture & Feature Matrix

### **1. High-Velocity RAG Pipeline (Layer 1 RAM Cache)**

Peridot's Retrieval-Augmented Generation pipeline operates entirely within localized memory space for deterministic, zero-cloud context retrieval.

#### Vector Search Layer
Uses:
```text
faiss-cpu
```

for:
- high-density vector indexing
- semantic similarity retrieval
- RAM-resident search acceleration

without requiring external vector databases.

#### Semantic Embedding Layer

Powered by:
```text
sentence-transformers
```

to generate localized semantic embeddings directly on-device.

#### Context Injection Pipeline

Relevant document chunks are dynamically injected into the active inference context window before generation begins.

This allows:
- grounded responses
- local document reasoning
- mathematically relevant context retrieval
- internet-independent augmentation

without external API routing.

---

### **2. Optimized Local Inference Engine**

The inference layer is engineered specifically for:
- 8GB VRAM environments
- sustained tensor workloads
- Ryzen/NVIDIA hybrid systems
- low-overhead local execution

#### GGUF Runtime

Built on:
```text
llama-cpp-python
```

with:
```text
cuBLAS GPU acceleration
```

allowing heavily quantized models to remain performant within constrained VRAM budgets.

#### Tensor Infrastructure

Integrated `torch` support is used for:
- embedding generation
- tensor preprocessing
- semantic routing operations
- auxiliary inference-side computation

while keeping primary generation workloads isolated to the optimized GGUF runtime.

---

### **3. Dynamic Hardware Telemetry & Runtime Awareness**

Peridot continuously monitors the host system to prevent:
- VRAM exhaustion
- thermal throttling
- inference instability
- CUDA starvation
- runaway memory conditions

#### GPU Telemetry

Uses direct:
```text
pynvml
```

polling for:
- VRAM allocation
- GPU utilization
- thermal metrics
- power telemetry

without spawning unnecessary CUDA contexts.

#### CPU Telemetry

Implements:
- `wmic` fallbacks
- registry polling fallback logic
- Ryzen-aware detection routines

to bypass inconsistent processor reporting behavior under Windows 11.

#### Adaptive Runtime Scaling

Telemetry-aware execution logic can dynamically:
- adjust queue pressure
- modify batching behavior
- stabilize inference under sustained load
- prevent hardware exhaustion events

during prolonged execution.

---

### **4. Asynchronous API & Gateway Services**

Peridot operates as a localized inference backbone capable of interfacing with external client applications while remaining air-gapped.

#### REST Layer

Built on:
```text
Flask + Werkzeug
```

to expose secure local inference endpoints.

#### Real-Time Streaming

Uses:
```text
websocket-client
```

for:
- bidirectional streaming
- low-latency inference updates
- realtime subsystem communication
- continuous runtime signaling

without HTTP polling overhead.

#### Cross-Origin Integration

`flask-cors` enables controlled local interface interoperability between:
- UI layers
- telemetry dashboards
- auxiliary local clients

while remaining fully local.

---

### **5. Persistent State & Thread-Safe Caching**

Peridot maintains structural integrity during sustained read/write operations and concurrent kernel activity.

#### File Locking

Uses:
```text
filelock
```

to prevent:
- race conditions
- concurrent write corruption
- state desynchronization

between active kernel processes.

#### Disk Cache Layer

Uses:
```text
diskcache + SQLite
```

for:
- high-speed query retrieval
- persistent intermediate caching
- reduced redundant tensor computation

during repetitive workloads.

#### Multimodal Readiness

Localized image preprocessing support is handled through:
```text
Pillow
```

for future visual pipeline integration.

---

## `[01] — Inference Engine`

Core inference runtime:

```text
Model:     Llama-3-8B-Instruct (GGUF · Q4_K_M)
Backend:   llama-cpp-python + cuBLAS
Endpoint:  localhost:5000 (no external routing)
Context:   8192 tokens (sliding window)
Precision: 4-bit quantization
```

### Why Llama-3-8B?

Llama-3-8B provides one of the strongest instruction-following architectures at the 8B scale while remaining efficient enough to sustain high-throughput local inference under an 8GB VRAM ceiling.

Quantization allows the model to:
- maintain quality
- preserve VRAM headroom
- coexist with telemetry and auxiliary subsystems
- avoid aggressive offloading penalties

during sustained execution.

---

## `[02] — Sensory Subsystems`

Local audio processing layer. No cloud APIs.

### Auditory System — Powered by Whisper

```text
Voice-to-text transcription
Hands-free command input
100% offline audio processing
```

Audio never leaves the host machine.

---

## `[03] — Permission Layer`

Peridot intercepts execution before any privileged operation is permitted to run.

Permissions are user-controlled through:

```json
{
  "allow_file_read": true,
  "allow_file_write": false,
  "allow_code_execute": false,
  "allow_web_fetch": true,
  "approved_domains": ["arxiv.org", "pubmed.ncbi.nlm.nih.gov"],
  "blocked_domains": ["example-malicious-site.com"]
}
```

### Restricted Mode

Delete:
```text
constitution.json
```

and Peridot regenerates the file in safe mode with all permissions disabled.

### Unrestricted Mode

Remove the file entirely and restart the runtime.

The operator remains fully in control of execution policy.

---

## `[04] — GhostLogger & Audit Infrastructure`

Every query, action, permission decision, and security event is tracked through Peridot's layered audit infrastructure.

### Standard Audit Trail

```text
[2026-03-14 14:32:01] QUERY     "analyze this data"
[2026-03-14 14:32:01] PERMISSION read(data.csv) → ALLOWED
[2026-03-14 14:32:01] ACTION    file_read(data.csv) → SUCCESS
[2026-03-14 14:32:03] RESPONSE  delivered (312 tokens, 5.2s)
[2026-03-14 14:32:03] HASH      sha256: a3f9c2e8...
```

### GhostLogger Security Layer

Security-critical events are isolated into:
```text
logs/security.log
```

GhostLogger operates independently from:
- UI execution
- inference generation
- telemetry polling
- auxiliary runtime operations

to preserve forensic continuity under heavy system load.

### Log Integrity

SHA-256 verification is applied during shutdown to maintain tamper-evident audit validation.

---

## `[05] — Medical Research Module (Folding@Home Integration)`

When idle, Peridot can allocate unused GPU resources toward distributed medical research through Folding@home.

### Idle State

```text
GPU Utilization:  <5%
Action:           Folding@home activated
Research:         Cancer, Alzheimer's, COVID-19 variants
Contribution:     ~400,000 points/day (varies by GPU)
```

### Active State

```text
User query detected
Action:           WebSocket pause signal dispatched
Latency:          6.55 ms (VRAM freed)
GPU Utilization:  85%+ (inference)
```

### Runtime Characteristics

- Opt-in only
- Fully auditable
- Zero restart overhead
- Dynamic VRAM reclamation
- Inference-priority execution
- Transparent runtime state tracking

### Commands

```text
research enable
research disable
research status
```

---

## `[06] — Terminal UI`

Custom `tkinter` interface engineered for technical users rather than consumer abstraction.

### Features
- Real-time CPU/RAM/GPU telemetry
- Persistent conversation history
- Drag-and-drop visual input support
- Medical research status monitoring
- Command palette integration

The interface prioritizes:
```text
Visibility
Control
Functionality
```

over minimalism.

---

# `> AUDITING & TESTING`

Peridot includes dedicated runtime validation and forensic auditing infrastructure designed to continuously verify kernel integrity during execution.

---

## GhostLogger Security Auditing

GhostLogger functions as Peridot's persistent asynchronous auditing layer.

Unlike standard logging systems, GhostLogger operates independently from:
- the inference engine
- the UI layer
- telemetry polling
- auxiliary runtime execution

This separation allows security auditing to continue even under sustained inference load.

### Recorded Events

GhostLogger tracks:
- authentication failures
- malicious prompt injections
- blocked file access attempts
- subprocess violations
- constitution validation failures
- runtime security anomalies

All security activity is written to:

```text
logs/security.log
```

without interrupting inference performance.

---

## Automated Penetration Testing

Peridot includes a dedicated red-team validation suite.

```bash
python tests/security_tests.py
```

### Test Coverage

- API authentication bypass attempts
- file blacklist enforcement
- input sanitization validation
- path traversal prevention
- permission boundary validation

---

## ARPM Validation Framework

Peridot v1.3 introduced the:

```text
Aether-Route Performance Matrix (ARPM)
```

ARPM is Peridot's dedicated benchmarking and validation framework designed to test:
- inference stability
- hardware responsiveness
- VRAM transition behavior
- sustained runtime integrity
- telemetry reliability

Benchmarking methodology and execution walkthroughs are documented in:

```text
benchmarking/BENCHMARKING.md
```

### ARPM Validation Pipeline

```text
Benchmark Runner
      ↓
Telemetry Extraction
      ↓
JSON Export
      ↓
Validation Review
```

---

## Threat Model Documentation

See:
```text
SECURITY.md
```

for:
- formal threat modeling
- security assumptions
- defense boundaries
- responsible disclosure procedures

---

# `> HARDWARE SUPPORT`

| Tier | Hardware | Mode | Expected Speed |
|:-----|:---------|:----:|:--------------:|
| ✅ **Full Support** | NVIDIA RTX 3060+ (6GB+) | Standard | 40–70 t/s |
| ✅ **Full Support** | NVIDIA RTX 4050+ (8GB+) | Standard | 50–80 t/s |
| ✅ **Full Support** | NVIDIA RTX 5050 (8GB) | Standard | **43–55 t/s** (tested) |
| ⚙️ **CPU Fallback** | Any modern x64 CPU | CPU-Only | 8–12 t/s |
| ⚠️ **Lite Mode** | AMD Radeon 680M/780M | Phi-3 | 8–15 t/s |
| ⚠️ **Lite Mode** | Intel Iris Xe | Phi-3 | 5–10 t/s |
| 🛠️ **Community** | AMD RX 6000/7000 series | ROCm (Linux) | 35–50 t/s |
| 🛠️ **Community** | Intel Arc A750/A770 | Vulkan | 25–40 t/s |

**Lite Mode:** Automatically selects Phi-3 Mini and reduces context to 2048 tokens.

**Community Builds:** Maintained by contributors. See:
```text
COMMUNITY_INSTALL.md
```

---

# `> INSTALLATION`

## Prerequisites

```text
OS:      Windows 10/11 (64-bit)
GPU:     NVIDIA RTX Series, 6GB+ VRAM recommended
Python:  3.11
Storage: ~10GB free (SSD strongly recommended)
RAM:     16GB recommended
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

### 3. Run Smart Installer

The setup wizard:
- performs hardware validation
- selects the correct CUDA build
- downloads the recommended model
- configures runtime dependencies automatically

```bash
python setup.py
```

Expected output:

```text
PERIDOT SETUP WIZARD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[✓] NVIDIA GPU detected: RTX 5050 (8.0GB VRAM)
[✓] CUDA 12.1 compatible
[✓] Recommended model: Llama-3-8B-Instruct (Q4_K_M)
[✓] Installing CUDA-enabled llama-cpp-python...
[✓] Downloading model (4.7GB)...
[✓] Writing config...

Setup complete. Run: python launcher.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

# `> USAGE`

## Launch

```bash
python launcher.py
```

Initialization sequence:

```text
>> Initializing Peridot Sovereign Kernel...
>> [1/2] Igniting Neural Engine (server.py)...
>> [WAIT] Verifying VRAM and API health...
>> [2/2] Launching Interface (main.py)...

[OK] Inference engine online — localhost:5000
[OK] Audio Subsystem: [ONLINE]
[OK] VRAM State Machine: [ACTIVE]
[OK] GhostLogger: [ACTIVE]
[OK] Peridot ready.
```

---

## Command Reference

| Command | Description |
|:--------|:------------|
| `help` | Show all available commands |
| `clear` | Clear chat history and screen |
| `status` | Display system diagnostics (Audio, VRAM, Brain) |
| `research enable` | Activate Folding@home contribution |
| `research disable` | Disable research (lock VRAM to inference) |
| `research status` | Check folding state + free VRAM |
| `exit` | Shutdown Peridot gracefully |

All remaining input is treated as natural language and processed through the inference engine.

---

## Configuration

Edit:

```text
constitution.json
```

to modify runtime permissions and execution policy.

```json
{
  "system_prompt": "You are Peridot, a sovereign AI assistant...",
  "allow_file_read": true,
  "allow_file_write": false,
  "allow_code_execute": false,
  "allow_web_fetch": true,
  "approved_domains": ["arxiv.org", "pubmed.ncbi.nlm.nih.gov"],
  "blocked_domains": []
}
```

### Reset To Defaults

Delete:
```text
constitution.json
```

and restart the runtime.

Peridot regenerates the configuration automatically.

---

# `> ROADMAP`

```text
[████████████████████] v1.0    Core Inference Engine (NVIDIA/Windows)
[████████████████████] v1.1    Performance Optimization (BETA)
[████████████████████] v1.2    Stability + VRAM Handoff + Medical Research
[████████████████████] v1.2.2  Security Hardening + Benchmarking
[████████████████████] v1.3    RAG Engine (Document Analysis)
[█████████████████░░░] v1.4    Performance Optimisation (RAM, CPU & VRAM usage)
[░░░░░░░░░░░░░░░░░░░░] v1.4.3  TurboQuant Implementation.
[░░░░░░░░░░░░░░░░░░░░] v1.5    Linux Support (Ubuntu/Debian)
[░░░░░░░░░░░░░░░░░░░░] v1.6    AMD GPU Support (ROCm)
[░░░░░░░░░░░░░░░░░░░░] v1.7    macOS Support (Apple Silicon)
[░░░░░░░░░░░░░░░░░░░░] v2.0    WebUI (FastAPI + React)
```

**Current Focus (v1.3)**

Localized document analysis, telemetry refinement, and runtime orchestration under the Aether-Route update layer.

---

# `> PHILOSOPHY`

Peridot exists because the AI industry's default assumption is that **your data belongs to them**.

It does not.

Every design decision reflects a single principle:

```text
the user is sovereign
```

That means:
- no telemetry without explicit consent
- no autonomous action without permission
- no hidden cloud inference
- no unremovable execution boundaries
- no ethical guardrails that cannot be modified by the operator

The `constitution.json` system ships with sensible defaults.

You can:
- make them stricter
- make them looser
- remove them entirely

That decision belongs to the user, not the developer.

**This is what AI should look like.**

For full philosophical reasoning, see:

```text
PHILOSOPHY.md
```

---

# `> LICENSE & DISCLAIMER`

**License:** MIT — free for personal and commercial use. Fork it, break it, build on it.

**Disclaimer:** Peridot is experimental software. The operator assumes responsibility for all commands executed, hardware utilization, and generated content. Provided as-is without warranty of any kind.

---

<div align="center">

`PERIDOT` · `SOVEREIGN AI KERNEL` · `v1.3.1 BETA`

**Engineered by [uncoalesced](https://github.com/uncoalesced)**

*Your hardware. Your model. Your rules.*

</div>