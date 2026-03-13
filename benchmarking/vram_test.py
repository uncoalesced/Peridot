"""
PERIDOT | VRAM HANDOFF BENCHMARK
Measures the exact latency of the Folding@Home WebSocket pause command.
"""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core_system.research import MedicalResearchModule

class MockCore:
    def __init__(self):
        self.last_interaction_time = time.time()

def run_vram_test():
    print("=====================================")
    print("  PERIDOT VRAM LATENCY BENCHMARK")
    print("=====================================\n")
    
    mock_core = MockCore()
    module = MedicalResearchModule(core=mock_core)
    
    if not module.check_installation():
        print("[ERROR] FAHClient not found. Cannot run VRAM benchmark.")
        return

    print("1. Forcing FAHClient to start folding (allocating VRAM)...")
    module.enabled = True
    module.unpause()
    time.sleep(5) # Give the GPU 5 seconds to spool up and grab VRAM
    
    vram_before = module.get_vram_free()
    print(f"  -> Free VRAM while folding: {vram_before}MB")
    
    print("\n2. Simulating User Prompt (Triggering Hardware Interrupt)...")
    start_time = time.time()
    
    # Execute the hot-swap
    module.pause()
    
    # Calculate exact ms latency of the command execution
    latency_ms = (time.time() - start_time) * 1000
    
    # Wait 1 second for the NVIDIA driver to register the purged memory
    time.sleep(1)
    vram_after = module.get_vram_free()
    vram_freed = vram_after - vram_before
    
    print(f"  -> Hot-Swap Command Latency: {latency_ms:.2f}ms")
    print(f"  -> Free VRAM after purge: {vram_after}MB")
    print(f"  -> Total VRAM Recovered: {vram_freed}MB\n")
    
    print("STATUS: BENCHMARK COMPLETE.")

if __name__ == "__main__":
    run_vram_test()