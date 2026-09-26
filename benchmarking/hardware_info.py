# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
#
# Licensed under the MIT License.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Hardware Specification Discovery
Gathers system-level telemetry for benchmark contextualization.
"""

import platform
import subprocess
import psutil

# The shared logger import used to sit behind a sys.path prologue that pointed
# at <repo>/utils -- one directory too high, a path that does not exist -- so
# the ImportError branch always won and this module silently ran on a bare
# logging.getLogger. It is now a plain package import.
from benchmarking.utils.benchmark_utils import get_vram_mb, logger


def _get_cpu_info():
    """Extracts precise CPU model string via shell commands."""
    cpu_name = platform.processor()

    try:
        if platform.system() == "Windows":
            # WMIC provides the most accurate model string for Ryzen AI processors
            cpu_name = (
                subprocess.check_output("wmic cpu get name", shell=True)
                .decode()
                .split("\n")[1]
                .strip()
            )
        elif platform.system() == "Linux":
            cpu_name = (
                subprocess.check_output(
                    "cat /proc/cpuinfo | grep 'model name' | head -1", shell=True
                )
                .decode()
                .split(":")[1]
                .strip()
            )
    except Exception as e:
        logger.debug(f"Extended CPU discovery failed: {e}")

    return cpu_name


def _get_gpu_info():
    """Telemetry for NVIDIA GPUs via NVML. Bypasses Torch to save VRAM."""
    vram = get_vram_mb()
    return {
        "gpu_name": vram["name"],
        "gpu_memory_total_gb": round(vram["total"] / 1024, 2),
        "gpu_count": vram["count"],
    }


def get_specs():
    """Returns a comprehensive dictionary of the Peridot host environment."""
    ram = psutil.virtual_memory()

    specs = {
        "os": f"{platform.system()} {platform.release()}",
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "cpu_model": _get_cpu_info(),
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "cpu_cores_logical": psutil.cpu_count(logical=True),
        "ram_total_gb": round(ram.total / (1024**3), 2),
        "python_version": platform.python_version(),
    }

    # Integrate GPU data
    gpu_data = _get_gpu_info()
    specs.update(gpu_data)

    return specs


if __name__ == "__main__":
    import json

    # Direct execution provides a clean JSON dump of the hardware profile
    print(json.dumps(get_specs(), indent=2))
