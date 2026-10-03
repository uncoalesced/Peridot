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
import time
from pathlib import Path
import psutil
from core_system.envfile import load_env, read_env, set_env_key  # noqa: F401 - re-exported

# Initialize basic logging for the bootstrap phase
logging.basicConfig(level=logging.INFO, format="%(asctime)s | [CONFIG] %(message)s")
logger = logging.getLogger("Peridot-Config")

# -----------------------------------------------------------------------------
# HARDWARE AUTO-DETECTION (Phase 2: VRAM Scaling)
# -----------------------------------------------------------------------------
def _detect_total_vram_mb() -> int:
    """
    Detect total GPU VRAM in MB via NVML, falling back to nvidia-smi.
    Returns 0 if detection fails (CPU-only or no NVIDIA GPU).
    Cross-platform: works on Windows NT and Linux/Unix.

    NVML first because this runs at import in every process (launcher, server,
    UI): measured 2026-09-25, nvidia-smi took ~1.7s per call vs ~0.1s for NVML.
    """
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        return int(pynvml.nvmlDeviceGetMemoryInfo(handle).total // (1024 * 1024))
    except Exception:
        pass
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
    """Get model size in MB: the file, or a HF folder's *.safetensors shards."""
    try:
        if model_path.is_dir():
            return sum(f.stat().st_size for f in model_path.glob("*.safetensors")) // (1024 * 1024)
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
    # ponytail: "Qwen3.8-27B-UD-IQ1_S.gguf" used to be pinned at 20 here, but
    # that comment/value described the old 9.2GiB Q2_K_XL quant, not this one.
    # IQ1_S is 5905MB on disk, which _calculate_gpu_layers() already offloads
    # in full (99) on 8GB VRAM -- no pin needed. Re-add a pin here only if a
    # specific quant is measured to need one.
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
load_env(Path(__file__).parent / ".env", override=True)

# -----------------------------------------------------------------------------
# SOVEREIGNTY LOCK (v1.5.4)
# -----------------------------------------------------------------------------
# The main process is air-gapped, unconditionally. These are forced AFTER
# load_env() so a stale or hand-edited .env cannot re-open the network.
#
# huggingface_hub reads these at *import* time, so this must run before any
# transformers / sentence-transformers / huggingface_hub import. config is the
# first Peridot module imported by server.py, main.py and install_wizard.py,
# so this is
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
#
# 2026-09-25: unblocked. scripts/build_llama_cpp_python.ps1 builds
# llama-cpp-python ea3b56bd (llama.cpp fb34fc262) with native sm_120 kernels on
# CUDA 13.1, and the on-disk quant is now UD-IQ1_S (5.9GB, nextn_predict_layers
# 0 -- no MTP head). Measured on RTX 5050 Laptop 8GB, fully offloaded:
# 23.6 t/s decode, ~500 t/s prefill on a 1.7k-token prompt
# (benchmarking/results/decode_rate_20260925_224748.json,
# decode_sweep_20260925_225519.json) -- vs 5.3 t/s / 34 t/s for the 14B, which
# only fits 28 of 48 layers. Requires the source build: the PyPI 0.3.23 wheel
# still cannot load it (fall back with ACTIVE_MODEL_NAME=Qwen2.5-14B-...).
DEFAULT_MODEL_NAME = "Qwen3.8-27B-UD-IQ1_S.gguf"
_PREVIOUS_DEFAULT_MODEL = "Qwen2.5-14B-Instruct-Q4_K_M.gguf"


def _resolve_default_model(model_dir: Path) -> str:
    """Default model, or a local stand-in when it isn't downloaded.

    A v1.5.4 install upgraded by `git pull` has the 14B but not the 27B, and no
    ACTIVE_MODEL_NAME in .env -- without this the server hard-exits on boot.
    Only used when ACTIVE_MODEL_NAME is unset; an explicit choice is never
    second-guessed.
    """
    if (model_dir / DEFAULT_MODEL_NAME).exists():
        return DEFAULT_MODEL_NAME
    if (model_dir / _PREVIOUS_DEFAULT_MODEL).exists():
        fallback = _PREVIOUS_DEFAULT_MODEL
    else:
        fallback = next((p.name for p in sorted(model_dir.glob("*.gguf"))), DEFAULT_MODEL_NAME)
    if fallback != DEFAULT_MODEL_NAME:
        logger.warning(f"{DEFAULT_MODEL_NAME} not found in {model_dir}; using {fallback}. "
                       "Run install_wizard.py to get the default model.")
    return fallback


ACTIVE_MODEL_NAME: str = os.getenv("ACTIVE_MODEL_NAME") or _resolve_default_model(MODEL_DIR)
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
# Measured context windows per model, by VRAM size, overriding the generic
# heuristic. KV bytes per token are model-specific (the 27B is hybrid Gated
# DeltaNet: only its attention layers keep a KV cache), so a VRAM-only rule
# either wastes most of the window or overflows. Measured 2026-09-25, RTX 5050
# 8GB, KV q8_0, fully offloaded -- VRAM used: 4k 6626MB, 8k 6766MB, 16k 7030MB,
# 32k 7596MB, 64k saturated. 16k leaves ~1.1GB for the desktop and the
# watchdog's total-100MB margin; 32k would leave ~550MB.
_MEASURED_CONTEXT: dict[tuple[str, int], int] = {
    # (model, minimum total VRAM MB) -> context length
    ("Qwen3.8-27B-UD-IQ1_S.gguf", 8000): 16384,
}
_measured_context = max(
    (ctx for (name, min_vram), ctx in _MEASURED_CONTEXT.items()
     if name == ACTIVE_MODEL_NAME and _TOTAL_VRAM_MB >= min_vram),
    default=None,
)
if _measured_context and os.getenv("KV_CACHE_TYPE", "f16") == "f16":
    # The table was measured with q8_0 KV; f16 roughly doubles the attention KV
    # (27B f16: 8k 7006MB, 16k 7510MB -- 16k would leave only ~640MB).
    _measured_context //= 2
CONTEXT_LENGTH: int = int(os.getenv(
    "CONTEXT_LENGTH", str(_measured_context or _calculate_context_length(_TOTAL_VRAM_MB))
))

MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "1024"))
# Decode threads = physical cores (hyperthreads contend for the same FPUs and
# slow token generation); batch/prefill threads may use every logical core.
_PHYSICAL_CORES: int = psutil.cpu_count(logical=False) or os.cpu_count() or 8
THREADS: int = int(os.getenv("THREADS", str(_PHYSICAL_CORES)))
THREADS_BATCH: int = int(os.getenv("THREADS_BATCH", str(os.cpu_count() or _PHYSICAL_CORES)))
BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "1024"))
# Physical micro-batch per GPU launch. Smaller than BATCH_SIZE shrinks the CUDA
# compute buffer, leaving VRAM for layers/KV. Tuned by
# `python -m benchmarking.benchmark_decode_rate --sweep`.
UBATCH_SIZE: int = int(os.getenv("UBATCH_SIZE", "512"))
# KV cache precision: f16 | q8_0 | q4_0 (quantized needs flash attention, which
# the provider always enables). Default f16: measured 2026-09-25, q8_0 costs no
# speed (23.2 vs 23.5 t/s) but on the 1.6-bit Qwen3.8-27B-UD-IQ1_S it made the
# model stop after 2-3 tokens under the full system prompt on 6/6 samples,
# vs 1/6 with f16. Quantizing KV on top of an extreme weight quant is not free.
# q8_0 remains a valid override for less aggressively quantized models.
KV_CACHE_TYPE: str = os.getenv("KV_CACHE_TYPE", "f16")

# Sampling. These are calibration knobs, not constants -- every env var below
# still overrides. The defaults were near-greedy (temp 0.1 / top_p 0.9), which
# is actively harmful on Qwen3-family thinking models: with almost no sampling
# entropy the model locks onto whatever degenerate pattern the in-context
# history suggests and reproduces it deterministically (observed 2026-08-20 as
# repeated empty <think></think> / bare [KERNEL_RESPONSE] turns). Values below
# are Qwen's published recommendations for thinking mode.
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.6"))
TOP_P: float = float(os.getenv("TOP_P", "0.95"))
TOP_K: int = int(os.getenv("TOP_K", "20"))
# Qwen recommends no repeat penalty for thinking models: 1.1 penalises the
# tokens the reasoning just used, which the answer then needs to repeat.
from core_system.prompting.constitution import model_supports_thinking  # noqa: E402 - stdlib-only module
REPEAT_PENALTY: float = float(os.getenv(
    "REPEAT_PENALTY", "1.0" if model_supports_thinking(MODEL_PATH) else "1.1"))

# --- NETWORK & SECURITY ---
SERVER_HOST: str = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "5000"))
SHUTDOWN_TIMEOUT: int = int(os.getenv("SHUTDOWN_TIMEOUT", "2"))

AI_SERVER_URL: str = f"http://{SERVER_HOST}:{SERVER_PORT}/ask"
SHUTDOWN_URL: str = f"http://{SERVER_HOST}:{SERVER_PORT}/shutdown"

# --- CRYPTOGRAPHIC HANDSHAKE ---
# Generate secure API key on first boot if missing
ENV_PATH = ROOT_PATH / ".env"


def _env_file_key():
    return read_env(ENV_PATH).get("API_KEY")


def _ensure_api_key():
    """Mint API_KEY exactly once across processes.

    Server and UI each import config; on first boot both used to generate a
    different key and the last writer won, leaving the other process with a
    key the server rejects. An O_EXCL lock file serialises the mint; losers
    poll .env until the winner's key appears.
    """
    lock = BASE_DIR / ".env.lock"
    deadline = time.monotonic() + 5
    while True:
        key = _env_file_key()
        if key:
            return key
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() < deadline:
                time.sleep(0.1)
                continue
            # ponytail: holder died mid-mint, so treat the lock as stale; a
            # second waiter racing this unlink is possible but needs a crash first.
            lock.unlink(missing_ok=True)
            continue
        try:
            key = _env_file_key()  # re-read: a peer may have minted while we waited
            if key:
                return key
            key = secrets.token_hex(32)
            # Never log the key itself. This previously interpolated `new_key` into the
            # message, so a live 64-character credential was written to stdout and to
            # logs/ on first boot. The key is persisted to .env below; that file is
            # the intended place to read it from.
            logger.warning("No API_KEY found. Generated a new secure key and wrote it to .env")
            set_env_key(ENV_PATH, "API_KEY", key)
            return key
        finally:
            os.close(fd)
            lock.unlink(missing_ok=True)


if not os.getenv("API_KEY"):
    os.environ["API_KEY"] = _ensure_api_key()

API_KEY: str = os.getenv("API_KEY")
os.environ["PERIDOT_AUTH_TOKEN"] = API_KEY

# --- MEDICAL RESEARCH CLUSTER (FAH v8) ---
RESEARCH_IDLE_THRESHOLD: int = int(os.getenv("RESEARCH_IDLE_THRESHOLD", "30")) # Time (s) before VRAM yields
RESEARCH_CHECK_INTERVAL: int = int(os.getenv("RESEARCH_CHECK_INTERVAL", "10")) # Polling rate (s)

# ZAT-SCS predictive preemption (always-on mic RMS stream + global keyboard hook
# at 10Hz, pre-warming the GPU before a prompt is sent). Opt-in: with the
# F@H handoff no longer costing ~2s per request, its benefit is small, and an
# always-open microphone/keyboard hook is not a default a sovereign app should ship.
ZAT_SCS_ENABLED: bool = os.getenv("ZAT_SCS_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")

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