#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | MTBF STRESS TEST
# -----------------------------------------------------------------------------
# Engineered by uncoalesced
# -----------------------------------------------------------------------------
"""
Mean Time Between Failures (MTBF) stress test for Peridot Sovereign Kernel.
Tests hardware handoff reliability and autonomous RAG degradation under sustained load.
"""

import json
import time
import requests
import threading
from datetime import datetime
from pathlib import Path
import sys

# Add project root to path
ROOT_PATH = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_PATH))

from config import (
    SERVER_HOST, SERVER_PORT, API_KEY,
    RESEARCH_IDLE_THRESHOLD, RESEARCH_CHECK_INTERVAL
)

SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Stress test configuration
DEFAULT_DURATION_HOURS = 24
DEFAULT_DURATION_SECONDS = DEFAULT_DURATION_HOURS * 3600
LOG_FILE = ROOT_PATH / "logs" / "mtbf_stress_results.jsonl"

# Prompts for testing
HEAVY_PROMPT = "Explain the principles of quantum entanglement and its implications for faster-than-light communication, including references to Bell's theorem and recent experimental results."
RAPID_PROMPT = "What is 2+2?"


def log_event(event_type: str, data: dict):
    """Log an event as JSON line to the stress test log."""
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        "data": data
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    # Also print to console for visibility
    print(f"[{event_type}] {json.dumps(data)}")


def get_telemetry_metrics():
    """Fetch current telemetry metrics from the server."""
    try:
        resp = requests.get(f"{SERVER_URL}/telemetry/stability", headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        log_event("telemetry_error", {"error": str(e)})
    return None


def send_inference_request(prompt: str, session_id: str = None) -> dict:
    """Send a single inference request and return the response."""
    payload = {
        "query": prompt,
        "prompt": prompt,
        "session_id": session_id
    }
    try:
        start = time.time()
        resp = requests.post(f"{SERVER_URL}/ask", headers=HEADERS, json=payload, timeout=120)
        elapsed = time.time() - start

        if resp.status_code == 200:
            result = resp.json()
            # Check if response indicates kernel panic in the text
            response_text = result.get("response", "")
            if "KERNEL PANIC" in response_text or "[KERNEL PANIC]" in response_text:
                return {"status": "panic", "response": response_text, "elapsed": elapsed}
            return {"status": "success", "response": response_text, "elapsed": elapsed}
        else:
            # HTTP error (e.g., 503)
            return {"status": "http_error", "code": resp.status_code, "response": resp.text, "elapsed": elapsed}
    except requests.exceptions.RequestException as e:
        return {"status": "request_error", "error": str(e), "elapsed": time.time() - start}


def stress_test_loop(duration_seconds: int):
    """Main stress test loop."""
    start_time = time.time()
    end_time = start_time + duration_seconds

    log_event("stress_test_start", {
        "duration_hours": duration_seconds / 3600,
        "research_idle_threshold": RESEARCH_IDLE_THRESHOLD,
        "server_url": SERVER_URL
    })

    session_id = None  # We'll reuse session for continuity

    while time.time() < end_time:
        loop_start = time.time()

        # 1. Send heavy inference request (triggers potential handoff)
        heavy_resp = send_inference_request(HEAVY_PROMPT, session_id)
        if heavy_resp.get("session_id"):
            session_id = heavy_resp["session_id"]

        # Log outcome
        if heavy_resp["status"] == "success":
            log_event("heavy_inference_success", {
                "elapsed_seconds": heavy_resp["elapsed"],
                "session_id": session_id
            })
            # Optionally log telemetry after success
            metrics = get_telemetry_metrics()
            if metrics:
                log_event("telemetry_after_heavy", metrics)
        elif heavy_resp["status"] == "panic":
            log_event("kernel_panic_detected", {
                "trigger": "heavy_inference",
                "elapsed_seconds": heavy_resp["elapsed"],
                "response": heavy_resp["response"]
            })
        else:
            log_event("heavy_inference_failed", {
                "status": heavy_resp["status"],
                "elapsed_seconds": heavy_resp["elapsed"],
                "error": heavy_resp.get("error", heavy_resp.get("response"))
            })

        # 2. Wait for research to activate (IDLE -> FAH_ACTIVE)
        wait_time = max(0, RESEARCH_IDLE_THRESHOLD - 5)  # Subtract a bit to account for request time
        if wait_time > 0:
            time.sleep(wait_time)

        # 3. Immediately interrupt with new prompt to test handoff/VRAM purge
        interrupt_resp = send_inference_request(HEAVY_PROMPT, session_id)
        if interrupt_resp.get("session_id"):
            session_id = interrupt_resp["session_id"]

        if interrupt_resp["status"] == "success":
            log_event("interrupt_inference_success", {
                "elapsed_seconds": interrupt_resp["elapsed"],
                "session_id": session_id
            })
        elif interrupt_resp["status"] == "panic":
            log_event("kernel_panic_detected", {
                "trigger": "interrupt_inference",
                "elapsed_seconds": interrupt_resp["elapsed"],
                "response": interrupt_resp["response"]
            })
        else:
            log_event("interrupt_inference_failed", {
                "status": interrupt_resp["status"],
                "elapsed_seconds": interrupt_resp["elapsed"],
                "error": interrupt_resp.get("error", interrupt_resp.get("response"))
            })

        # 4. Rapid query burst to trigger autonomous RAG degradation
        for i in range(3):  # 3 rapid queries
            rapid_resp = send_inference_request(RAPID_PROMPT, session_id)
            if rapid_resp.get("session_id"):
                session_id = rapid_resp["session_id"]

            if rapid_resp["status"] == "success":
                log_event("rapid_inference_success", {
                    "sequence": i,
                    "elapsed_seconds": rapid_resp["elapsed"],
                    "session_id": session_id
                })
            elif rapid_resp["status"] == "panic":
                log_event("kernel_panic_detected", {
                    "trigger": f"rapid_inference_{i}",
                    "elapsed_seconds": rapid_resp["elapsed"],
                    "response": rapid_resp["response"]
                })
            else:
                log_event("rapid_inference_failed", {
                    "status": rapid_resp["status"],
                    "sequence": i,
                    "elapsed_seconds": rapid_resp["elapsed"],
                    "error": rapid_resp.get("error", rapid_resp.get("response"))
                })

            # Small delay between rapid queries
            time.sleep(0.5)

        # Calculate remaining time to maintain approximate cycle timing
        cycle_elapsed = time.time() - loop_start
        # Target cycle time: research threshold + request overhead + burst
        # We'll just sleep a bit to avoid hammering
        time.sleep(max(0, 2))

    log_event("stress_test_end", {
        "total_duration_seconds": time.time() - start_time,
        "total_hours": (time.time() - start_time) / 3600
    })


def main():
    """Entry point."""
    # Ensure log directory exists
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Clear previous log file (optional)
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    # Parse command line argument for duration
    duration_hours = DEFAULT_DURATION_HOURS
    if len(sys.argv) > 1:
        try:
            duration_hours = float(sys.argv[1])
        except ValueError:
            print(f"Invalid duration: {sys.argv[1]}. Using default {DEFAULT_DURATION_HOURS} hours.")

    duration_seconds = int(duration_hours * 3600)

    print(f"Starting Peridot MTBF stress test for {duration_hours} hours...")
    print(f"Logs will be written to: {LOG_FILE}")

    try:
        stress_test_loop(duration_seconds)
    except KeyboardInterrupt:
        log_event("stress_test_interrupted", {"reason": "KeyboardInterrupt"})
        print("\nStress test interrupted by user.")
    except Exception as e:
        log_event("stress_test_fatal_error", {"error": str(e)})
        print(f"\nStress test failed with error: {e}")
        raise


if __name__ == "__main__":
    main()