# Engineered by uncoalesced
"""
Benchmark: Cold Start Time
Measures how long it takes for Peridot to go from stopped to ready for queries.
"""

import sys
import time
import subprocess
import statistics
import os
from pathlib import Path

# Add utils and current dir to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
sys.path.insert(0, str(Path(__file__).parent))

from benchmark_utils import (
    BenchmarkResult, get_system_info, format_duration, logger
)
import api_client

# Root path injection to grab the v1.3 Config (if applicable)
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from config import SERVER_PORT
except ImportError:
    SERVER_PORT = 5000

# Saving strictly inside the benchmarking directory
RESULTS_DIR = Path(__file__).parent / "results"
SERVER_PATH = Path(__file__).parent.parent / "server.py"

def kill_existing_peridot():
    """Kill any existing Peridot processes safely."""
    import psutil
    
    killed_count = 0
    # Optimize by filtering for python processes early if possible
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if cmdline and any(name in str(cmd).lower() for cmd in cmdline for name in ['server.py', 'launcher.py', 'main.py']):
                logger.info(f"Killing existing process: PID {proc.info['pid']}")
                proc.kill()
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    if killed_count > 0:
        logger.info(f"Killed {killed_count} existing Peridot process(es)")
        # 4 second sleep to allow Windows and the RTX 5050 to fully dump VRAM
        time.sleep(4)
    
    return killed_count

def wait_for_health(timeout=200):
    """Wait for Peridot to respond to health check via api_client."""
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            response = api_client.get_health()
            if response.get("status") == "healthy" or response:
                return True
        except RuntimeError:
            pass
        # 2 second sleep to prevent spamming the Flask initialization
        time.sleep(2)
    
    return False

def measure_cold_start():
    """Measure cold start time."""
    logger.info("Measuring cold start time...")
    
    logger.info("  Ensuring Peridot is stopped...")
    kill_existing_peridot()
    
    try:
        api_client.get_health()
        logger.error("  Peridot is still responding! Cannot accurately measure cold start.")
        return None
    except RuntimeError:
        logger.info("  Confirmed: Peridot is offline")
    
    logger.info(f"  Starting Neural Engine from: {SERVER_PATH}")
    if not SERVER_PATH.exists():
        logger.error(f"  server.py not found at {SERVER_PATH}")
        return None
    
    start_time = time.time()
    
    # Inherit current environment and forcefully inject the client's API Key
    env = os.environ.copy()
    if api_client.API_KEY:
        env["API_KEY"] = api_client.API_KEY
        # Failsafe injection just in case the server prefers the old variable name
        env["PERIDOT_AUTH_TOKEN"] = api_client.API_KEY 
        
    # The subprocess will print directly to the terminal to prevent silent deadlocks.
    proc = subprocess.Popen(
        [sys.executable, str(SERVER_PATH)],
        cwd=SERVER_PATH.parent,
        env=env
    )
    
    logger.info(f"  Process started (PID: {proc.pid})")
    logger.info("  Waiting for VRAM allocation and API readiness...")
    
    if not wait_for_health(timeout=200):
        logger.error("  Peridot did not become ready within 200 seconds. Killing process.")
        proc.kill()
        return None
    
    startup_time = time.time() - start_time
    logger.info(f"  Neural Engine is ready! Startup time: {format_duration(startup_time)}")
    
    logger.info("  Testing Layer 1 Inference...")
    test_start = time.time()
    
    try:
        response = api_client.post_chat(
            message="Acknowledge this cold start test.",
            max_tokens=20,
            timeout=120
        )
        
        first_query_time = time.time() - test_start
        logger.info(f"  First query completed in {format_duration(first_query_time)}")
            
    except RuntimeError as e:
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
    
    logger.warning("[WARNING] This benchmark will stop and restart the Neural Engine!")
    logger.warning("[WARNING] Press Ctrl+C within 5 seconds to cancel...\n")
    
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        logger.info("\nBenchmark cancelled by user")
        sys.exit(0)
    
    system_info = get_system_info()
    logger.info("System Information:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")
    logger.info("")
    
    result = BenchmarkResult(
        name="cold_start",
        description="Cold start time from stopped to ready (Neural Engine Only)"
    )
    
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
                
                result.add_measurement(measurement['startup_time_s'])
                logger.info(f"Cold start {i+1} complete\n")
            else:
                logger.error(f"Cold start {i+1} failed\n")
            
            kill_existing_peridot()
            
            if i < runs - 1:
                logger.info("Waiting 3 seconds before next run...")
                time.sleep(3)
                
        except Exception as e:
            logger.error(f"Cold start {i+1} critically failed: {e}\n")
            kill_existing_peridot()
            continue
    
    if startup_times:
        result.add_metadata("startup_times_s", startup_times)
        result.add_metadata("first_query_times_s", first_query_times)
        result.add_metadata("total_times_s", total_times)
        
        result.add_metadata("avg_startup_time_s", statistics.mean(startup_times))
        if first_query_times:
            result.add_metadata("avg_first_query_time_s", statistics.mean(first_query_times))
        if total_times:
            result.add_metadata("avg_total_time_s", statistics.mean(total_times))
    
    result.save(RESULTS_DIR)
    
    stats = result.get_statistics()
    if not stats:
        logger.error("No valid statistics generated. All runs failed.")
        return

    logger.info("\n" + "="*60)
    logger.info("COLD START SUMMARY")
    logger.info("="*60 + "\n")
    
    logger.info("Startup time (to VRAM Allocation & Health Check):")
    logger.info(f"  Mean: {stats.get('mean', 0):.2f}s")
    logger.info(f"  Median: {stats.get('median', 0):.2f}s")
    logger.info(f"  Std Dev: {stats.get('stdev', 0):.2f}s")
    logger.info(f"  Range: {stats.get('min', 0):.2f} - {stats.get('max', 0):.2f}s")
    logger.info("")
    
    if first_query_times:
        logger.info("First query time (Inference):")
        logger.info(f"  Mean: {statistics.mean(first_query_times):.2f}s")
        logger.info(f"  Median: {statistics.median(first_query_times):.2f}s")
        logger.info("")
    
    if total_times:
        logger.info("Total time to first response:")
        logger.info(f"  Mean: {statistics.mean(total_times):.2f}s")
        logger.info(f"  Median: {statistics.median(total_times):.2f}s")
        logger.info("")
    
    logger.info("="*60)
    logger.info("Benchmark complete! Results saved to:")
    logger.info(f"  {RESULTS_DIR.absolute()}")
    logger.info("="*60 + "\n")

if __name__ == "__main__":
    main()