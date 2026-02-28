import time
import subprocess
import os
import torch  # Ensure torch is installed in your venv


def get_vram_usage():
    cmd = "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits"
    output = subprocess.check_output(cmd, shell=True)
    return int(output.decode().strip())


def run_stress_test():
    print("--- Peridot VRAM Hammer Diagnostic ---")

    # 1. Baseline
    baseline = get_vram_usage()
    print(f"[1/4] Baseline VRAM: {baseline} MB")

    # 2. Heavy VRAM Allocation
    print("[2/4] Allocating 4GB of VRAM to simulate heavy Folding@home load...")
    try:
        # Create a large tensor on the GPU
        dummy_tensor = torch.zeros((1024, 1024, 1024), device="cuda")
        active_vram = get_vram_usage()
        print(f"      Active Stress VRAM: {active_vram} MB")
    except Exception as e:
        print(f"      Allocation failed: {e}")
        return

    # 3. Trigger the Purge
    print("[3/4] Triggering Prompt Simulation. Manually clearing VRAM...")
    start_time = time.perf_counter()

    # In the real app, this is where SIGTERM hits.
    # Here, we simulate the 'Hard-Kill' by deleting the object and clearing the cache.
    del dummy_tensor
    torch.cuda.empty_cache()

    # 4. Measuring Latency
    purge_vram = get_vram_usage()
    end_time = time.perf_counter()

    latency = (end_time - start_time) * 1000

    print(f"[4/4] Purge Complete.")
    print(f"      Latency: {latency:.2f} ms")
    print(f"      Final VRAM: {purge_vram} MB")

    if purge_vram <= (baseline + 100):
        print(
            f"\n[RESULT] PASS: Blackwell handled the {active_vram - baseline}MB dump in {latency:.2f}ms."
        )
    else:
        print("\n[RESULT] FAIL: VRAM fragmentation or residual allocation detected.")


if __name__ == "__main__":
    if torch.cuda.is_available():
        run_stress_test()
    else:
        print("CUDA not detected. Ensure torch is installed with CUDA support.")
