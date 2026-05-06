"""
PERIDOT | INFERENCE BENCHMARK
Measures exact Tokens per Second (t/s) across the localhost API.
"""

import time
import requests
import sys
from pathlib import Path
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SERVER_HOST, SERVER_PORT, API_KEY

BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/ask"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

PROMPTS = [
    ("Short", "What is 2+2? Answer in one sentence."),
    ("Medium", "Explain the concept of quantum entanglement in exactly two paragraphs."),
    ("Long", "Write a highly detailed, comprehensive essay on the history of artificial intelligence, including major milestones and future implications.")
]

RUNS_PER_TEST = 5


def estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def run_single(prompt: str):
    start_time = time.perf_counter()
    
    r = requests.post(
        BASE_URL,
        json={"command": prompt},
        headers=HEADERS,
        timeout=300
    )
    r.raise_for_status()
    
    elapsed = time.perf_counter() - start_time
    response_text = r.json().get("response", "")
    
    tokens = estimate_tokens(response_text)
    tps = tokens / elapsed if elapsed > 0 else 0
    
    return {
        "tokens": tokens,
        "time": elapsed,
        "tps": tps
    }


def run_benchmark():
    print("=====================================")
    print("  PERIDOT INFERENCE BENCHMARK")
    print("=====================================\n")

    # Health check
    try:
        health = requests.get(
            f"http://{SERVER_HOST}:{SERVER_PORT}/health",
            timeout=3
        )
        if health.status_code != 200:
            print("[ERROR] Server not ready (health check failed)\n")
            return
    except Exception:
        print("[ERROR] Cannot reach Peridot server\n")
        return

    for name, prompt in PROMPTS:
        print(f"Testing [{name}] prompt...")
        
        results = []
        
        # Warmup
        try:
            run_single(prompt)
            time.sleep(1)
        except Exception:
            pass
        
        for i in range(RUNS_PER_TEST):
            try:
                res = run_single(prompt)
                results.append(res)
                
                print(f"  Run {i+1}: {res['tokens']} tokens | {res['time']:.2f}s | {res['tps']:.2f} t/s")
                
                time.sleep(0.5)
            except requests.exceptions.RequestException as e:
                print(f"  Run {i+1}: [FAILED] {e}")
        
        if results:
            tps_values = [r["tps"] for r in results]
            tokens_avg = statistics.mean([r["tokens"] for r in results])
            time_avg = statistics.mean([r["time"] for r in results])
            
            print("\n  --- Summary ---")
            print(f"  Avg Tokens: {tokens_avg:.0f}")
            print(f"  Avg Time: {time_avg:.2f}s")
            print(f"  Mean TPS: {statistics.mean(tps_values):.2f} t/s")
            print(f"  Median TPS: {statistics.median(tps_values):.2f} t/s")
            print(f"  Std Dev: ±{statistics.stdev(tps_values) if len(tps_values)>1 else 0:.2f}")
            print("")
        else:
            print("  [FAILED] No successful runs\n")


if __name__ == "__main__":
    run_benchmark()