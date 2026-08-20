# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | ISOLATED DECODE-RATE BENCHMARK
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Pure generation-rate measurement, for cross-engine comparison.

WHY THIS EXISTS
---------------
`benchmark_inference.py` measures the wrong thing, in two compounding ways:

  1. It divides an APPROXIMATE token count (`len(words) * 1.3`, not tokenizer
     output) by FULL HTTP ROUND-TRIP time -- prefill, RAG retrieval, routing and
     transport all included.
  2. Far worse: it sends the SAME prompt on every run, so after the first run
     `server.py`'s L1 semantic cache returns a stored response and "Bypasses GPU
     entirely." A 30-request run produced 3 real inferences and 27 cache hits,
     inflating the reported rate by roughly 12x.

This benchmark removes every one of those confounders. It talks to the provider
abstraction directly -- no HTTP, no cache, no RAG, no routing -- counts tokens
with the real tokenizer, and times prefill separately from decode.

Because it targets `BaseInferenceProvider` rather than llama.cpp specifically,
the same numbers are directly comparable across llama-cpp-python, ExLlamaV2 and
vLLM once those exist. That is the point: the first cross-engine comparison must
not be measuring different things on each side.
"""

from __future__ import annotations

import argparse
import logging
import statistics
import sys
from pathlib import Path

PERIDOT_ROOT = Path(__file__).parent.parent.absolute()
if str(PERIDOT_ROOT) not in sys.path:
    sys.path.insert(0, str(PERIDOT_ROOT))

from benchmarking.utils.benchmark_utils import BenchmarkResult  # noqa: E402
from core_system.providers import ProviderLoadError, provider_for  # noqa: E402

logger = logging.getLogger("benchmark_decode_rate")

RESULTS_DIR = PERIDOT_ROOT / "benchmarking" / "results"

# Distinct prompts. Even though this path never touches the L1 cache, using
# varied prompts keeps the measurement honest if it is ever re-pointed at HTTP.
PROMPTS = [
    "Explain how a CPU cache hierarchy works, covering L1, L2 and L3 levels.",
    "Describe the differences between preemptive and cooperative multitasking.",
    "Summarise how virtual memory paging works in a modern operating system.",
    "Explain what a race condition is and how a mutex prevents one.",
    "Describe how a B-tree index speeds up database lookups.",
]


def run_benchmark(
    model_path: Path,
    n_ctx: int,
    n_gpu_layers: int,
    max_tokens: int,
    runs: int,
    warmup: int,
) -> BenchmarkResult:
    result = BenchmarkResult(
        name="decode_rate",
        description="Isolated decode rate (t/s), excluding prefill, cache and transport",
    )

    provider = provider_for(model_path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers)
    logger.info("Loading %s ...", model_path.name)
    provider.load()

    caps = provider.capabilities
    result.add_metadata("engine", caps.engine)
    result.add_metadata("model", model_path.name)
    result.add_metadata("n_gpu_layers", n_gpu_layers)
    result.add_metadata("n_ctx", n_ctx)
    result.add_metadata("max_tokens", max_tokens)

    prefill_rates: list[float] = []
    decode_seconds: list[float] = []
    completion_tokens: list[int] = []

    try:
        for i in range(warmup):
            prompt = PROMPTS[i % len(PROMPTS)]
            logger.info("Warmup %d/%d ...", i + 1, warmup)
            provider.generate(prompt, max_tokens=max_tokens, temperature=0.1)

        for i in range(runs):
            prompt = PROMPTS[i % len(PROMPTS)]
            logger.info("Run %d/%d ...", i + 1, runs)
            r = provider.generate(prompt, max_tokens=max_tokens, temperature=0.1)

            result.add_measurement(r.decode_tokens_per_second)
            prefill_rates.append(r.prefill_tokens_per_second)
            decode_seconds.append(r.decode_seconds)
            completion_tokens.append(r.completion_tokens)

            logger.info(
                "  %d tok | prefill %.2fs | decode %.2fs | %.2f t/s",
                r.completion_tokens,
                r.prefill_seconds,
                r.decode_seconds,
                r.decode_tokens_per_second,
            )
    finally:
        provider.unload()

    if prefill_rates:
        result.add_metadata("prefill_tps_median", statistics.median(prefill_rates))
        result.add_metadata("decode_seconds_median", statistics.median(decode_seconds))
        result.add_metadata("completion_tokens_median", statistics.median(completion_tokens))

    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    import config

    parser = argparse.ArgumentParser(description="Isolated decode-rate benchmark")
    parser.add_argument("--model", type=Path, default=config.MODEL_PATH)
    parser.add_argument("--n-ctx", type=int, default=config.CONTEXT_LENGTH)
    parser.add_argument("--n-gpu-layers", type=int, default=config.GPU_LAYERS)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args()

    try:
        result = run_benchmark(
            model_path=Path(args.model),
            n_ctx=args.n_ctx,
            n_gpu_layers=args.n_gpu_layers,
            max_tokens=args.max_tokens,
            runs=args.runs,
            warmup=args.warmup,
        )
    except ProviderLoadError as e:
        logger.error("Provider failed to load: %s", e)
        return 1

    stats = result.get_statistics()
    if not stats:
        logger.error("No successful measurements.")
        return 1

    result.save(RESULTS_DIR)

    print("\n" + "=" * 58)
    print("ISOLATED DECODE RATE (no HTTP, no cache, no RAG)")
    print("=" * 58)
    print(f"  Engine        : {result.metadata['engine']}")
    print(f"  Model         : {result.metadata['model']}")
    print(f"  GPU layers    : {result.metadata['n_gpu_layers']}")
    print(f"  Median decode : {stats['median']:.2f} t/s")
    print(f"  Mean decode   : {stats['mean']:.2f} t/s")
    print(f"  Std dev       : {stats['stdev']:.2f} t/s")
    print(f"  Range         : {stats['min']:.2f} - {stats['max']:.2f} t/s")
    print(f"  Prefill median: {result.metadata.get('prefill_tps_median', 0):.2f} t/s")
    print("=" * 58)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
