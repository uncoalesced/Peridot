# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.5 (FSM + WATCHDOG)
# Copyright (C) 2026 uncoalesced
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

import threading
import queue
import time
import sys
import pynvml
from enum import Enum, auto

class KernelState(Enum):
    BOOT = auto()
    IDLE = auto()
    FAH_ACTIVE = auto()
    INTERRUPT_WAIT = auto()
    VRAM_PURGE = auto()
    INFERENCE = auto()
    COOLDOWN = auto()
    PANIC = auto()

class SovereignKernel:
    def __init__(self):
        self.state = KernelState.BOOT
        self.state_lock = threading.Lock()
        self.event_queue = queue.Queue()
        self.is_running = True
        
        # Initialize Nvidia Management Library
        try:
            pynvml.nvmlInit()
            self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.gpu_name = pynvml.nvmlDeviceGetName(self.gpu_handle)
            print(f"[HARDWARE] NVML Bound to: {self.gpu_name}")
        except pynvml.NVMLError as e:
            print(f"[FATAL] NVML Initialization failed: {e}")
            sys.exit(1)
            
        print("[KERNEL] v1.5 State Machine Initialized.")

    def request_state_change(self, new_state: KernelState, reason: str = ""):
        with self.state_lock:
            old_state = self.state
            if old_state == KernelState.PANIC and new_state != KernelState.BOOT:
                print(f"[REJECTED] Kernel is in PANIC. Cannot transition to {new_state.name}.")
                return False
                
            self.state = new_state
            print(f"[STATE SHIFT] {old_state.name} -> {new_state.name} | {reason}")
            return True

    def memory_watchdog_daemon(self):
        """Dedicated thread polling RTX 5050 VRAM registers every 100ms."""
        print("[WATCHDOG] VRAM Telemetry Online.")
        
        # Hard limit for 8GB card (leaving buffer for OS)
        CRITICAL_VRAM_MB = 7500 
        
        while self.is_running:
            try:
                info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
                used_vram_mb = info.used / (1024 ** 2)
                
                with self.state_lock:
                    current_state = self.state
                
                # OOM Protection: If we aren't explicitly generating text and VRAM spikes, PANIC.
                if used_vram_mb > CRITICAL_VRAM_MB and current_state not in [KernelState.INFERENCE]:
                    print(f"\n[WATCHDOG ALARM] Unmanaged VRAM spike detected: {used_vram_mb:.0f} MB!")
                    self.event_queue.put("OOM_WARNING")
                    
            except pynvml.NVMLError as e:
                print(f"[WATCHDOG ERROR] Lost contact with GPU: {e}")
                
            time.sleep(0.1) # 100ms polling rate

    def _execute_vram_purge(self):
        """Hardware interrupt with actual VRAM verification."""
        print("[HARDWARE] Sending SIGSTOP to Folding@home daemon...")
        
        # We wait up to 2 seconds for VRAM to physically clear
        timeout = 20  # 20 * 0.1s = 2.0 seconds
        cleared = False
        
        while timeout > 0:
            info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
            used_vram_mb = info.used / (1024 ** 2)
            
            # Assuming FAH purged, VRAM should drop near OS baseline (e.g., < 2000MB)
            if used_vram_mb < 2000:
                cleared = True
                break
                
            time.sleep(0.1)
            timeout -= 1
            
        if cleared:
            print(f"[HARDWARE] VRAM Purge Verified. Current Load: {used_vram_mb:.0f} MB.")
            self.request_state_change(KernelState.INFERENCE, "Hardware cleared for LLM payload.")
        else:
            self.event_queue.put("FAH_HANG_DETECTED")

    def orchestrator_loop(self):
        self.request_state_change(KernelState.IDLE, "Boot sequence complete.")
        
        while self.is_running:
            try:
                event = self.event_queue.get(timeout=1.0)
                
                with self.state_lock:
                    current = self.state
                
                if event == "PROMPT_RECEIVED":
                    if current in [KernelState.IDLE, KernelState.FAH_ACTIVE]:
                        self.request_state_change(KernelState.INTERRUPT_WAIT, "Inference requested.")
                        self.request_state_change(KernelState.VRAM_PURGE, "Initiating hardware handoff.")
                        self._execute_vram_purge()
                        
                elif event == "INFERENCE_COMPLETE":
                    self.request_state_change(KernelState.COOLDOWN, "LLM Payload unloaded.")
                    time.sleep(2)
                    self.request_state_change(KernelState.IDLE, "Returning to standby.")
                    
                elif event == "FAH_HANG_DETECTED":
                    self.request_state_change(KernelState.PANIC, "FAH failed to release VRAM. Aborting inference to prevent OOM crash.")
                    
                elif event == "OOM_WARNING":
                    self.request_state_change(KernelState.PANIC, "External memory pressure breached critical threshold.")
                    
                elif event == "SHUTDOWN":
                    self.is_running = False
                    print("[KERNEL] Graceful shutdown initiated.")
                    
            except queue.Empty:
                pass

    def start(self):
        # Ignite the FSM core
        self.core_thread = threading.Thread(target=self.orchestrator_loop, daemon=True)
        self.core_thread.start()
        
        # Ignite the Watchdog
        self.watchdog_thread = threading.Thread(target=self.memory_watchdog_daemon, daemon=True)
        self.watchdog_thread.start()

# --- TESTING THE FSM + WATCHDOG ---
if __name__ == "__main__":
    kernel = SovereignKernel()
    kernel.start()
    
    time.sleep(1)
    
    # 1. Normal execution
    print("\n>>> SIMULATING USER PROMPT >>>")
    kernel.event_queue.put("PROMPT_RECEIVED")
    time.sleep(3)
    kernel.event_queue.put("INFERENCE_COMPLETE")
    
    time.sleep(2)
    
    # 2. Shut it down
    kernel.event_queue.put("SHUTDOWN")
    kernel.core_thread.join()