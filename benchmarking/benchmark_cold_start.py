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

# Root path injection to grab the v1.3 Config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import API_KEY, SERVER_PORT

# Configuration
API_URL = f"http://127.0.0.1:{SERVER_PORT}"
RESULTS_DIR = Path(__file__).parent.parent / "results"
SERVER_PATH = Path(__file__).parent.parent / "server.py"


def kill_existing_peridot():
    """Kill any existing Peridot processes."""
    import psutil
    
    killed_count = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any(name in str(cmd).lower() for cmd in cmdline for name in ['server.py', 'launcher.py', 'main.py']):
                logger.info(f"Killing existing process: PID {proc.info['pid']}")
                proc.kill()
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if killed_count > 0:
        logger.info(f"Killed {killed_count} existing Peridot process(es)")
        time.sleep(2)  # Wait for processes to fully terminate
    
    return killed_count


def wait_for_health(timeout=120): # Increased timeout for 8B model loading
    """Wait for Peridot to respond to health check."""
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            response = requests.get(f"{API_URL}/health", timeout=1)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(1)
    
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
    
    # Start Peridot Neural Engine and measure startup time
    logger.info(f"  Starting Neural Engine from: {SERVER_PATH}")
    
    if not SERVER_PATH.exists():
        logger.error(f"  server.py not found at {SERVER_PATH}")
        return None
    
    start_time = time.time()
    
    # Start the process
    proc = subprocess.Popen(
        [sys.executable, str(SERVER_PATH)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=SERVER_PATH.parent
    )
    
    logger.info(f"  Process started (PID: {proc.pid})")
    logger.info("  Waiting for VRAM allocation and health endpoint...")
    
    # Wait for health check to succeed
    if not wait_for_health(timeout=120):
        logger.error("  Peridot did not become ready within 120 seconds")
        proc.kill()
        return None
    
    startup_time = time.time() - start_time
    
    logger.info(f"  Neural Engine is ready! Startup time: {format_duration(startup_time)}")
    
    # Test that it actually works (make a query)
    logger.info("  Testing v1.3 inference...")
    test_start = time.time()
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        
        response = requests.post(
            f"{API_URL}/ask",
            json={"command": "Acknowledge this cold start test."},
            headers=headers,
            timeout=120
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
    logger.info("PERIDOT v1.3 COLD START BENCHMARK")
    logger.info("="*60 + "\n")
    
    logger.warning("⚠️  This benchmark will stop and restart the Neural Engine!")
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
        description="Cold start time from stopped to ready (Neural Engine Only)"
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
            
            # Kill the engine to prepare for the next cold start loop
            kill_existing_peridot()
            
            # Small delay between runs
            if i < runs - 1:
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
    
    logger.info(f"Startup time (to VRAM Allocation & Health Check):")
    logger.info(f"  Mean: {stats['mean']:.2f}s")
    logger.info(f"  Median: {stats['median']:.2f}s")
    logger.info(f"  Std Dev: {stats['stdev']:.2f}s")
    logger.info(f"  Range: {stats['min']:.2f} - {stats['max']:.2f}s")
    logger.info("")
    
    if first_query_times:
        logger.info(f"First query time (Inference):")
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

if __name__ == "__main__":
    main()