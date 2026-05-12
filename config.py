# Engineered by uncoalesced

import os
from pathlib import Path
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# ENVIRONMENT BOOTSTRAP
# -----------------------------------------------------------------------------
# Load the .env file FIRST. This applies HF_HUB_OFFLINE and locks the API_KEY
# before any other libraries initialize.
load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent
ROOT_PATH = BASE_DIR.resolve()
INPUT_PATH = ROOT_PATH / "input"
PROCESSED_PATH = INPUT_PATH / "processed"
LOG_PATH = ROOT_PATH / "logs"
BACKUP_PATH = ROOT_PATH / "backups"
MODEL_DIR = ROOT_PATH / "models"

# Create directories if missing
for path in [LOG_PATH, BACKUP_PATH, PROCESSED_PATH, MODEL_DIR]:
    path.mkdir(exist_ok=True)

# Model Configuration
MODEL_PATH = MODEL_DIR / "Meta-Llama-3-8B-Instruct.Q4_K_M.gguf"
MODEL_TYPE = "llama-3"
QUANTIZATION = "Q4_K_M"

# --- GPU & MEMORY LIMITS (BLACKWELL RTX 5050 - NATIVE FP4 PROFILE) ---
# Validated during ARPM Benchmarks: All 32 layers fit in VRAM with ~2040MB free.
GPU_LAYERS = 100 

# Context length restored to full capacity based on stable KV cache telemetry
CONTEXT_LENGTH = 8192

# Safe output generation cap
MAX_TOKENS = 512
# ---------------------------------------------------------------------

# Inference Settings
TEMPERATURE = 0.7
TOP_P = 0.9
REPEAT_PENALTY = 1.1

# Server Settings
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000
SHUTDOWN_TIMEOUT = 2

# API Endpoints
AI_SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/ask"
SHUTDOWN_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/shutdown"

# --- CRYPTOGRAPHIC HANDSHAKE ---
# Pulls directly from .env to maintain perfect synchronization across all processes
API_KEY = os.getenv("API_KEY", "08101954")

# Push it to os.environ so ephemeral RAM scrapers still find it
os.environ["PERIDOT_AUTH_TOKEN"] = API_KEY

# Medical Research Settings
RESEARCH_IDLE_THRESHOLD = 60  # Tightened to 1 minute
RESEARCH_CHECK_INTERVAL = 10  # seconds

# Validate critical paths
if not MODEL_PATH.exists():
    print(f"[WARNING] Model not found at {MODEL_PATH}. Run setup to download.")