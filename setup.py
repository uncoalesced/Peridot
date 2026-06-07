#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
PERIDOT SETUP WIZARD v1.5.1 - TURBOQUANT
Intelligent hardware detection, VRAM profiling, and engine configuration
Supports NVIDIA GPUs, AMD GPUs, and CPU-only fallback
"""

import os
import sys
import platform
import subprocess
import json
import time
import secrets
from pathlib import Path
from typing import Dict
import urllib.request

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    banner = f"""
{Colors.CYAN}{'='*70}
{Colors.BOLD}
██████╗ ███████╗██████╗ ██╗██████╗  ██████╗ ████████╗
██╔══██╗██╔════╝██╔══██╗██║██╔══██╗██╔═══██╗╚══██╔══╝
██████╔╝█████╗  ██████╔╝██║██║  ██║██║   ██║   ██║   
██╔═══╝ ██╔══╝  ██╔══██╗██║██║  ██║██║   ██║   ██║   
██║     ███████╗██║  ██║██║██████╔╝╚██████╔╝   ██║   
╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝╚═════╝  ╚═════╝    ╚═╝   
{Colors.ENDC}
{Colors.GREEN}       SETUP WIZARD v1.5.1 (TURBOQUANT) - SOVEREIGN AI KERNEL{Colors.ENDC}
{Colors.CYAN}{'='*70}{Colors.ENDC}

{Colors.YELLOW}Engineered by uncoalesced{Colors.ENDC}
    """
    print(banner)

def wait_for_enter(message="Press ENTER to continue...", allow_cancel=True):
    print(f"\n{Colors.CYAN}{message} {'(or ESC to cancel)' if allow_cancel else ''}{Colors.ENDC}")
    if os.name == 'nt':
        import msvcrt
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b'\r': return True
                elif key == b'\x1b' and allow_cancel: return False
    else:
        import termios, tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                key = sys.stdin.read(1)
                if key in ['\r', '\n']: return True
                elif key == '\x1b' and allow_cancel: return False
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def get_numeric_choice(prompt: str, min_val: int, max_val: int) -> int:
    while True:
        try:
            print(f"\n{Colors.YELLOW}{prompt}{Colors.ENDC}")
            choice = int(input(f"{Colors.GREEN}Enter your choice ({min_val}-{max_val}): {Colors.ENDC}"))
            if min_val <= choice <= max_val: return choice
            print(f"{Colors.RED}[ERROR] Please enter a number between {min_val} and {max_val}{Colors.ENDC}")
        except ValueError:
            print(f"{Colors.RED}[ERROR] Please enter a valid number{Colors.ENDC}")
        except KeyboardInterrupt:
            print(f"\n{Colors.RED}[CANCELLED] Setup cancelled by user{Colors.ENDC}")
            sys.exit(0)

class HardwareDetector:
    def __init__(self):
        self.system_info = {
            'os': platform.system(),
            'architecture': platform.machine(),
            'python_version': platform.python_version(),
            'ram_gb': 0,
            'gpu_vendor': None,
            'gpu_name': None,
            'gpu_memory_gb': 0,
            'cuda_available': False,
        }
        
    def detect_system_ram(self):
        try:
            import psutil
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "-q"])
            import psutil
        self.system_info['ram_gb'] = round(psutil.virtual_memory().total / (1024**3), 2)
    
    def detect_nvidia_gpu(self) -> bool:
        try:
            import pynvml
            pynvml.nvmlInit()
            if pynvml.nvmlDeviceGetCount() > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                name = pynvml.nvmlDeviceGetName(handle)
                self.system_info['gpu_name'] = name.decode('utf-8') if isinstance(name, bytes) else name
                self.system_info['gpu_memory_gb'] = round(pynvml.nvmlDeviceGetMemoryInfo(handle).total / (1024**3), 2)
                self.system_info['gpu_vendor'] = 'NVIDIA'
                self.system_info['cuda_available'] = True
                pynvml.nvmlShutdown()
                return True
        except: pass
        return False
    
    def detect_hardware(self) -> Dict:
        print(f"\n{Colors.CYAN}[→] Detecting system hardware...{Colors.ENDC}")
        self.detect_system_ram()
        print(f"{Colors.GREEN}[✓] RAM: {self.system_info['ram_gb']} GB{Colors.ENDC}")
        
        if self.detect_nvidia_gpu():
            print(f"{Colors.GREEN}[✓] GPU: {self.system_info['gpu_name']} ({self.system_info['gpu_memory_gb']} GB){Colors.ENDC}")
        else:
            print(f"{Colors.YELLOW}[!] No NVIDIA GPU detected - Falling back to CPU mode{Colors.ENDC}")
            self.system_info['gpu_vendor'] = 'CPU'
            self.system_info['gpu_name'] = 'CPU Only'
        return self.system_info

class HardwareProfile:
    PROFILES = {
        'nvidia_8gb_deep': {
            'name': 'NVIDIA 8GB+ (Deep Thinker Profile)',
            'vram_min': 8,
            'recommended_model': 'llama3-8b-iq3',
            'expected_speed': '50-60 t/s',
            'backend': 'cuda',
        },
        'nvidia_8gb_agile': {
            'name': 'NVIDIA 8GB+ (Agile/Medical Research Profile)',
            'vram_min': 8,
            'recommended_model': 'qwen2.5-3b',
            'expected_speed': '90-110 t/s',
            'backend': 'cuda',
        },
        'nvidia_12gb_plus': {
            'name': 'NVIDIA 12GB+ (Heavy Profile)',
            'vram_min': 12,
            'recommended_model': 'llama3-8b-q4',
            'expected_speed': '60+ t/s',
            'backend': 'cuda',
        },
        'nvidia_low_vram': {
            'name': 'NVIDIA 4-6GB (Speed Demon Profile)',
            'vram_min': 4,
            'recommended_model': 'llama3.2-1b',
            'expected_speed': '100+ t/s',
            'backend': 'cuda',
        },
        'cpu_standard': {
            'name': 'CPU Only Fallback',
            'vram_min': 0,
            'recommended_model': 'llama3.2-1b',
            'expected_speed': '10-20 t/s',
            'backend': 'cpu',
        },
    }
    
    MODELS = {
        'llama3-8b-iq3': {
            'name': 'Llama 3 8B Instruct (IQ3_XXS) [Deep Thinker]',
            'file': 'Meta-Llama-3-8B-Instruct-IQ3_XXS.gguf',
            'url': 'https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF/resolve/main/Meta-Llama-3-8B-Instruct-IQ3_XXS.gguf',
            'size_gb': 3.6,
            'description': 'Maximum intelligence. Consumes ~4.7GB VRAM.',
        },
        'qwen2.5-3b': {
            'name': 'Qwen 2.5 3B Instruct (Q4_K_M) [Agile / Daily Driver]',
            'file': 'qwen2.5-3b-instruct-q4_k_m.gguf',
            'url': 'https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf',
            'size_gb': 2.2,
            'description': 'Blistering speed. Leaves massive VRAM overhead for Folding@home.',
        },
        'llama3-8b-q4': {
            'name': 'Llama 3 8B Instruct (Q4_K_M) [Heavy]',
            'file': 'Meta-Llama-3-8B-Instruct.Q4_K_M.gguf',
            'url': 'https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF/resolve/main/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf',
            'size_gb': 4.7,
            'description': 'Standard quality. Requires 12GB+ VRAM for safe operation.',
        },
        'llama3.2-1b': {
            'name': 'Llama 3.2 1B Instruct (Q8_0) [Speed Demon]',
            'file': 'Llama-3.2-1B-Instruct-Q8_0.gguf',
            'url': 'https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q8_0.gguf',
            'size_gb': 1.3,
            'description': 'Extremely lightweight. Perfect for CPU or 4GB GPUs.',
        },
    }
    
    @staticmethod
    def auto_select_profile(sys_info: Dict) -> str:
        vram = sys_info.get('gpu_memory_gb', 0)
        if sys_info.get('gpu_vendor') == 'NVIDIA':
            if vram >= 12: return 'nvidia_12gb_plus'
            if vram >= 8: return 'nvidia_8gb_deep'
            return 'nvidia_low_vram'
        return 'cpu_standard'

def download_model(model_id: str, install_dir: Path) -> bool:
    model_info = HardwareProfile.MODELS[model_id]
    models_dir = install_dir / 'models'
    models_dir.mkdir(exist_ok=True)
    model_path = models_dir / model_info['file']
    
    if model_path.exists():
        print(f"{Colors.GREEN}[✓] Model already exists: {model_info['name']}{Colors.ENDC}")
        return True
        
    print(f"\n{Colors.YELLOW}Downloading: {model_info['name']} ({model_info['size_gb']} GB){Colors.ENDC}")
    if not wait_for_enter("Start download?"): return False
    
    try:
        def progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = min(100, (downloaded / total_size) * 100)
            bar = '█' * int(50 * downloaded // total_size) + '-' * (50 - int(50 * downloaded // total_size))
            print(f'\r{Colors.GREEN}[↓] |{bar}| {percent:.1f}%{Colors.ENDC}', end='')
            
        urllib.request.urlretrieve(model_info['url'], model_path, progress)
        print(f"\n{Colors.GREEN}[✓] Download complete!{Colors.ENDC}")
        return True
    except Exception as e:
        print(f"\n{Colors.RED}[ERROR] Download failed: {e}{Colors.ENDC}")
        if model_path.exists(): model_path.unlink()
        return False

def install_dependencies(profile_id: str) -> bool:
    backend = HardwareProfile.PROFILES[profile_id]['backend']
    print(f"\n{Colors.CYAN}[→] Installing TurboQuant architecture dependencies...{Colors.ENDC}")
    
    core_packages = ['flask', 'flask-cors', 'requests', 'psutil', 'pynvml', 'websocket-client', 'python-dotenv']
    for pkg in core_packages:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])
        
    if backend == 'cuda':
        print(f"{Colors.CYAN}[→] Binding CUDA acceleration...{Colors.ENDC}")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "llama-cpp-python", 
            "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cu121", "-q"
        ])
    else:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "llama-cpp-python", "-q"])
        
    print(f"{Colors.GREEN}[✓] Dependencies locked.{Colors.ENDC}")
    return True

def create_environment(install_dir: Path) -> bool:
    """Generates the .env file with strict OS-level owner-only permissions (0o600)."""
    env_path = install_dir / '.env'
    if env_path.exists():
        print(f"{Colors.GREEN}[✓] Security perimeter (.env) already exists.{Colors.ENDC}")
        return True
        
    api_key = secrets.token_hex(16)
    env_content = f"""# PERIDOT SOVEREIGN KERNEL - SECURITY PERIMETER
HF_HUB_OFFLINE=1
API_KEY={api_key}
"""
    try:
        # Security Upgrade: Lock file permissions to Owner Read/Write only (600)
        # This prevents other users or local processes from reading the loopback key.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        mode = 0o600
        fd = os.open(env_path, flags, mode)
        with os.fdopen(fd, 'w') as f:
            f.write(env_content)
            
        print(f"{Colors.GREEN}[✓] Cryptographic handshake initialized (.env locked to OS user).{Colors.ENDC}")
        return True
    except Exception as e:
        print(f"{Colors.RED}[ERROR] Failed to lock environment: {e}{Colors.ENDC}")
        return False

def main():
    try:
        clear_screen()
        print_banner()
        if not wait_for_enter("Initialize Setup?"): sys.exit(0)
        
        install_dir = Path.cwd()
        
        # Hardware Detection
        clear_screen()
        print_banner()
        sys_info = HardwareDetector().detect_hardware()
        wait_for_enter("Hardware detection complete. Continue?", allow_cancel=False)
        
        # Profile Selection Phase
        vram = sys_info.get('gpu_memory_gb', 0)
        vendor = sys_info.get('gpu_vendor')

        clear_screen()
        print_banner()

        if vendor == 'NVIDIA' and vram >= 8:
            print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
            print(f"{Colors.BOLD}ENGINE TUNING: INTELLIGENCE VS. SPEED{Colors.ENDC}")
            print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}\n")
            
            print(f"{Colors.YELLOW}Your {vram}GB GPU supports multiple execution paths. Choose your primary directive:{Colors.ENDC}\n")
            
            print(f" 1. {Colors.BOLD}DEEP THINKER (High Quality, Slower){Colors.ENDC}")
            print(f"    {Colors.CYAN}Engine:{Colors.ENDC} Llama 3 8B (IQ3_XXS) | ~60 t/s | ~4.7GB VRAM")
            print(f"    {Colors.GREEN}Pros:{Colors.ENDC} Maximum semantic depth. Strict RAG document citation. Highly accurate.")
            print(f"    {Colors.RED}Cons:{Colors.ENDC} Consumes more VRAM, leaving less overhead for background Folding@home.\n")
            
            print(f" 2. {Colors.BOLD}AGILE / DAILY DRIVER (Blistering Fast, Lower Precision){Colors.ENDC}")
            print(f"    {Colors.CYAN}Engine:{Colors.ENDC} Qwen 2.5 3B (Q4_K_M) | ~100+ t/s | ~2.7GB VRAM")
            print(f"    {Colors.GREEN}Pros:{Colors.ENDC} Instantaneous generation. Leaves massive 5GB+ VRAM buffer for maximum medical research throughput.")
            print(f"    {Colors.RED}Cons:{Colors.ENDC} Smaller parameter count. May hallucinate on complex multi-document RAG queries.\n")

            print(f" 3. {Colors.BOLD}MANUAL MATRIX OVERRIDE{Colors.ENDC}")
            print(f"    {Colors.YELLOW}Show all raw hardware profiles.{Colors.ENDC}\n")

            choice = get_numeric_choice("Select Execution Path:", 1, 3)

            if choice == 1:
                selected = 'nvidia_12gb_plus' if vram >= 12 else 'nvidia_8gb_deep'
            elif choice == 2:
                selected = 'nvidia_8gb_agile'
            else:
                profiles = list(HardwareProfile.PROFILES.items())
                for idx, (pid, p) in enumerate(profiles, 1):
                    print(f" {idx}. {p['name']} -> {HardwareProfile.MODELS[p['recommended_model']]['name']}")
                selected = profiles[get_numeric_choice("Select Profile:", 1, len(profiles)) - 1][0]
        else:
            print(f"\n{Colors.GREEN}Select Configuration Mode:{Colors.ENDC}")
            print(" 1. Auto-Detect (Recommended)")
            print(" 2. Manual Matrix Override")
            
            if get_numeric_choice("Mode:", 1, 2) == 1:
                selected = HardwareProfile.auto_select_profile(sys_info)
            else:
                profiles = list(HardwareProfile.PROFILES.items())
                for idx, (pid, p) in enumerate(profiles, 1):
                    print(f" {idx}. {p['name']} -> {HardwareProfile.MODELS[p['recommended_model']]['name']}")
                selected = profiles[get_numeric_choice("Select Profile:", 1, len(profiles)) - 1][0]
            
        profile = HardwareProfile.PROFILES[selected]
        model_id = profile['recommended_model']
        
        clear_screen()
        print_banner()
        if not download_model(model_id, install_dir): sys.exit(1)
        if not install_dependencies(selected): sys.exit(1)
        if not create_environment(install_dir): sys.exit(1)
        
        clear_screen()
        print_banner()
        print(f"{Colors.BOLD}{Colors.GREEN}SYSTEM INITIALIZATION COMPLETE{Colors.ENDC}\n")
        print(f"{Colors.YELLOW}Important Configuration Note:{Colors.ENDC}")
        print(f"Open {Colors.CYAN}config.py{Colors.ENDC} and ensure ACTIVE_MODEL_NAME matches:")
        print(f"-> {HardwareProfile.MODELS[model_id]['file']}\n")
        print(f"{Colors.GREEN}To ignite the kernel: python launcher.py{Colors.ENDC}\n")
        
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}[CANCELLED] Setup interrupted.{Colors.ENDC}")
        sys.exit(0)

if __name__ == "__main__":
    main()