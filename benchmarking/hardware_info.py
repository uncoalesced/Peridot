import torch
import platform
import subprocess


def get_specs():
    specs = {
        "os": f"{platform.system()} {platform.release()}",
        "cpu": platform.processor(),
        "gpu_name": "Unknown",
        "vram_gb": 0,
        "cuda_version": "N/A",
    }

    if torch.cuda.is_available():
        props = torch.cuda.get_device_properties(0)
        specs["gpu_name"] = props.name
        specs["vram_gb"] = round(props.total_memory / (1024**3), 2)
        specs["cuda_cap"] = f"{props.major}.{props.minor}"
        specs["cuda_version"] = torch.version.cuda

    return specs
