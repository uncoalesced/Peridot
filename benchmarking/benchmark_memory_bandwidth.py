# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Peridot Sovereign Kernel | Aether-Route Bandwidth Telemetry (ARPM)

Executes raw transfer rate profiling across PCIe, VRAM, and NVMe subsystems 
to establish eviction thresholds for the Hierarchical Cache Manager (v1.4.x).
"""

import time
import os
import torch
import tempfile
import json
from pathlib import Path

# ANSI Formatting
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

# Test configuration (1GB payload for statistical significance)
TENSOR_SIZE_MB = 1024  
ELEMENT_COUNT = (TENSOR_SIZE_MB * 1024 * 1024) // 4  # FP32 elements

def measure_pcie_bandwidth():
    """Measures Host-to-Device (RAM -> VRAM) transfer rates over the PCIe bus."""
    print(f"{CYAN}[1/3] Profiling PCIe Bus Throughput (Tier 2 → Tier 1)...{RESET}")
    
    if not torch.cuda.is_available():
        print(f"{RED}[FATAL] CUDA is unavailable. Hardware abstraction layer failure.{RESET}")
        return None

    # Allocate Pinned (Page-Locked) Memory for maximum transfer speed
    cpu_tensor = torch.randn(ELEMENT_COUNT, dtype=torch.float32).pin_memory()
    
    # Warmup
    _ = cpu_tensor.cuda(non_blocking=True)
    torch.cuda.synchronize()

    # Benchmark
    start_time = time.perf_counter()
    gpu_tensor = cpu_tensor.cuda(non_blocking=True)
    torch.cuda.synchronize()
    duration = time.perf_counter() - start_time
    
    bandwidth_gb_s = (TENSOR_SIZE_MB / 1024) / duration
    print(f"  - Transfer Size: {TENSOR_SIZE_MB} MB")
    print(f"  - Latency: {duration:.4f}s")
    print(f"  - Bandwidth: {GREEN}{bandwidth_gb_s:.2f} GB/s{RESET}")
    
    del cpu_tensor
    del gpu_tensor
    torch.cuda.empty_cache()
    
    return bandwidth_gb_s

def measure_vram_bandwidth():
    """Measures Device-to-Device (VRAM Internal) copy speeds."""
    print(f"\n{CYAN}[2/3] Profiling VRAM Internal Bandwidth (Tier 1)...{RESET}")
    
    gpu_tensor_a = torch.randn(ELEMENT_COUNT, dtype=torch.float32, device='cuda')
    
    # Warmup
    _ = gpu_tensor_a.clone()
    torch.cuda.synchronize()

    # Benchmark
    start_time = time.perf_counter()
    gpu_tensor_b = gpu_tensor_a.clone()
    torch.cuda.synchronize()
    duration = time.perf_counter() - start_time
    
    bandwidth_gb_s = (TENSOR_SIZE_MB / 1024) / duration
    print(f"  - Transfer Size: {TENSOR_SIZE_MB} MB")
    print(f"  - Latency: {duration:.4f}s")
    print(f"  - Bandwidth: {GREEN}{bandwidth_gb_s:.2f} GB/s{RESET}")
    
    del gpu_tensor_a
    del gpu_tensor_b
    torch.cuda.empty_cache()
    
    return bandwidth_gb_s

def measure_nvme_bandwidth():
    """Simulates mmap-style sequential reads from the storage subsystem."""
    print(f"\n{CYAN}[3/3] Profiling NVMe Storage Subsystem (Tier 3)...{RESET}")
    
    # Generate 1GB dummy payload
    dummy_data = os.urandom(TENSOR_SIZE_MB * 1024 * 1024)
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = temp_file.name
        temp_file.write(dummy_data)
        temp_file.flush()
        os.fsync(temp_file.fileno()) # Force write to disk, bypass OS cache
        
    # Flush OS page cache to ensure a true disk read (Windows limitation bypass)
    # Re-opening the file without buffering simulates direct I/O
    
    start_time = time.perf_counter()
    with open(temp_path, "rb", buffering=0) as f:
        _ = f.read()
    duration = time.perf_counter() - start_time
    
    os.remove(temp_path)
    
    bandwidth_mb_s = TENSOR_SIZE_MB / duration
    bandwidth_gb_s = bandwidth_mb_s / 1024
    
    print(f"  - Payload: {TENSOR_SIZE_MB} MB")
    print(f"  - Latency: {duration:.4f}s")
    print(f"  - Throughput: {YELLOW}{bandwidth_mb_s:.2f} MB/s ({bandwidth_gb_s:.2f} GB/s){RESET}")
    
    return bandwidth_gb_s

def generate_threshold_profile(pcie_bw, vram_bw, nvme_bw):
    """Calculates Aether-Route eviction thresholds based on hardware physics."""
    print(f"\n{CYAN}===================================================={RESET}")
    print(f"{CYAN} AETHER-ROUTE v1.4.x METRIC SYNTHESIS{RESET}")
    print(f"{CYAN}===================================================={RESET}")
    
    # Threshold Logic
    # If PCIe bandwidth drops below 10GB/s, NPU prefetching must be throttled.
    # If NVMe drops below 3GB/s, KV Cache serialization must use higher compression.
    
    profile = {
        "hardware_profile": {
            "vram_bandwidth_gbs": round(vram_bw, 2),
            "pcie_bandwidth_gbs": round(pcie_bw, 2),
            "nvme_bandwidth_gbs": round(nvme_bw, 2)
        },
        "aether_route_parameters": {
            "enable_npu_prefetch": pcie_bw > 10.0,
            "tier_3_compression_required": nvme_bw < 3.0,
            "kv_eviction_block_size_mb": 16 if nvme_bw < 1.0 else 64
        }
    }
    
    print(json.dumps(profile, indent=2))
    
    # Write to config matrix for kernel ingestion
    config_dir = Path(__file__).parent.parent / "config"
    config_dir.mkdir(exist_ok=True)
    with open(config_dir / "hardware_thresholds.json", "w") as f:
        json.dump(profile, f, indent=2)
        
    print(f"\n{GREEN}[OK] Threshold matrix compiled to config/hardware_thresholds.json{RESET}")

def main():
    print(f"{CYAN}INITIALIZING ARPM BANDWIDTH TELEMETRY...{RESET}")
    print("-" * 50)
    
    vram_bw = measure_vram_bandwidth()
    pcie_bw = measure_pcie_bandwidth()
    nvme_bw = measure_nvme_bandwidth()
    
    if all([vram_bw, pcie_bw, nvme_bw]):
        generate_threshold_profile(pcie_bw, vram_bw, nvme_bw)
    else:
        print(f"{RED}[FATAL] Telemetry collection failed. Could not compile threshold matrix.{RESET}")

if __name__ == "__main__":
    main()