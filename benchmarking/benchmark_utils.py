"""
Shared utilities for Peridot benchmarking suite.
# Engineered by uncoalesced
"""

import json
import time
import statistics
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("benchmark_utils")


class BenchmarkResult:
    """Container for benchmark results with statistical analysis."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.measurements: List[float] = []
        self.metadata: Dict[str, Any] = {}
        self.timestamp = datetime.now().isoformat()
        
    def add_measurement(self, value: float):
        self.measurements.append(value)
        
    def add_metadata(self, key: str, value: Any):
        self.metadata[key] = value
        
    def get_statistics(self) -> Dict[str, float]:
        if not self.measurements:
            return {}
            
        return {
            "min": min(self.measurements),
            "max": max(self.measurements),
            "mean": statistics.mean(self.measurements),
            "median": statistics.median(self.measurements),
            "stdev": statistics.stdev(self.measurements) if len(self.measurements) > 1 else 0.0,
            "count": len(self.measurements)
        }
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "timestamp": self.timestamp,
            "measurements": self.measurements,
            "statistics": self.get_statistics(),
            "metadata": self.metadata
        }
        
    def save(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
            
        logger.info(f"Saved benchmark result to {filepath}")
        return filepath


def timer(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        return result, elapsed
    return wrapper


def repeat_measurement(func, runs: int = 10, warmup: int = 2) -> List[float]:
    measurements = []
    
    logger.info(f"Running {warmup} warmup iterations...")
    for i in range(warmup):
        try:
            func()
        except Exception as e:
            logger.warning(f"Warmup run {i+1} failed: {e}")
    
    logger.info(f"Running {runs} measurement iterations...")
    for i in range(runs):
        try:
            value = func()
            measurements.append(value)
            logger.debug(f"Run {i+1}/{runs}: {value}")
        except Exception as e:
            logger.error(f"Measurement run {i+1} failed: {e}")
            
    return measurements


def get_system_info() -> Dict[str, Any]:
    import platform
    import psutil
    
    info = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": psutil.cpu_count(logical=False),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "python_version": sys.version.split()[0]
    }
    
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        gpu_name = pynvml.nvmlDeviceGetName(handle)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        
        info["gpu_name"] = gpu_name
        info["gpu_memory_gb"] = round(mem_info.total / (1024**3), 2)
        pynvml.nvmlShutdown()
    except Exception as e:
        logger.warning(f"Could not get GPU info: {e}")
        info["gpu_name"] = "Unknown"
        info["gpu_memory_gb"] = 0
        
    return info


def format_duration(seconds: float) -> str:
    if seconds < 0.001:
        return f"{seconds*1000000:.2f}µs"
    elif seconds < 1:
        return f"{seconds*1000:.2f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    else:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.2f}s"


def format_throughput(tokens: int, seconds: float) -> str:
    if seconds == 0:
        return "∞ t/s"
    tps = tokens / seconds
    return f"{tps:.2f} t/s"


def format_bytes(bytes_value: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f}{unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f}PB"


def check_peridot_running(base_url: str = "http://localhost:5000") -> bool:
    import requests
    
    try:
        response = requests.get(f"{base_url}/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def wait_for_peridot(base_url: str = "http://localhost:5000", timeout: int = 30) -> bool:
    import requests
    
    logger.info(f"Waiting for Peridot at {base_url}...")
    start = time.time()
    
    while time.time() - start < timeout:
        if check_peridot_running(base_url):
            logger.info("Peridot is ready!")
            return True
        time.sleep(0.5)
        
    logger.error(f"Peridot did not become ready within {timeout}s")
    return False


class ProgressBar:
    """Simple progress bar for terminal output."""
    
    def __init__(self, total: int, prefix: str = "Progress"):
        self.total = total
        self.current = 0
        self.prefix = prefix
        
    def update(self, n: int = 1):
        self.current += n
        self._print()
        
    def _print(self):
        percent = (self.current / self.total) * 100
        filled = int(50 * self.current // self.total)
        bar = '█' * filled + '-' * (50 - filled)
        print(f'\r{self.prefix}: |{bar}| {percent:.1f}% ({self.current}/{self.total})', end='', flush=True)
        
        if self.current >= self.total:
            print()