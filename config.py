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
    Cross-platform: works on Windows NT and Linux/Unix.
    """
    import sys
    try:
        # Safe subprocess call without shell=True
        cmd = ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"]
        kwargs = {"stderr": subprocess.DEVNULL}
        # Windows NT only: use CREATE_NO_WINDOW to suppress console window
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        output = subprocess.check_output(cmd, **kwargs).decode().strip()
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
    Accounts for context window size to ensure proper tensor splitting 
    where the remainder bleeds into system RAM.
    """
    if total_vram_mb == 0:
        return 0  # CPU-only mode
        
    context_reserve_mb = 1024
    safe_vram_mb = total_vram_mb - 256 # 256MB OS buffer
    
    # If the whole model PLUS context fits, offload everything
    if model_size_mb > 0 and (model_size_mb + context_reserve_mb) < safe_vram_mb:
        return 99  # Full GPU offload
    
    if model_size_mb > 0:
        # Otherwise, fill available VRAM (minus context) and let the rest tensor split to RAM
        available_for_layers = safe_vram_mb - context_reserve_mb
        ratio = available_for_layers / model_size_mb
        return max(20, min(int(ratio * 35), 99))
    return 20

# -----------------------------------------------------------------------------
# PROVISIONAL GPU LAYER OVERRIDES (v1.5.4)
# -----------------------------------------------------------------------------
# _calculate_gpu_layers() was tuned against 4-bit-quant 8B-14B models. Its
# layer-count model does not hold for 2-bit UD quants of a 27.8B parameter
# model: per-layer VRAM cost, KV-cache footprint and the compute buffer all
# scale differently, and nothing here has been benchmarked against that shape.
#
# Rather than trust an unvalidated extrapolation on a model that would OOM the
# GPU on boot if it guessed high, these entries pin a deliberately conservative
# value. Boot safety over throughput.
#
# PROVISIONAL - NOT BENCHMARKED. Operators with headroom should raise this via
# the GPU_LAYERS env var and report results.
_PROVISIONAL_GPU_LAYERS: dict[str, int] = {
    # 9.2GiB file vs 8GB VRAM: leaves ~4.5GB free for KV cache + compute buffer
    # + CUDA context, with the remaining layers tensor-split into system RAM.
    #
    # DORMANT: this model cannot currently be loaded at all (llama.cpp 0.3.23
    # lacks qwen35 MTP support -- see the ACTIVE_MODEL_NAME note below), so the
    # value has never been exercised against a successful load. It is retained
    # so the pin is already in place when MTP support lands; re-derive it from a
    # real benchmark at that point rather than trusting this number.
    "Qwen3.8-27B-UD-Q2_K_XL.gguf": 20,
}

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

# -----------------------------------------------------------------------------
# SOVEREIGNTY LOCK (v1.5.4)
# -----------------------------------------------------------------------------
# The main process is air-gapped, unconditionally. These are forced AFTER
# load_dotenv() so a stale or hand-edited .env cannot re-open the network.
#
# huggingface_hub reads these at *import* time, so this must run before any
# transformers / sentence-transformers / huggingface_hub import. config is the
# first Peridot module imported by server.py, main.py and setup.py, so this is
# the earliest reliable point.
#
# Model downloads are NOT done here. They run in an isolated child process
# (core_system/model_fetch.py) which is the only place HF_HUB_OFFLINE=0 exists.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

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

# --- ENGINE CONFIGURATION (v1.5.4) ---
# Default reverted from Qwen3.8-27B-UD-Q2_K_XL.gguf (post-v1.5.4).
#
# The 27B cannot be loaded by the pinned llama-cpp-python 0.3.23:
#
#   llama_model_load: error loading model: missing tensor 'blk.64.ssm_conv1d.weight'
#
# Root cause is a RUNTIME GAP, not a bad file. The GGUF declares:
#   qwen35.block_count          = 65
#   qwen35.nextn_predict_layers = 1
# i.e. 64 hybrid SSM/attention layers plus one MTP (multi-token prediction)
# head at index 64. llama.cpp 0.3.23 ignores nextn_predict_layers and builds
# all 65 blocks as standard hybrid layers, so it demands an SSM tensor that
# correctly does not exist on the MTP head.
#
# Verified against a byte-exact re-download from unsloth/Qwen3.8-27B-GGUF
# (9,828,981,664 bytes): fails identically, and identically at n_gpu_layers=0,
# so it is neither corruption nor a VRAM/offload problem.
#
# Unblocked by llama-cpp-python >= a release with qwen35 MTP support (0.3.35 is
# current; 0.3.23 is pinned). That upgrade requires a cuBLAS rebuild and belongs
# with the v1.6.x inference-provider work, not a patch bump.
ACTIVE_MODEL_NAME: str = os.getenv("ACTIVE_MODEL_NAME", "Qwen2.5-14B-Instruct-Q4_K_M.gguf")
MODEL_PATH: Path = MODEL_DIR / ACTIVE_MODEL_NAME

# Dynamic hardware-aware configuration
_MODEL_SIZE_MB: int = _get_model_size_mb(MODEL_PATH)

# GPU_LAYERS resolution order:
#   1. GPU_LAYERS env var (operator override, always wins)
#   2. _PROVISIONAL_GPU_LAYERS pin for models the auto-heuristic has not been
#      validated against (see the table above)
#   3. _calculate_gpu_layers() auto-heuristic
_provisional_layers = _PROVISIONAL_GPU_LAYERS.get(ACTIVE_MODEL_NAME)
if _TOTAL_VRAM_MB == 0:
    _default_gpu_layers = 0  # CPU-only: the provisional pin does not apply
elif _provisional_layers is not None:
    _default_gpu_layers = _provisional_layers
else:
    _default_gpu_layers = _calculate_gpu_layers(_MODEL_SIZE_MB, _TOTAL_VRAM_MB)

GPU_LAYERS: int = int(os.getenv("GPU_LAYERS", str(_default_gpu_layers)))

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

if _provisional_layers is not None and "GPU_LAYERS" not in os.environ:
    logger.warning(
        f"GPU_LAYERS={GPU_LAYERS} is a PROVISIONAL pin for {ACTIVE_MODEL_NAME} "
        "(auto-heuristic unvalidated for this quant/size). Not benchmarked. "
        "Override with the GPU_LAYERS env var if you have VRAM headroom."
    )