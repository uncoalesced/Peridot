# benchmarking/inference_bench.py
# Engineered by uncoalesced.

import time
from llama_cpp import Llama

MODEL_PATH = "models/brain.gguf"


def run_benchmarks():
    print(f"\n{'='*50}")
    print("   PERIDOT RAW INFERENCE BENCHMARK")
    print(f"{'='*50}")

    print(">> Loading Neural Engine into VRAM...")
    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=2048,
        n_threads=8,  # Ryzen 7
        n_gpu_layers=33,  # RTX 5050
        verbose=False,
    )

    tests = [
        (
            "Short Response  (50t)",
            "Name 50 random colors as a comma-separated list.",
            50,
        ),
        (
            "Medium Response (150t)",
            "Explain how a CPU cache works in technical detail.",
            150,
        ),
        (
            "Long Response   (512t)",
            "Write a highly detailed, multi-paragraph cyberpunk short story.",
            512,
        ),
    ]

    print("\n>> Running token generation tests...\n")

    for name, prompt, max_t in tests:
        # Warmup (optional, but helps stabilize cuBLAS)
        if max_t == 50:
            llm("Warmup", max_tokens=1)

        start_time = time.perf_counter()
        output = llm(prompt, max_tokens=max_t)
        duration = time.perf_counter() - start_time

        tokens_generated = output["usage"]["completion_tokens"]
        tps = tokens_generated / duration

        print(f"[{name}]")
        print(f" -> Speed:  {tps:.2f} t/s")
        print(f" -> Output: {tokens_generated} tokens in {duration:.2f} seconds\n")

    print(f"{'='*50}\n")


if __name__ == "__main__":
    run_benchmarks()
