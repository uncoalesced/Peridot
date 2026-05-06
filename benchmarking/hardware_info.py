import platform
import subprocess
import psutil

try:
    import torch
except ImportError:
    torch = None

try:
    import pynvml
except ImportError:
    pynvml = None


def _get_cpu_info():
    cpu_name = platform.processor()

    # Better CPU name on Windows/Linux
    if not cpu_name:
        try:
            if platform.system() == "Windows":
                cpu_name = subprocess.check_output(
                    "wmic cpu get name", shell=True
                ).decode().split("\n")[1].strip()
            elif platform.system() == "Linux":
                cpu_name = subprocess.check_output(
                    "cat /proc/cpuinfo | grep 'model name' | head -1",
                    shell=True
                ).decode().split(":")[1].strip()
        except Exception:
            cpu_name = "Unknown"

    return cpu_name


def _get_gpu_info():
    gpu_info = {
        "gpu_name": "Unknown",
        "vram_gb": 0,
        "cuda_version": "N/A",
        "cuda_capability": "N/A",
        "gpu_count": 0
    }

    # Preferred: torch
    if torch and torch.cuda.is_available():
        try:
            props = torch.cuda.get_device_properties(0)
            gpu_info["gpu_name"] = props.name
            gpu_info["vram_gb"] = round(props.total_memory / (1024**3), 2)
            gpu_info["cuda_capability"] = f"{props.major}.{props.minor}"
            gpu_info["cuda_version"] = torch.version.cuda
            gpu_info["gpu_count"] = torch.cuda.device_count()
            return gpu_info
        except Exception:
            pass

    # Fallback: pynvml
    if pynvml:
        try:
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)

            gpu_info["gpu_name"] = name.decode() if isinstance(name, bytes) else name
            gpu_info["vram_gb"] = round(mem.total / (1024**3), 2)
            gpu_info["gpu_count"] = pynvml.nvmlDeviceGetCount()

            pynvml.nvmlShutdown()
        except Exception:
            pass

    return gpu_info


def get_specs():
    """Return comprehensive hardware specifications."""

    ram = psutil.virtual_memory()

    specs = {
        "os": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "cpu": _get_cpu_info(),
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "cpu_cores_logical": psutil.cpu_count(logical=True),
        "ram_total_gb": round(ram.total / (1024**3), 2),
        "ram_available_gb": round(ram.available / (1024**3), 2),
        "python_version": platform.python_version(),
    }

    # Merge GPU info
    specs.update(_get_gpu_info())

    return specs


if __name__ == "__main__":
    import json
    print(json.dumps(get_specs(), indent=2))