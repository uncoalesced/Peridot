<div align="center">

```
██████╗ ███████╗██████╗ ██╗██████╗  ██████╗ ████████╗
██╔══██╗██╔════╝██╔══██╗██║██╔══██╗██╔═══██╗╚══██╔══╝
██████╔╝█████╗  ██████╔╝██║██║  ██║██║   ██║   ██║   
██╔═══╝ ██╔══╝  ██╔══██╗██║██║  ██║██║   ██║   ██║   
██║     ███████╗██║  ██║██║██████╔╝╚██████╔╝   ██║   
╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝╚═════╝  ╚═════╝    ╚═╝   
```

### `SOVEREIGN AI KERNEL — v1.3 BETA`

[![STATUS](https://img.shields.io/badge/STATUS-OPERATIONAL-00ff88?style=for-the-badge&labelColor=0a0a0a)](https://github.com/uncoalesced/Peridot)
[![PLATFORM](https://img.shields.io/badge/PLATFORM-WINDOWS_GPU-4fc3f7?style=for-the-badge&labelColor=0a0a0a)](https://github.com/uncoalesced/Peridot)
[![PRIVACY](https://img.shields.io/badge/PRIVACY-AIR_GAPPED-ff4444?style=for-the-badge&labelColor=0a0a0a)](https://github.com/uncoalesced/Peridot)
[![LICENSE](https://img.shields.io/badge/LICENSE-MIT-f9e642?style=for-the-badge&labelColor=0a0a0a)](LICENSE)
[![Python](https://img.shields.io/badge/PYTHON-3.11-4fc3f7?style=for-the-badge&labelColor=0a0a0a)](https://python.org)

<br>

> **⚠️ BETA RELEASE**  
> Medical research module under active validation. [Report issues →](https://github.com/uncoalesced/Peridot/issues)

<br>

**Engineered by [uncoalesced](https://github.com/uncoalesced)**

*GPU-accelerated, air-gapped AI runtime with defense-in-depth security.*  
*Zero telemetry. Zero cloud dependency. Absolute user sovereignty.*

<br>

</div>

---

## `> OVERVIEW`

Peridot is a **local LLM runtime** with permission-based function calling that runs entirely on your hardware and logs every action it takes.

Most AI assistants are surveillance infrastructure with a chat interface. Peridot is the opposite.

```
┌─────────────────────────────────────────────────────────┐
│  USER INPUT                                             │
│     │                                                   │
│     ▼                                                   │
│  SECURITY GATE                                          │
│  • Input Sanitization (XSS/Code Injection)              │
│  • File Access Blacklist (.env, .ssh/, /etc/)           │
│  • Path Traversal Prevention                            │
│     │                                                   │
│     ▼                                                   │
│  PERMISSION LAYER                                       │
│  • constitution.json (user-controlled)                  │
│  • Function call authorization                          │
│     │                                                   │
│     ▼                                                   │
│  INFERENCE ENGINE                                       │
│  • Llama-3-8B-Instruct (Q4_K_M)                         │
│  • localhost:5000 (air-gapped)                          │
│  • 45-55 tokens/sec sustained                           │
│     │                                                   │
│     ▼                                                   │
│  AUDIT LOG                                              │
│  • SHA-256 verified                                     │
│  • Append-only (immutable)                              │
│  • Security events logged separately                    │
└─────────────────────────────────────────────────────────┘
```

---

### File Access Blacklist

The kernel actively blocks access to sensitive files and directories:

**Blocked Files:**
- `.env` (environment variables)
- `.ssh/id_rsa` (SSH private keys)
- `passwords.txt` (credential stores)
- `auth.token` (authentication tokens)

**Blocked Directories:**
- `C:\Windows\` (Windows system files)
- `/etc/` (Linux configuration)
- `/root/` (Linux root home)
- `/boot/` (Bootloader files)

Path traversal attacks (`../../../etc/passwd`) are **automatically neutralized** via path normalization.

---

### Ephemeral API Authentication

API keys are generated **cryptographically in RAM** at boot and destroyed on shutdown.

**Features:**
- Zero disk footprint (CWE-312 mitigation)
- `secrets.compare_digest()` prevents timing attacks
- Keys exist only in `os.environ` (process memory)
- Automatic cleanup on exit

**No API key files are ever written to disk.**

---

### Rate Limiting

Local inference API enforces strict request throttling:

```
60 requests per minute per client IP
```

Prevents:
- Local DoS attacks
- Automation abuse
- Runaway scripts

---

### Subprocess Command Whitelisting

Medical research integration (Folding@Home) uses **hardcoded command whitelist**:

```python
ALLOWED_COMMANDS = ("pause", "unpause", "finish", "shutdown")
```

Any other command is **immediately rejected** and logged as a security violation.

---

## `> SECURITY`

Peridot v1.2.2 introduced a **hardened defense-in-depth security architecture** protecting the inference engine from malicious input and unauthorized access.

### Input Sanitization

All user prompts are sanitized **before** reaching the LLM. Blocked patterns include:

```python
<script>         # XSS attacks
eval()           # Code execution
os.system()      # Shell injection
__import__       # Python import abuse
subprocess.      # Subprocess exploitation
```

Malicious inputs are **immediately rejected** and logged to `logs/security.log`.

---

### Constitution Validation

If `constitution.json` is missing or corrupted, Peridot **automatically falls back** to a locked-down safe mode:

```json
{
  "allow_file_read": false,
  "allow_file_write": false,
  "allow_code_execute": false,
  "allow_web_fetch": false
}
```

**No privileged operations occur without explicit user authorization.**

For full threat model and vulnerability disclosure process, see [SECURITY.md](SECURITY.md).

---

## `> PERFORMANCE`

Measured on **real hardware**. No overclocking. No cherry-picked runs.

**Test Hardware:**
- **GPU:** NVIDIA GeForce RTX 5050 Laptop (8GB VRAM)
- **CPU:** AMD Ryzen 7 250 AI
- **Model:** Llama-3-8B-Instruct (Q4_K_M quantization)

---

### Inference Benchmarks

> **Note:** Benchmark images will be added in the upcoming commits.  
> Current data is measured via the `\benchmarking` folder in the repository.

| Task | Output Tokens | Throughput |
|:-----|:-------------:|:----------:|
| Short Response (chat) | ~50 tokens | **~55 t/s** |
| Medium Response (logic) | ~150 tokens | **~50 t/s** |
| Long Response (creative) | ~512 tokens | **~45 t/s** |

**Measured sustained throughput:** `45–55 tokens/sec`

**Cold start:** ~6.2 seconds (model load into VRAM)

> For comparison: Average human reading speed is ~4 tokens/sec.  
> Peridot generates text **~12× faster** than you can read it.

---

### VRAM Handoff Benchmarks

Dynamic GPU resource reallocation between Folding@Home and inference.

> **Note:** VRAM handoff benchmark images will be added in the upcoming commits.

**Measured Latencies:**
- **VRAM Hot-Swap:** 6.55 ms (pause command → VRAM freed)
- **Post-Handoff Inference:** ~50 t/s sustained (no degradation)

**Technical Implementation:**  
When a user query arrives, the system sends a WebSocket `pause` command to Folding@Home. The FAHClient releases GPU memory in **6.55 ms**, allowing the inference engine to immediately reclaim VRAM without performance loss.

**Zero overhead.** Inference always takes priority.

---

## `> ARCHITECTURE`

Peridot is built as a set of independent, composable modules. Each subsystem can be enabled, configured, or disabled without touching the core kernel.

### Core Architecture & Feature Matrix

**1. High-Velocity RAG Pipeline (Layer 1 RAM Cache)**

The Retrieval-Augmented Generation (RAG) engine operates entirely in-memory for zero-latency context retrieval.

- **Vector Search Engine:** Utilizes `faiss-cpu` for localized, high-density vector indexing and similarity search. This avoids the overhead of external vector databases, keeping the embedding search strictly within local RAM.
- **Semantic Embeddings:** Powered by `sentence-transformers`, generating dense vector representations of textual data locally.
- **Context Injection:** Seamlessly fetches mathematically relevant document chunks and injects them into the LLM context window prior to generation, ensuring grounded and context-aware responses without internet access.

**2. Optimized Local Inference Engine**

The generation layer is built for hardware efficiency and execution speed.

- **GGUF/Quantized Execution:** Built on `llama-cpp-python`, allowing the kernel to run heavily quantized LLMs (e.g., 4-bit or 8-bit). This is strictly optimized to keep large models within an 8GB VRAM threshold while offloading secondary layers to the system CPU.
- **PyTorch Backend:** Integrated `torch` support for custom tensor operations, embedding generation, and potential multimodal routing.

**3. Dynamic Hardware Telemetry & Load Balancing**

The kernel does not operate blindly; it maintains real-time awareness of the host hardware state to prevent thermal throttling and out-of-memory (OOM) crashes.

- **GPU Monitoring:** Uses `nvidia-ml-py` to track VRAM allocation, GPU utilization, and core temperatures on Nvidia hardware (e.g., RTX 50-series) at the driver level.
- **System Telemetry:** Employs `psutil` to monitor system RAM (optimizing for 16GB environments) and CPU thread saturation (optimized for Ryzen architectures).
- **Adaptive Throttling:** The pipeline can dynamically adjust batch sizes or queue requests if the hardware telemetry detects resource exhaustion.

**4. Asynchronous API & Gateway Services**

Peridot acts as a localized server backbone, ready to interface with client applications.

- **RESTful Backbone:** Built on `Flask` and `Werkzeug` to provide secure, local HTTP endpoints for client requests.
- **Real-Time Bi-Directional Streaming:** Integrates `websocket-client` for continuous, low-latency data streams—critical for real-time transcription, screen-sharing analysis, or ongoing chat generation without HTTP overhead.
- **Cross-Origin Support:** `flask-cors` ensures seamless integration with separate front-end interfaces or local network applications.

**5. Persistent State & Thread-Safe Caching**

Maintains structural integrity during continuous read/write operations.

- **Asynchronous File Locking:** Uses `filelock` to prevent race conditions when multiple concurrent kernel processes attempt to read or write to the same memory banks or configuration files.
- **High-Speed Disk Caching:** Utilizes `diskcache` backed by SQLite for lightning-fast retrieval of frequent queries or intermediate tensor states, reducing redundant computational overhead.
- **Multimodal Readiness:** Incorporates `Pillow` for localized image processing and transformation before passing visual data into the inference or RAG pipelines.

---

### `[01] — Inference Engine`

Core LLM runtime built on `llama-cpp-python` with `cuBLAS` GPU acceleration.

```
Model:     Llama-3-8B-Instruct (GGUF · Q4_K_M)
Backend:   llama-cpp-python + cuBLAS
Endpoint:  localhost:5000 (no external routing)
Context:   8192 tokens (sliding window)
Precision: 4-bit quantization (optimal VRAM/quality balance)
```

**Why Llama-3-8B?**  
Best instruction-following accuracy at the 8B parameter scale. Fits comfortably in 6GB VRAM with Q4 quantization, leaving headroom for system processes.

---

### `[02] — Sensory Subsystems`

Local audio processing. No cloud APIs.

**Auditory System** — powered by `OpenAI Whisper`

```
Voice-to-text transcription
Hands-free command input
100% offline (no audio transmission)
```

---

### `[03] — Permission Layer`

Function-call interceptor that blocks execution **before any action runs**.

Edit `constitution.json` to control behavior:

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

**To remove all restrictions:** Delete `constitution.json`. Peridot enters unrestricted mode.

**To enable safe mode:** Delete `constitution.json` and restart. Peridot regenerates with all permissions disabled.

---

### `[04] — Audit Log`

Append-only log of every query, action, and permission decision.

```
[2026-03-14 14:32:01] QUERY     "analyze this data"
[2026-03-14 14:32:01] PERMISSION read(data.csv) → ALLOWED
[2026-03-14 14:32:01] ACTION    file_read(data.csv) → SUCCESS
[2026-03-14 14:32:03] RESPONSE  delivered (312 tokens, 5.2s)
[2026-03-14 14:32:03] HASH      sha256: a3f9c2e8...
```

SHA-256 session hashing applied at shutdown to **cryptographically verify log integrity**.

**Security events are logged separately** to `logs/security.log` for forensic analysis.

---

### `[05] — Medical Research Module (Folding@Home Integration)`

When Peridot is idle, your GPU contributes to medical research via **Folding@home** (Stanford University).

**Idle State:**
```
GPU Utilization:  <5%
Action:           Folding@home activated
Research:         Cancer protein dynamics, Alzheimer's, COVID-19 variants
Contribution:     ~400,000 points/day (varies by GPU)
```

**Active State:**
```
User query detected
Action:           WebSocket pause command sent
Latency:          6.55 ms (VRAM freed)
GPU Utilization:  85% (inference)
```

**Features:**
- **Opt-in** (disabled by default)
- **Audited** (all sessions logged)
- **Zero overhead** (inference always takes priority)
- **Transparent** (see exactly when GPU contributed)

**Diseases targeted:** Alzheimer's, Cancer, Parkinson's, COVID-19 variants

Commands:
```
research enable   # Activate medical research contribution
research disable  # Disable (VRAM locked to inference only)
research status   # Check current folding state + VRAM stats
```

---

### `[06] — Terminal UI`

Custom `tkinter` interface designed for technical users.

**Features:**
- Real-time hardware telemetry (CPU/RAM/GPU VRAM)
- Drag-and-drop image input (for future vision modules)
- Persistent conversation history
- Medical research status indicator
- Command palette

**Not designed to look like a consumer product.** Designed to be **functional**.

---

## `> AUDITING & TESTING`

### Dedicated Security Logger

Asynchronous security event logger:

```
logs/security.log
```

Records:
- Authentication failures
- Blocked file access attempts
- Malicious input rejections
- Constitution validation errors

Runs **silently** without affecting UI performance.

---

### Automated Penetration Testing

Built-in red team test suite validates security measures:

```bash
python tests/security_tests.py
```

**Tests include:**
- API authentication bypass attempts
- File blacklist enforcement
- Input sanitization effectiveness
- Path traversal attack prevention

---

### Threat Model Documentation

See [SECURITY.md](SECURITY.md) for:
- Formal threat model
- Security assumptions
- Active defense mechanisms
- Responsible vulnerability disclosure process

---

## `> HARDWARE SUPPORT`

| Tier | Hardware | Mode | Expected Speed |
|:-----|:---------|:----:|:--------------:|
| ✅ **Full Support** | NVIDIA RTX 3060+ (6GB+) | Standard | 40–70 t/s |
| ✅ **Full Support** | NVIDIA RTX 4050+ (8GB+) | Standard | 50–80 t/s |
| ✅ **Full Support** | NVIDIA RTX 5050 (8GB) | Standard | **45–55 t/s** (tested) |
| ⚙️ **CPU Fallback** | Any modern x64 CPU | CPU-Only | 8–12 t/s |
| ⚠️ **Lite Mode** | AMD Radeon 680M/780M | Phi-3 | 8–15 t/s |
| ⚠️ **Lite Mode** | Intel Iris Xe | Phi-3 | 5–10 t/s |
| 🛠️ **Community** | AMD RX 6000/7000 series | ROCm (Linux) | 35–50 t/s |
| 🛠️ **Community** | Intel Arc A750/A770 | Vulkan | 25–40 t/s |

**Lite Mode:** Automatically selects Phi-3 Mini and reduces context to 2048 tokens.  
**Community Builds:** Maintained by contributors. See [COMMUNITY_INSTALL.md](COMMUNITY_INSTALL.md).

---

## `> INSTALLATION`

### Prerequisites

```
OS:      Windows 10/11 (64-bit)
GPU:     NVIDIA RTX Series, 6GB+ VRAM recommended
Python:  3.11
Storage: ~10GB free (SSD strongly recommended)
```

### Setup

**1. Clone the repository**

```bash
git clone https://github.com/uncoalesced/Peridot.git
cd Peridot
```

**2. Create virtual environment**

```bash
python -m venv venv
.\venv\Scripts\activate
```

**3. Run smart installer**

The setup wizard performs a hardware audit, selects the correct CUDA build, and downloads the appropriate model automatically.

```bash
python setup.py
```

Expected output:
```
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

## `> USAGE`

### Launch

```bash
python launcher.py
```

Wait for initialization:

```
>> Initializing Peridot Sovereign Kernel...
>> [1/2] Igniting Neural Engine (server.py)...
>> [WAIT] Verifying VRAM and API health...
>> [2/2] Launching Interface (main.py)...

[OK] Inference engine online — localhost:5000
[OK] Audio Subsystem: [ONLINE]
[OK] VRAM State Machine: [ACTIVE]
[OK] Peridot ready.
```

---

### Command Reference

| Command | Description |
|:--------|:------------|
| `help` | Show all available commands |
| `clear` | Clear chat history and screen |
| `status` | Display system diagnostics (Audio, VRAM, Brain) |
| `research enable` | Activate Folding@home contribution |
| `research disable` | Disable research (lock VRAM to inference) |
| `research status` | Check folding state + free VRAM |
| `exit` | Shutdown Peridot gracefully |

All other input is treated as natural language and processed by the inference engine.

---

### Configuration

Edit `constitution.json` to modify Peridot's permissions and behavior:

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

**Reset to defaults:** Delete `constitution.json` and restart. Peridot regenerates it automatically.

---

## `> ROADMAP`

```
[████████████████████] v1.0    Core Inference Engine (NVIDIA/Windows)
[████████████████████] v1.1    Performance Optimization (BETA)
[████████████████████] v1.2    Stability + VRAM Handoff + Medical Research
[████████████████████] v1.2.2  Security Hardening + Benchmarking
[████████████████████] v1.3    RAG Engine (Document Analysis)
[██░░░░░░░░░░░░░░░░░░] v1.4    Performance Optimisation (RAM, CPU & VRAM usage)
[░░░░░░░░░░░░░░░░░░░░] v1.4.3  TurboQuant Implementation.
[░░░░░░░░░░░░░░░░░░░░] v1.5    Linux Support (Ubuntu/Debian)
[░░░░░░░░░░░░░░░░░░░░] v1.6    AMD GPU Support (ROCm)
[░░░░░░░░░░░░░░░░░░░░] v1.7    macOS Support (Apple Silicon)
[░░░░░░░░░░░░░░░░░░░░] v2.0    WebUI (FastAPI + React)
```

**Current Focus (v1.3):**  
RAG engine for local document analysis with FAISS vector storage and PyMuPDF ingestion pipeline.

---

## `> PHILOSOPHY`

Peridot exists because the AI industry's default assumption is that **your data belongs to them**.

It does not.

Every design decision reflects a single principle: **the user is sovereign**.

That means:
- No telemetry without explicit consent
- No autonomous action without permission
- No ethical guardrails that cannot be modified or removed by the person running the software

The `constitution.json` system ships with sensible defaults. You can make them stricter. You can make them looser. **You can delete the file entirely.**

That choice belongs to **you**, not the developer.

**This is what AI should look like.**

For full philosophical reasoning, see [PHILOSOPHY.md](PHILOSOPHY.md).

---

## `> LICENSE & DISCLAIMER`

**License:** MIT — free for personal and commercial use. Fork it, break it, build on it.

**Disclaimer:** Peridot is experimental software. The user assumes full responsibility for all commands executed, content generated, and hardware usage. Provided as-is, without warranty of any kind.

---

<div align="center">

`PERIDOT` · `SOVEREIGN AI KERNEL` · `v1.3 BETA`

**Engineered by [uncoalesced](https://github.com/uncoalesced)**

*Your hardware. Your model. Your rules.*

</div>