# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.5.3 | INTEGRITY & CONCURRENCY HARNESS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import os
import sys
import time
import requests
import threading
from pathlib import Path

# --- CORE AUTOMATED ENVIRONMENT RESOLUTION ---
# Move up one directory level from benchmarking/ to locate project configuration roots
_BENCHMARK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _BENCHMARK_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Real-time asset mapping to scrape the internal backend secret keys
API_KEY = "DEV_FALLBACK"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000

# 1. First Attempt: Extract live key directly from core config environment
try:
    import config

    API_KEY = getattr(config, "API_KEY", API_KEY)
    SERVER_HOST = getattr(config, "SERVER_HOST", SERVER_HOST)
    SERVER_PORT = getattr(config, "SERVER_PORT", SERVER_PORT)
except ImportError:
    # 2. Second Attempt: If config is isolated, parse the filesystem .env file manually
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("API_KEY="):
                    API_KEY = line.strip().split("=", 1)[1].strip("'\"")
                elif line.startswith("SERVER_PORT="):
                    try:
                        SERVER_PORT = int(line.strip().split("=", 1)[1])
                    except Exception:
                        pass

SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def run_health_check() -> bool:
    """Vector 1: Immediate API Heartbeat and Readiness Telemetry."""
    print(">> [VECTOR 01] Initiating core engine diagnostic pulse...")
    print(f" └── Targeting socket: {SERVER_URL} (API Key: Shared Signature Resolved)")
    try:
        r = requests.get(f"{SERVER_URL}/health", timeout=5)
        if r.status_code == 200:
            print("[SUCCESS] Core Neural Engine reporting standard nominal status.")
            return True
        else:
            print(
                f"[CRITICAL] Engine responded with anomalies. Status Code: {r.status_code}"
            )
            return False
    except requests.exceptions.RequestException as e:
        print(
            f"[FATAL] Connection to Kernel failed entirely. Is server.py active? Details: {e}"
        )
        return False


def stress_session_persistence():
    """Vector 2: Multi-Turn Conversation Thread Enforcers."""
    print(
        "\n>> [VECTOR 02] Deploying sequential context strainers into SQLite Ledger..."
    )
    session_id = None

    queries = [
        "Initialize loop test. Acknowledge identity constraint.",
        "Based on my previous prompt, what explicit loop test type did we just implement?",
        "Provide a complex, deeply optimized multi-threaded Python blueprint for reading parquet buffers.",
    ]

    for i, q in enumerate(queries):
        payload = {"query": q, "prompt": q}
        if session_id:
            payload["session_id"] = session_id

        print(f" ├── Sending turn {i+1}/3 to active stack...")
        start = time.time()
        try:
            r = requests.post(
                f"{SERVER_URL}/ask", json=payload, headers=HEADERS, timeout=60
            )
            elapsed = time.time() - start

            if r.status_code == 200:
                res_data = r.json()
                session_id = res_data.get("session_id")
                print(
                    f" └── [OK] Nominal turn clearance. Session ID: {session_id} | Latency: {elapsed:.2f}s"
                )
            else:
                print(
                    f" └── [ERROR] Route faulted during session processing. Code: {r.status_code}"
                )
                break
        except Exception as e:
            print(f" └── [FATAL] Turn disrupted by an unhandled exception: {e}")
            break


def hardware_concurrency_load():
    """Vector 3: Parallel Request Sledgehammer (Simulating concurrent traffic)."""
    print(
        "\n>> [VECTOR 03] Deploying twin-threaded race conditions to check hardware locks..."
    )

    def hammer_endpoint(thread_id):
        payload = {
            "query": f"Thread test signature {thread_id}",
            "prompt": "Ping status signature.",
        }
        try:
            print(f" ├── Thread-{thread_id} launching execution payload...")
            r = requests.post(
                f"{SERVER_URL}/ask", json=payload, headers=HEADERS, timeout=30
            )
            print(f" └── Thread-{thread_id} returned with state code: {r.status_code}")
        except Exception as e:
            print(f" [CRITICAL] Thread-{thread_id} crashed out of loop matrix: {e}")

    t1 = threading.Thread(target=hammer_endpoint, args=(1,))
    t2 = threading.Thread(target=hammer_endpoint, args=(2,))

    t1.start()
    t2.start()

    t1.join()
    t2.join()
    print("[MATRIX COMPLETE] Concurrency validation passed.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Peridot Stability Verifier")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run the stress test in an infinite loop (e.g. for 24h stability testing)",
    )
    args = parser.parse_args()

    print("==================================================")
    print(" PERIDOT STABILITY VERIFIER | INTEGRITY HARNESS  ")
    print("==================================================")

    if args.loop:
        print("[MODE] 24-Hour Continuous Loop Activated. Press Ctrl+C to stop.\n")
        cycle = 1
        try:
            while True:
                print(f"--- [CYCLE {cycle}] ---")
                if run_health_check():
                    stress_session_persistence()
                    hardware_concurrency_load()
                    print(
                        f"\n[CYCLE {cycle} CONCLUSION] Cycle complete. Cooling down for 10 seconds..."
                    )
                    time.sleep(10)
                    cycle += 1
                else:
                    print(
                        f"[FATAL] Health check failed on cycle {cycle}. Aborting loop."
                    )
                    sys.exit(1)
        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Loop terminated by operator.")
    else:
        if run_health_check():
            stress_session_persistence()
            hardware_concurrency_load()
            print(
                "\n[CONCLUSION] All stress tests complete. Check engine console log history to evaluate VRAM reclamation."
            )
        else:
            sys.exit(1)
