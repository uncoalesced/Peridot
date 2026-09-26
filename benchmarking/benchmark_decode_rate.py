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
import itertools
import json
import logging
import statistics
from datetime import datetime
from pathlib import Path

PERIDOT_ROOT = Path(__file__).parent.parent.absolute()

from benchmarking.utils.benchmark_utils import (  # noqa: E402
    RESULTS_DIR,
    BenchmarkResult,
)
from core_system.providers import ProviderLoadError, provider_for  # noqa: E402

logger = logging.getLogger("benchmark_decode_rate")


# Distinct prompts. Even though this path never touches the L1 cache, using
# varied prompts keeps the measurement honest if it is ever re-pointed at HTTP.
PROMPTS = [
    "Explain how a CPU cache hierarchy works, covering L1, L2 and L3 levels.",
    "Describe the differences between preemptive and cooperative multitasking.",
    "Summarise how virtual memory paging works in a modern operating system.",
    "Explain what a race condition is and how a mutex prevents one.",
    "Describe how a B-tree index speeds up database lookups.",
]

# Prefill probe: RAG context + history make real prompts ~1-2k tokens, so the
# prefill rate of a 20-token prompt says nothing about time-to-first-token.
LONG_PROMPT = (" ".join(PROMPTS) + " ") * 24 + "Summarise the above in one sentence."


def run_benchmark(
    model_path: Path,
    n_ctx: int,
    n_gpu_layers: int,
    max_tokens: int,
    runs: int,
    warmup: int,
    long_prefill: bool = False,
    **tuning,
) -> BenchmarkResult:
    """`tuning` goes straight to the provider (n_threads, n_ubatch, kv_cache_type, ...)."""
    result = BenchmarkResult(
        name="decode_rate",
        description="Isolated decode rate (t/s), excluding prefill, cache and transport",
    )

    provider = provider_for(model_path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers, **tuning)
    logger.info("Loading %s ...", model_path.name)
    provider.load()
    for key, value in tuning.items():
        result.add_metadata(key, value)

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

        if long_prefill:
            provider.reset()  # force a cold prefill of the whole long prompt
            r = provider.generate(LONG_PROMPT, max_tokens=1, temperature=0.1)
            result.add_metadata("long_prompt_tokens", r.prompt_tokens)
            result.add_metadata("long_prefill_tps", r.prefill_tokens_per_second)
            logger.info("  long prefill: %d tok at %.1f t/s", r.prompt_tokens, r.prefill_tokens_per_second)
    finally:
        provider.unload()

    if prefill_rates:
        result.add_metadata("prefill_tps_median", statistics.median(prefill_rates))
        result.add_metadata("decode_seconds_median", statistics.median(decode_seconds))
        result.add_metadata("completion_tokens_median", statistics.median(completion_tokens))

    return result


def _csv(kind):
    return lambda text: [kind(v) for v in text.split(",") if v]


def run_sweep(args, config) -> int:
    """Cartesian sweep over GPU layers x KV type x ubatch x threads.

    One JSON with a row per config; a config that fails to load (OOM, bad
    type) is recorded and skipped, not fatal.
    """
    rows = []
    grid = list(itertools.product(args.layers, args.kv, args.ubatch, args.threads))
    for idx, (layers, kv, ubatch, threads) in enumerate(grid, 1):
        tag = f"layers={layers} kv={kv} ubatch={ubatch} threads={threads}"
        logger.info("[%d/%d] %s", idx, len(grid), tag)
        row = {"n_gpu_layers": layers, "kv_cache_type": kv, "n_ubatch": ubatch, "n_threads": threads}
        try:
            r = run_benchmark(
                model_path=Path(args.model), n_ctx=args.n_ctx, n_gpu_layers=layers,
                max_tokens=args.max_tokens, runs=args.runs, warmup=args.warmup,
                long_prefill=True, n_batch=max(ubatch, config.BATCH_SIZE), n_ubatch=ubatch,
                kv_cache_type=kv, n_threads=threads, n_threads_batch=config.THREADS_BATCH,
                flash_attn=True,
            )
            stats = r.get_statistics()
            row.update(
                status="ok",
                decode_tps_median=stats.get("median"),
                long_prefill_tps=r.metadata.get("long_prefill_tps"),
                long_prompt_tokens=r.metadata.get("long_prompt_tokens"),
            )
        except Exception as e:  # noqa: BLE001 - OOM/unsupported configs are data here
            row.update(status="failed", error=str(e)[:200])
        logger.info("  -> %s", row)
        rows.append(row)

    ok = [r for r in rows if r["status"] == "ok"]
    best = max(ok, key=lambda r: r["decode_tps_median"] or 0, default=None)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"decode_sweep_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps({
        "model": Path(args.model).name, "n_ctx": args.n_ctx, "max_tokens": args.max_tokens,
        "runs": args.runs, "rows": rows, "best_decode": best,
    }, indent=2), encoding="utf-8")

    print(f"\n{'layers':>6} {'kv':>5} {'ubatch':>6} {'thr':>3} {'decode t/s':>10} {'prefill t/s':>11}")
    for r in rows:
        if r["status"] == "ok":
            print(f"{r['n_gpu_layers']:>6} {r['kv_cache_type']:>5} {r['n_ubatch']:>6} {r['n_threads']:>3} "
                  f"{r['decode_tps_median']:>10.2f} {r['long_prefill_tps']:>11.1f}")
        else:
            print(f"{r['n_gpu_layers']:>6} {r['kv_cache_type']:>5} {r['n_ubatch']:>6} {r['n_threads']:>3}  FAILED")
    print(f"\nBest decode: {best}\nSaved: {out}")
    return 0 if ok else 1


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
    parser.add_argument("--sweep", action="store_true",
                        help="Grid over --layers/--kv/--ubatch/--threads; one JSON of results")
    parser.add_argument("--layers", type=_csv(int), default=[config.GPU_LAYERS])
    parser.add_argument("--kv", type=_csv(str), default=["f16", "q8_0", "q4_0"])
    parser.add_argument("--ubatch", type=_csv(int), default=[256, 512, 1024])
    parser.add_argument("--threads", type=_csv(int), default=[config.THREADS])
    args = parser.parse_args()

    if args.sweep:
        return run_sweep(args, config)

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
