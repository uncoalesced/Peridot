# Engineered by uncoalesced
"""
Peridot API Client
Handles local HTTP communication with the sovereign kernel for benchmarking.
"""

import os
import requests
from pathlib import Path
from requests.exceptions import RequestException
from dotenv import load_dotenv

# Force the client to load the exact same .env file the server uses
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Hunt for the correct key and strip any accidental quote characters
raw_key = os.environ.get("PERIDOT_AUTH_TOKEN") or os.environ.get("API_KEY") or "08101954"
API_KEY = raw_key.strip('"').strip("'")

print(f"\n[DEBUG] api_client initialized. Using API Key: {API_KEY}\n")

BASE_URL = "http://127.0.0.1:5000"

def get_headers() -> dict:
    """Construct standard headers for kernel communication."""
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    return headers

def post_chat(message: str, max_tokens: int = 100, timeout: int = 120) -> dict:
    """Send a standard inference request to the kernel."""
    url = f"{BASE_URL}/ask"
    
    payload = {
        "command": message,
        "max_tokens": max_tokens
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=get_headers(),
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()
    except RequestException as e:
        raise RuntimeError(f"Kernel communication failed during /ask: {e}")

def get_health() -> dict:
    """Ping the kernel to verify it is online and responsive."""
    try:
        response = requests.get(
            f"{BASE_URL}/health", 
            headers=get_headers(), 
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except RequestException as e:
        raise RuntimeError(f"Health check failed. Is Peridot running? Error: {e}")