#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | CONFIGURATION ENGINE
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import os
import sys
import logging
import secrets
import subprocess
from pathlib import Path
from dotenv import load_dotenv, set_key

# Initialize basic logging for the bootstrap phase
logging.basicConfig(level=logging.INFO, format="%(asctime)s | [CONFIG] %(message)s")
logger = logging.getLogger("Peridot-Config")

# -----------------------------------------------------------------------------
# HARDWARE AUTO-DETECTION (Phase 2: VRAM Scaling)
# -----------------------------------------------------------------------------
def _detect_total_vram_mb() -> int:
    """
    Detect total GPU VRAM in MB using nvidia-smi.
    Returns 0 if detection fails (CPU-only or no NVIDIA GPU).
    """
    try:
        # Safe subprocess call without shell=True
        cmd = ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, creationflags=0x08000000).decode().strip()
        if output:
            # Take the first GPU's VRAM (in MB)
            return int(output.split('\n')[0])
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError, IndexError):
        pass
    return 0

def _get_model_size_mb(model_path: Path) -> int:
    """Get model file size in MB."""
    try:
        if model_path.exists():
            return model_path.stat().st_size // (1024 * 1024)
    except Exception:
        pass
    return 0

def _calculate_gpu_layers(model_size_mb: int, total_vram_mb: int) -> int:
    """
    Calculate optimal GPU layers.
    If model fits in < 75% of VRAM, offload all layers (99).
    Otherwise, use conservative default (20).
    """
    if total_vram_mb == 0:
        return 0  # CPU-only mode
    if model_size_mb > 0 and model_size_mb < (total_vram_mb * 0.75):
        return 99  # Full GPU offload
    return 20  # Partial offload

def _calculate_context_length(total_vram_mb: int) -> int:
    """
    Calculate optimal context length based on available VRAM.
    >10GB VRAM: 8192 tokens
    <=10GB VRAM: 4096 tokens
    CPU-only: 2048 tokens
    """
    if total_vram_mb == 0:
        return 2048
    if total_vram_mb > 10240:  # > 10GB
        return 8192
    return 4096

# Detect hardware capabilities at module load time
_TOTAL_VRAM_MB: int = _detect_total_vram_mb()
_TOTAL_VRAM_GB: float = _TOTAL_VRAM_MB / 1024.0

# -----------------------------------------------------------------------------
# ENVIRONMENT BOOTSTRAP
# -----------------------------------------------------------------------------
load_dotenv(override=True)

# --- SYSTEM PATHS ---
BASE_DIR: Path = Path(__file__).parent.resolve()
ROOT_PATH: Path = BASE_DIR

INPUT_PATH: Path = ROOT_PATH / "input"
PROCESSED_PATH: Path = INPUT_PATH / "processed"
LOG_PATH: Path = ROOT_PATH / "logs"
BACKUP_PATH: Path = ROOT_PATH / "backups"
STORAGE_PATH: Path = ROOT_PATH / "storage"
MODEL_DIR: Path = ROOT_PATH / "models"

for directory in (LOG_PATH, BACKUP_PATH, PROCESSED_PATH, MODEL_DIR, STORAGE_PATH, INPUT_PATH):
    directory.mkdir(parents=True, exist_ok=True)

# --- ENGINE CONFIGURATION (v1.5.1 TurboQuant) ---
ACTIVE_MODEL_NAME: str = os.getenv("ACTIVE_MODEL_NAME", "Qwen2.5-14B-Instruct-Q4_K_M.gguf")
MODEL_PATH: Path = MODEL_DIR / ACTIVE_MODEL_NAME

# Dynamic hardware-aware configuration
_MODEL_SIZE_MB: int = _get_model_size_mb(MODEL_PATH)

# GPU_LAYERS: Auto-calculate based on VRAM vs model size
# Allow env override for manual tuning
GPU_LAYERS: int = int(os.getenv("GPU_LAYERS", str(_calculate_gpu_layers(_MODEL_SIZE_MB, _TOTAL_VRAM_MB))))

# CONTEXT_LENGTH: Auto-calculate based on total VRAM
CONTEXT_LENGTH: int = int(os.getenv("CONTEXT_LENGTH", str(_calculate_context_length(_TOTAL_VRAM_MB))))

MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "1024"))
THREADS: int = int(os.getenv("THREADS", "8"))
BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "1024"))

TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
TOP_P: float = float(os.getenv("TOP_P", "0.9"))
REPEAT_PENALTY: float = float(os.getenv("REPEAT_PENALTY", "1.1"))

# --- NETWORK & SECURITY ---
SERVER_HOST: str = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "5000"))
SHUTDOWN_TIMEOUT: int = int(os.getenv("SHUTDOWN_TIMEOUT", "2"))

AI_SERVER_URL: str = f"http://{SERVER_HOST}:{SERVER_PORT}/ask"
SHUTDOWN_URL: str = f"http://{SERVER_HOST}:{SERVER_PORT}/shutdown"

# --- CRYPTOGRAPHIC HANDSHAKE ---
# Generate secure API key on first boot if missing
ENV_PATH = ROOT_PATH / ".env"
if not os.getenv("API_KEY"):
    new_key = secrets.token_hex(32)
    logger.warning(f"No API_KEY found. Generated new secure key: {new_key}")
    if ENV_PATH.exists():
        set_key(str(ENV_PATH), "API_KEY", new_key)
    else:
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write(f"API_KEY={new_key}\n")
    os.environ["API_KEY"] = new_key

API_KEY: str = os.getenv("API_KEY")
os.environ["PERIDOT_AUTH_TOKEN"] = API_KEY

# --- MEDICAL RESEARCH CLUSTER (FAH v8) ---
RESEARCH_IDLE_THRESHOLD: int = int(os.getenv("RESEARCH_IDLE_THRESHOLD", "30")) # Time (s) before VRAM yields
RESEARCH_CHECK_INTERVAL: int = int(os.getenv("RESEARCH_CHECK_INTERVAL", "10")) # Polling rate (s)

# -----------------------------------------------------------------------------
# HARDWARE TELEMETRY EXPORTS (for UI and other modules)
# -----------------------------------------------------------------------------
TOTAL_VRAM_MB: int = _TOTAL_VRAM_MB
TOTAL_VRAM_GB: float = _TOTAL_VRAM_GB

# -----------------------------------------------------------------------------
# STARTUP VALIDATION
# -----------------------------------------------------------------------------
if not MODEL_PATH.exists():
    logger.warning(f"Core logic matrix not found at {MODEL_PATH}. Awaiting TurboQuant payload ingestion.")

logger.info(f"Hardware Profile: VRAM={TOTAL_VRAM_GB:.1f}GB | Model={_MODEL_SIZE_MB}MB | GPU_LAYERS={GPU_LAYERS} | CTX={CONTEXT_LENGTH}")