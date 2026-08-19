<div align="center">

# PERIDOT SOVEREIGN KERNEL

### Community Hardware Implementation

*Community-Maintained Deployment Documentation*

</div>

---

# `> CRITICAL DISCLAIMER: UNCHARTED SILICON`

To be completely direct:

As of the current build, the Peridot Kernel has ONLY been officially tested and benchmarked on an NVIDIA RTX 5050 (8GB).

CPU fallback mode has been successfully validated (specifically against architectures like the Ryzen 7 250 AI with 16GB of DDR5 RAM), and while it functions natively, official CPU throughput benchmarks have not been established.

We have not tested this on:
- AMD GPUs
- Intel Arc GPUs
- Native Linux environments

If you are deploying Peridot on non-NVIDIA hardware, there is absolutely no concrete assurance that it will work out of the box.

However, if you do test this, whether it runs flawlessly at 60 t/s or crashes spectacularly with an Out Of Memory fault any telemetry, crash logs, or benchmarks you are comfortable sharing are immensely valuable.

If it breaks, tell us.

If it works, prove it.

This documentation outlines the theoretical deployment procedures for the Peridot kernel on non-NVIDIA architectures.

These configurations are strictly community maintained.

Hardware specific issues should be logged in the repository Issue tracker utilizing the:

```text
[AMD]
[Intel Arc]
```

tags.

---

# `> 0. NATIVE LINUX (NVIDIA) — v1.5.4`

Target distributions: **Debian 12**, **Ubuntu 22.04 LTS or newer**, **Arch Linux**.

---

## Validation Status

```text
Code:     complete
Hardware: NOT VALIDATED
```

No Linux machine with an NVIDIA GPU was available during the v1.5.4 cycle.
The pathing, session detection and sensor-degradation paths are covered by
automated tests, but **no GPU-accelerated inference run has been performed on
Linux**. Do not treat the throughput figures in `README.md` as transferable.

If you boot this on Linux with a working CUDA stack, the crash log or the
benchmark is equally valuable. File it under the `[Linux]` tag.

---

## System Dependencies

The acoustic sensor binds PortAudio and the keystroke sensor binds X11. Both
degrade cleanly if absent, but for the full ZAT-SCS feature set:

### Debian 12 / Ubuntu 22.04+

```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-tk
```

### Arch Linux

```bash
sudo pacman -S --needed portaudio tk
```

---

## Wayland: ZAT-SCS Runs Degraded

This is expected behaviour, not a fault.

Peridot's predictive preemption layer measures keystroke cadence through a
`pynput` global hook. That hook is an **X11 client**. Wayland compositors do
not expose global keyboard input to unprivileged clients by design, and Wayland
is the default session on Ubuntu 22.04+, Fedora, and most Arch desktop setups.

The kernel detects the session at boot and adapts rather than crashing:

| Session | Detection source | Keyboard term | P(I_t) |
|---|---|---|---|
| Windows / macOS | `sys.platform` | active | full |
| X11 | `XDG_SESSION_TYPE=x11` or `$DISPLAY` | active | full |
| **Wayland** | `XDG_SESSION_TYPE=wayland` or `$WAYLAND_DISPLAY` | **weight = 0** | **audio-only** |
| Headless / TTY | neither set | **weight = 0** | **audio-only** |

Under Wayland the interaction probability reduces to the acoustic term alone:

```text
P(I_t) = min(1.0, P(I_{t-1}) * e^(-lambda * dt) + w_aud * g(A))
```

The degradation is logged at WARNING on boot:

```text
[ZAT-SCS] P(I_t) degraded to audio-only (session=wayland,
reason=global keyboard hook unavailable under 'wayland' session).
WEIGHT_KEY 0.45 -> 0.00.
```

Consequence: speculative preemption still fires on ambient acoustic activity,
but typing alone will not warm the VRAM. Inference correctness is unaffected --
you lose the latency optimisation, nothing else. If both sensors are absent the
kernel logs that speculative preemption is inert and falls back to standard
prefill latency.

### Forcing X11 (optional)

To get the full ZAT-SCS feature set, log into an X11 session instead. On GNOME,
uncomment in `/etc/gdm3/custom.conf`:

```text
WaylandEnable=false
```

Then restart the display manager. This is an operator choice, not a
requirement -- Peridot runs correctly either way.

---

## Sovereign Mode on Linux

Identical to Windows. The kernel force-sets `HF_HUB_OFFLINE=1` and
`TRANSFORMERS_OFFLINE=1` at boot regardless of `.env` contents, and refuses to
start if either is unset. To acquire a model after install, use the isolated
fetch path -- it is the only thing in the system permitted to go online:

```bash
python -m core_system.model_fetch <repo_id> <filename>
```

---

# `> 1. AMD RADEON ARCHITECTURE (ROCm)`

Support for AMD graphics processing units is currently restricted to Linux environments utilizing the ROCm framework.

Windows deployments via ROCm are highly experimental and are not supported within this documentation.

---

## Hardware Compatibility Matrix

| Architecture | VRAM | Validation Status | Expected Inference (t/s) |
|:--|:--:|:--:|:--:|
| RX 6600 | 8GB | Unverified | 35-42 (Est.) |
| RX 6700 XT | 12GB | Unverified | 42-50 (Est.) |
| RX 6800 XT | 16GB | Unverified | 48-55 (Est.) |
| RX 6900 XT | 16GB | Unverified | 50-58 (Est.) |
| RX 7600 | 8GB | Unverified | 38-45 (Est.) |
| RX 7700 XT | 12GB | Unverified | 45-52 (Est.) |
| RX 7800 XT | 16GB | Unverified | 52-60 (Est.) |
| RX 7900 XT | 20GB | Unverified | 58-65 (Est.) |
| RX 7900 XTX | 24GB | Unverified | 60-70 (Est.) |

---

## System Prerequisites

- **Operating System:** Ubuntu 22.04 LTS, Ubuntu 24.04 LTS, or Debian 12
- **Kernel:** 5.15 or later
- **Drivers:** AMDGPU kernel module
- **Environment:** Python 3.11 or 3.12

---

## Deployment Steps

---

### Step 1.1: Verify Hardware Detection

Ensure the operating system recognizes the AMD architecture.

```bash
lspci | grep -i amd
lsmod | grep amdgpu
```

---

### Step 1.2: Install ROCm Framework

Execute the following commands based on your Linux distribution to install the Radeon Open Compute (ROCm) stack.

#### Ubuntu 24.04 LTS

```bash
wget https://repo.radeon.com/amdgpu-install/6.0/ubuntu/noble/amdgpu-install_6.0.60000-1_all.deb
sudo dpkg -i amdgpu-install_6.0.60000-1_all.deb
sudo apt update
sudo amdgpu-install --usecase=rocm
sudo usermod -a -G render,video $USER
sudo reboot
```

---

### Step 1.3: Verify ROCm Installation

Post-reboot, confirm the compute nodes are active.

```bash
/opt/rocm/bin/rocminfo
/opt/rocm/bin/rocm-smi
```

---

### Step 1.4: Repository Cloning and Environment Setup

```bash
git clone https://github.com/uncoalesced/Peridot.git
cd Peridot

python -m venv venv
source venv/bin/activate

pip install --upgrade pip
```

---

### Step 1.5: Build Engine with HIP Support

The `llama-cpp-python` binding must be compiled manually to interface with the ROCm backend.

```bash
export ROCM_PATH=/opt/rocm
export HIP_PATH=/opt/rocm

sudo apt install cmake build-essential

CMAKE_ARGS="-DLLAMA_HIPBLAS=on" pip install llama-cpp-python --no-cache-dir --force-reinstall --upgrade
```

---

### Step 1.6: Finalize Dependencies and Model Allocation

```bash
pip install -r requirements.txt

mkdir -p models

wget -O models/llama-3-8b-q4.gguf https://huggingface.co/QuantFactory/Meta-Llama-3-8B-Instruct-GGUF/resolve/main/Meta-Llama-3-8B-Instruct.Q4_K_M.gguf
```

---

### Step 1.7: Configuration (`config.py`)

Modify the configuration file to address the AMD hardware.

```python
MODEL_PATH = "models/llama-3-8b-q4.gguf"
GPU_LAYERS = 33  # Adjust downward if VRAM is <16GB
N_CTX = 4096
USE_GPU = True
GPU_TYPE = "amd"
```

---

### Step 1.8: System Initialization

```bash
export GPU_DEVICE_ORDINAL=0
export HIP_VISIBLE_DEVICES=0

python launcher.py
```

---

# `> 2. INTEL ARC ARCHITECTURE (VULKAN)`

Intel Arc integrations utilize the Vulkan backend, which maintains operational compatibility across both Windows 11 and Linux environments.

---

## Hardware Compatibility Matrix

| Architecture | VRAM | Validation Status | Expected Inference (t/s) |
|:--|:--:|:--:|:--:|
| Arc A310 | 4GB | Unverified | 15-20 (Est.) |
| Arc A380 | 6GB | Unverified | 20-28 (Est.) |
| Arc A750 | 8GB | Unverified | 25-35 (Est.) |
| Arc A770 | 8GB | Unverified | 28-38 (Est.) |
| Arc A770 | 16GB | Unverified | 30-42 (Est.) |

---

## Deployment Steps

---

### Step 2.1: Install Intel Drivers and Vulkan SDK

#### Windows

Install:
- latest Intel Arc graphics drivers
- LunarG Vulkan SDK (Runtime)

#### Linux (Ubuntu 22.04+)

Ensure kernel:

```text
6.2+
```

is active.

Install runtime packages:

```bash
sudo apt update
sudo apt install intel-opencl-icd vulkan-tools mesa-vulkan-drivers
```

---

### Step 2.2: Build Engine with Vulkan Support

Ensure the virtual environment is active before compilation.

#### Windows (PowerShell)

```powershell
$env:CMAKE_ARGS="-DLLAMA_VULKAN=on"

pip install llama-cpp-python --no-cache-dir --force-reinstall --upgrade
```

#### Linux

```bash
sudo apt install cmake build-essential

CMAKE_ARGS="-DLLAMA_VULKAN=on" pip install llama-cpp-python --no-cache-dir --force-reinstall --upgrade
```

---

### Step 2.3: Configuration (`config.py`)

Adjust the VRAM layer offloading to accommodate Intel architecture.

```python
MODEL_PATH = "models/llama-3-8b-q4.gguf"
GPU_LAYERS = 25  # Recommended baseline for 8GB Arc GPUs
N_CTX = 4096
USE_GPU = True
GPU_TYPE = "intel_arc"
```

---

# `> 3. MEDICAL RESEARCH MODULE INTEGRATION`

The Peridot kernel VRAM handoff for medical research (Folding@home) natively supports:
- AMD (via OpenCL)
- Intel (via Vulkan)

backends.

To initialize the daemon on either architecture:

```bash
python medical_research.py setup
```

---

## Expected Throughput

### AMD RX 6600+

```text
~300,000 PPD (Points Per Day)
```

### Intel Arc A750+

```text
~200,000 PPD
```

---

# `> 4. SUBMITTING TELEMETRY AND BENCHMARK DATA`

To expand hardware validation matrices, community members are encouraged to submit performance telemetry.

If you achieve stable execution on undocumented hardware:

- fork the repository
- update the relevant markdown tables
- submit a Pull Request

---

## PR Title

```text
Hardware Telemetry: [GPU Model]
```

---

## Description Requirements

- Hardware Architecture (e.g., AMD RX 7800 XT)
- Host CPU and RAM Setup
- OS Version / Kernel
- Driver or ROCm Build Version
- Sustained Inference Speed (t/s)
- Layer Configuration (`GPU_LAYERS`)

---

# `> 5. RAG ENGINE: HARDWARE-AWARE EMBEDDING TIERS`

Peridot dynamically scales Retrieval Augmented Generation (RAG) capabilities based on available VRAM.

This prevents:
- Out-Of-Memory (OOM) faults
- instability
- disruption of the ~21ms Folding@home handoff latency

---

## Tier 0: LITE Configuration (4GB - 6GB VRAM)

### Target Hardware

- Intel Arc A310
- AMD RX 6500 XT

### Embedding Model

```text
all-MiniLM-L3-v2 (~45MB)
```

### Execution

```text
Forced strictly to CPU
```

### Details

Leaves 100% of limited VRAM available for the quantized LLM.

Retrieval takes slightly longer, but system stability is guaranteed.

---

## Tier 1: Baseline Configuration (8GB VRAM)

### Target Hardware

- AMD RX 6600
- Intel Arc A750

### Embedding Model

```text
all-MiniLM-L6-v2 (~90MB)
```

### Execution

```text
Forced strictly to CPU
```

### Details

The standard Peridot configuration.

Balances highly accurate retrieval with zero VRAM footprint while protecting the background medical research state machine.

---

## Tier 2: Balanced Configuration (12GB - 16GB VRAM)

### Target Hardware

- AMD RX 6700 XT
- RX 7800 XT
- Intel Arc A770

### Embedding Model

```text
nomic-embed-text-v1.5 (~550MB)
```

### Execution

```text
VRAM Accelerated
```

### Details

Utilizes the VRAM buffer to load a massive:

```text
8192-token context window
```

Capable of ingesting entire document chapters in a single pass with sub-millisecond retrieval.

---

## Tier 3: High-Fidelity Configuration (24GB+ VRAM)

### Target Hardware

- AMD RX 7900 XTX

### Embedding Model

```text
mxbai-embed-large-v1 (~1.5GB)
```

### Execution

```text
VRAM Accelerated
```

### Details

Enterprise-grade retrieval.

Best suited for:
- massive personal databases
- deep semantic search operations

---

<div align="center">

**Engineered by uncoalesced**

</div>