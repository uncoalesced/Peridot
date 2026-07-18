import time
from core_system.telemetry.config.settings import SPECULATIVE_THRESHOLD, INACTIVITY_TIMER
from core_system.telemetry.orchestration.mps import adjust_gpu_mps
from core_system.telemetry.orchestration.uvm import premap_weights_uvm
from core_system.audit import ghost

class SovereignGPUOrchestrator:
    def __init__(self, client, kernel=None):
        self.client = client
        self.kernel = kernel
        self.current_state = "COLD_IDLE"
        self.last_activity_time = time.time()

    def evaluate_probability(self, probability: float):
        current_time = time.time()
        
        if self.current_state == "COLD_IDLE" and probability >= SPECULATIVE_THRESHOLD:
            self._transition_to_speculative()
        elif self.current_state == "SPECULATIVE_PREPARED":
            if probability < SPECULATIVE_THRESHOLD:
                if current_time - self.last_activity_time > INACTIVITY_TIMER:
                    self._transition_to_idle_cooldown()
            else:
                self.last_activity_time = current_time

    def trigger_active_inference(self):
        self.current_state = "ACTIVE_INFERENCE"
        ghost.info("[ZAT-SCS | STATE] Transitioning to ACTIVE_INFERENCE. Suspending F@H.")
        adjust_gpu_mps(0)

    def return_to_idle(self):
        self.current_state = "COLD_IDLE"
        self.last_activity_time = time.time()
        ghost.info("[ZAT-SCS | STATE] Transitioning back to COLD_IDLE.")
        if self.kernel:
            from core_system.kernel import KernelState
            self.kernel.request_state_change(KernelState.IDLE, "ZAT-SCS predictive decay fallback.")
        else:
            adjust_gpu_mps(100)

    def _transition_to_speculative(self):
        self.current_state = "SPECULATIVE_PREPARED"
        self.last_activity_time = time.time()
        ghost.info(f"[ZAT-SCS | STATE] P(I_t) >= {SPECULATIVE_THRESHOLD}. Transitioning to SPECULATIVE_PREPARED.")
        
        if self.kernel:
            # We must import KernelState locally to avoid circular imports if passed
            from core_system.kernel import KernelState
            self.kernel.request_state_change(KernelState.SPECULATIVE_PREPARED, "ZAT-SCS predictive preemption triggered.")
        else:
            adjust_gpu_mps(10)
            premap_weights_uvm()
            self.client.speculative_restore_async()

    def _transition_to_idle_cooldown(self):
        self.current_state = "COLD_IDLE"
        ghost.info("[ZAT-SCS | STATE] Inactivity threshold met. Transitioning to COLD_IDLE.")
        adjust_gpu_mps(100)
        
        if self.kernel:
            from core_system.kernel import KernelState
            self.kernel.request_state_change(KernelState.IDLE, "ZAT-SCS predictive decay fallback.")
