"""
Master Benchmark Runner
Runs all benchmarks in sequence and generates comprehensive report.
# Engineered by uncoalesced
"""

import sys
import subprocess
import time
import json
from pathlib import Path
from datetime import datetime

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from benchmark_utils import logger, get_system_info


SCRIPTS_DIR = Path(__file__).parent
RESULTS_DIR = Path(__file__).parent.parent / "results"


# Define all available benchmarks
BENCHMARKS = [
    {
        "name": "inference",
        "script": "benchmark_inference.py",
        "description": "Inference speed across workload sizes",
        "priority": "critical",
        "estimated_time": "2-3 minutes"
    },
    {
        "name": "vram_handoff",
        "script": "benchmark_vram_handoff.py",
        "description": "VRAM handoff latency (UNIQUE FEATURE)",
        "priority": "critical",
        "estimated_time": "3-4 minutes"
    },
    {
        "name": "cold_start",
        "script": "benchmark_cold_start.py",
        "description": "Cold start time from stopped to ready",
        "priority": "critical",
        "estimated_time": "5-7 minutes",
        "warning": "Will stop and restart Peridot"
    },
    {
        "name": "memory_stability",
        "script": "benchmark_memory_stability.py",
        "description": "Memory usage over consecutive queries",
        "priority": "important",
        "estimated_time": "2-3 minutes"
    },
    {
        "name": "gpu_utilization",
        "script": "benchmark_gpu_utilization.py",
        "description": "GPU usage during inference",
        "priority": "important",
        "estimated_time": "1-2 minutes"
    },
    {
        "name": "context_scaling",
        "script": "benchmark_context_scaling.py",
        "description": "Performance vs context window size",
        "priority": "important",
        "estimated_time": "3-5 minutes"
    },
    {
        "name": "sustained_load",
        "script": "benchmark_sustained_load.py",
        "description": "Extended continuous use test",
        "priority": "optional",
        "estimated_time": "10+ minutes",
        "warning": "Long-running benchmark"
    }
]


def run_benchmark(benchmark: dict) -> bool:
    """Run a single benchmark script."""
    script_path = SCRIPTS_DIR / benchmark["script"]
    
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return False
    
    logger.info("\n" + "="*60)
    logger.info(f"RUNNING: {benchmark['name']}")
    logger.info(f"Description: {benchmark['description']}")
    logger.info(f"Estimated time: {benchmark['estimated_time']}")
    if "warning" in benchmark:
        logger.warning(f"⚠️  {benchmark['warning']}")
    logger.info("="*60 + "\n")
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=script_path.parent,
            timeout=900  # 15 minute timeout
        )
        
        if result.returncode == 0:
            logger.info(f"\n✅ {benchmark['name']} completed successfully")
            return True
        else:
            logger.error(f"\n❌ {benchmark['name']} failed with code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"\n❌ {benchmark['name']} timed out after 15 minutes")
        return False
    except Exception as e:
        logger.error(f"\n❌ {benchmark['name']} failed: {e}")
        return False


def main():
    """Run benchmark suite."""
    logger.info("\n" + "="*80)
    logger.info("PERIDOT COMPREHENSIVE BENCHMARK SUITE")
    logger.info("="*80 + "\n")
    
    # Show system info
    system_info = get_system_info()
    logger.info("System Information:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")
    logger.info("")
    
    # Show available benchmarks
    logger.info("Available benchmarks:\n")
    
    critical = [b for b in BENCHMARKS if b['priority'] == 'critical']
    important = [b for b in BENCHMARKS if b['priority'] == 'important']
    optional = [b for b in BENCHMARKS if b['priority'] == 'optional']
    
    logger.info("CRITICAL (Always run):")
    for b in critical:
        logger.info(f"  - {b['name']}: {b['description']} ({b['estimated_time']})")
    
    logger.info("\nIMPORTANT (Recommended):")
    for b in important:
        logger.info(f"  - {b['name']}: {b['description']} ({b['estimated_time']})")
    
    logger.info("\nOPTIONAL (Extended tests):")
    for b in optional:
        logger.info(f"  - {b['name']}: {b['description']} ({b['estimated_time']})")
    
    logger.info("")
    
    # Ask what to run
    print("\nSelect benchmark suite to run:")
    print("  1. Critical only (fastest, ~10-15 minutes)")
    print("  2. Critical + Important (recommended, ~15-25 minutes)")
    print("  3. All benchmarks (comprehensive, ~25-40 minutes)")
    print("  4. Custom selection")
    print("  q. Quit")
    
    choice = input("\nYour choice [1-4, q]: ").strip().lower()
    
    if choice == 'q':
        logger.info("Exiting...")
        return
    
    # Determine which benchmarks to run
    to_run = []
    
    if choice == '1':
        to_run = critical
    elif choice == '2':
        to_run = critical + important
    elif choice == '3':
        to_run = BENCHMARKS
    elif choice == '4':
        logger.info("\nSelect benchmarks to run (space-separated numbers):")
        for i, b in enumerate(BENCHMARKS, 1):
            logger.info(f"  {i}. {b['name']}")
        
        selection = input("\nBenchmarks to run (e.g., '1 2 5'): ").strip()
        try:
            indices = [int(x) - 1 for x in selection.split()]
            to_run = [BENCHMARKS[i] for i in indices if 0 <= i < len(BENCHMARKS)]
        except:
            logger.error("Invalid selection!")
            return
    else:
        logger.error("Invalid choice!")
        return
    
    if not to_run:
        logger.error("No benchmarks selected!")
        return
    
    # Estimate total time
    logger.info(f"\n{len(to_run)} benchmarks selected")
    logger.info("\nBenchmarks to run:")
    for b in to_run:
        logger.info(f"  - {b['name']} ({b['estimated_time']})")
    
    logger.info("\n⚠️  This will take approximately 15-40 minutes depending on selection")
    confirm = input("\nContinue? [y/N]: ").strip().lower()
    
    if confirm != 'y':
        logger.info("Cancelled by user")
        return
    
    # Create results directory
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Run benchmarks
    start_time = time.time()
    results = []
    
    for i, benchmark in enumerate(to_run, 1):
        logger.info(f"\n\n{'='*80}")
        logger.info(f"BENCHMARK {i}/{len(to_run)}")
        logger.info(f"{'='*80}")
        
        success = run_benchmark(benchmark)
        results.append({
            "name": benchmark['name'],
            "success": success,
            "timestamp": datetime.now().isoformat()
        })
        
        # Small delay between benchmarks
        if i < len(to_run):
            logger.info("\nWaiting 3 seconds before next benchmark...")
            time.sleep(3)
    
    total_time = time.time() - start_time
    
    # Print final summary
    logger.info("\n\n" + "="*80)
    logger.info("BENCHMARK SUITE COMPLETE")
    logger.info("="*80 + "\n")
    
    logger.info(f"Total time: {total_time/60:.1f} minutes")
    logger.info(f"Results saved to: {RESULTS_DIR.absolute()}\n")
    
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    
    logger.info(f"Summary:")
    logger.info(f"  Successful: {successful}/{len(results)}")
    logger.info(f"  Failed: {failed}/{len(results)}")
    logger.info("")
    
    for result in results:
        status = "✅" if result['success'] else "❌"
        logger.info(f"  {status} {result['name']}")
    
    logger.info("\n" + "="*80)
    logger.info("Next steps:")
    logger.info("  1. Review results in: " + str(RESULTS_DIR))
    logger.info("  2. Generate report: python generate_report.py")
    logger.info("="*80 + "\n")


if __name__ == "__main__":
    main()
