# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
#
# Licensed under the MIT License.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Inference Speed
Measures token generation throughput across different workload sizes.
"""

import sys
import time
from pathlib import Path

# -----------------------------------------------------------------------------
# PATH BOOTSTRAPPING FIX
# -----------------------------------------------------------------------------
benchmarking_dir = Path(__file__).parent.absolute()
peridot_root = benchmarking_dir.parent
utils_path = benchmarking_dir / "utils"

for path in [str(peridot_root), str(utils_path)]:
    if path not in sys.path:
        sys.path.insert(0, path)

from benchmark_utils import (
    BenchmarkResult,
    repeat_measurement,
    get_system_info,
    format_duration,
    format_throughput,
    logger,
    AetherClient,
    check_peridot_running,
)

# DIRECTORY FIX: Stay inside benchmarking
RESULTS_DIR = benchmarking_dir / "results"

# Test prompts with expected token ranges
TEST_WORKLOADS = [
    {
        "name": "short",
        "description": "Quick chat query",
        "prompt": "What is 2+2?",
        "max_tokens": 30,
        "expected_tokens": 25,
    },
    {
        "name": "medium",
        "description": "Standard explanation",
        "prompt": "Explain the concept of machine learning in simple terms.",
        "max_tokens": 150,
        "expected_tokens": 120,
    },
    {
        "name": "long",
        "description": "Extended generation",
        "prompt": "Write a detailed 300-word explanation of how neural networks work, including key concepts like neurons, layers, weights, and backpropagation.",
        "max_tokens": 400,
        "expected_tokens": 350,
    },
]


def count_tokens_rough(text: str) -> int:
    words = text.split()
    return int(len(words) * 1.3)


def measure_inference_speed(client: AetherClient, prompt: str, max_tokens: int) -> dict:
    start_time = time.time()

    try:
        # AetherClient natively handles the payload split, headers, and RAM key extraction
        data = client.send_query(query=prompt, timeout=60)

        elapsed = time.time() - start_time
        response_text = data.get("response", "")

        tokens = count_tokens_rough(response_text)
        throughput = tokens / elapsed if elapsed > 0 else 0

        return {
            "tokens": tokens,
            "elapsed": elapsed,
            "throughput": throughput,
            "response_length": len(response_text),
        }

    except Exception as e:
        logger.error(f"Measurement failed: {e}")
        raise


def run_workload_benchmark(
    client: AetherClient, workload: dict, runs: int = 10
) -> BenchmarkResult:
    logger.info(f"\n{'='*60}")
    logger.info(f"Benchmarking: {workload['name']} ({workload['description']})")
    logger.info(f"Prompt: {workload['prompt'][:50]}...")
    logger.info(f"Expected tokens: ~{workload['expected_tokens']}")
    logger.info(f"{'='*60}\n")

    result = BenchmarkResult(
        name=f"inference_{workload['name']}",
        description=f"Inference speed for {workload['description']}",
    )

    result.add_metadata("workload_type", workload["name"])
    result.add_metadata("prompt", workload["prompt"])
    result.add_metadata("max_tokens", workload["max_tokens"])
    result.add_metadata("expected_tokens", workload["expected_tokens"])

    logger.info("Warmup run...")
    try:
        measure_inference_speed(client, workload["prompt"], workload["max_tokens"])
        time.sleep(1)
    except Exception as e:
        logger.warning(f"Warmup failed: {e}")

    throughputs = []
    tokens_generated = []
    elapsed_times = []

    for i in range(runs):
        logger.info(f"Run {i+1}/{runs}...")

        try:
            measurement = measure_inference_speed(
                client, workload["prompt"], workload["max_tokens"]
            )

            throughputs.append(measurement["throughput"])
            tokens_generated.append(measurement["tokens"])
            elapsed_times.append(measurement["elapsed"])

            logger.info(f"  Tokens: {measurement['tokens']}")
            logger.info(f"  Time: {format_duration(measurement['elapsed'])}")
            logger.info(
                f"  Throughput: {format_throughput(measurement['tokens'], measurement['elapsed'])}"
            )

            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Run {i+1} failed: {e}")
            continue

    for tp in throughputs:
        result.add_measurement(tp)

    if throughputs:
        import statistics

        result.add_metadata("avg_tokens_generated", statistics.mean(tokens_generated))
        result.add_metadata("avg_elapsed_time", statistics.mean(elapsed_times))
        result.add_metadata("throughputs", throughputs)
        result.add_metadata("successful_runs", len(throughputs))
        result.add_metadata("failed_runs", runs - len(throughputs))

    return result


def main():
    logger.info("\n" + "=" * 60)
    logger.info("PERIDOT INFERENCE SPEED BENCHMARK")
    logger.info("=" * 60 + "\n")

    # Use the robust check from benchmark_utils
    if not check_peridot_running():
        logger.error(
            "Peridot is not running or health check failed! Please start Peridot first."
        )
        logger.error("Run: python launcher.py")
        sys.exit(1)

    system_info = get_system_info()
    logger.info("System Information:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")
    logger.info("")

    # Instantiate the master client once to reuse the connection session
    client = AetherClient()
    all_results = []

    for workload in TEST_WORKLOADS:
        result = run_workload_benchmark(client, workload, runs=10)
        all_results.append(result)

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        result.save(RESULTS_DIR)

        stats = result.get_statistics()
        if stats:
            logger.info(f"\n{workload['name'].upper()} Summary:")
            logger.info(f"  Mean throughput: {stats['mean']:.2f} t/s")
            logger.info(f"  Median throughput: {stats['median']:.2f} t/s")
            logger.info(f"  Std deviation: {stats['stdev']:.2f} t/s")
            logger.info(f"  Range: {stats['min']:.2f} - {stats['max']:.2f} t/s")
            logger.info("")

    logger.info("\n" + "=" * 60)
    logger.info("OVERALL SUMMARY")
    logger.info("=" * 60 + "\n")

    summary_table = []
    for i, result in enumerate(all_results):
        stats = result.get_statistics()
        if not stats:
            continue

        workload = TEST_WORKLOADS[i]

        summary_table.append(
            {
                "Workload": workload["name"].capitalize(),
                "Avg Tokens": f"{result.metadata['avg_tokens_generated']:.0f}",
                "Avg Time": format_duration(result.metadata["avg_elapsed_time"]),
                "Throughput": f"{stats['median']:.2f} t/s",
                "Std Dev": f"+/- {stats['stdev']:.2f}",
            }
        )

    if summary_table:
        headers = list(summary_table[0].keys())
        col_widths = {
            h: max(len(h), max(len(str(row[h])) for row in summary_table))
            for h in headers
        }

        header_row = " | ".join(h.ljust(col_widths[h]) for h in headers)
        logger.info(header_row)
        logger.info("-" * len(header_row))

        for row in summary_table:
            logger.info(" | ".join(str(row[h]).ljust(col_widths[h]) for h in headers))

    logger.info("\n" + "=" * 60)
    logger.info("Benchmark complete! Results saved to:")
    logger.info(f"  {RESULTS_DIR.absolute()}")
    logger.info("=" * 60 + "\n")


if __name__ == "__main__":
    main()
