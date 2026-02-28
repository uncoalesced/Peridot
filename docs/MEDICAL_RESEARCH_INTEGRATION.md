# Medical Research Module - Integration Guide

## Quick Start

### 1. Add to main.py

Add this to the top of your `main.py`:

```python
from medical_research import init_medical_research, start_medical_research_monitoring
```

Add this in your initialization section (before main loop):

```python
# Initialize medical research module
research_module = init_medical_research()

# Start monitoring if enabled
if research_module.enabled:
    start_medical_research_monitoring(research_module)
```

### 2. Add to UI Commands

Add these commands to your command router:

```python
# In commandrouter.py or wherever you handle commands

def handle_research_command(args):
    """Handle medical research commands"""
    if not args:
        research_module.print_stats()
    elif args[0] == 'enable':
        research_module.enable()
        research_module.start_monitoring()
    elif args[0] == 'disable':
        research_module.disable()
    elif args[0] == 'stats':
        research_module.print_stats()
    elif args[0] == 'start':
        research_module.force_start()
    elif args[0] == 'stop':
        research_module.force_stop()

# Register command
commands['research'] = handle_research_command
```

### 3. Standalone Testing (Before Integration)

Test the module independently:

```bash
# Setup wizard
python medical_research.py setup

# View stats
python medical_research.py stats

# Start monitoring (runs until Ctrl+C)
python medical_research.py start

# Stop
python medical_research.py stop
```

### 4. Configuration File

The module creates `medical_research_config.json`:

```json
{
  "enabled": true,
  "user": "YourUsername",
  "team": "267960",
  "power_level": "full",
  "first_run": false,
  "total_uptime_hours": 123.5,
  "install_date": "2026-02-08T12:00:00"
}
```

You can manually edit this if needed.

## Full Integration Example

Here's how your `main.py` might look:

```python
# main.py

import sys
from core import PeridotCore
from ui import PeridotUI
from medical_research import init_medical_research, start_medical_research_monitoring

def main():
    print("="*70)
    print("PERIDOT - SOVEREIGN AI ASSISTANT")
    print("="*70)
    
    # Initialize core systems
    peridot = PeridotCore()
    ui = PeridotUI(peridot)
    
    # Initialize medical research (will auto-setup on first run)
    research = init_medical_research()
    
    # Start medical research monitoring if enabled
    if research.enabled:
        start_medical_research_monitoring(research)
    
    # Add research stats to Peridot's help
    print("\nMedical Research: Type 'research' for contribution stats")
    
    # Main conversation loop
    try:
        while True:
            user_input = ui.get_input()
            
            if user_input.lower() == 'research':
                research.print_stats()
                continue
            elif user_input.lower() == 'research enable':
                research.enable()
                research.start_monitoring()
                continue
            elif user_input.lower() == 'research disable':
                research.disable()
                continue
            
            # Normal Peridot processing
            response = peridot.process(user_input)
            ui.display_response(response)
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        research.stop_monitoring()
        peridot.shutdown()

if __name__ == "__main__":
    main()
```

## API Reference

### MedicalResearchModule

```python
# Initialize
module = MedicalResearchModule()

# Setup (interactive)
module.setup_interactive()  # Returns True if successful

# Enable/Disable
module.enable()
module.disable()

# Monitoring
module.start_monitoring()  # Starts background thread
module.stop_monitoring()   # Stops background thread

# Manual control
module.force_start()  # Force start FAH
module.force_stop()   # Force stop FAH

# Statistics
stats = module.get_stats()  # Returns dict
module.print_stats()        # Pretty print to console

# Check status
is_idle = module.is_peridot_idle()  # True if GPU < 15% util
```

### Stats Dictionary

```python
{
    'enabled': bool,
    'gpu': str,                      # "NVIDIA GeForce RTX 5050"
    'gpu_type': str,                 # 'nvidia', 'amd', or 'none'
    'vram_gb': float,                # 8.0
    'username': str,                 # "YourUsername"
    'team': str,                     # "267960"
    'work_units_completed': int,     # 42
    'points_earned': int,            # 125000
    'current_project': str,          # "Project 14536"
    'current_disease': str,          # "Cancer"
    'progress': int,                 # 0-100
    'total_runtime_hours': float,    # 123.5
    'install_date': str,             # "2026-02-08T12:00:00"
    'current_state': str,            # 'folding', 'paused', 'unknown'
}
```

## Customization

### Adjust Idle Thresholds

```python
# In your code, after initialization
research.idle_threshold = 0.10  # Start if GPU < 10% (more aggressive)
research.vram_threshold = 1.5   # Start if VRAM < 1.5GB
research.check_interval = 15    # Check every 15 seconds (more responsive)
```

### Change Power Level

```python
# Edit config file directly or:
research.config['power_level'] = 'medium'  # 'light', 'medium', or 'full'
research._save_config()

# Then reconfigure FAH
research.fah_client.configure(
    user=research.config['user'],
    team=research.config['team'],
    gpu_type=research.gpu_type,
    power_level='medium'
)
```

## Logging Integration

Add to your Peridot audit log:

```python
# When FAH starts
log_entry = {
    'timestamp': datetime.now().isoformat(),
    'action': 'medical_research_start',
    'gpu_util_before': gpu_util,
    'state': 'folding'
}

# When FAH pauses
log_entry = {
    'timestamp': datetime.now().isoformat(),
    'action': 'medical_research_pause',
    'gpu_util': gpu_util,
    'state': 'paused',
    'session_hours': session_hours
}
```

## Troubleshooting

### FAH Not Starting

```python
# Check installation
if not research.fah_client.is_installed():
    print("FAH not installed. Run: python medical_research.py setup")

# Check if service is running (Windows)
import subprocess
result = subprocess.run(['sc', 'query', 'FAHClient'], capture_output=True)
print(result.stdout.decode())

# Manual start
research.fah_client.start()
```

### GPU Not Detected

```python
# Test detection
from medical_research import GPUDetector

gpu_type, gpu_name, vram = GPUDetector.detect_gpu()
print(f"Detected: {gpu_name} ({gpu_type}) with {vram}GB VRAM")

# If NVIDIA not detected, check nvidia-smi
subprocess.run(['nvidia-smi'])
```

### Stats Not Updating

```python
# Check log file location
print(f"Log path: {research.fah_client.data_path}")

# Manually read log
log_path = research.fah_client.data_path + '/log.txt'
with open(log_path, 'r') as f:
    print(f.read()[-2000:])  # Last 2000 chars
```

## Team Peridot

Once you have 10+ users, create the official Team Peridot:

1. Go to https://stats.foldingathome.org/team
2. Create team "Peridot" 
3. Get team number (e.g., 267960)
4. Update default team in module:
   ```python
   self.config['team'] = '267960'  # Replace with actual number
   ```

## Performance Impact Testing

Test script to verify zero impact:

```python
import time
from medical_research import GPUDetector

# Baseline (Peridot only)
print("Test 1: Peridot only (run inference for 60s)")
input("Press Enter when ready...")
time.sleep(60)
print(f"GPU Util: {GPUDetector.get_gpu_utilization()*100:.1f}%")
print(f"VRAM: {GPUDetector.get_gpu_memory_used():.1f}GB")

# With FAH (should auto-pause)
print("\nTest 2: Peridot + FAH monitoring (run inference for 60s)")
research.start_monitoring()
input("Press Enter when ready...")
time.sleep(60)
print(f"GPU Util: {GPUDetector.get_gpu_utilization()*100:.1f}%")
print(f"VRAM: {GPUDetector.get_gpu_memory_used():.1f}GB")
print(f"FAH State: {research.last_state}")

# Should show same performance and FAH paused
```

## Next Steps

1. Test standalone: `python medical_research.py setup`
2. Verify FAH is working: `python medical_research.py start`
3. Watch for auto-pause when you open Peridot
4. Integrate into main.py
5. Add to README.md
6. Create Team Peridot on F@H website
