# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
GPU Utilization Telemetry
Monitors GPU usage during inference to verify efficient GPU utilization.
"""

import sys
import time
import requests
import threading
import psutil
from pathlib import Path

# Force Python to recognize both the Peridot root AND the utils folder
peridot_root = str(Path(__file__).parent.parent.absolute())
# FIX: Correctly path to E:\Peridot\benchmarking\utils
utils_path = str(Path(__file__).parent.absolute() / "utils")

if peridot_root not in sys.path:
    sys.path.insert(0, peridot_root)
if utils_path not in sys.path:
    sys.path.insert(0, utils_path)

from config import AI_SERVER_URL
from benchmark_utils import BenchmarkResult, get_system_info, logger

# DIRECTORY FIX: Removed one .parent to stay inside the benchmarking directory
RESULTS_DIR = Path(__file__).parent / "results"

def get_ephemeral_key():
    """Forensically extracts the RAM-only API key from the running server process."""
    try:
        for proc in psutil.process_iter(['name', 'cmdline']):
            cmdline = proc.info.get('cmdline') or []
            cmd_str = ' '.join(cmdline).lower()
            if 'server.py' in cmd_str or 'launcher.py' in cmd_str:
                env = proc.environ()
                key = env.get('API_KEY') or env.get('PERIDOT_AUTH_TOKEN')
                if key:
                    return key
    except Exception as e:
        logger.debug(f"Process memory inspection failed: {e}")
    
    # Fallback if extraction fails
    from config import API_KEY
    return API_KEY


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
        while self.running:
            try:
                util = self.pynvml.nvmlDeviceGetUtilizationRates(self.handle)
                self.utilizations.append(util.gpu)
                
                temp = self.pynvml.nvmlDeviceGetTemperature(
                    self.handle,
                    self.pynvml.NVML_TEMPERATURE_GPU
                )
                self.temperatures.append(temp)
                
                try:
                    power = self.pynvml.nvmlDeviceGetPowerUsage(self.handle)
                    self.power_usage.append(power / 1000.0)
                except:
                    pass
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"GPU monitoring error: {e}")
                break
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("GPU monitoring started")
    
    def stop(self):
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
        try:
            self.pynvml.nvmlShutdown()
        except:
            pass


def run_inference_with_monitoring(duration_s: int = 30):
    active_key = get_ephemeral_key()
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {active_key}"
    }
    
    prompts = [
        "Explain machine learning in detail.",
        "What is quantum computing and how does it work?",
        "Describe the history of artificial intelligence.",
        "How do neural networks learn from data?",
        "What are the applications of computer vision?"
    ]
    
    logger.info(f"Running inference for {duration_s} seconds. Target: {AI_SERVER_URL}")
    
    start_time = time.time()
    query_count = 0
    
    while time.time() - start_time < duration_s:
        raw_query = prompts[query_count % len(prompts)]
        
        # Format for Aether-Route split payload
        full_prompt = f"<|start_header_id|>user<|end_header_id|>\n\n{raw_query}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        
        try:
            payload = {"query": raw_query, "prompt": full_prompt}
            response = requests.post(AI_SERVER_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            query_count += 1
            
            logger.debug(f"Query {query_count} completed")
            
        except Exception as e:
            logger.error(f"Query failed: {e}")
            time.sleep(1)
    
    return query_count


def main():
    logger.info("\n" + "="*60)
    logger.info("PERIDOT GPU UTILIZATION BENCHMARK")
    logger.info("="*60 + "\n")
    
    # Dynamically strip /ask to hit the /health endpoint safely
    health_url = AI_SERVER_URL.replace("/ask", "") + "/health"
    try:
        response = requests.get(health_url, timeout=2)
        if response.status_code != 200:
            logger.error(f"Peridot returned abnormal status: {response.status_code}")
            sys.exit(1)
    except requests.exceptions.RequestException:
        logger.error("Peridot is not running! Please start Peridot Neural Engine first.")
        sys.exit(1)
    
    system_info = get_system_info()
    logger.info("System Information:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")
    logger.info("")
    
    result = BenchmarkResult(
        name="gpu_utilization",
        description="GPU utilization during Aether-Route inference"
    )
    
    logger.info("="*60)
    logger.info("Test: Idle GPU Utilization (10 seconds)")
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
    
    logger.info("="*60)
    logger.info("Test: GPU Utilization During Inference (30 seconds)")
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
    
    result.add_measurement(active_stats['utilization']['mean'])
    
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result.save(RESULTS_DIR)
    
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