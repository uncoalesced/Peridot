"""
Module: Resource Monitor
Continuous hardware telemetry for the Peridot Kernel.
# Engineered by uncoalesced
"""

import threading
import psutil
import time
from enhancedlogger import EnhancedLogger

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False

logger = EnhancedLogger()
REFRESH_INTERVAL = 10  # seconds


def monitor_resources(stop_event: threading.Event):
    """Monitors CPU, RAM, and GPU/VRAM in a background thread."""
    
    # Initialize NVML once per thread lifespan to save overhead
    gpu_handle = None
    if NVML_AVAILABLE:
        try:
            pynvml.nvmlInit()
            gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception as e:
            logger.error(f"NVML Init Failed: {e}", source="RESOURCE")

    # Prime the CPU check (interval=None calculates delta since this call)
    psutil.cpu_percent(interval=None)

    while not stop_event.is_set():
        try:
            # 1. System Telemetry (Ryzen 7 / 16GB RAM)
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            
            log_str = f"CPU: {cpu:.1f}% | RAM: {ram.percent:.1f}% ({ram.used / (1024**3):.1f}GB)"

            # 2. GPU Telemetry (RTX 5050 / VRAM)
            if gpu_handle:
                try:
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(gpu_handle)
                    util = pynvml.nvmlDeviceGetUtilizationRates(gpu_handle)
                    vram_used = mem_info.used / (1024**3)
                    vram_total = mem_info.total / (1024**3)
                    
                    log_str += f" | GPU: {util.gpu}% | VRAM: {vram_used:.1f}/{vram_total:.1f}GB"
                except Exception as e:
                    logger.debug(f"GPU Telemetry skip: {e}", source="RESOURCE")

            # Route everything exclusively through the logger
            logger.info(log_str, source="RESOURCE")
            
            # Responsive sleep cycle: Sleep in 0.5s chunks to exit immediately on stop_event
            for _ in range(int(REFRESH_INTERVAL * 2)):
                if stop_event.is_set():
                    break
                time.sleep(0.5)

        except Exception as e:
            logger.error(f"Telemetry fault: {e}", source="RESOURCE")
            time.sleep(1)

    # Cleanup hardware bindings on shutdown
    if NVML_AVAILABLE:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass