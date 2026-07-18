<div align="center">

# PERIDOT | MEDICAL RESEARCH INTEGRATION

### Folding@Home Runtime Integration — v1.5.3-STABLE

*Inference First. Distributed Compute Second.*

</div>

---

# `> OVERVIEW`

The Medical Research Module utilizes the Folding@Home (FAH) v8 Client to donate idle GPU compute toward disease research:
- Cancer
- Alzheimer's
- Parkinson's

---

## Critical Architecture Rule

The Peridot Neural Engine is sovereign.

Inference always takes absolute priority.

To enforce this, the module communicates directly with the FAH client through local WebSockets:

```text
Port 7396
```

This architecture enables:
- sub-21ms hardware handoff
- direct VRAM arbitration
- immediate pause signaling

The FAH client is paused the exact millisecond the user submits a prompt.

---

# `> QUICK START`

---

## 1. Engine Initialization (`server.py`)

The VRAM State Machine is localized entirely within:

```text
server.py
```

to prevent IPC latency.

Add the following to the server boot sequence:

```python
from core_system.research import MedicalResearchModule

# Initialize and mount to the Neural Engine
research_module = MedicalResearchModule()

if research_module.enabled:
    research_module.mount_to_engine()
```

---

## 2. Core Routing (`core.py`)

Ensure the command router can trigger manual override states.

```python
def handle_research_command(args):
    """Routes explicit user commands to the FAH WebSocket."""
    if not args:
        return research_module.get_telemetry()
    elif args[0] == 'enable':
        return research_module.enable()
    elif args[0] == 'disable':
        return research_module.disable()
    elif args[0] == 'stats':
        return research_module.get_formatted_stats()
    elif args[0] == 'force-fold':
        return research_module.force_state("fold")
    elif args[0] == 'force-pause':
        return research_module.force_state("pause")

# Register command
command_registry['research'] = handle_research_command
```

---

# `> CONFIGURATION`

## `medical_research_config.json`

The module dynamically generates this file during first boot.

```json
{
  "enabled": true,
  "user": "uncoalesced_node",
  "team": "267960",
  "power_level": "full",
  "websocket_port": 7396,
  "handshake_timeout_ms": 50,
  "total_uptime_hours": 12.5
}
```

---

## Note

```text
Team 267960
```

is the designated collective identifier for uncoalesced nodes.

---

# `> WEBSOCKET API REFERENCE`

The `MedicalResearchModule` interacts with the FAH client using strict JSON payloads.

---

## Hardware Handoff (The Context Loop)

When:

```text
server.py
```

receives a:

```text
/ask
```

request, it must execute the pause payload before loading the Llama-3 KV Cache.

```python
# Inside the inference route
def execute_inference(prompt):
    # 1. Fire the WebSocket Pause Payload (21ms latency)
    research_module.suspend_for_inference()

    # 2. Allocate VRAM and Generate
    response = llama_model.generate(prompt)

    # 3. Release hardware back to FAH
    research_module.resume_folding()

    return response
```

---

## Stats Dictionary

Telemetry is pulled synchronously from the WebSocket through:

```text
get_telemetry()
```

```python
{
    'status': 'ONLINE',
    'state': 'PAUSED_FOR_INFERENCE', # or 'FOLDING'
    'gpu': 'NVIDIA GeForce RTX 5050',
    'vram_gb': 8.0,
    'points_earned': 125000,
    'current_project': 'Project 14536 (Cancer)',
    'progress_percent': 42.5,
    'latency_ms': 18
}
```

---

# `> TROUBLESHOOTING`

---

## 1. WebSocket Connection Refused

If the engine throws:

```text
ConnectionRefusedError: [WinError 10061]
```

### Verify The Following

- Ensure the F@H v8 Web Client is installed and actively running in the Windows background.
- Verify:

```text
websocket_port
```

inside:

```text
medical_research_config.json
```

matches the active FAH client configuration.

Default:

```text
7396
```

---

## 2. Missing Dependency

If you encounter:

```text
ModuleNotFoundError: No module named 'websocket'
```

your environment namespace is poisoned.

Execute:

```bash
.\venv\Scripts\python.exe -m pip uninstall -y websocket
.\venv\Scripts\python.exe -m pip uninstall -y websocket-client
.\venv\Scripts\python.exe -m pip install websocket-client
```

---

## 3. VRAM Handoff Failure (CUDA OOM)

If the LLM crashes with:

```text
CUDA out of memory
```

during inference:

The FAH client did not release VRAM fast enough.

Increase:

```text
handshake_timeout_ms
```

inside the configuration file from:

```text
50
```

to:

```text
150
```

This gives the FAH core additional time to gracefully pause before the LLM forcefully allocates the generation buffer.

---

<div align="center">

`PERIDOT MEDICAL RESEARCH MODULE` · `v1.5.3`

**Engineered by uncoalesced**

*Distributed Compute.*  
*Inference Sovereignty.*  
*Hardware-Aware Orchestration.*

</div>