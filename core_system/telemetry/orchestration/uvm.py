import os
from core_system.audit import ghost

def premap_weights_uvm():
    os.environ["GGML_CUDA_ENABLE_UNIFIED_MEMORY"] = "1"
    ghost.info("[ZAT-SCS | UVM] Unified Virtual Memory pre-mapping tables initialized.")
