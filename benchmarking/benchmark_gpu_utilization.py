"""
Benchmark 5: GPU Utilization
Monitors GPU usage during inference to verify efficient GPU utilization.
# Engineered by uncoalesced
"""

import sys
import time
import requests
import threading
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from benchmark_utils import (
    BenchmarkResult, get_system_info, logger
)


# Configuration
API_URL = "http://localhost:5000/chat"
RESULTS_DIR = Path(__file__).parent.parent / "results"


class GPUMonitor:
    """Monitor GPU utilization in background thread."""
    
    def __init__(self):
        self.utilizations = []
        self.temperatures = []
        self.power_usage = []
        self.running = False
        self.thread = None
        
        try:
            import pynvml
            pynvml.nvmlInit()
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.pynvml = pynvml
        except Exception as e:
            logger.error(f"Failed to initialize GPU monitoring: {e}")
            raise
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.running:
            try:
                # Get utilization
                util = self.pynvml.nvmlDeviceGetUtilizationRates(self.handle)
                self.utilizations.append(util.gpu)
                
                # Get temperature
                temp = self.pynvml.nvmlDeviceGetTemperature(
                    self.handle,
                    self.pynvml.NVML_TEMPERATURE_GPU
                )
                self.temperatures.append(temp)
                
                # Get power usage
                try:
                    power = self.pynvml.nvmlDeviceGetPowerUsage(self.handle)
                    self.power_usage.append(power / 1000.0)  # Convert mW to W
                except:
                    pass  # Power monitoring not always available
                
                time.sleep(0.5)  # Sample every 500ms
                
            except Exception as e:
                logger.error(f"GPU monitoring error: {e}")
                break
    
    def start(self):
        """Start monitoring in background."""
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("GPU monitoring started")
    
    def stop(self):
        """Stop monitoring and return results."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        
        logger.info("GPU monitoring stopped")
        
        import statistics
        result = {
            "samples": len(self.utilizations),
            "utilization": {
                "min": min(self.utilizations) if self.utilizations else 0,
                "max": max(self.utilizations) if self.utilizations else 0,
                "mean": statistics.mean(self.utilizations) if self.utilizations else 0,
                "median": statistics.median(self.utilizations) if self.utilizations else 0,
                "stdev": statistics.stdev(self.utilizations) if len(self.utilizations) > 1 else 0,
                "all_values": self.utilizations
            },
            "temperature": {
                "min": min(self.temperatures) if self.temperatures else 0,
                "max": max(self.temperatures) if self.temperatures else 0,
                "mean": statistics.mean(self.temperatures) if self.temperatures else 0,
                "all_values": self.temperatures
            }
        }
        
        if self.power_usage:
            result["power"] = {
                "min": min(self.power_usage),
                "max": max(self.power_usage),
                "mean": statistics.mean(self.power_usage),
                "all_values": self.power_usage
            }
        
        return result
    
    def cleanup(self):
        """Cleanup GPU monitoring."""
        try:
            self.pynvml.nvmlShutdown()
        except:
            pass


def run_inference_with_monitoring(duration_s: int = 30):
    """Run continuous inference while monitoring GPU."""
    import os
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("PERIDOT_AUTH_TOKEN")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    prompts = [
        "Explain machine learning in detail.",
        "What is quantum computing and how does it work?",
        "Describe the history of artificial intelligence.",
        "How do neural networks learn from data?",
        "What are the applications of computer vision?"
    ]
    
    logger.info(f"Running inference for {duration_s} seconds...")
    
    start_time = time.time()
    query_count = 0
    
    while time.time() - start_time < duration_s:
        prompt = prompts[query_count % len(prompts)]
        
        try:
            payload = {"message": prompt, "max_tokens": 150}
            response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            query_count += 1
            
            logger.debug(f"Query {query_count} completed")
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            time.sleep(1)
    
    return query_count


def main():
    """Run GPU utilization benchmark."""
    logger.info("\n" + "="*60)
    logger.info("PERIDOT GPU UTILIZATION BENCHMARK")
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
        name="gpu_utilization",
        description="GPU utilization during inference"
    )
    
    # Test 1: Idle GPU (no queries)
    logger.info("="*60)
    logger.info("Test 1: Idle GPU Utilization (10 seconds)")
    logger.info("="*60 + "\n")
    
    monitor_idle = GPUMonitor()
    monitor_idle.start()
    time.sleep(10)
    idle_stats = monitor_idle.stop()
    monitor_idle.cleanup()
    
    logger.info(f"Idle GPU utilization: {idle_stats['utilization']['mean']:.1f}%")
    logger.info(f"Idle temperature: {idle_stats['temperature']['mean']:.1f}°C")
    logger.info("")
    
    result.add_metadata("idle_utilization", idle_stats['utilization'])
    result.add_metadata("idle_temperature", idle_stats['temperature'])
    
    # Test 2: Active inference
    logger.info("="*60)
    logger.info("Test 2: GPU Utilization During Inference (30 seconds)")
    logger.info("="*60 + "\n")
    
    monitor_active = GPUMonitor()
    monitor_active.start()
    query_count = run_inference_with_monitoring(duration_s=30)
    active_stats = monitor_active.stop()
    monitor_active.cleanup()
    
    logger.info(f"\nQueries executed: {query_count}")
    logger.info(f"Active GPU utilization: {active_stats['utilization']['mean']:.1f}%")
    logger.info(f"Peak GPU utilization: {active_stats['utilization']['max']:.1f}%")
    logger.info(f"Active temperature: {active_stats['temperature']['mean']:.1f}°C")
    
    if 'power' in active_stats:
        logger.info(f"Average power: {active_stats['power']['mean']:.1f}W")
    
    logger.info("")
    
    result.add_metadata("active_utilization", active_stats['utilization'])
    result.add_metadata("active_temperature", active_stats['temperature'])
    result.add_metadata("queries_executed", query_count)
    
    if 'power' in active_stats:
        result.add_metadata("active_power", active_stats['power'])
    
    # Use average active utilization as primary metric
    result.add_measurement(active_stats['utilization']['mean'])
    
    # Save result
    result.save(RESULTS_DIR)
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("GPU UTILIZATION SUMMARY")
    logger.info("="*60 + "\n")
    
    logger.info(f"Idle GPU utilization:")
    logger.info(f"  Mean: {idle_stats['utilization']['mean']:.1f}%")
    logger.info(f"  Range: {idle_stats['utilization']['min']:.1f}% - {idle_stats['utilization']['max']:.1f}%")
    logger.info("")
    
    logger.info(f"Active GPU utilization (during inference):")
    logger.info(f"  Mean: {active_stats['utilization']['mean']:.1f}%")
    logger.info(f"  Median: {active_stats['utilization']['median']:.1f}%")
    logger.info(f"  Range: {active_stats['utilization']['min']:.1f}% - {active_stats['utilization']['max']:.1f}%")
    logger.info(f"  Std Dev: {active_stats['utilization']['stdev']:.1f}%")
    logger.info("")
    
    # Check efficiency
    if active_stats['utilization']['mean'] > 70:
        logger.info("✅ Excellent GPU utilization (>70%)")
    elif active_stats['utilization']['mean'] > 50:
        logger.info("✅ Good GPU utilization (>50%)")
    else:
        logger.warning(f"⚠️  Low GPU utilization (<50%)")
    
    logger.info("")
    
    logger.info(f"Temperature:")
    logger.info(f"  Idle: {idle_stats['temperature']['mean']:.1f}°C")
    logger.info(f"  Active: {active_stats['temperature']['mean']:.1f}°C")
    logger.info(f"  Peak: {active_stats['temperature']['max']:.1f}°C")
    logger.info("")
    
    if 'power' in active_stats:
        logger.info(f"Power consumption:")
        logger.info(f"  Average: {active_stats['power']['mean']:.1f}W")
        logger.info(f"  Peak: {active_stats['power']['max']:.1f}W")
        logger.info("")
    
    logger.info("="*60)
    logger.info("Benchmark complete! Results saved to:")
    logger.info(f"  {RESULTS_DIR.absolute()}")
    logger.info("="*60 + "\n")


if __name__ == "__main__":
    main()
