"""
Benchmark 6: Context Window Scaling
Tests how performance scales with different context lengths.
# Engineered by uncoalesced
"""

import sys
import time
import requests
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from benchmark_utils import (
    BenchmarkResult, get_system_info, format_duration, format_throughput, logger
)


# Configuration
API_URL = "http://localhost:5000/chat"
RESULTS_DIR = Path(__file__).parent.parent / "results"


def generate_context(target_tokens: int) -> str:
    """
    Generate a context string with approximately target_tokens.
    Uses Lorem Ipsum-style text for realistic token distribution.
    """
    # Base text that will be repeated
    base_text = """Machine learning is a subset of artificial intelligence that focuses on 
    developing algorithms and statistical models that enable computer systems to improve 
    their performance on a specific task through experience. Deep learning, a specialized 
    branch of machine learning, uses neural networks with multiple layers to automatically 
    learn hierarchical representations of data. """
    
    # Approximate tokens per base_text chunk (rough: 60 words ≈ 78 tokens)
    tokens_per_chunk = 78
    
    # Calculate how many repetitions we need
    repetitions = max(1, target_tokens // tokens_per_chunk)
    
    context = (base_text * repetitions).strip()
    
    return context


def count_tokens_rough(text: str) -> int:
    """Rough token count approximation."""
    words = text.split()
    return int(len(words) * 1.3)


def measure_with_context(context_tokens: int, runs: int = 5) -> dict:
    """Measure inference speed with a specific context length."""
    import os
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("PERIDOT_AUTH_TOKEN")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    # Generate context
    context = generate_context(context_tokens)
    actual_context_tokens = count_tokens_rough(context)
    
    # Question to ask after the context
    question = "\n\nBased on the above, what is machine learning?"
    
    full_prompt = context + question
    
    logger.info(f"\nTesting with ~{context_tokens} token context")
    logger.info(f"Actual context tokens: {actual_context_tokens}")
    logger.info(f"Total prompt tokens: {count_tokens_rough(full_prompt)}")
    
    throughputs = []
    response_times = []
    
    # Warmup
    try:
        payload = {"message": full_prompt, "max_tokens": 50}
        requests.post(API_URL, json=payload, headers=headers, timeout=60)
        time.sleep(1)
    except:
        pass
    
    # Run measurements
    for i in range(runs):
        try:
            payload = {"message": full_prompt, "max_tokens": 50}
            
            start = time.time()
            response = requests.post(API_URL, json=payload, headers=headers, timeout=60)
            elapsed = time.time() - start
            
            response.raise_for_status()
            
            # Count tokens in response
            response_text = response.json().get("response", "")
            response_tokens = count_tokens_rough(response_text)
            
            throughput = response_tokens / elapsed if elapsed > 0 else 0
            
            throughputs.append(throughput)
            response_times.append(elapsed)
            
            logger.debug(f"  Run {i+1}: {format_throughput(response_tokens, elapsed)}")
            
        except Exception as e:
            logger.error(f"  Run {i+1} failed: {e}")
            continue
    
    import statistics
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
    """Run context scaling benchmark."""
    logger.info("\n" + "="*60)
    logger.info("PERIDOT CONTEXT WINDOW SCALING BENCHMARK")
    logger.info("="*60 + "\n")
    
    # Check if Peridot is running
    try:
        response = requests.get("http://localhost:5000/health", timeout=2)
        if response.status_code != 200:
            logger.error("Peridot is not responding correctly!")
            sys.exit(1)
    except:
        logger.error("Peridot is not running! Please start Peridot first.")
        sys.exit(1)
    
    # Gather system info
    system_info = get_system_info()
    logger.info("System Information:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")
    logger.info("")
    
    # Create result container
    result = BenchmarkResult(
        name="context_scaling",
        description="Performance vs context window size"
    )
    
    # Test different context lengths
    context_sizes = [512, 1024, 2048, 4096, 8192]
    
    logger.info(f"Testing context sizes: {context_sizes}")
    logger.info("This may take several minutes...\n")
    
    results_by_size = []
    
    for size in context_sizes:
        logger.info("="*60)
        logger.info(f"Context Size: {size} tokens")
        logger.info("="*60)
        
        measurement = measure_with_context(size, runs=5)
        
        if measurement:
            results_by_size.append(measurement)
            
            logger.info(f"Average throughput: {measurement['avg_throughput']:.2f} t/s")
            logger.info(f"Average response time: {format_duration(measurement['avg_response_time'])}")
            
            # Add throughput as measurement
            result.add_measurement(measurement['median_throughput'])
        else:
            logger.error(f"Failed to measure context size {size}")
        
        logger.info("")
        
        # Small delay between tests
        time.sleep(2)
    
    # Add metadata
    result.add_metadata("context_sizes", context_sizes)
    result.add_metadata("results_by_size", results_by_size)
    
    # Save result
    result.save(RESULTS_DIR)
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("CONTEXT SCALING SUMMARY")
    logger.info("="*60 + "\n")
    
    # Table
    logger.info(f"{'Context Size':<15} {'Avg Throughput':<20} {'Response Time':<15}")
    logger.info("-" * 50)
    
    for res in results_by_size:
        logger.info(
            f"{res['context_tokens']:<15} "
            f"{res['avg_throughput']:<20.2f} t/s "
            f"{format_duration(res['avg_response_time']):<15}"
        )
    
    logger.info("")
    
    # Calculate degradation
    if len(results_by_size) >= 2:
        baseline = results_by_size[0]['avg_throughput']
        largest = results_by_size[-1]['avg_throughput']
        degradation_pct = ((baseline - largest) / baseline) * 100
        
        logger.info(f"Performance degradation from smallest to largest context:")
        logger.info(f"  {results_by_size[0]['context_tokens']} tokens: {baseline:.2f} t/s")
        logger.info(f"  {results_by_size[-1]['context_tokens']} tokens: {largest:.2f} t/s")
        logger.info(f"  Degradation: {degradation_pct:.1f}%")
        logger.info("")
        
        if degradation_pct < 20:
            logger.info("✅ Minimal performance degradation across context sizes")
        elif degradation_pct < 40:
            logger.info("✅ Moderate performance degradation")
        else:
            logger.warning("⚠️  Significant performance degradation with large contexts")
    
    logger.info("")
    logger.info("="*60)
    logger.info("Benchmark complete! Results saved to:")
    logger.info(f"  {RESULTS_DIR.absolute()}")
    logger.info("="*60 + "\n")


if __name__ == "__main__":
    main()
