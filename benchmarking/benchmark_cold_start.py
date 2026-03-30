"""
Benchmark 3: Cold Start Time
Measures how long it takes for Peridot to go from stopped to ready for queries.
# Engineered by uncoalesced
"""

import sys
import time
import subprocess
import requests
import signal
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from benchmark_utils import (
    BenchmarkResult, get_system_info, format_duration, logger
)


# Configuration
API_URL = "http://localhost:5000"
RESULTS_DIR = Path(__file__).parent.parent / "results"
LAUNCHER_PATH = Path(__file__).parent.parent.parent.parent / "launcher.py"


def kill_existing_peridot():
    """Kill any existing Peridot processes."""
    import psutil
    
    killed_count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any('launcher.py' in str(cmd) or 'peridot' in str(cmd).lower() for cmd in cmdline):
                logger.info(f"Killing existing process: PID {proc.info['pid']}")
                proc.kill()
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if killed_count > 0:
        logger.info(f"Killed {killed_count} existing Peridot process(es)")
        time.sleep(2)  # Wait for processes to fully terminate
    
    return killed_count


def wait_for_health(timeout=60):
    """Wait for Peridot to respond to health check."""
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            response = requests.get(f"{API_URL}/health", timeout=1)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(0.1)
    
    return False


def measure_cold_start():
    """Measure cold start time."""
    logger.info("Measuring cold start time...")
    
    # Ensure Peridot is stopped
    logger.info("  Ensuring Peridot is stopped...")
    kill_existing_peridot()
    
    # Verify it's really stopped
    try:
        requests.get(f"{API_URL}/health", timeout=1)
        logger.error("  Peridot is still running! Cannot measure cold start.")
        return None
    except:
        logger.info("  Confirmed: Peridot is stopped")
    
    # Start Peridot and measure startup time
    logger.info(f"  Starting Peridot from: {LAUNCHER_PATH}")
    
    if not LAUNCHER_PATH.exists():
        logger.error(f"  launcher.py not found at {LAUNCHER_PATH}")
        logger.error("  Please run this benchmark from the benchmarking directory")
        return None
    
    start_time = time.time()
    
    # Start the process
    proc = subprocess.Popen(
        [sys.executable, str(LAUNCHER_PATH)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=LAUNCHER_PATH.parent
    )
    
    logger.info(f"  Process started (PID: {proc.pid})")
    logger.info("  Waiting for health endpoint...")
    
    # Wait for health check to succeed
    if not wait_for_health(timeout=60):
        logger.error("  Peridot did not become ready within 60 seconds")
        proc.kill()
        return None
    
    startup_time = time.time() - start_time
    
    logger.info(f"  Peridot is ready! Startup time: {format_duration(startup_time)}")
    
    # Test that it actually works (make a query)
    logger.info("  Testing inference...")
    test_start = time.time()
    
    try:
        import os
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get("PERIDOT_AUTH_TOKEN")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        response = requests.post(
            f"{API_URL}/chat",
            json={"message": "Hello", "max_tokens": 10},
            headers=headers,
            timeout=30
        )
        
        first_query_time = time.time() - test_start
        
        if response.status_code == 200:
            logger.info(f"  First query completed in {format_duration(first_query_time)}")
        else:
            logger.warning(f"  First query returned status {response.status_code}")
            
    except Exception as e:
        logger.error(f"  First query failed: {e}")
        first_query_time = None
    
    return {
        "startup_time_s": startup_time,
        "first_query_time_s": first_query_time,
        "total_time_to_first_response_s": startup_time + (first_query_time or 0),
        "process_pid": proc.pid
    }


def main():
    """Run cold start benchmark."""
    logger.info("\n" + "="*60)
    logger.info("PERIDOT COLD START BENCHMARK")
    logger.info("="*60 + "\n")
    
    logger.warning("⚠️  This benchmark will stop and restart Peridot!")
    logger.warning("⚠️  Press Ctrl+C within 5 seconds to cancel...\n")
    
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        logger.info("\nBenchmark cancelled by user")
        sys.exit(0)
    
    # Gather system info
    system_info = get_system_info()
    logger.info("System Information:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")
    logger.info("")
    
    # Create result container
    result = BenchmarkResult(
        name="cold_start",
        description="Cold start time from stopped to ready"
    )
    
    # Run multiple cold start measurements
    runs = 5
    logger.info(f"Running {runs} cold start measurements...\n")
    
    startup_times = []
    first_query_times = []
    total_times = []
    
    for i in range(runs):
        logger.info(f"{'='*60}")
        logger.info(f"Cold Start {i+1}/{runs}")
        logger.info(f"{'='*60}")
        
        try:
            measurement = measure_cold_start()
            
            if measurement:
                startup_times.append(measurement['startup_time_s'])
                if measurement['first_query_time_s']:
                    first_query_times.append(measurement['first_query_time_s'])
                total_times.append(measurement['total_time_to_first_response_s'])
                
                # Add to result (use startup time as primary metric)
                result.add_measurement(measurement['startup_time_s'])
                
                logger.info(f"Cold start {i+1} complete\n")
            else:
                logger.error(f"Cold start {i+1} failed\n")
            
            # Small delay between runs
            if i < runs - 1:  # Don't wait after last run
                logger.info("Waiting 3 seconds before next run...")
                time.sleep(3)
                
        except Exception as e:
            logger.error(f"Cold start {i+1} failed: {e}\n")
            continue
    
    # Add metadata
    import statistics
    if startup_times:
        result.add_metadata("startup_times_s", startup_times)
        result.add_metadata("first_query_times_s", first_query_times)
        result.add_metadata("total_times_s", total_times)
        
        result.add_metadata("avg_startup_time_s", statistics.mean(startup_times))
        if first_query_times:
            result.add_metadata("avg_first_query_time_s", statistics.mean(first_query_times))
        if total_times:
            result.add_metadata("avg_total_time_s", statistics.mean(total_times))
    
    # Save result
    result.save(RESULTS_DIR)
    
    # Print summary
    stats = result.get_statistics()
    logger.info("\n" + "="*60)
    logger.info("COLD START SUMMARY")
    logger.info("="*60 + "\n")
    
    logger.info(f"Startup time (to health check):")
    logger.info(f"  Mean: {stats['mean']:.2f}s")
    logger.info(f"  Median: {stats['median']:.2f}s")
    logger.info(f"  Std Dev: {stats['stdev']:.2f}s")
    logger.info(f"  Range: {stats['min']:.2f} - {stats['max']:.2f}s")
    logger.info("")
    
    if first_query_times:
        logger.info(f"First query time:")
        logger.info(f"  Mean: {statistics.mean(first_query_times):.2f}s")
        logger.info(f"  Median: {statistics.median(first_query_times):.2f}s")
        logger.info("")
    
    if total_times:
        logger.info(f"Total time to first response:")
        logger.info(f"  Mean: {statistics.mean(total_times):.2f}s")
        logger.info(f"  Median: {statistics.median(total_times):.2f}s")
        logger.info("")
    
    logger.info("="*60)
    logger.info("Benchmark complete! Results saved to:")
    logger.info(f"  {RESULTS_DIR.absolute()}")
    logger.info("="*60 + "\n")
    
    logger.info("⚠️  Peridot is still running. Stop it manually if needed.")


if __name__ == "__main__":
    main()
