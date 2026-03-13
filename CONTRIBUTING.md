# CONTRIBUTING TO PERIDOT

The Peridot Kernel is an open-source, sovereign AI architecture. We are building a system that is 100% local, air-gapped, and ruthlessly protective of its host hardware. 

Contributions are welcome, provided they adhere strictly to the core philosophy: **Build First. Ship Code. No Hype.**

### > ARCHITECTURE RULES

1. **Absolute Sovereignty (Zero Cloud):** PRs introducing external APIs (OpenAI, Anthropic, telemetry trackers, etc.) will be immediately rejected. Peridot does not phone home.
2. **Security by Design:** We employ a strict Defense-in-Depth model. Any new features must route through the `core_system/security.py` gatekeeper. PRs that bypass input sanitization or API authentication will not be merged.
3. **The VRAM State Machine:** VRAM is precious. Enhancements to the Medical Research (Folding@Home) module must maintain a strict sub-500ms latency for hardware handoffs. Inference always takes priority.
4. **Hardware Agnosticism:** Code should default to CPU/RAM gracefully if specific GPU architectures (CUDA/ROCm) are unavailable.

### > DEVELOPMENT WORKFLOW

1. **Fork & Clone:** Fork the repository and set up your local virtual environment.
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt --upgrade