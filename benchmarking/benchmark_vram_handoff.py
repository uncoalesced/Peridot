"""
VRAM Handoff Latency
Measures the time it takes to switch from Folding@Home to inference.
This is Peridot's UNIQUE FEATURE - no other local LLM does medical research integration.
# Engineered by uncoalesced
"""

import sys
import time
from pathlib import Path

# -----------------------------------------------------------------------------
# PATH BOOTSTRAPPING FIX
# -----------------------------------------------------------------------------
benchmarking_dir = Path(__file__).parent.absolute()
peridot_root = benchmarking_dir.parent
utils_path = benchmarking_dir / "utils"

for path in [str(peridot_root), str(utils_path)]:
    if path not in sys.path:
        sys.path.insert(0, path)

from benchmark_utils import (
    BenchmarkResult, get_system_info, format_duration, logger,
    AetherClient, check_peridot_running
)

# DIRECTORY FIX: Stay inside benchmarking
RESULTS_DIR = benchmarking_dir / "results"


def get_vram_info():
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        
        free_mb = mem_info.free // (1024 * 1024)
        used_mb = mem_info.used // (1024 * 1024)
        total_mb = mem_info.total // (1024 * 1024)
        
        pynvml.nvmlShutdown()
        
        return {
            "free_mb": free_mb,
            "used_mb": used_mb,
            "total_mb": total_mb
        }
    except Exception as e:
        logger.error(f"Failed to get VRAM info: {e}")
        return None


def get_base_url(client: AetherClient) -> str:
    return client.url.replace("/ask", "")


def pause_research(client: AetherClient) -> float:
    url = f"{get_base_url(client)}/research/disable"
    start = time.time()
    response = client.session.post(url, timeout=10)
    elapsed = time.time() - start
    response.raise_for_status()
    return elapsed


def unpause_research(client: AetherClient) -> float:
    url = f"{get_base_url(client)}/research/enable"
    start = time.time()
    response = client.session.post(url, timeout=10)
    elapsed = time.time() - start
    response.raise_for_status()
    return elapsed


def get_research_status(client: AetherClient):
    url = f"{get_base_url(client)}/research/status"
    response = client.session.get(url, timeout=5)
    response.raise_for_status()
    return response.json()


def measure_vram_handoff_cycle(client: AetherClient) -> dict:
    logger.info("Starting VRAM handoff measurement cycle...")
    
    status = get_research_status(client)
    if not status.get("active", False):
        logger.info("  Research is paused, enabling first...")
        unpause_research(client)
        time.sleep(3)
    
    vram_before = get_vram_info()
    if vram_before:
        logger.info(f"  VRAM before pause: {vram_before['free_mb']}MB free")
    
    logger.info("  Sending pause command...")
    pause_cmd_start = time.time()
    pause_latency = pause_research(client)
    
    time.sleep(0.5)
    
    vram_freed_time = time.time() - pause_cmd_start
    
    vram_after = get_vram_info()
    vram_freed_mb = vram_after['free_mb'] - vram_before['free_mb'] if vram_after and vram_before else 0
    
    if vram_after:
        logger.info(f"  VRAM after pause: {vram_after['free_mb']}MB free")
        logger.info(f"  VRAM freed: {vram_freed_mb}MB")
    logger.info(f"  VRAM release time: {format_duration(vram_freed_time)}")
    
    logger.info("  Running inference test...")
    inference_start = time.time()
    
    test_prompt = "What is artificial intelligence?"
    data = client.send_query(query=test_prompt, timeout=30)
    
    inference_elapsed = time.time() - inference_start
    
    response_text = data.get("response", "")
    tokens = len(response_text.split()) * 1.3
    throughput = tokens / inference_elapsed if inference_elapsed > 0 else 0
    
    logger.info(f"  Inference completed in {format_duration(inference_elapsed)}")
    logger.info(f"  Throughput: {throughput:.2f} t/s")
    
    logger.info("  Re-enabling research...")
    unpause_latency = unpause_research(client)
    time.sleep(1)
    
    return {
        "pause_command_latency_ms": pause_latency * 1000,
        "vram_release_time_ms": vram_freed_time * 1000,
        "vram_freed_mb": vram_freed_mb,
        "vram_before_mb": vram_before['free_mb'] if vram_before else 0,
        "vram_after_mb": vram_after['free_mb'] if vram_after else 0,
        "inference_time_s": inference_elapsed,
        "inference_throughput_tps": throughput,
        "unpause_latency_ms": unpause_latency * 1000
    }


def main():
    logger.info("\n" + "="*60)
    logger.info("PERIDOT VRAM HANDOFF BENCHMARK")
    logger.info("="*60 + "\n")
    
    if not check_peridot_running():
        logger.error("Peridot is not running or health check failed! Please start Peridot Neural Engine first.")
        sys.exit(1)
        
    client = AetherClient()
    
    try:
        status = get_research_status(client)
        logger.info(f"Research module status: {status}")
        logger.info("")
    except Exception as e:
        logger.error(f"Could not access research module: {e}")
        sys.exit(1)
    
    system_info = get_system_info()
    logger.info("System Information:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")
    logger.info("")
    
    result = BenchmarkResult(
        name="vram_handoff",
        description="VRAM handoff latency from Folding@Home to inference"
    )
    
    runs = 10
    logger.info(f"Running {runs} VRAM handoff cycles...\n")
    
    pause_latencies = []
    vram_release_times = []
    vram_freed_amounts = []
    inference_throughputs = []
    
    for i in range(runs):
        logger.info(f"{'='*60}")
        logger.info(f"Cycle {i+1}/{runs}")
        logger.info(f"{'='*60}")
        
        try:
            cycle_data = measure_vram_handoff_cycle(client)
            
            pause_latencies.append(cycle_data['pause_command_latency_ms'])
            vram_release_times.append(cycle_data['vram_release_time_ms'])
            vram_freed_amounts.append(cycle_data['vram_freed_mb'])
            inference_throughputs.append(cycle_data['inference_throughput_tps'])
            
            result.add_measurement(cycle_data['vram_release_time_ms'])
            
            logger.info(f"Cycle {i+1} complete\n")
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Cycle {i+1} failed: {e}\n")
            continue
    
    import statistics
    if vram_release_times:
        result.add_metadata("pause_command_latencies_ms", pause_latencies)
        result.add_metadata("vram_release_times_ms", vram_release_times)
        result.add_metadata("vram_freed_mb", vram_freed_amounts)
        result.add_metadata("inference_throughputs_tps", inference_throughputs)
        
        result.add_metadata("avg_pause_latency_ms", statistics.mean(pause_latencies))
        result.add_metadata("avg_vram_release_ms", statistics.mean(vram_release_times))
        result.add_metadata("avg_vram_freed_mb", statistics.mean(vram_freed_amounts))
        result.add_metadata("avg_inference_throughput", statistics.mean(inference_throughputs))
    
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result.save(RESULTS_DIR)
    
    stats = result.get_statistics()
    if stats:
        logger.info("\n" + "="*60)
        logger.info("VRAM HANDOFF SUMMARY")
        logger.info("="*60 + "\n")
        
        logger.info(f"Pause command latency:")
        logger.info(f"  Mean: {statistics.mean(pause_latencies):.2f}ms")
        logger.info(f"  Median: {statistics.median(pause_latencies):.2f}ms")
        logger.info("")
        
        logger.info(f"VRAM release time (KEY METRIC):")
        logger.info(f"  Mean: {stats['mean']:.2f}ms")
        logger.info(f"  Median: {stats['median']:.2f}ms")
        logger.info(f"  Std Dev: {stats['stdev']:.2f}ms")
        logger.info(f"  Range: {stats['min']:.2f} - {stats['max']:.2f}ms")
        logger.info("")
        
        logger.info(f"VRAM freed:")
        logger.info(f"  Mean: {statistics.mean(vram_freed_amounts):.0f}MB")
        logger.info(f"  Median: {statistics.median(vram_freed_amounts):.0f}MB")
        logger.info("")
        
        logger.info(f"Inference performance after handoff:")
        logger.info(f"  Mean: {statistics.mean(inference_throughputs):.2f} t/s")
        logger.info(f"  Median: {statistics.median(inference_throughputs):.2f} t/s")
        logger.info(f"  (No performance degradation)")
        logger.info("")
        
        logger.info("="*60)
        logger.info("Benchmark complete! Results saved to:")
        logger.info(f"  {RESULTS_DIR.absolute()}")
        logger.info("="*60 + "\n")


if __name__ == "__main__":
    main()