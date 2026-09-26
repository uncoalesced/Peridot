from pathlib import Path
SPECULATIVE_THRESHOLD = 0.65
INACTIVITY_TIMER = 15.0
LAMBDA_DECAY = 0.1
WEIGHT_KEY = 0.45
WEIGHT_AUD = 0.35
TELEMETRY_HZ = 10
# Upstream llama.cpp `llama-server` used by the ZAT-SCS speculative slot
# restore path (LlamaClient -> POST /slots/{id}/restore). This is NOT
# Peridot's own Flask backend, which config.py serves on port 5000.
# These were previously named SERVER_HOST/SERVER_PORT, colliding with the
# identically-named config.py symbols and reading as a port misconfiguration.
UPSTREAM_LLAMA_HOST = "127.0.0.1"
UPSTREAM_LLAMA_PORT = 8080
SLOT_SAVE_PATH = Path("./slots")
