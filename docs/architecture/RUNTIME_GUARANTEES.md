# PERIDOT SOVEREIGN KERNEL: Runtime Guarantees
**Version:** 1.5.4-STABLE  
**Target Hardware:** Constrained Consumer Architecture (8GB VRAM / 16GB RAM)

This document defines the strict operational boundaries, degradation policies, and failure-isolation guarantees enforced by the Peridot v1.5.4 Central Nervous System (FSM). Peridot operates on the principle that inference throughput is secondary to system stability.

## 1. VRAM Arbitration Guarantees
Peridot guarantees that background GPU tasks (e.g., Folding@home) will never collide with the LLM context window, resulting in a CUDA Out-Of-Memory (OOM) crash.
* **Maximum Tolerated VRAM:** The NVML Watchdog enforces a strict `7500MB` ceiling on the 8GB RTX 5050.
* **Interrupt Latency:** Background tasks are paused via WebSocket `SIGSTOP`. The kernel guarantees a hardware lock within `500ms`.
* **Timeout Behavior:** If the GPU is not successfully purged within `2.0 seconds`, the FSM triggers a `KERNEL PANIC`. The prompt is discarded, a 503 error is returned to the user, and the GPU is sandboxed to prevent OS-level graphics artifacting.

## 2. Aether-Route (RAG) Degradation Policy
To prevent System RAM swap-thrashing when ingesting massive vector arrays, Peridot guarantees physical limits on active memory via a Tiered LRU Cache.
* **Tier 1 (DDR5 RAM):** Capable of storing `X` semantic chunks for zero-latency retrieval.
* **Tier 2 (NVMe SQLite):** Infinite cold storage.
* **Degraded Mode Guarantee:** When Tier 1 capacity is breached, Peridot will silently banish the oldest vectors to Tier 2. Retrieval latency will degrade from `~0.1s` to `~1.5s` as data is read from the SSD, but the system guarantees it will **never** overflow the host machine's RAM or trigger an OS page fault.

## 3. Failure Isolation Boundaries
The kernel relies on an asynchronous event queue. The API layer and the Hardware FSM are strictly isolated.
* **Deadlock Protection:** If the `llama.cpp` inference thread hangs, it will not freeze the Flask orchestration server. The API will timeout and return an error while preserving the background idle-monitor loop.
* **Phantom VRAM Defense:** The kernel does not rely on OS-reported "free memory." It explicitly queries the NVIDIA driver (`nvidia-ml-py`) for physical byte allocation before every inference cycle.

## 4. Audit & Persistence Guarantees
* **Append-Only Telemetry:** All system actions (Purges, Panics, RAG Hits) are logged via the `GhostLogger`. This ledger is append-only and cryptographically bound.
* **Air-Gap Integrity:** The `setup.py` initialization forces `HF_HUB_OFFLINE=1` into the OS environment variables, guaranteeing zero outbound telemetry packets regardless of underlying HuggingFace library defaults.