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

# Path Bootstrapping
BASE_DIR = Path(__file__).parent.absolute()
RESULTS_DIR = BASE_DIR / "results"
REPORT_SCRIPT = BASE_DIR / "generate_report.py"

# Add utils
sys.path.insert(0, str(BASE_DIR / "utils"))
try:
    from benchmark_utils import logger, get_system_info
except ImportError:
    print("[ERROR] benchmark_utils.py not found in /utils/")
    sys.exit(1)

# Ordered benchmarks (dependency-safe order)
BENCHMARKS = [
    ("inference", "benchmark_inference.py"),
    ("vram_handoff", "benchmark_vram_handoff.py"),
    ("cold_start", "benchmark_cold_start.py"),
    ("memory_stability", "benchmark_memory_stability.py"),
    ("gpu_utilization", "benchmark_gpu_utilization.py"),
    ("context_scaling", "benchmark_context_scaling.py"),
    ("sustained_load", "benchmark_sustained_load.py"),
]


def run_script(script_name: str) -> bool:
    script_path = BASE_DIR / script_name

    if not script_path.exists():
        logger.error(f"[MISSING] {script_name}")
        return False

    logger.info("\n" + "=" * 70)
    logger.info(f"RUNNING: {script_name}")
    logger.info("=" * 70 + "\n")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(BASE_DIR),
            timeout=1800  # 30 min max per benchmark
        )

        if result.returncode == 0:
            logger.info(f"[SUCCESS] {script_name}")
            return True
        else:
            logger.error(f"[FAILED] {script_name} (code {result.returncode})")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"[TIMEOUT] {script_name}")
        return False
    except Exception as e:
        logger.error(f"[ERROR] {script_name}: {e}")
        return False


def generate_report():
    if not REPORT_SCRIPT.exists():
        logger.warning("Report generator not found, skipping...")
        return

    logger.info("\n" + "=" * 70)
    logger.info("GENERATING UNIFIED REPORT")
    logger.info("=" * 70 + "\n")

    try:
        subprocess.run(
            [sys.executable, str(REPORT_SCRIPT)],
            cwd=str(BASE_DIR),
            timeout=120
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

        results.append({
            "name": name,
            "success": success,
            "time": datetime.now().isoformat()
        })

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