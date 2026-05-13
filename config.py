#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import os
from pathlib import Path
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# ENVIRONMENT BOOTSTRAP
# -----------------------------------------------------------------------------
# Load the .env file FIRST. This applies HF_HUB_OFFLINE and locks the API_KEY
# before any other libraries initialize.
load_dotenv()

# --- SYSTEM PATHS ---
BASE_DIR = Path(__file__).parent
ROOT_PATH = BASE_DIR.resolve()
INPUT_PATH = ROOT_PATH / "input"
PROCESSED_PATH = INPUT_PATH / "processed"
LOG_PATH = ROOT_PATH / "logs"
BACKUP_PATH = ROOT_PATH / "backups"
STORAGE_PATH = ROOT_PATH / "storage"
MODEL_DIR = ROOT_PATH / "models"

# Create directories if missing
for path in [LOG_PATH, BACKUP_PATH, PROCESSED_PATH, MODEL_DIR, STORAGE_PATH, INPUT_PATH]:
    path.mkdir(exist_ok=True)

# --- ENGINE CONFIGURATION (v1.4 TurboQuant) ---

# Toggle this variable depending on your daily driver. 
# Do NOT use the Q4_K_M anymore. Use the IQ3_M or the Qwen 3B.
ACTIVE_MODEL_NAME = "Meta-Llama-3-8B-Instruct-IQ3_M.gguf" 
# ACTIVE_MODEL_NAME = "qwen2.5-3b-instruct-q4_k_m.gguf"

MODEL_PATH = MODEL_DIR / ACTIVE_MODEL_NAME

# Hardware Allocation (BLACKWELL RTX 5050 / Ryzen 7)
GPU_LAYERS = 100        # 100 forces full VRAM offloading
CONTEXT_LENGTH = 8192   # TurboQuant Standard (Requires ~1.2GB VRAM buffer)
MAX_TOKENS = 1024       # Expanded for deeper RAG summaries

# Generation Parameters (Tuned for strict RAG precision)
TEMPERATURE = 0.1       # Dropped from 0.7 to 0.1 to stop hallucinations
TOP_P = 0.9
REPEAT_PENALTY = 1.1

# --- NETWORK & SECURITY ---
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000
SHUTDOWN_TIMEOUT = 2

# API Endpoints
AI_SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/ask"
SHUTDOWN_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/shutdown"

# --- CRYPTOGRAPHIC HANDSHAKE ---
API_KEY = os.getenv("API_KEY", "08101954")
os.environ["PERIDOT_AUTH_TOKEN"] = API_KEY

# --- MEDICAL RESEARCH (FAH v8) ---
RESEARCH_IDLE_THRESHOLD = 30  # Dropped to 30s to maximize Folding uptime
RESEARCH_CHECK_INTERVAL = 10  # seconds

# Validate critical paths
if not MODEL_PATH.exists():
    print(f"[WARNING] Model not found at {MODEL_PATH}. Awaiting TurboQuant payload.")