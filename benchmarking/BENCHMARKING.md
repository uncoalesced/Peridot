# PERIDOT KERNEL — Benchmarking Guide

Because Peridot is a sovereign, hardware-dependent OS, actual performance will vary based on your specific CPU, RAM, and NVIDIA GPU architecture.

We rely on the community to crowdsource empirical data. This guide explains how to properly benchmark your system and share the results.

---

# 1. Preparing the Environment

Peridot uses a strictly ephemeral, RAM-only API key to prevent unauthorized local processes from hijacking the LLM (CWE-312 mitigation).

To run the benchmark scripts from a separate terminal, you must temporarily synchronize a static key.

## Terminal 1 — The Server

Kill your current Peridot instance.

Start the server directly while injecting a benchmark key.

### Windows (PowerShell)

```powershell
$env:PERIDOT_AUTH_TOKEN="BENCHMARK_KEY"
python server.py
```

### Linux / macOS

```bash
PERIDOT_AUTH_TOKEN="BENCHMARK_KEY" python server.py
```

---

## Terminal 2 — The Test Suite

Open a second terminal, activate your virtual environment, and inject the exact same key.

### Windows (PowerShell)

```powershell
$env:PERIDOT_AUTH_TOKEN="BENCHMARK_KEY"
```

### Linux / macOS

```bash
export PERIDOT_AUTH_TOKEN="BENCHMARK_KEY"
```

---

# 2. Running the Tests

With the security perimeter temporarily synchronized, execute both benchmark scripts from **Terminal 2**.

## Test A — VRAM Hot-Swap Latency

This test measures the millisecond latency of the hardware interrupt when yielding the GPU from Folding@Home back to the LLM.

```bash
python benchmarks/vram_test.py
```

---

## Test B — Inference Speed

This test measures sustained **tokens-per-second (t/s)** across the local API under different context loads.

```bash
python benchmarks/inference_test.py
```

---

# 3. Uploading Your Results

Once you have your numbers, we want them. This helps optimize the **VRAM State Machine** for different hardware architectures.

1. Go to the **Configurations Discussion Board**
2. Click **New Discussion**
3. Copy and paste the template below
4. Fill in your system specifications and results
5. Submit the post

---

# Benchmark Submission Template

```text
System Architecture:

OS: [e.g., Windows 11 / Ubuntu 22.04]
CPU: [e.g., Ryzen 7 5800X / Intel i9-13900K]
RAM: [e.g., 32GB DDR4 3200MHz]
GPU: [e.g., RTX 3060 12GB / RTX 5050 8GB]

Benchmark Results:

VRAM Hot-Swap Latency: [e.g., 6.55 ms]
Inference Speed (Short): [e.g., 38.92 t/s]
Inference Speed (Medium): [e.g., 57.29 t/s]
Inference Speed (Long): [e.g., 41.02 t/s]

Additional Notes:

[Any quantization used, modifications to GPU_LAYERS in config.py,
or background processes running during the test.]
```

---

You can save this file directly as:

```
benchmarks/BENCHMARKING.md
```

This keeps all benchmarking instructions standardized and easy for contributors to follow.