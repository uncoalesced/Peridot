#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import time
import json
import os
from pathlib import Path
from typing import Dict, Any

try:
    import pynvml
    from llama_cpp import Llama
except ImportError:
    print("[FATAL] Missing benchmark dependencies. Ensure llama-cpp-python and pynvml are installed.")
    exit(1)

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
REPORT_PATH = LOG_DIR / "benchmark_matrix.json"

# Synthetic RAG Payload to simulate Aether Route stress
SYNTHETIC_CONTEXT = """
[SOURCE: medical_report_01.pdf]: The patient exhibits signs of acute demyelination. VRAM offloading must maintain a strict 21ms latency to prevent hardware interrupts.
[SOURCE: engineering_log.txt]: The Aether-Route protocol successfully bypassed the L1 cache, shifting 8GB of context directly to the Ryzen 7 CPU to preserve RTX 5050 overhead.
[SOURCE: financial_q3.csv]: Q3 operating costs for cloud AI routing totaled $14,000. Peridot localized execution reduced this to $0.00, utilizing existing power grids.
""" * 50

def get_vram_usage() -> int:
    """Returns currently used VRAM in MB."""
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        return info.used // 1024 // 1024
    except pynvml.NVMLError:
        return 0

def run_stress_test(model_path: str, gpu_layers: int = 100) -> Dict[str, Any]:
    """Floods the model and records precise telemetry."""
    print(f"\n>> Initiating TurboQuant Benchmark on: {Path(model_path).name}")
    print(f">> Pre-boot VRAM Load: {get_vram_usage()} MB")
    
    metrics = {
        "model": Path(model_path).name,
        "quantization": Path(model_path).suffix,
        "gpu_layers": gpu_layers,
        "ttft_sec": 0.0,
        "tps": 0.0,
        "peak_vram_mb": 0,
        "status": "FAILED"
    }

    try:
        start_boot = time.time()
        llm = Llama(
            model_path=str(model_path),
            n_ctx=8192,
            n_threads=8,
            n_gpu_layers=gpu_layers,
            flash_attn=True,
            verbose=False
        )
        boot_time = time.time() - start_boot
        print(f">> Engine Boot Sequence: {boot_time:.2f}s | VRAM: {get_vram_usage()} MB")

        prompt = (
            "<|start_header_id|>system<|end_header_id|>\n\n"
            "You are the Peridot Sovereign Kernel. Read the context and summarize the cost savings and VRAM latency rules.\n\n"
            f"CONTEXT:\n{SYNTHETIC_CONTEXT}<|eot_id|>\n"
            "<|start_header_id|>user<|end_header_id|>\n\n"
            "Begin summary.<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        )

        print(">> Ingesting Synthetic RAG Payload...")
        
        # Tracking Time till first token
        ttft_start = time.time()
        output_stream = llm(
            prompt,
            max_tokens=512,
            temperature=0.1,
            stream=True
        )

        first_token = True
        generated_tokens = 0
        gen_start = 0

        for chunk in output_stream:
            if first_token:
                metrics["ttft_sec"] = time.time() - ttft_start
                print(f">> TTFT (Time-to-First-Token): {metrics['ttft_sec']:.4f}s")
                gen_start = time.time()
                first_token = False
            generated_tokens += 1
            
            current_vram = get_vram_usage()
            if current_vram > metrics["peak_vram_mb"]:
                metrics["peak_vram_mb"] = current_vram

        total_gen_time = time.time() - gen_start
        metrics["tps"] = generated_tokens / total_gen_time
        metrics["status"] = "SUCCESS"

        print(f">> Peak Generation VRAM: {metrics['peak_vram_mb']} MB")
        print(f">> Sustained Speed: {metrics['tps']:.2f} t/s")

    except Exception as e:
        print(f"[FATAL] Benchmark crashed: {e}")
        metrics["error"] = str(e)
    
    finally:
        try:
            del llm
        except UnboundLocalError:
            pass
        return metrics

def execute_matrix():
    print(f"{'='*50}\n PERIDOT DIAGNOSTICS | TURBOQUANT MATRIX\n{'='*50}")

    models_dir = Path("models")
    if not models_dir.exists() or not any(models_dir.iterdir()):
        print("[WARN] No GGUF models found in 'models/' directory to benchmark.")
        return

    matrix_results = []
    
    for model_file in models_dir.glob("*.gguf"):
        result = run_stress_test(str(model_file), gpu_layers=100)
        matrix_results.append(result)
        
        print(">> Cooldown cycle initiated (10s)...")
        time.sleep(11)

    with open(REPORT_PATH, "w") as f:
        json.dump(matrix_results, f, indent=4)
    
    print(f"\n>> Benchmark Matrix complete. Report saved to: {REPORT_PATH}")

if __name__ == "__main__":
    execute_matrix()