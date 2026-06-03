#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | CONFIGURATION ENGINE
# Copyright (C) 2026 uncoalesced
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Initialize basic logging for the bootstrap phase
logging.basicConfig(level=logging.INFO, format="%(asctime)s | [CONFIG] %(message)s")
logger = logging.getLogger("Peridot-Config")

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

# --- ENGINE CONFIGURATION (v1.5 TurboQuant) ---
ACTIVE_MODEL_NAME: str = os.getenv("ACTIVE_MODEL_NAME", "Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf")
MODEL_PATH: Path = MODEL_DIR / ACTIVE_MODEL_NAME

GPU_LAYERS: int = int(os.getenv("GPU_LAYERS", "-1"))
CONTEXT_LENGTH: int = int(os.getenv("CONTEXT_LENGTH", "8192"))
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
API_KEY: str = os.getenv("API_KEY")
os.environ["PERIDOT_AUTH_TOKEN"] = API_KEY

# --- MEDICAL RESEARCH CLUSTER (FAH v8) ---
RESEARCH_IDLE_THRESHOLD: int = int(os.getenv("RESEARCH_IDLE_THRESHOLD", "30")) # Time (s) before VRAM yields
RESEARCH_CHECK_INTERVAL: int = int(os.getenv("RESEARCH_CHECK_INTERVAL", "10")) # Polling rate (s)

# -----------------------------------------------------------------------------
# STARTUP VALIDATION
# -----------------------------------------------------------------------------
if not MODEL_PATH.exists():
    logger.warning(f"Core logic matrix not found at {MODEL_PATH}. Awaiting TurboQuant payload ingestion.")