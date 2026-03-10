import os
import secrets
from pathlib import Path

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

# GPU Configuration
GPU_LAYERS = 33  # Adjust based on VRAM (6GB = ~28, 8GB = ~33)
MAX_TOKENS = 8192
CONTEXT_LENGTH = 8192

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

# RAM-Only Authentication (Zero Disk Footprint)
API_KEY = os.environ.get("PERIDOT_AUTH_TOKEN")
if not API_KEY:
    # Fallback for manual script execution if launcher.py isn't used
    API_KEY = secrets.token_hex(16)
    os.environ["PERIDOT_AUTH_TOKEN"] = API_KEY

# Medical Research Settings
RESEARCH_IDLE_THRESHOLD = 60  # Tightened to 1 minute
RESEARCH_CHECK_INTERVAL = 10  # seconds

# Validate critical paths
if not MODEL_PATH.exists():
    print(f"[WARNING] Model not found at {MODEL_PATH}. Run setup to download.")