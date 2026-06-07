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
import os
from pathlib import Path

# Path Bootstrapping
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
    """Extracts precise CPU model string with robust pathing for Windows."""
    cpu_name = platform.processor()
    if platform.system() == "Windows":
        try:
            # Explicitly target System32 to avoid 'not recognized' errors
            system32 = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'Wbem', 'wmic.exe')
            cpu_name = subprocess.check_output(
                f'"{system32}" cpu get name', shell=True
            ).decode().split("\n")[1].strip()
        except Exception:
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                cpu_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            except Exception:
                cpu_name = platform.processor()
    return cpu_name

def _get_gpu_info():
    gpu_info = {"gpu_name": "Unknown", "gpu_memory_total_gb": 0, "gpu_count": 0}
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
        except Exception:
            pass
    return gpu_info

def get_specs():
    ram = psutil.virtual_memory()
    specs = {
        "os": f"{platform.system()} {platform.release()}",
        "cpu_model": _get_cpu_info(),
        "ram_total_gb": round(ram.total / (1024**3), 2),
        "python_version": platform.python_version(),
    }
    specs.update(_get_gpu_info())
    return specs

if __name__ == "__main__":
    import json
    print(json.dumps(get_specs(), indent=2))