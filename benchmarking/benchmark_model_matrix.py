#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Benchmark: Multi-Model Matrix (TurboQuant sweep)

Sweeps every GGUF in models/ and records, per model: time-to-first-token,
decode rate, and peak VRAM. This is the only benchmark that compares models
against each other -- benchmark_decode_rate measures one model in isolation and
benchmark_cold_start measures server boot.

Relocated here from core_system/benchmark.py, which was an orphan module (no
importers, never invoked by the runner) and unusable as written:

  * `exit(1)` fired at *import* time when llama_cpp was missing, so merely
    importing the module could kill the interpreter.
  * It constructed llama_cpp.Llama directly, bypassing core_system.providers
    entirely, so it ignored the provider abstraction the rest of v1.6 uses.
  * It hardcoded the Llama-3 chat template while the shipped default model is
    Qwen2.5-14B (chatml) -- every measurement ran on a mismatched prompt.
  * It re-queried NVML inside the per-token generation loop, perturbing the
    very throughput number it was reporting.
  * A bare `return` inside `finally` silently swallowed every exception.

Run from the repository root:
    python -m benchmarking.benchmark_model_matrix
"""

import argparse
import statistics
import sys
from pathlib import Path

from core_system.prompting.constitution import get_model_format
from core_system.providers import ProviderLoadError, provider_for
from benchmarking.utils.benchmark_utils import (
    RESULTS_DIR,
    BenchmarkResult,
    get_vram_mb,
    logger,
    report_footer,
    report_header,
)

PERIDOT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PERIDOT_ROOT / "models"

# One neutral prompt, reused across models so the comparison is apples to apples.
PROMPT = (
    "Summarise, in one short paragraph, why keeping model weights resident in "
    "VRAM reduces inference latency."
)


def _wrap_prompt(model_path: Path) -> str:
    """Apply the model's own chat template.

    get_model_format() reads the format from the GGUF metadata, so a Qwen model
    gets chatml and a Llama-3 model gets Llama-3 headers. The previous
    implementation hardcoded Llama-3 for every model.
    """
    fmt = get_model_format(str(model_path))
    if fmt == "chatml":
        return "<|im_start|>user\n" + PROMPT + "<|im_end|>\n<|im_start|>assistant\n"
    if fmt == "llama3":
        return (
            "<|start_header_id|>user<|end_header_id|>\n\n"
            + PROMPT
            + "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        )
    # Unknown format: send the bare prompt rather than a wrong scaffold.
    return PROMPT


def benchmark_model(
    model_path: Path, n_ctx: int, n_gpu_layers: int, max_tokens: int, runs: int
) -> dict:
    """Measure one model. Never raises -- failures are recorded in the row."""
    row = {
        "model": model_path.name,
        "size_mb": round(model_path.stat().st_size / (1024 * 1024), 1),
        "n_gpu_layers": n_gpu_layers,
        "n_ctx": n_ctx,
        "status": "FAILED",
    }

    vram_before = get_vram_mb()
    row["vram_before_mb"] = vram_before["used"]
    logger.info("=" * 70)
    logger.info(f"MODEL: {model_path.name}  ({row['size_mb']} MB)")
    logger.info(f"  VRAM in use before load: {vram_before['used']} MB")

    provider = None
    try:
        provider = provider_for(model_path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers)
        provider.load()
        row["engine"] = provider.capabilities.engine

        vram_loaded = get_vram_mb()
        row["vram_after_load_mb"] = vram_loaded["used"]
        logger.info(f"  VRAM in use after load:  {vram_loaded['used']} MB")

        prompt = _wrap_prompt(model_path)
        ttft, decode_rates, peak_vram = [], [], vram_loaded["used"]

        for i in range(runs):
            result = provider.generate(prompt, max_tokens=max_tokens, temperature=0.1)
            # prefill_seconds IS time-to-first-token: the provider times prefill
            # and decode separately, so TTFT no longer needs a manual stopwatch
            # wrapped around a token stream.
            ttft.append(result.prefill_seconds)
            decode_rates.append(result.decode_tokens_per_second)
            # Sampled once per run, never inside the token loop.
            peak_vram = max(peak_vram, get_vram_mb()["used"])
            logger.info(
                f"  run {i + 1}/{runs}: ttft {result.prefill_seconds:.3f}s | "
                f"{result.decode_tokens_per_second:.2f} t/s | "
                f"{result.completion_tokens} tok"
            )

        row.update(
            ttft_seconds_median=round(statistics.median(ttft), 4),
            decode_tps_median=round(statistics.median(decode_rates), 2),
            peak_vram_mb=peak_vram,
            status="SUCCESS",
        )
        logger.info(
            f"  MEDIAN: ttft {row['ttft_seconds_median']}s | "
            f"{row['decode_tps_median']} t/s | peak VRAM {peak_vram} MB"
        )

    except ProviderLoadError as exc:
        row["error"] = f"ProviderLoadError: {exc}"
        logger.error(f"  could not load {model_path.name}: {exc}")
    except Exception as exc:  # noqa: BLE001 - one bad model must not end the sweep
        row["error"] = f"{type(exc).__name__}: {exc}"
        logger.error(f"  benchmark failed for {model_path.name}: {exc}")
    finally:
        if provider is not None:
            try:
                provider.unload()
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"  unload failed for {model_path.name}: {exc}")

    return row


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sweep every GGUF in models/ and compare TTFT, decode rate and peak VRAM."
        )
    )
    parser.add_argument("--n-ctx", type=int, default=4096)
    parser.add_argument(
        "--n-gpu-layers",
        type=int,
        default=-1,
        help="-1 offloads as many layers as fit (llama.cpp convention)",
    )
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument(
        "--model",
        action="append",
        default=None,
        help="Benchmark only this filename; repeatable",
    )
    args = parser.parse_args()

    if not MODELS_DIR.is_dir():
        logger.error(f"No models directory at {MODELS_DIR}")
        return 1

    models = sorted(MODELS_DIR.glob("*.gguf"))
    if args.model:
        wanted = set(args.model)
        models = [m for m in models if m.name in wanted]
    if not models:
        logger.error(f"No GGUF models to benchmark in {MODELS_DIR}")
        return 1

    report_header(f"PERIDOT | MULTI-MODEL MATRIX ({len(models)} model(s))")

    result = BenchmarkResult(
        name="model_matrix",
        description="Per-model TTFT, decode rate and peak VRAM across every local GGUF",
    )
    rows = []
    for model_path in models:
        row = benchmark_model(
            model_path, args.n_ctx, args.n_gpu_layers, args.max_tokens, args.runs
        )
        rows.append(row)
        if row["status"] == "SUCCESS":
            # The headline measurement is decode rate, so that is what feeds the
            # statistics block; everything else rides along in metadata.
            result.add_measurement(row["decode_tps_median"])

    result.add_metadata("models", rows)
    result.add_metadata("succeeded", sum(1 for r in rows if r["status"] == "SUCCESS"))
    result.add_metadata("failed", sum(1 for r in rows if r["status"] != "SUCCESS"))

    filepath = result.save(RESULTS_DIR)

    logger.info("")
    logger.info(f"{'MODEL':<45} {'TTFT':>8} {'T/S':>8} {'PEAK VRAM':>10}")
    for row in rows:
        if row["status"] == "SUCCESS":
            logger.info(
                f"{row['model']:<45} {row['ttft_seconds_median']:>8.3f} "
                f"{row['decode_tps_median']:>8.2f} {row['peak_vram_mb']:>9} MB"
            )
        else:
            logger.info(f"{row['model']:<45} {'FAILED':>28}")

    report_footer(filepath)
    return 0


if __name__ == "__main__":
    sys.exit(main())
