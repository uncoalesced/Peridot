# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
#
# Licensed under the MIT License.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Benchmark: VRAM Hammer Diagnostic
Synthetic hardware stress test for Blackwell VRAM flushing.
"""

import sys
import time
import torch
from pathlib import Path

# -----------------------------------------------------------------------------
# PATH BOOTSTRAPPING
# -----------------------------------------------------------------------------
benchmarking_dir = Path(__file__).parent.absolute()
peridot_root = benchmarking_dir.parent
utils_path = benchmarking_dir / "utils"

for path in [str(peridot_root), str(utils_path)]:
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    import pynvml
    from benchmark_utils import logger, BenchmarkResult
except ImportError:
    print(
        "[ERROR] Missing dependencies. Ensure pynvml and benchmark_utils are available."
    )
    sys.exit(1)


def get_vram_used():
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    pynvml.nvmlShutdown()
    return info.used / (1024 * 1024)  # Convert to MB


def run_hammer_test():
    logger.info("\n" + "=" * 60)
    logger.info("PERIDOT VRAM HAMMER DIAGNOSTIC")
    logger.info("=" * 60 + "\n")

    if not torch.cuda.is_available():
        logger.error("CUDA not detected. Synthetic stress test aborted.")
        return

    result = BenchmarkResult(
        name="vram_hammer", description="Synthetic 4GB VRAM allocation and purge cycle."
    )

    # 1. Baseline
    baseline = get_vram_used()
    logger.info(f"[1/4] Baseline VRAM: {baseline:.2f} MB")

    # 2. Allocation
    logger.info("[2/4] Hammering Blackwell with 4GB tensor allocation...")
    try:
        # Forcing 4GB of zero-filled memory on the RTX 5050
        dummy_tensor = torch.zeros((1024, 1024, 1024), device="cuda")
        active_vram = get_vram_used()
        logger.info(f"      Active Stress VRAM: {active_vram:.2f} MB")
    except Exception as e:
        logger.error(f"      Allocation failed: {e}")
        return

    # 3. The Purge
    logger.info("[3/4] Triggering Hardware Purge Signal...")
    start_time = time.perf_counter()

    # Manual context flush
    del dummy_tensor
    torch.cuda.empty_cache()
    torch.cuda.synchronize()  # Ensure the GPU has actually finished the flush

    end_time = time.perf_counter()
    latency = (end_time - start_time) * 1000

    # 4. Final Telemetry
    final_vram = get_vram_used()
    result.add_measurement(latency)

    logger.info(f"[4/4] Purge Complete.")
    logger.info(f"      Hardware Latency: {latency:.2f} ms")
    logger.info(f"      Final Residual VRAM: {final_vram:.2f} MB")

    # Success Logic
    if final_vram <= (baseline + 150):
        logger.info(f"\n[RESULT] PASS: RTX 5050 flushed 4GB in {latency:.2f}ms.")
    else:
        logger.warning(
            "\n[RESULT] WARN: Residual VRAM detected. Potential driver fragmentation."
        )

    result.save(benchmarking_dir / "results")


if __name__ == "__main__":
    run_hammer_test()
