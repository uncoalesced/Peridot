import time
import json
import os
import subprocess
import cupy as cp
from hardware_info import get_specs


def run_vram_purge_test(size_gb=3):
    """Measures how fast the hardware can dump a large VRAM block."""
    try:
        # Allocate
        m_block = cp.zeros((size_gb * 1024**3 // 4,), dtype=cp.float32)
        cp.cuda.Stream.null.synchronize()

        # Measure Purge
        start = time.perf_counter()
        del m_block
        cp.get_default_memory_pool().free_all_blocks()
        cp.cuda.Stream.null.synchronize()
        latency = (time.perf_counter() - start) * 1000
        return round(latency, 2)
    except Exception as e:
        return f"Error: {str(e)}"


def run_benchmark():
    print("--- Peridot Research Benchmark (v1.1) ---")
    specs = get_specs()
    print(f"Hardware: {specs['gpu_name']} | VRAM: {specs['vram_gb']}GB")

    # 1. VRAM Purge Test
    print(f"Testing {specs['gpu_name']} VRAM purge latency (3GB)...")
    purge_latency = run_vram_purge_test(3)
    print(f"Result: {purge_latency} ms")

    # 2. Performance Metrics
    # In the future, this will hook into your kernel.generate stats
    results = {
        "metadata": specs,
        "results": {
            "vram_purge_ms": purge_latency,
            "inference_tps_standard": 57.25,  # Placeholder for your LOQ stats
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    }

    if not os.path.exists("benchmarking/results"):
        os.makedirs("benchmarking/results")

    filename = f"benchmarking/results/bench_{int(time.time())}.json"
    with open(filename, "w") as f:
        json.dump(results, f, indent=4)

    print(f"\n[DONE] Data saved. This helps map {specs['gpu_name']} architecture.")


if __name__ == "__main__":
    run_benchmark()
