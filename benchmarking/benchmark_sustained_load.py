"""
Benchmark 7: Sustained Load
Tests performance and stability under extended continuous use.
# Engineered by uncoalesced
"""

import sys
import time
import requests
import psutil
from pathlib import Path
from datetime import datetime

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from benchmark_utils import (
    BenchmarkResult, get_system_info, format_duration, logger, ProgressBar
)

# Configuration
API_URL = "http://localhost:5000/ask"
RESULTS_DIR = Path(__file__).parent.parent / "results"


def get_peridot_memory():
    """Get memory usage of Peridot process."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any('launcher.py' in str(cmd) for cmd in cmdline):
                mem_info = proc.memory_info()
                return mem_info.rss / (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


def count_tokens_rough(text: str) -> int:
    return int(len(text.split()) * 1.3)


def run_query(prompt: str, max_tokens: int = 100):
    import os
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("PERIDOT_AUTH_TOKEN")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    payload = {"command": prompt}
    
    start = time.time()
    response = requests.post(API_URL, json=payload, headers=headers, timeout=60)
    elapsed = time.time() - start
    
    response.raise_for_status()
    
    response_text = response.json().get("response", "")
    tokens = count_tokens_rough(response_text)
    throughput = tokens / elapsed if elapsed > 0 else 0
    
    return {
        "elapsed": elapsed,
        "tokens": tokens,
        "throughput": throughput,
        "timestamp": datetime.now().isoformat()
    }


def main():
    logger.info("\n" + "="*60)
    logger.info("PERIDOT SUSTAINED LOAD BENCHMARK")
    logger.info("="*60 + "\n")
    
    try:
        response = requests.get("http://localhost:5000/health", timeout=2)
        if response.status_code != 200:
            logger.error("Peridot is not responding correctly!")
            sys.exit(1)
    except:
        logger.error("Peridot is not running! Please start Peridot first.")
        sys.exit(1)
    
    initial_mem = get_peridot_memory()
    if not initial_mem:
        logger.error("Could not find Peridot process!")
        sys.exit(1)
    
    system_info = get_system_info()
    logger.info("System Information:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")
    logger.info("")
    
    duration_minutes = 10
    duration_seconds = duration_minutes * 60
    
    logger.info(f"Configuration:")
    logger.info(f"  Duration: {duration_minutes} minutes ({duration_seconds} seconds)")
    logger.info(f"  Initial memory: {initial_mem:.2f} MB")
    logger.info("")
    
    logger.warning("⚠️  This benchmark will run for 10 minutes!")
    logger.warning("⚠️  Press Ctrl+C to stop early (results will still be saved)\n")
    
    result = BenchmarkResult(
        name="sustained_load",
        description=f"Sustained load test over {duration_minutes} minutes"
    )
    
    result.add_metadata("duration_minutes", duration_minutes)
    result.add_metadata("initial_memory_mb", initial_mem)
    
    prompts = [
        "Explain machine learning briefly.",
        "What is quantum computing?",
        "Describe neural networks.",
        "How does NLP work?",
        "What is computer vision?",
        "Explain deep learning.",
        "What are transformers in AI?",
        "How does reinforcement learning work?",
        "What is supervised learning?",
        "Explain unsupervised learning."
    ]
    
    start_time = time.time()
    query_count = 0
    successful_queries = 0
    failed_queries = 0
    
    throughputs = []
    response_times = []
    memory_samples = []
    timestamps = []
    
    logger.info("Starting sustained load test...\n")
    
    try:
        while time.time() - start_time < duration_seconds:
            elapsed_time = time.time() - start_time
            progress_pct = (elapsed_time / duration_seconds) * 100
            
            prompt = prompts[query_count % len(prompts)]
            
            try:
                metrics = run_query(prompt)
                
                successful_queries += 1
                throughputs.append(metrics['throughput'])
                response_times.append(metrics['elapsed'])
                timestamps.append(metrics['timestamp'])
                
                if successful_queries % 20 == 0:
                    mem = get_peridot_memory()
                    if mem:
                        memory_samples.append({
                            "query_num": successful_queries,
                            "memory_mb": mem,
                            "elapsed_time_s": elapsed_time
                        })
                
                if successful_queries % 10 == 0:
                    import statistics
                    avg_throughput = statistics.mean(throughputs[-10:])
                    logger.info(
                        f"Progress: {progress_pct:.1f}% | "
                        f"Queries: {successful_queries} | "
                        f"Avg throughput (last 10): {avg_throughput:.2f} t/s"
                    )
                
                query_count += 1
                time.sleep(0.2)
                
            except Exception as e:
                failed_queries += 1
                logger.error(f"Query {query_count + 1} failed: {e}")
                time.sleep(1)
                query_count += 1
                continue
                
    except KeyboardInterrupt:
        logger.info("\n\nBenchmark interrupted by user!")
        logger.info("Saving partial results...\n")
    
    total_time = time.time() - start_time
    final_mem = get_peridot_memory()
    
    import statistics
    
    if throughputs:
        for tp in throughputs:
            result.add_measurement(tp)
        
        result.add_metadata("total_queries", query_count)
        result.add_metadata("successful_queries", successful_queries)
        result.add_metadata("failed_queries", failed_queries)
        result.add_metadata("total_time_s", total_time)
        result.add_metadata("queries_per_minute", (successful_queries / total_time) * 60)
        
        result.add_metadata("avg_throughput", statistics.mean(throughputs))
        result.add_metadata("median_throughput", statistics.median(throughputs))
        result.add_metadata("min_throughput", min(throughputs))
        result.add_metadata("max_throughput", max(throughputs))
        
        result.add_metadata("avg_response_time", statistics.mean(response_times))
        result.add_metadata("memory_samples", memory_samples)
        
        if final_mem:
            result.add_metadata("final_memory_mb", final_mem)
            result.add_metadata("memory_growth_mb", final_mem - initial_mem)
    
    result.save(RESULTS_DIR)
    
    logger.info("\n" + "="*60)
    logger.info("SUSTAINED LOAD SUMMARY")
    logger.info("="*60 + "\n")
    
    logger.info(f"Test duration: {format_duration(total_time)}")
    logger.info(f"Target duration: {format_duration(duration_seconds)}")
    logger.info(f"Completion: {(total_time/duration_seconds)*100:.1f}%")
    logger.info("")
    
    logger.info(f"Queries:")
    logger.info(f"  Total attempted: {query_count}")
    logger.info(f"  Successful: {successful_queries}")
    logger.info(f"  Failed: {failed_queries}")
    logger.info(f"  Success rate: {(successful_queries/query_count)*100:.1f}%")
    logger.info(f"  Queries per minute: {result.metadata.get('queries_per_minute', 0):.1f}")
    logger.info("")
    
    if throughputs:
        logger.info(f"Throughput:")
        logger.info(f"  Average: {statistics.mean(throughputs):.2f} t/s")
        logger.info(f"  Median: {statistics.median(throughputs):.2f} t/s")
        logger.info(f"  Std Dev: {statistics.stdev(throughputs):.2f} t/s")
        logger.info(f"  Range: {min(throughputs):.2f} - {max(throughputs):.2f} t/s")
        logger.info("")
        
        logger.info(f"Response time:")
        logger.info(f"  Average: {format_duration(statistics.mean(response_times))}")
        logger.info(f"  Median: {format_duration(statistics.median(response_times))}")
        logger.info("")
    
    if memory_samples:
        logger.info(f"Memory:")
        logger.info(f"  Initial: {initial_mem:.2f} MB")
        if final_mem:
            logger.info(f"  Final: {final_mem:.2f} MB")
            growth = final_mem - initial_mem
            logger.info(f"  Growth: {growth:+.2f} MB ({(growth/initial_mem)*100:+.1f}%)")
            
            if abs(growth) < 100:
                logger.info("  ✅ Memory stable")
            else:
                logger.warning("  ⚠️  Significant memory growth")
        logger.info("")
    
    if len(throughputs) > 20:
        first_20 = statistics.mean(throughputs[:20])
        last_20 = statistics.mean(throughputs[-20:])
        degradation = ((first_20 - last_20) / first_20) * 100
        
        logger.info(f"Performance over time:")
        logger.info(f"  First 20 queries: {first_20:.2f} t/s")
        logger.info(f"  Last 20 queries: {last_20:.2f} t/s")
        logger.info(f"  Change: {degradation:+.1f}%")
        
        if abs(degradation) < 10:
            logger.info("  ✅ Stable performance")
        else:
            logger.warning(f"  ⚠️  Performance changed by {abs(degradation):.1f}%")
        logger.info("")
    
    logger.info("="*60)
    logger.info("Benchmark complete! Results saved to:")
    logger.info(f"  {RESULTS_DIR.absolute()}")
    logger.info("="*60 + "\n")


if __name__ == "__main__":
    main()