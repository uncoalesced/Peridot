import os
import sys
import subprocess
from core_system.audit import ghost

def adjust_gpu_mps(percentage: int):
    if sys.platform != "linux":
        ghost.info(f"[ZAT-SCS | MOCK] MPS allocation scaled to {percentage}% on Windows NT.")
        return

    try:
        os.environ["CUDA_MPS_ENABLE_PER_CTX_DEVICE_MULTIPROCESSOR_PARTITIONING"] = "1"
        subprocess_kwargs = {"shell": False, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True}
        cmd = ["nvidia-cuda-mps-control"]
        payload = f"set_default_active_thread_percentage {percentage}\n"
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, **subprocess_kwargs)
        proc.communicate(input=payload, timeout=2.0)
        ghost.info(f"[ZAT-SCS | MPS] Compute allocation set to {percentage}% SM capacity.")
    except Exception as e:
        ghost.error(f"[ZAT-SCS | ERROR] MPS scaling error: {e}")
