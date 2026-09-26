# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
#
# Licensed under the MIT License.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Memory Stability
Tests for memory leaks by running many consecutive queries.
"""

import sys
import time


from benchmarking.utils.benchmark_utils import (
    RESULTS_DIR,
    AetherClient,
    BenchmarkResult,
    ProgressBar,
    check_peridot_running,
    get_peridot_memory,
    get_system_info,
    logger,
)

# DIRECTORY FIX: Stay inside benchmarking


def run_query(client: AetherClient, query_num: int):
    """Run a single query and return response time."""
    prompts = [
        "What is machine learning?",
        "Explain quantum computing.",
        "How do neural networks work?",
        "What is the difference between AI and ML?",
        "Describe deep learning.",
        "What is natural language processing?",
        "Explain computer vision.",
        "What are transformers in AI?",
        "How does backpropagation work?",
        "What is reinforcement learning?",
    ]

    raw_query = prompts[query_num % len(prompts)]

    start = time.time()

    # AetherClient natively handles payload formatting, headers, and the persistent session
    client.send_query(query=raw_query, timeout=30)

    elapsed = time.time() - start
    return elapsed


def main():
    logger.info("\n" + "=" * 60)
    logger.info("PERIDOT MEMORY STABILITY BENCHMARK")
    logger.info("=" * 60 + "\n")

    if not check_peridot_running():
        logger.error(
            "Peridot is not running or health check failed! Please start Peridot Neural Engine first."
        )
        sys.exit(1)

    initial_mem = get_peridot_memory()
    if not initial_mem:
        logger.error("Could not find Peridot process!")
        sys.exit(1)

    logger.info(f"Peridot process found (PID: {initial_mem['pid']})")
    logger.info(f"Initial memory usage: {initial_mem['rss_mb']:.2f} MB\n")

    system_info = get_system_info()
    logger.info("System Information:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")
    logger.info("")

    result = BenchmarkResult(
        name="memory_stability", description="Memory usage over consecutive queries"
    )

    result.add_metadata("initial_memory_mb", initial_mem["rss_mb"])
    result.add_metadata("pid", initial_mem["pid"])

    num_queries = 100
    sample_interval = 5

    logger.info(f"Running {num_queries} consecutive queries...")
    logger.info(f"Sampling memory every {sample_interval} queries\n")

    memory_samples = []
    query_times = []

    progress = ProgressBar(num_queries, prefix="Progress")

    # Instantiate client once to reuse session connections
    client = AetherClient()

    for i in range(num_queries):
        try:
            query_time = run_query(client, i)
            query_times.append(query_time)

            if i % sample_interval == 0:
                mem = get_peridot_memory()
                if mem:
                    memory_samples.append(
                        {
                            "query_num": i,
                            "rss_mb": mem["rss_mb"],
                            "vms_mb": mem["vms_mb"],
                        }
                    )
                    result.add_measurement(mem["rss_mb"])

            progress.update()
            time.sleep(0.1)

        except Exception as e:
            logger.error(f"\nQuery {i+1} failed: {e}")
            continue

    final_mem = get_peridot_memory()
    if final_mem:
        result.add_metadata("final_memory_mb", final_mem["rss_mb"])
        result.add_metadata(
            "memory_growth_mb", final_mem["rss_mb"] - initial_mem["rss_mb"]
        )

    result.add_metadata("total_queries", num_queries)
    result.add_metadata("successful_queries", len(query_times))
    result.add_metadata("memory_samples", memory_samples)

    import statistics

    if query_times:
        result.add_metadata("avg_query_time_s", statistics.mean(query_times))
        result.add_metadata("median_query_time_s", statistics.median(query_times))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result.save(RESULTS_DIR)

    logger.info("\n" + "=" * 60)
    logger.info("MEMORY STABILITY SUMMARY")
    logger.info("=" * 60 + "\n")

    logger.info(f"Queries executed: {len(query_times)}/{num_queries}")
    logger.info(f"Initial memory: {initial_mem['rss_mb']:.2f} MB")

    if final_mem:
        logger.info(f"Final memory: {final_mem['rss_mb']:.2f} MB")
        growth = final_mem["rss_mb"] - initial_mem["rss_mb"]
        logger.info(
            f"Memory growth: {growth:+.2f} MB ({growth/initial_mem['rss_mb']*100:+.2f}%)"
        )

        if abs(growth) < 50:
            logger.info("[OK] Memory stable (growth < 50 MB)")
        else:
            logger.warning("[WARN] Significant memory growth detected!")

    logger.info("")

    if memory_samples:
        logger.info("Memory samples:")
        logger.info(f"  {'Query':<10} {'RSS (MB)':<12} {'VMS (MB)':<12}")
        logger.info("  " + "-" * 34)
        for sample in memory_samples[::5]:
            logger.info(
                f"  {sample['query_num']:<10} {sample['rss_mb']:<12.2f} {sample['vms_mb']:<12.2f}"
            )

    logger.info("")

    if query_times:
        logger.info("Query performance:")
        logger.info(f"  Average: {statistics.mean(query_times):.3f}s")
        logger.info(f"  Median: {statistics.median(query_times):.3f}s")
        logger.info(f"  Std Dev: {statistics.stdev(query_times):.3f}s")

    logger.info("")
    logger.info("=" * 60)
    logger.info("Benchmark complete! Results saved to:")
    logger.info(f"  {RESULTS_DIR.absolute()}")
    logger.info("=" * 60 + "\n")


if __name__ == "__main__":
    main()
