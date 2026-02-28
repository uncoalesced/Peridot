# Peridot Sovereign Kernel  
## Community Hardware Implementation

---

This documentation outlines the deployment procedures for the Peridot kernel on non-NVIDIA architectures, specifically AMD Radeon and Intel Arc graphics processors.

These configurations are strictly community-maintained.

The Peridot core architecture is optimized and officially validated exclusively on NVIDIA environments; therefore, alternative GPU deployments require manual configuration and are provided without official guarantees of stability.

Hardware-specific issues should be logged in the repository's Issue tracker utilizing the `[AMD]` or `[Intel Arc]` tags.

---

# 1. AMD Radeon Architecture (ROCm)

Support for AMD graphics processing units is currently restricted to Linux environments utilizing the ROCm framework.

Windows deployments via ROCm are highly experimental and are not supported within this documentation.

---

## Hardware Compatibility Matrix

| Architecture | VRAM | Validation Status | Expected Inference (t/s) |
|--------------|------|------------------|--------------------------|
| RX 6600      | 8GB  | Confirmed       | 35-42                    |
| RX 6700 XT   | 12GB | Confirmed       | 42-50                    |
| RX 6800 XT   | 16GB | Confirmed       | 48-55                    |
| RX 6900 XT   | 16GB | Confirmed       | 50-58                    |
| RX 7600      | 8GB  | Limited Testing | 38-45 (Est.)             |
| RX 7700 XT   | 12GB | Limited Testing | 45-52 (Est.)             |
| RX 7800 XT   | 16GB | Confirmed       | 52-60                    |
| RX 7900 XT   | 20GB | Confirmed       | 58-65                    |
| RX 7900 XTX  | 24GB | Confirmed       | 60-70                    |

---

## System Prerequisites

- **Operating System:** Ubuntu 22.04 LTS, Ubuntu 24.04 LTS, or Debian 12  
- **Kernel:** 5.15 or later  
- **Drivers:** AMDGPU kernel module  
- **Environment:** Python 3.11  

---

## Deployment Steps

### Step 1.1: Verify Hardware Detection

Ensure the operating system recognizes the AMD architecture:

```bash
lspci | grep -i amd
lsmod | grep amdgpu
```

---

### Step 1.2: Install ROCm Framework

Execute the following commands based on your Linux distribution to install the Radeon Open Compute (ROCm) stack.

#### For Ubuntu 24.04 LTS

```bash
wget https://repo.radeon.com/amdgpu-install/6.0/ubuntu/noble/amdgpu-install_6.0.60000-1_all.deb
sudo dpkg -i amdgpu-install_6.0.60000-1_all.deb
sudo apt update
sudo amdgpu-install --usecase=rocm
sudo usermod -a -G render,video $USER
sudo reboot
```

#### For Ubuntu 22.04 LTS

```bash
wget https://repo.radeon.com/amdgpu-install/6.0/ubuntu/jammy/amdgpu-install_6.0.60000-1_all.deb
sudo dpkg -i amdgpu-install_6.0.60000-1_all.deb
sudo apt update
sudo amdgpu-install --usecase=rocm
sudo usermod -a -G render,video $USER
sudo reboot
```

---

### Step 1.3: Verify ROCm Installation

Post-reboot, confirm the compute nodes are active:

```bash
/opt/rocm/bin/rocminfo
/opt/rocm/bin/rocm-smi
```

---

### Step 1.4: Repository Cloning and Environment Setup

```bash
git clone https://github.com/uncoalesced/Peridot.git
cd Peridot
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

---

### Step 1.5: Build Engine with HIP Support

The llama-cpp-python binding must be compiled manually to interface with the ROCm backend.

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

### Step 1.7: Configuration (config.py)

Modify the configuration file to address the AMD hardware:

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

# 2. Intel Arc Architecture (Vulkan)

Intel Arc integrations utilize the Vulkan backend, which maintains operational compatibility across both Windows 11 and Linux environments.

---

## Hardware Compatibility Matrix

| Architecture | VRAM | Validation Status | Expected Inference (t/s) |
|--------------|------|------------------|--------------------------|
| Arc A310     | 4GB  | Limited Testing | 15-20                    |
| Arc A380     | 6GB  | Confirmed       | 20-28                    |
| Arc A750     | 8GB  | Confirmed       | 25-35                    |
| Arc A770     | 8GB  | Confirmed       | 28-38                    |
| Arc A770     | 16GB | Confirmed       | 30-42                    |

---

## Deployment Steps

### Step 2.1: Install Intel Drivers and Vulkan SDK

Windows:  
Install the latest Intel Arc graphics drivers and the LunarG Vulkan SDK (Runtime).

Linux (Ubuntu 22.04+):  
Ensure kernel 6.2+ is active. Install necessary runtime packages:

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

### Step 2.3: Configuration (config.py)

Adjust the VRAM layer offloading to accommodate Intel architecture:

```python
MODEL_PATH = "models/llama-3-8b-q4.gguf"
GPU_LAYERS = 25  # Recommended baseline for 8GB Arc GPUs
N_CTX = 4096
USE_GPU = True
GPU_TYPE = "intel_arc"
```

---

# 3. Medical Research Module Integration

The Peridot kernel's VRAM handoff for medical research (Folding@home) natively supports both AMD (via OpenCL) and Intel (via Vulkan) backends.

To initialize the daemon on either architecture, run:

```bash
python medical_research.py setup
```

AMD RX 6600+ Expected Throughput: ~300,000 PPD (Points Per Day).  
Intel Arc A750+ Expected Throughput: ~200,000 PPD.

---

# 4. Submitting Telemetry and Benchmark Data

To expand our hardware validation matrices, community members are encouraged to submit performance telemetry.

If you achieve stable execution on undocumented hardware, please fork this repository, update the relevant markdown tables, and submit a Pull Request formatted as follows:

### PR Title

```
Hardware Telemetry: [GPU Model]
```

### Description Requirements

- Hardware Architecture  
- OS Version / Kernel  
- Driver or ROCm Build Version  
- Sustained Inference Speed (t/s)  
- Layer Configuration (GPU_LAYERS)  

---


## 5. RAG Engine: Hardware-Aware Embedding Tiers

Peridot dynamically scales its Retrieval-Augmented Generation (RAG) capabilities based on available VRAM to prevent Out-Of-Memory (OOM) faults and preserve the 21ms Folding@home handoff latency.

### Tier 0: LITE Configuration (4GB - 6GB VRAM)
* **Target Hardware:** Intel Arc A310, AMD RX 6500 XT, older community hardware.
* **Embedding Model:** `all-MiniLM-L3-v2` (~45MB).
* **Execution:** Forced strictly to CPU. 
* **Details:** Leaves 100% of the limited VRAM available for the quantized LLM. Retrieval takes slightly longer, but system stability is guaranteed.

### Tier 1: Baseline Configuration (8GB VRAM)
* **Target Hardware:** AMD RX 6600, Intel Arc A750.
* **Embedding Model:** `all-MiniLM-L6-v2` (~90MB).
* **Execution:** Forced strictly to CPU.
* **Details:** The standard Peridot configuration. Balances highly accurate retrieval with zero VRAM footprint, protecting the background medical research state machine.

### Tier 2: Balanced Configuration (12GB - 16GB VRAM)
* **Target Hardware:** AMD RX 6700 XT, RX 7800 XT, Intel Arc A770.
* **Embedding Model:** `nomic-embed-text-v1.5` (~550MB).
* **Execution:** VRAM Accelerated.
* **Details:** Utilizes the VRAM buffer to load a massive 8192-token context window. Capable of ingesting entire document chapters in a single pass with sub-millisecond retrieval.

### Tier 3: High-Fidelity Configuration (24GB+ VRAM)
* **Target Hardware:** AMD RX 7900 XTX.
* **Embedding Model:** `mxbai-embed-large-v1` (~1.5GB).
* **Execution:** VRAM Accelerated.
* **Details:** Enterprise-grade retrieval. Best suited for massive personal databases and deep semantic search operations.
---

For technical assistance regarding these implementations, utilize the GitHub Discussions panel or open a properly tagged Issue.
