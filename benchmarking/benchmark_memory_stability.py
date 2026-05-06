"""
Benchmark 4: Memory Stability
Tests for memory leaks by running many consecutive queries.
# Engineered by uncoalesced
"""

import sys
import time
import requests
import psutil
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from benchmark_utils import (
    BenchmarkResult, get_system_info, format_bytes, logger, ProgressBar
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
                return {
                    "rss_mb": mem_info.rss / (1024 * 1024),
                    "vms_mb": mem_info.vms / (1024 * 1024),
                    "pid": proc.info['pid']
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None


def run_query(query_num: int):
    """Run a single query and return response time."""
    import os
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("PERIDOT_AUTH_TOKEN")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    prompts = [
        "What is machine learning?",
        "Explain quantum computing.",
        "How do neural networks work?",
        "What is the difference between AI and ML?",
        "Describe deep learning.",
        "What is natural language processing?",
        "Explain computer vision.",
        "What are transformers in AI?",
        "How does backpropagation work?",
        "What is reinforcement learning?"
    ]
    
    prompt = prompts[query_num % len(prompts)]
    
    payload = {
        "command": prompt
    }
    
    start = time.time()
    response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
    elapsed = time.time() - start
    
    response.raise_for_status()
    return elapsed


def main():
    logger.info("\n" + "="*60)
    logger.info("PERIDOT MEMORY STABILITY BENCHMARK")
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
    
    logger.info(f"Peridot process found (PID: {initial_mem['pid']})")
    logger.info(f"Initial memory usage: {initial_mem['rss_mb']:.2f} MB\n")
    
    system_info = get_system_info()
    logger.info("System Information:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")
    logger.info("")
    
    result = BenchmarkResult(
        name="memory_stability",
        description="Memory usage over consecutive queries"
    )
    
    result.add_metadata("initial_memory_mb", initial_mem['rss_mb'])
    result.add_metadata("pid", initial_mem['pid'])
    
    num_queries = 100
    sample_interval = 5
    
    logger.info(f"Running {num_queries} consecutive queries...")
    logger.info(f"Sampling memory every {sample_interval} queries\n")
    
    memory_samples = []
    query_times = []
    
    progress = ProgressBar(num_queries, prefix="Progress")
    
    for i in range(num_queries):
        try:
            query_time = run_query(i)
            query_times.append(query_time)
            
            if i % sample_interval == 0:
                mem = get_peridot_memory()
                if mem:
                    memory_samples.append({
                        "query_num": i,
                        "rss_mb": mem['rss_mb'],
                        "vms_mb": mem['vms_mb']
                    })
                    result.add_measurement(mem['rss_mb'])
            
            progress.update()
            time.sleep(0.1)
            
        except Exception as e:
            logger.error(f"\nQuery {i+1} failed: {e}")
            continue
    
    final_mem = get_peridot_memory()
    if final_mem:
        result.add_metadata("final_memory_mb", final_mem['rss_mb'])
        result.add_metadata("memory_growth_mb", final_mem['rss_mb'] - initial_mem['rss_mb'])
    
    result.add_metadata("total_queries", num_queries)
    result.add_metadata("successful_queries", len(query_times))
    result.add_metadata("memory_samples", memory_samples)
    
    import statistics
    if query_times:
        result.add_metadata("avg_query_time_s", statistics.mean(query_times))
        result.add_metadata("median_query_time_s", statistics.median(query_times))
    
    result.save(RESULTS_DIR)
    
    logger.info("\n" + "="*60)
    logger.info("MEMORY STABILITY SUMMARY")
    logger.info("="*60 + "\n")
    
    logger.info(f"Queries executed: {len(query_times)}/{num_queries}")
    logger.info(f"Initial memory: {initial_mem['rss_mb']:.2f} MB")
    
    if final_mem:
        logger.info(f"Final memory: {final_mem['rss_mb']:.2f} MB")
        growth = final_mem['rss_mb'] - initial_mem['rss_mb']
        logger.info(f"Memory growth: {growth:+.2f} MB ({growth/initial_mem['rss_mb']*100:+.2f}%)")
        
        if abs(growth) < 50:
            logger.info("✅ Memory stable (growth < 50 MB)")
        else:
            logger.warning(f"⚠️  Significant memory growth detected!")
    
    logger.info("")
    
    if memory_samples:
        logger.info("Memory samples:")
        logger.info(f"  {'Query':<10} {'RSS (MB)':<12} {'VMS (MB)':<12}")
        logger.info("  " + "-"*34)
        for sample in memory_samples[::5]:
            logger.info(f"  {sample['query_num']:<10} {sample['rss_mb']:<12.2f} {sample['vms_mb']:<12.2f}")
    
    logger.info("")
    
    if query_times:
        logger.info(f"Query performance:")
        logger.info(f"  Average: {statistics.mean(query_times):.3f}s")
        logger.info(f"  Median: {statistics.median(query_times):.3f}s")
        logger.info(f"  Std Dev: {statistics.stdev(query_times):.3f}s")
    
    logger.info("")
    logger.info("="*60)
    logger.info("Benchmark complete! Results saved to:")
    logger.info(f"  {RESULTS_DIR.absolute()}")
    logger.info("="*60 + "\n")


if __name__ == "__main__":
    main()