# benchmarking/handoff_bench.py
# Engineered by uncoalesced.

import time
import json
import websocket
from llama_cpp import Llama

MODEL_PATH = "models/brain.gguf"


def send_fah_command(cmd_state):
    """Sends the WebSocket command and measures execution time."""
    start = time.perf_counter()
    try:
        ws = websocket.create_connection(
            "ws://127.0.0.1:7396/api/websocket", timeout=2.0
        )
        ws.send(json.dumps({"cmd": "state", "state": cmd_state}))
        ws.close()
        return (time.perf_counter() - start) * 1000
    except Exception as e:
        print(f"Socket Error: {e}")
        return -1


def run_benchmark():
    print(f"\n{'='*50}")
    print("   PERIDOT VRAM HANDOFF BENCHMARK")
    print(f"{'='*50}")

    # 1. Spin up FAH
    print(">> Forcing FAH into Folding State (Allocating VRAM)...")
    send_fah_command("fold")
    time.sleep(5)  # Give the CUDA core 5 seconds to fully saturate the GPU

    # 2. Measure Handoff
    print(">> Firing VRAM Purge Signal...")
    latency_ms = send_fah_command("pause")
    print(f">> [RESULT] WebSocket Handoff Latency: {latency_ms:.2f} ms")

    # 3. Load Model (Simulating the immediate inference demand)
    print("\n>> Loading Neural Engine to claim cleared VRAM...")
    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=2048,
        n_threads=8,  # Ryzen 7 Optimization
        n_gpu_layers=33,  # RTX 5050 Engaged
        verbose=False,
    )

    # 4. Measure TPS
    print(">> Running 100-token stress test...")
    start_tps = time.perf_counter()
    output = llm("Explain the architecture of a GPU in detail.", max_tokens=100)
    duration = time.perf_counter() - start_tps

    tokens = output["usage"]["completion_tokens"]
    tps = tokens / duration

    print(f">> [RESULT] Sustained Inference Speed: {tps:.2f} t/s")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    run_benchmark()
