# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
#
# Licensed under the MIT License.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

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

# Read the operator key from the environment. No fallback: v1.5.1 eliminated the
# hardcoded default key from the kernel, but this client kept a copy of it.
raw_key = os.environ.get("PERIDOT_AUTH_TOKEN") or os.environ.get("API_KEY") or ""
API_KEY = raw_key.strip('"').strip("'")

BASE_URL = "http://127.0.0.1:5000"

_NO_KEY_MESSAGE = (
    "No API key found. Set PERIDOT_AUTH_TOKEN or API_KEY in .env before "
    "running the benchmarking suite."
)


def get_headers() -> dict:
    """Construct standard headers for kernel communication.

    The missing-key check lives here rather than at module scope. Raising at
    import time meant importing this module -- which benchmark_cold_start and
    benchmark_context_scaling both do at their own import -- hard-failed before
    argparse or --help could run, so those scripts could not even be inspected
    without a configured .env.

    Never echo the key. It previously went to stdout on every run, putting a
    live credential into console scrollback and any captured CI log.
    """
    if not API_KEY:
        raise RuntimeError(_NO_KEY_MESSAGE)
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }


def post_chat(message: str, max_tokens: int = 100, timeout: int = 120) -> dict:
    """Send a standard inference request to the kernel."""
    url = f"{BASE_URL}/ask"

    payload = {"command": message, "max_tokens": max_tokens}

    try:
        response = requests.post(
            url, json=payload, headers=get_headers(), timeout=timeout
        )
        response.raise_for_status()
        return response.json()
    except RequestException as e:
        raise RuntimeError(f"Kernel communication failed during /ask: {e}")


def get_health() -> dict:
    """Ping the kernel to verify it is online and responsive."""
    try:
        response = requests.get(f"{BASE_URL}/health", headers=get_headers(), timeout=5)
        response.raise_for_status()
        return response.json()
    except RequestException as e:
        raise RuntimeError(f"Health check failed. Is Peridot running? Error: {e}")
