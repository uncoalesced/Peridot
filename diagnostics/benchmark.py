# -----------------------------------------------------------------------------
# PERIDOT | HARDWARE BENCHMARK PROTOCOL (Direct Metal)
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import time
import sys
import os
import glob
from llama_cpp import Llama

# ANSI Colors for Output
GREEN = "\033[92m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"


def find_model():
    """Locates the .gguf model file in the models directory."""
    # Recursive search for any .gguf file
    files = glob.glob("**/*.gguf", recursive=True)
    if not files:
        print(f"{RED}[ERROR] No .gguf model found! Did you run setup.py?{RESET}")
        sys.exit(1)
    return files[0]


def run_test(llm, name, prompt, expected_tokens):
    print(f"\n{CYAN}Running Test: {name}...{RESET}")

    start_time = time.time()

    # Raw Generation
    output = llm.create_chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=expected_tokens,
        temperature=0.7,
        stream=False,
    )

    end_time = time.time()
    duration = end_time - start_time

    # Calculate Stats
    token_count = output["usage"]["completion_tokens"]
    tps = token_count / duration

    print(f" > Time: {duration:.2f}s")
    print(f" > Tokens: {token_count}")
    print(f" > Speed: {GREEN}{tps:.2f} Tokens/Sec{RESET}")

    return tps, duration, token_count


def main():
    print(f"{GREEN}INITIALIZING PERIDOT HARDWARE BENCHMARK...{RESET}")
    print("-" * 50)

    # 1. Locate Model
    model_path = find_model()
    print(f"Target Model: {model_path}")

    # 2. Load to GPU (Heavy Lift)
    print("Loading Model to VRAM (n_gpu_layers=-1)...")
    load_start = time.time()

    try:
        # We load with verbose=False to keep output clean
        llm = Llama(
            model_path=model_path,
            n_gpu_layers=-1,  # Force all layers to GPU
            n_ctx=2048,
            verbose=False,
        )
    except Exception as e:
        print(f"{RED}Failed to load model: {e}{RESET}")
        return

    load_time = time.time() - load_start
    print(f"Engine Loaded in {GREEN}{load_time:.2f}s{RESET}")
    print("-" * 50)

    # 3. Warmup
    print("Performing Warmup Sequence...")
    llm.create_chat_completion(
        messages=[{"role": "user", "content": "Hi"}], max_tokens=5
    )
    print("Warmup Complete.\n")

    # 4. The Gauntlet
    results = []

    # Test A: Short (Chat)
    tps_a, time_a, _ = run_test(
        llm, "Quick Chat", "Define 'Sovereignty' in 10 words.", 30
    )

    # Test B: Medium (Logic)
    tps_b, time_b, _ = run_test(
        llm, "Logic Core", "Write a Python list comprehension example.", 100
    )

    # Test C: Long (Creative)
    tps_c, time_c, _ = run_test(
        llm,
        "Creative Load",
        "Write a gritty sci-fi opening paragraph about a rainy neon city.",
        200,
    )

    # 5. Generate Report
    avg_tps = (tps_a + tps_b + tps_c) / 3

    print(f"\n{GREEN}BENCHMARK COMPLETE.{RESET}")
    print("-" * 50)

    markdown_report = f"""
### ⚡ Performance Benchmarks
*Hardware: NVIDIA RTX 5050 (Laptop) | Model: Llama-3-8B-Quantized*

| Task Complexity | Tokens Generated | Time (s) | Speed (T/s) |
| :--- | :---: | :---: | :---: |
| **Short (Chat)** | ~30 | {time_a:.2f}s | **{tps_a:.2f}** |
| **Medium (Logic)** | ~100 | {time_b:.2f}s | **{tps_b:.2f}** |
| **Long (Creative)** | ~200 | {time_c:.2f}s | **{tps_c:.2f}** |

**Average Speed:** {avg_tps:.2f} Tokens/Second
**Model Load Time:** {load_time:.2f}s
"""

    print("\n--- COPY THIS INTO YOUR README ---")
    print(markdown_report)
    print("----------------------------------")


if __name__ == "__main__":
    main()
