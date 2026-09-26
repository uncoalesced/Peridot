# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Shared utilities for Peridot benchmarking suite.
"""

import json
import time
import statistics
import logging
import platform
import sys
import requests
import psutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# ENVIRONMENT & PATH BOOTSTRAPPING
# -----------------------------------------------------------------------------
PERIDOT_ROOT = Path(__file__).parent.parent.parent.absolute()

# Force load the .env file BEFORE importing config
env_path = PERIDOT_ROOT / ".env"
load_dotenv(dotenv_path=env_path, override=True)

try:
    from config import AI_SERVER_URL
except ImportError:
    AI_SERVER_URL = "http://127.0.0.1:5000/ask"

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("benchmark_utils")

# Every benchmark writes its JSON here. This was recomputed in 10 separate files.
RESULTS_DIR = PERIDOT_ROOT / "benchmarking" / "results"

# Process names that indicate a running Peridot instance.
_PERIDOT_PROCESS_NAMES = ("server.py", "launcher.py", "main.py")


def get_vram_mb() -> Dict[str, Any]:
    """Single NVML query for GPU name and memory, in MB.

    There were seven near-identical copies of this init/handle/query/shutdown
    dance across benchmarking/. Returns zeros and name "Unknown" when NVML or a
    GPU is unavailable, so callers never need their own try/except.
    """
    result = {"name": "Unknown", "total": 0, "used": 0, "free": 0, "count": 0}
    try:
        import pynvml

        pynvml.nvmlInit()
        try:
            result["count"] = pynvml.nvmlDeviceGetCount()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", "replace")
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            result.update(
                name=name,
                total=mem.total // 1024 // 1024,
                used=mem.used // 1024 // 1024,
                free=mem.free // 1024 // 1024,
            )
        finally:
            pynvml.nvmlShutdown()
    except Exception as exc:
        logger.warning(f"Could not read GPU info: {exc}")
    return result


def find_peridot_processes() -> List[psutil.Process]:
    """Return live Peridot processes (server/launcher/main)."""
    found = []
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            cmd = " ".join(proc.info.get("cmdline") or []).lower()
            if any(name in cmd for name in _PERIDOT_PROCESS_NAMES):
                found.append(proc)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return found


def kill_existing_peridot(settle_seconds: float = 4.0) -> int:
    """Terminate any running Peridot processes. Returns how many were killed.

    Needed by the cold-start and context-scaling benchmarks, which must own the
    server lifecycle. Previously duplicated verbatim in both of them.
    """
    killed = 0
    for proc in find_peridot_processes():
        try:
            proc.kill()
            killed += 1
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    if killed:
        logger.info(f"Terminated {killed} running Peridot process(es)")
        # Default 4s: Windows plus the RTX 5050 need that long to fully dump
        # VRAM before a cold-start measurement is meaningful.
        time.sleep(settle_seconds)
    return killed


def get_peridot_memory() -> Optional[Dict[str, Any]]:
    """Resident/virtual memory of the running Peridot server, in MB.

    Returns None when no server process is found -- callers test falsiness, so
    this must not return a zero-filled dict. Previously duplicated in
    benchmark_memory_stability (dict) and benchmark_sustained_load (bare float).
    """
    for proc in find_peridot_processes():
        try:
            mem = proc.memory_info()
            return {
                "rss_mb": mem.rss / (1024 * 1024),
                "vms_mb": mem.vms / (1024 * 1024),
                "pid": proc.pid,
            }
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return None


def count_tokens_rough(text: str) -> int:
    """Word-count-based token estimate (words * 1.3).

    WARNING: an estimate only, for HTTP-path benchmarks that have no access to
    the model tokenizer. It systematically misreports throughput -- see the
    header of benchmark_inference.py. For a real token count use
    benchmark_decode_rate.py, which goes through the provider's own tokenizer.
    Consolidated here from four separate copies so the caveat lives in one place.
    """
    return int(len(text.split()) * 1.3)


def report_header(title: str, system_info: Optional[Dict[str, Any]] = None) -> None:
    """Print the standard benchmark banner plus system info."""
    logger.info("=" * 70)
    logger.info(title)
    logger.info("=" * 70)
    if system_info is None:
        system_info = get_system_info()
    logger.info("System:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")


def report_footer(filepath: Optional[Path] = None) -> None:
    """Print the standard benchmark completion footer."""
    logger.info("=" * 70)
    if filepath is not None:
        logger.info(f"Benchmark complete. Results saved to: {filepath}")
    else:
        logger.info("Benchmark complete.")
    logger.info("=" * 70)


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
            "stdev": (
                statistics.stdev(self.measurements)
                if len(self.measurements) > 1
                else 0.0
            ),
            "count": len(self.measurements),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "timestamp": self.timestamp,
            "measurements": self.measurements,
            "statistics": self.get_statistics(),
            "metadata": self.metadata,
        }

    def save(self, output_dir: Path):
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = output_dir / filename

        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        logger.info(f"Saved benchmark result to {filepath}")
        return filepath


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
    info = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": psutil.cpu_count(logical=False),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "python_version": sys.version.split()[0],
    }

    vram = get_vram_mb()
    info["gpu_name"] = vram["name"]
    info["gpu_memory_gb"] = round(vram["total"] / 1024, 2)

    return info


# -----------------------------------------------------------------------------
# RESTORED FORMATTING UTILITIES
# -----------------------------------------------------------------------------
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
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f}{unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f}PB"


def check_peridot_running(base_url: str = AI_SERVER_URL) -> bool:
    try:
        health_url = base_url.replace("/ask", "") + "/health"
        response = requests.get(health_url, timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def wait_for_peridot(
    base_url: str = AI_SERVER_URL, timeout: int = 30, poll_seconds: float = 0.5
) -> bool:
    """Block until /health answers, or `timeout` elapses.

    `poll_seconds` exists because the cold-start and context-scaling benchmarks
    start their own server and poll slowly (2s) to avoid hammering Flask while
    it initialises. They each carried a private copy of this loop.
    """
    logger.info("Waiting for Peridot Neural Engine...")
    start = time.time()

    while time.time() - start < timeout:
        if check_peridot_running(base_url):
            logger.info("Neural Link Established!")
            return True
        time.sleep(poll_seconds)

    logger.error(f"Peridot did not respond within {timeout}s")
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
        bar = "█" * filled + "-" * (50 - filled)
        print(
            f"\r{self.prefix}: |{bar}| {percent:.1f}% ({self.current}/{self.total})",
            end="",
            flush=True,
        )

        if self.current >= self.total:
            print()


# -----------------------------------------------------------------------------
# AETHER-ROUTE MASTER CLIENT
# -----------------------------------------------------------------------------
def get_ephemeral_key() -> str:
    """Forensically extracts the RAM-only API key from the running server process."""
    try:
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:  # Inner try-except prevents AccessDenied from crashing the loop
                cmdline = proc.info.get("cmdline") or []
                cmd_str = " ".join(cmdline).lower()
                if "server.py" in cmd_str or "launcher.py" in cmd_str:
                    env = proc.environ()
                    key = env.get("API_KEY") or env.get("PERIDOT_AUTH_TOKEN")
                    if key:
                        return key
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
    except Exception as e:
        logger.debug(f"Process memory inspection failed: {e}")

    # Fallback if extraction fails
    try:
        from config import API_KEY

        return API_KEY
    except Exception:
        return ""


class AetherClient:
    """Unified API Client for sending Aether-Route payloads from any benchmark."""

    def __init__(self):
        self.url = AI_SERVER_URL
        self.active_key = get_ephemeral_key()
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.active_key}",
        }
        # Session prevents socket exhaustion during sustained generation tests
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def send_query(self, query: str, timeout: int = 180):
        """Send a query and return the parsed JSON body.

        Deliberately sends only "query". server.py assembles the real prompt
        via build_full_context() using the loaded model's own chat format, so a
        client-side template is both unused and a mismatch risk -- this used to
        hardcode Llama-3 header tokens while the shipped default model is
        Qwen/chatml.
        """
        payload = {"query": query}
        response = self.session.post(self.url, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
