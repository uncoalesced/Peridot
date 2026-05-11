# Aether-Route Performance Matrix (ARPM) — Benchmarking Guide

Peridot is a sovereign, hardware-dependent system. Because the Aether-Route architecture relies on a tight handoff between the Ryzen AI NPU/CPU and NVIDIA Blackwell-era CUDA cores, performance varies significantly based on system configuration.

The ARPM suite provides a standardized method for quantifying system throughput, VRAM handoff efficiency, and memory stability.

---

## 1. Prerequisites

The ARPM suite is designed to be zero-config. It automatically handles security authentication by scanning the host environment for the active Peridot session key.

### Requirements

- **Peridot Server Active**  
  Ensure `python server.py` or the Peridot Launcher is running in a separate terminal.

- **Environment**  
  Ensure your virtual environment is active (`.venv`).

- **Hardware Telemetry**  
  Ensure `pynvml` is installed to allow the suite to pull RTX-specific power and thermal data.

---

## 2. Execution

The suite features a master runner that executes all telemetry scripts in a dependency-safe order, including cooling gaps to prevent thermal throttling from skewing results.

### Run Full Telemetry Suite

#### PowerShell

```powershell
.\venv\Scripts\python.exe benchmarking/run_all_benchmarks.py
```

### Script Breakdown

| Benchmark Module | Description |
|---|---|
| **Inference Speed** | Measures tokens-per-second (t/s) across short, medium, and long context windows. |
| **VRAM Handoff** | Measures the millisecond latency of purging Folding@Home buffers for incoming AI queries. |
| **Memory Stability** | Validates the Aether-Route context clearing logic over 100+ consecutive queries. |
| **GPU Utilization** | Tracks CUDA core saturation and power draw during Blackwell generation cycles. |

---

## 3. Understanding the ARPM Rating

After the suite completes, it generates a **System Readiness Rating (1–10)** located in:

```text
benchmarking/reports/README_PERFORMANCE_SECTION.md
```

### Rating Tiers

| Rating | Classification | Description |
|---|---|---|
| **9–10** | Elite | System handles 8B models with minimal latency and features near-instant VRAM handoff (`<600ms`). |
| **7–8** | High Performance | Capable of sustained local inference but may require specific quantization (`Q4_K_M`) to stay within VRAM limits. |
| **5–6** | Standard | Functional, but may experience bottlenecks during context scaling or high-load sustained tasks. |

---

## 4. Contributing Results

1. Navigate to the GitHub Discussions / Configurations board.
2. Open a **New Discussion**.
3. Paste the contents of:

```text
benchmarking/reports/README_PERFORMANCE_SECTION.md
```

4. Attach the hardware JSON found in:

```text
benchmarking/results/
```

for deep-level telemetry verification.