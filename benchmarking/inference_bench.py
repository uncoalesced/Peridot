# benchmarking/inference_bench.py
# Engineered by uncoalesced.

import time
import statistics
from llama_cpp import Llama

MODEL_PATH = "models/brain.gguf"
RUNS_PER_TEST = 3


def extract_tokens(output):
    """Robust token extraction across llama-cpp versions."""
    if isinstance(output, dict):
        if "usage" in output and "completion_tokens" in output["usage"]:
            return output["usage"]["completion_tokens"]
        elif "choices" in output:
            text = output["choices"][0]["text"]
            return int(len(text.split()) * 1.3)
    return 0


def run_single(llm, prompt, max_t):
    start_time = time.perf_counter()
    output = llm(prompt, max_tokens=max_t)
    duration = time.perf_counter() - start_time

    tokens_generated = extract_tokens(output)
    tps = tokens_generated / duration if duration > 0 else 0

    return tokens_generated, duration, tps


def run_benchmarks():
    print(f"\n{'='*50}")
    print("   PERIDOT RAW INFERENCE BENCHMARK")
    print(f"{'='*50}")

    print(">> Loading Neural Engine into VRAM...")
    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=2048,
        n_threads=8,
        n_gpu_layers=33,
        verbose=False,
    )

    tests = [
        ("Short Response  (50t)", "Name 50 random colors as a comma-separated list.", 50),
        ("Medium Response (150t)", "Explain how a CPU cache works in technical detail.", 150),
        ("Long Response   (512t)", "Write a highly detailed, multi-paragraph cyberpunk short story.", 512),
    ]

    print("\n>> Running token generation tests...\n")

    for name, prompt, max_t in tests:
        print(f"[{name}]")

        # Warmup
        llm("Warmup", max_tokens=1)

        tps_results = []
        token_results = []
        time_results = []

        for i in range(RUNS_PER_TEST):
            tokens, duration, tps = run_single(llm, prompt, max_t)

            tps_results.append(tps)
            token_results.append(tokens)
            time_results.append(duration)

            print(f"  Run {i+1}: {tokens} tokens | {duration:.2f}s | {tps:.2f} t/s")

        if tps_results:
            print("  --- Summary ---")
            print(f"  Avg Tokens: {statistics.mean(token_results):.0f}")
            print(f"  Avg Time: {statistics.mean(time_results):.2f}s")
            print(f"  Mean TPS: {statistics.mean(tps_results):.2f} t/s")
            print(f"  Median TPS: {statistics.median(tps_results):.2f} t/s")
            print(f"  Std Dev: ±{statistics.stdev(tps_results) if len(tps_results)>1 else 0:.2f}")

        print("")

    print(f"{'='*50}\n")


if __name__ == "__main__":
    run_benchmarks()