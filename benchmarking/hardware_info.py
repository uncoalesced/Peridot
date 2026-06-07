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
import sys
from pathlib import Path

# -----------------------------------------------------------------------------
# PATH BOOTSTRAPPING
# -----------------------------------------------------------------------------
benchmarking_dir = Path(__file__).parent.parent.absolute()
utils_path = benchmarking_dir / "utils"

if str(utils_path) not in sys.path:
    sys.path.insert(0, str(utils_path))

try:
    from benchmark_utils import logger
except ImportError:
    import logging
    logger = logging.getLogger("hardware_info")

try:
    import pynvml
except ImportError:
    pynvml = None


def _get_cpu_info():
    """Extracts precise CPU model string via shell commands."""
    cpu_name = platform.processor()

    try:
        if platform.system() == "Windows":
            # WMIC provides the most accurate model string for Ryzen AI processors
            cpu_name = subprocess.check_output(
                "wmic cpu get name", shell=True
            ).decode().split("\n")[1].strip()
        elif platform.system() == "Linux":
            cpu_name = subprocess.check_output(
                "cat /proc/cpuinfo | grep 'model name' | head -1",
                shell=True
            ).decode().split(":")[1].strip()
    except Exception as e:
        logger.debug(f"Extended CPU discovery failed: {e}")

    return cpu_name


def _get_gpu_info():
    """Telemetry for NVIDIA GPUs via NVML. Bypasses Torch to save VRAM."""
    gpu_info = {
        "gpu_name": "Unknown",
        "gpu_memory_total_gb": 0,
        "gpu_count": 0
    }

    if pynvml:
        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            gpu_info["gpu_count"] = device_count
            
            if device_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                name = pynvml.nvmlDeviceGetName(handle)
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)

                gpu_info["gpu_name"] = name.decode() if isinstance(name, bytes) else name
                gpu_info["gpu_memory_total_gb"] = round(mem.total / (1024**3), 2)

            pynvml.nvmlShutdown()
        except Exception as e:
            logger.warning(f"NVML GPU discovery failed: {e}")

    return gpu_info


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