# Peridot Benchmark Results

Generated: 2026-05-13 22:03:01

## System Readiness Rating: 8/10
- [WARN] 7.96GB VRAM detected (Suboptimal, heavy quantization required).
- [PASS] 15.31GB System RAM detected.
- [PASS] Handoff latency is elite (507.51ms).
- [PASS] Standard GPU generation is stable (796.82 t/s).
- [PASS] Zero memory leaks detected (Growth: +43.97MB).

---

## Test Configuration

**Hardware:**
- GPU: NVIDIA GeForce RTX 5050 Laptop (8GB VRAM)
- CPU: AMD Ryzen 7 250 AI
- RAM: 16GB
- Storage: NVMe SSD

**Software:**
- OS: Windows 11 / Ubuntu 22.04 LTS
- Python: 3.11
- Model: Llama-3-8B-Instruct (Q4_K_M quantization)
- Backend: llama-cpp-python

---

## Inference Speed (Short)

**Description:** Inference speed for Quick chat query
**Test date:** 2026-05-13T21:48:55.085766

### Summary Statistics

| Metric | Value |
|--------|-------|
| Mean | 855.77 |
| Median | 721.13 |
| Std Dev | 343.61 |
| Min | 585.26 |
| Max | 1653.25 |
| Samples | 10 |

### Test Details

- Average tokens generated: 24
- Average elapsed time: 31.17ms

---

## Inference Speed (Medium)

**Description:** Inference speed for Standard explanation
**Test date:** 2026-05-13T21:49:02.267390

### Summary Statistics

| Metric | Value |
|--------|-------|
| Mean | 967.63 |
| Median | 796.82 |
| Std Dev | 337.95 |
| Min | 641.40 |
| Max | 1482.50 |
| Samples | 10 |

### Test Details

- Average tokens generated: 23
- Average elapsed time: 26.37ms

---

## Inference Speed (Long)

**Description:** Inference speed for Extended generation
**Test date:** 2026-05-13T21:49:09.117329

### Summary Statistics

| Metric | Value |
|--------|-------|
| Mean | 17752.83 |
| Median | 19095.33 |
| Std Dev | 5179.65 |
| Min | 9751.91 |
| Max | 24191.55 |
| Samples | 10 |

### Test Details

- Average tokens generated: 417
- Average elapsed time: 25.86ms

---

## VRAM Handoff Latency

**Description:** VRAM handoff latency from Folding@Home to inference
**Test date:** 2026-05-13T21:49:25.942224

### Summary Statistics

| Metric | Value |
|--------|-------|
| Mean | 510.70 |
| Median | 507.51 |
| Std Dev | 5.36 |
| Min | 505.35 |
| Max | 518.42 |
| Samples | 10 |

### VRAM Handoff Metrics

| Metric | Value |
|--------|-------|
| Pause command latency | 9.81ms |
| VRAM release time | 507.51ms |
| VRAM freed | 0MB |
| Inference throughput | 10162.92 t/s |

---

## Memory Stability

**Description:** Memory usage over consecutive queries
**Test date:** 2026-05-13T21:50:43.086004

### Summary Statistics

| Metric | Value |
|--------|-------|
| Mean | 4151.12 |
| Median | 4150.32 |
| Std Dev | 10.55 |
| Min | 4127.68 |
| Max | 4168.19 |
| Samples | 20 |

### Memory Analysis

- Total queries: 100
- Successful queries: 100
- Initial memory: 4125.69MB
- Final memory: 4169.66MB
- Memory growth: +43.97MB

---

## GPU Utilization

**Description:** GPU utilization during Aether-Route inference
**Test date:** 2026-05-13T21:52:10.124390

### Summary Statistics

| Metric | Value |
|--------|-------|
| Mean | 70.98 |
| Median | 70.98 |
| Std Dev | 0.00 |
| Min | 70.98 |
| Max | 70.98 |
| Samples | 1 |

### GPU Utilization Details

| State | Mean | Median | Range |
|-------|------|--------|-------|
| Idle | 0.0% | 0.0% | 0.0%-0.0% |
| Active | 71.0% | 93.0% | 0.0%-100.0% |

---

## Sustained Load Test

**Description:** Sustained load test over 10 minutes
**Test date:** 2026-05-13T21:52:59.192232

### Summary Statistics

| Metric | Value |
|--------|-------|
| Mean | 7893.38 |
| Median | 7218.87 |
| Std Dev | 6486.53 |
| Min | 41.75 |
| Max | 44623.80 |
| Samples | 2043 |

---
