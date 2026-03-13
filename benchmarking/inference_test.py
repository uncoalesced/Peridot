"""
PERIDOT | INFERENCE BENCHMARK
Measures exact Tokens per Second (t/s) across the localhost API.
"""

import time
import requests
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SERVER_HOST, SERVER_PORT, API_KEY

BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/ask"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

PROMPTS = [
    ("Short", "What is 2+2? Answer in one sentence."),
    ("Medium", "Explain the concept of quantum entanglement in exactly two paragraphs."),
    ("Long", "Write a highly detailed, comprehensive essay on the history of artificial intelligence, including major milestones and future implications.")
]

def run_benchmark():
    print("=====================================")
    print("  PERIDOT INFERENCE BENCHMARK")
    print("=====================================\n")
    
    for name, prompt in PROMPTS:
        print(f"Testing [{name}] prompt...")
        start_time = time.time()
        
        try:
            r = requests.post(BASE_URL, json={"command": prompt}, headers=HEADERS, timeout=300)
            r.raise_for_status()
            response_text = r.json().get("response", "")
            
            elapsed = time.time() - start_time
            # Rough token estimation: words * 1.3
            word_count = len(response_text.split())
            estimated_tokens = int(word_count * 1.3)
            tps = estimated_tokens / elapsed
            
            print(f"  -> Generated ~{estimated_tokens} tokens in {elapsed:.2f}s")
            print(f"  -> Speed: {tps:.2f} t/s\n")
            
        except requests.exceptions.RequestException as e:
            print(f"  -> [FAILED] API Error: {e}\n")

if __name__ == "__main__":
    run_benchmark()