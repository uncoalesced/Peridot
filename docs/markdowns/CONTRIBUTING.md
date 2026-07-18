<div align="center">

# CONTRIBUTING TO PERIDOT

### Sovereign Development Protocol — v1.5.3-STABLE

*Build First. Ship Code. No Hype.*

</div>

---

# `> OVERVIEW`

Peridot is an open-source sovereign AI kernel engineered for:
- local inference
- hardware-aware orchestration
- deterministic execution
- defense-in-depth security
- zero-cloud operation

The runtime is designed to operate:
- fully local
- air-gapped
- auditable
- operator-controlled

without hidden telemetry, remote inference, or centralized dependency.

We welcome engineers interested in:
- local AI infrastructure
- VRAM optimization
- low-level orchestration
- inference acceleration
- security engineering
- systems architecture
- offline AI ecosystems

Contributions are welcome provided they respect the core philosophy:

```text
Build First.
Ship Code.
No Hype.
```

---

# `> THE PERIDOT DIRECTIVES`

## Architecture Rules

If your implementation violates these directives, the Pull Request will be rejected.

---

## 1. Absolute Sovereignty (Zero Cloud)

Peridot does not phone home.

Pull Requests introducing:
- remote inference APIs
- telemetry harvesting
- cloud-dependent orchestration
- hidden analytics
- external vector database dependency
- non-transparent remote execution

will not be merged.

This includes:
- OpenAI integrations
- Anthropic routing
- telemetry SDKs
- silent HuggingFace trackers
- cloud-first middleware

The operator remains sovereign over execution.

---

## 2. Security By Design

Peridot follows a strict defense-in-depth architecture.

Any capability involving:
- routing logic
- execution control
- file access
- subprocess behavior
- runtime permissions
- authentication
- external interaction

must pass through the security boundary enforced by:

```text
core_system/security.py
```

Pull Requests that:
- bypass sanitization
- weaken authentication
- circumvent permission validation
- reduce audit visibility
- introduce opaque execution behavior

will be rejected immediately.

---

## 3. The VRAM State Machine

VRAM is a finite resource.

Inference always takes absolute priority.

Enhancements affecting:
- Folding@home integration
- telemetry systems
- background workers
- RAG indexing
- asynchronous pipelines
- auxiliary runtime services

must preserve low-latency VRAM arbitration behavior.

Target handoff latency:

```text
<500ms
```

Do not introduce:
- persistent VRAM starvation
- unnecessary CUDA initialization
- blocking GPU synchronization
- runaway memory allocation

The kernel must remain responsive under sustained load.

---

## 4. Hardware Agnosticism

Peridot is optimized for NVIDIA Blackwell-class hardware, but the architecture must degrade gracefully.

Code should:
- detect unsupported hardware cleanly
- fallback to CPU execution safely
- avoid hard crashes on missing CUDA support
- preserve deterministic behavior where practical

Community support for:
- ROCm
- Vulkan
- CPU-only execution
- Intel Arc
- AMD Radeon

must not be broken by architecture-specific assumptions.

---

# `> DEVELOPMENT WORKFLOW`

---

## 1. Fork & Clone

Fork the repository and initialize a sterile virtual environment.

```bash
git clone https://github.com/YOUR-USERNAME/Peridot.git
cd Peridot

python -m venv venv
```

### Activate Environment

#### Linux / macOS

```bash
source venv/bin/activate
```

#### Windows PowerShell

```powershell
.\venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt --upgrade
```

---

## 2. Environment Setup

Never commit:
- API keys
- authentication tokens
- runtime credentials
- `.env` files

Create your local environment configuration:

```bash
cp .env.example .env
```

Ensure:

```text
API_KEY
```

is configured before launching the runtime.

---

## 3. Branch Naming Convention

Do not commit directly to:

```text
main
```

Create a dedicated branch for all work.

### Features

```text
feat/your-feature-name
```

Example:

```text
feat/fp4-turboquant
```

---

### Bug Fixes

```text
fix/issue-description
```

Example:

```text
fix/l1-cache-collision
```

---

### Security Patches

```text
sec/vulnerability-patch
```

Example:

```text
sec/auth-timing-attack
```

---

### Documentation

```text
docs/update-name
```

---

### Create Branch

```bash
git checkout -b feat/your-feature-name
```

---

# `> SUBMISSION PROTOCOL`

---

## 1. Commit Standards

Peridot uses:
- atomic commits
- descriptive history
- forensic traceability

Follow the Conventional Commits standard.

### Format

```text
<type>: <description>
```

---

### Good

```text
feat: implement Aether-Route CPU semantic router
```

```text
fix: patch L1 cache type error during context injection
```

```text
sec: harden subprocess sanitization boundary
```

---

### Bad

```text
fixed stuff
```

```text
update server.py
```

```text
misc changes
```

---

## 2. Pull Request Requirements

All Pull Requests should include:

---

### The Goal

What does the PR accomplish?

Be concise and technically precise.

---

### Architecture Impact

Explain impact on:
- VRAM usage
- inference speed
- memory pressure
- telemetry behavior
- runtime stability
- security boundaries

---

### Testing Done

Explicitly state:
- hardware configuration
- operating system
- inference backend
- relevant runtime conditions

Example:

```text
Validated on RTX 5050 Laptop GPU
16GB DDR5 RAM
Windows 11
CUDA 12.1
Llama-3-8B Q4_K_M
```

---

# `> REVIEW PROCESS`

The uncoalesced collective reviews Pull Requests for:

- adherence to sovereign architecture principles
- zero-cloud compliance
- security integrity
- runtime stability
- VRAM state machine preservation
- code clarity
- Pythonic efficiency
- auditability
- deterministic behavior

A PR may be rejected if it:
- weakens architectural transparency
- introduces unnecessary abstraction
- damages runtime stability
- reduces operator control
- compromises local-first execution

---

# `> ENGINEERING PHILOSOPHY`

Peridot prioritizes:

```text
Transparency
Performance
Security
Deterministic Local Execution
```

over:
- hype-driven architecture
- unnecessary frameworks
- opaque automation
- dependency bloat
- cloud convenience

The project is engineered for operators, not consumers.

---

# `> FINAL PRINCIPLE`

Peridot is not designed to become another surveillance platform wearing an AI interface.

Every contribution should reinforce:

```text
Your hardware.
Your model.
Your authority.
```

Act accordingly.

---

<div align="center">

`PERIDOT CONTRIBUTION PROTOCOL` · `v1.5.3`

**Engineered by uncoalesced**

*Build First.*  
*Ship Code.*  
*No Hype.*

</div>