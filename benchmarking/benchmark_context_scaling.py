# Engineered by uncoalesced
"""
Benchmark: Context Window Scaling
Tests how performance scales with different context lengths.
"""

import sys
import os
import time
import subprocess
import statistics
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
sys.path.insert(0, str(Path(__file__).parent))

from benchmark_utils import (
    BenchmarkResult, get_system_info, format_duration, format_throughput, logger
)
import api_client

RESULTS_DIR = Path(__file__).parent / "results"
SERVER_PATH = Path(__file__).parent.parent / "server.py"

def kill_existing_peridot():
    """Kill any existing Peridot processes safely."""
    import psutil
    
    killed_count = 0
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
        time.sleep(2)
    
    return False

def generate_context(target_tokens: int) -> str:
    """Generate a repetitive string to simulate a large context window."""
    base_text = """Machine learning is a subset of artificial intelligence that focuses on 
    developing algorithms and statistical models that enable computer systems to improve 
    their performance on a specific task through experience. Deep learning, a specialized 
    branch of machine learning, uses neural networks with multiple layers to automatically 
    learn hierarchical representations of data. """
    
    tokens_per_chunk = 78
    repetitions = max(1, target_tokens // tokens_per_chunk)
    context = (base_text * repetitions).strip()
    
    return context

def count_tokens_rough(text: str) -> int:
    """Rough approximation of token count based on word count."""
    words = text.split()
    return int(len(words) * 1.3)

def measure_with_context(context_tokens: int, runs: int = 3) -> dict:
    """Measure inference performance given a specific context size."""
    context = generate_context(context_tokens)
    actual_context_tokens = count_tokens_rough(context)

    question = "\n\nBased on the above, what is machine learning?"
    full_prompt = context + question

    logger.info(f"\nTesting with ~{context_tokens} token context")
    logger.info(f"Actual context tokens: {actual_context_tokens}")
    logger.info(f"Total prompt tokens: {count_tokens_rough(full_prompt)}")

    throughputs = []
    response_times = []

    # Warmup
    try:
        api_client.post_chat(message=full_prompt, max_tokens=10, timeout=120)
        time.sleep(1)
    except RuntimeError:
        pass

    # Run measurements
    for i in range(runs):
        try:
            start = time.time()
            response = api_client.post_chat(message=full_prompt, max_tokens=50, timeout=300)
            elapsed = time.time() - start

            response_text = response.get("response", "")
            response_tokens = count_tokens_rough(response_text)

            throughput = response_tokens / elapsed if elapsed > 0 else 0

            throughputs.append(throughput)
            response_times.append(elapsed)

            logger.info(f"  Run {i+1}: {format_throughput(response_tokens, elapsed)}")

        except Exception as e:
            logger.error(f"  Run {i+1} failed: {e}")
            continue

    if throughputs:
        return {
            "context_tokens": actual_context_tokens,
            "avg_throughput": statistics.mean(throughputs),
            "median_throughput": statistics.median(throughputs),
            "avg_response_time": statistics.mean(response_times),
            "throughputs": throughputs,
            "successful_runs": len(throughputs)
        }
    else:
        return None

def main():
    logger.info("\n" + "="*60)
    logger.info("PERIDOT CONTEXT WINDOW SCALING BENCHMARK")
    logger.info("="*60 + "\n")

    system_info = get_system_info()
    logger.info("System Information:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")
    logger.info("")

    logger.info("Autonomously booting Peridot Kernel for testing...")
    kill_existing_peridot()
    
    # Inherit environment and inject API key to prevent 403 Forbidden
    env = os.environ.copy()
    if api_client.API_KEY:
        env["API_KEY"] = api_client.API_KEY
        env["PERIDOT_AUTH_TOKEN"] = api_client.API_KEY
        
    proc = subprocess.Popen(
        [sys.executable, str(SERVER_PATH)],
        cwd=SERVER_PATH.parent,
        env=env
    )
    
    logger.info("Waiting for VRAM allocation...")
    if not wait_for_health(timeout=200):
        logger.error("Kernel offline: Failed to establish health check within 200 seconds.")
        proc.kill()
        sys.exit(1)
        
    logger.info("Kernel Online. Commencing Context Scaling Tests.")

    try:
        result = BenchmarkResult(
            name="context_scaling",
            description="Performance vs context window size"
        )

        context_sizes = [512, 1024, 2048, 4096]

        logger.info(f"Testing context sizes: {context_sizes}")
        logger.info("This may take several minutes...\n")

        results_by_size = []

        for size in context_sizes:
            logger.info("="*60)
            logger.info(f"Context Size: {size} tokens")
            logger.info("="*60)

            measurement = measure_with_context(size, runs=3)

            if measurement:
                results_by_size.append(measurement)
                logger.info(f"Average throughput: {measurement['avg_throughput']:.2f} t/s")
                logger.info(f"Average total time: {format_duration(measurement['avg_response_time'])}")
                result.add_measurement(measurement['median_throughput'])
            else:
                logger.error(f"Failed to measure context size {size}")

            logger.info("")
            time.sleep(2)

        result.add_metadata("context_sizes", context_sizes)
        result.add_metadata("results_by_size", results_by_size)

        result.save(RESULTS_DIR)

        logger.info("\n" + "="*60)
        logger.info("CONTEXT SCALING SUMMARY")
        logger.info("="*60 + "\n")

        logger.info(f"{'Context Size':<15} {'Avg Throughput':<20} {'Total Time':<15}")
        logger.info("-" * 50)

        for res in results_by_size:
            logger.info(
                f"{res['context_tokens']:<15} "
                f"{res['avg_throughput']:<20.2f} t/s "
                f"{format_duration(res['avg_response_time']):<15}"
            )

        logger.info("")

        if len(results_by_size) >= 2:
            baseline = results_by_size[0]['avg_throughput']
            largest = results_by_size[-1]['avg_throughput']
            
            if baseline > 0:
                degradation_pct = ((baseline - largest) / baseline) * 100
                logger.info("Performance degradation from smallest to largest context:")
                logger.info(f"  {results_by_size[0]['context_tokens']} tokens: {baseline:.2f} t/s")
                logger.info(f"  {results_by_size[-1]['context_tokens']} tokens: {largest:.2f} t/s")
                logger.info(f"  Degradation: {degradation_pct:.1f}%\n")

                if degradation_pct < 20:
                    logger.info("[SUCCESS] Minimal throughput degradation across context sizes")
                elif degradation_pct < 40:
                    logger.info("[SUCCESS] Moderate throughput degradation")
                else:
                    logger.warning("[WARNING] Significant throughput degradation with large contexts")

        logger.info("="*60)
        logger.info("Benchmark complete! Results saved to:")
        logger.info(f"  {RESULTS_DIR.absolute()}")
        logger.info("="*60 + "\n")

    finally:
        # Tear down the server once the benchmark finishes or if it crashes mid-run
        logger.info("\nBenchmark sequence complete. Tearing down Neural Engine...")
        kill_existing_peridot()

if __name__ == "__main__":
    main()