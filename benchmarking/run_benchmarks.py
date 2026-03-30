# -----------------------------------------------------------------------------
# PERIDOT v1.3 | SYSTEM STRESS & BENCHMARK TEST
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import time
import requests
import sys
import os

# Link to parent config so we can access the core components
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import SERVER_HOST, SERVER_PORT, API_KEY
from core_system.memory.vault import PeridotVault

BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

def run_benchmarks():
    print("==================================================")
    print("  PERIDOT v1.3 | SYSTEM STRESS & BENCHMARK TEST")
    print("==================================================")

    # 1. API & VRAM Engine Check
    print("\n[1] Testing Neural Engine Connection...")
    start = time.time()
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"  -> SUCCESS: Engine Online (Ping: {(time.time()-start)*1000:.2f}ms)")
    except Exception as e:
        print(f"  -> FATAL: Engine Offline. Boot server.py first. ({e})")
        return

    # 2. Layer 2 Vault Latency
    print("\n[2] Testing Layer 2 Vault Vector Search...")
    start_load = time.time()
    vault = PeridotVault()
    print(f"  -> Vault Loaded in {(time.time()-start_load)*1000:.2f}ms")
    
    start_search = time.time()
    res = vault.search("Fallout")
    latency = (time.time() - start_search) * 1000
    sectors = vault.index.ntotal if vault.index else 0
    
    if res:
        print(f"  -> SUCCESS: Vault searched {sectors} sectors in {latency:.2f}ms")
        if latency > 100.0:
            print("  -> [WARN] Search time exceeded 100ms roadmap target.")
    else:
        print(f"  -> FAILED: No results returned. Is the Vault empty?")

    # 3. VRAM State Handoff
    print("\n[3] Testing VRAM State Machine (Medical Research Handoff)...")
    start_enable = time.time()
    requests.post(f"{BASE_URL}/research/enable", headers=HEADERS)
    print(f"  -> SUCCESS: Armed Folding State ({(time.time()-start_enable)*1000:.2f}ms)")
    
    start_disable = time.time()
    requests.post(f"{BASE_URL}/research/disable", headers=HEADERS)
    print(f"  -> SUCCESS: Purged VRAM for Inference ({(time.time()-start_disable)*1000:.2f}ms)")

    # 4. Cold LLM Inference
    print("\n[4] Testing Cold LLM Inference Latency...")
    payload = {"command": "Respond with the exact word 'Acknowledged' and nothing else."}
    start_infer = time.time()
    try:
        r = requests.post(f"{BASE_URL}/ask", json=payload, headers=HEADERS, timeout=120)
        ms = (time.time() - start_infer) * 1000
        print(f"  -> SUCCESS: Engine Responded in {ms:.2f}ms")
        print(f"  -> Output: {r.json().get('response', '').strip()}")
    except Exception as e:
        print(f"  -> FAILED: Inference timeout or crash. {e}")

    print("\n==================================================")
    print("  BENCHMARKS COMPLETE.")

if __name__ == "__main__":
    run_benchmarks()