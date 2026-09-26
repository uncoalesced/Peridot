# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Master Benchmark Runner (Unified + Auto Report)
Runs all benchmarks, ensures correct execution order, and generates final report.
"""

import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.absolute()
PERIDOT_ROOT = BASE_DIR.parent
# RESULTS_DIR is shared with every benchmark via benchmark_utils; not recomputed here.
from benchmarking.utils.benchmark_utils import RESULTS_DIR, logger, get_system_info

# Ordered benchmarks. Each entry is a module under the `benchmarking` package.
#
# Ordering matters: benchmark_cold_start and benchmark_context_scaling both own
# the server lifecycle -- they kill any running Peridot and start their own --
# and cold_start does not restart it when it finishes. They used to sit 3rd and
# 6th, so every benchmark after cold_start hit a dead server and exited 1.
# Both now run last, after everything that needs a pre-existing live server.
BENCHMARKS = [
    ("inference", "benchmark_inference"),
    ("vram_handoff", "benchmark_vram_handoff"),
    ("memory_stability", "benchmark_memory_stability"),
    ("gpu_utilization", "benchmark_gpu_utilization"),
    ("sustained_load", "benchmark_sustained_load"),
    ("context_scaling", "benchmark_context_scaling"),
    ("cold_start", "benchmark_cold_start"),
    # Owns the GPU exclusively (loads each model in turn), so it runs last.
    ("model_matrix", "benchmark_model_matrix"),
]


def run_script(module_name: str) -> bool:
    """Run one benchmark as `python -m benchmarking.<module>` from the repo root.

    Invoking by file path put benchmarking/ on sys.path instead of the project
    root, so the package-relative imports these modules now use would not
    resolve. -m from PERIDOT_ROOT is the only spelling that satisfies both the
    `benchmarking.utils...` imports and the root-level `config` import.
    """
    if not (BASE_DIR / f"{module_name}.py").exists():
        logger.error(f"[MISSING] {module_name}.py")
        return False

    logger.info("\n" + "=" * 70)
    logger.info(f"RUNNING: {module_name}")
    logger.info("=" * 70 + "\n")

    try:
        result = subprocess.run(
            [sys.executable, "-m", f"benchmarking.{module_name}"],
            cwd=str(PERIDOT_ROOT),
            timeout=1800,  # 30 min max per benchmark
        )

        if result.returncode == 0:
            logger.info(f"[SUCCESS] {module_name}")
            return True
        else:
            logger.error(f"[FAILED] {module_name} (code {result.returncode})")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"[TIMEOUT] {module_name}")
        return False
    except Exception as e:
        logger.error(f"[ERROR] {module_name}: {e}")
        return False


def generate_report():
    if not (BASE_DIR / "generate_report.py").exists():
        logger.warning("Report generator not found, skipping...")
        return

    logger.info("\n" + "=" * 70)
    logger.info("GENERATING UNIFIED REPORT")
    logger.info("=" * 70 + "\n")

    try:
        subprocess.run(
            [sys.executable, "-m", "benchmarking.generate_report"],
            cwd=str(PERIDOT_ROOT),
            timeout=120,
        )
        logger.info("[SUCCESS] Report generated")
    except Exception as e:
        logger.error(f"[ERROR] Report generation failed: {e}")


def main():
    logger.info("\n" + "=" * 80)
    logger.info("PERIDOT FULL BENCHMARK SUITE (AUTO)")
    logger.info("=" * 80 + "\n")

    # System Info
    sys_info = get_system_info()
    logger.info("System Info:")
    for k, v in sys_info.items():
        logger.info(f"  {k}: {v}")
    logger.info("")

    # Ensure results directory
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Running {len(BENCHMARKS)} benchmarks...\n")

    start_time = time.time()
    results = []

    for i, (name, script) in enumerate(BENCHMARKS, 1):
        logger.info(f"\n[{i}/{len(BENCHMARKS)}] {name.upper()}")

        success = run_script(script)

        results.append(
            {"name": name, "success": success, "time": datetime.now().isoformat()}
        )

        # Small cooldown (important for GPU stabilization)
        if i < len(BENCHMARKS):
            time.sleep(3)

    total_time = time.time() - start_time

    # Generate report AFTER all benchmarks
    generate_report()

    # Final Summary
    logger.info("\n" + "=" * 80)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 80 + "\n")

    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count

    logger.info(f"Total Time: {total_time/60:.2f} minutes")
    logger.info(f"Success: {success_count}/{len(results)}")
    logger.info(f"Failed: {fail_count}/{len(results)}\n")

    for r in results:
        status = "[OK]" if r["success"] else "[FAIL]"
        logger.info(f"{status} {r['name']}")

    logger.info("\nResults Directory:")
    logger.info(f"  {RESULTS_DIR}")
    logger.info("\nReports:")
    logger.info(f"  {BASE_DIR / 'reports'}")

    logger.info("\nDone.\n")


if __name__ == "__main__":
    main()
