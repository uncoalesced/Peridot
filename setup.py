# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
PERIDOT SETUP WIZARD v1.3
Intelligent hardware detection and configuration system
Supports NVIDIA GPUs, AMD GPUs, and CPU-only inference

"""

import os
import sys
import platform
import subprocess
import json
import time
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import urllib.request
import hashlib

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    """Display Peridot setup banner"""
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
{Colors.GREEN}           SETUP WIZARD v1.3 - SOVEREIGN AI KERNEL{Colors.ENDC}
{Colors.CYAN}{'='*70}{Colors.ENDC}

{Colors.YELLOW}Engineered by uncoalesced{Colors.ENDC}
    """
    print(banner)

def wait_for_enter(message="Press ENTER to continue...", allow_cancel=True):
    """Wait for user to press enter, optionally allow ESC to cancel"""
    if allow_cancel:
        print(f"\n{Colors.CYAN}{message} (or ESC to cancel){Colors.ENDC}")
    else:
        print(f"\n{Colors.CYAN}{message}{Colors.ENDC}")
    
    if os.name == 'nt':  # Windows
        import msvcrt
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b'\r':  # Enter
                    return True
                elif key == b'\x1b' and allow_cancel:  # ESC
                    return False
    else:  # Unix/Linux/Mac
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                key = sys.stdin.read(1)
                if key == '\r' or key == '\n':  # Enter
                    return True
                elif key == '\x1b' and allow_cancel:  # ESC
                    return False
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def get_numeric_choice(prompt: str, min_val: int, max_val: int) -> int:
    """Get a numeric choice from user within a range"""
    while True:
        try:
            print(f"\n{Colors.YELLOW}{prompt}{Colors.ENDC}")
            choice = input(f"{Colors.GREEN}Enter your choice ({min_val}-{max_val}): {Colors.ENDC}")
            choice = int(choice)
            if min_val <= choice <= max_val:
                return choice
            else:
                print(f"{Colors.RED}[ERROR] Please enter a number between {min_val} and {max_val}{Colors.ENDC}")
        except ValueError:
            print(f"{Colors.RED}[ERROR] Please enter a valid number{Colors.ENDC}")
        except KeyboardInterrupt:
            print(f"\n{Colors.RED}[CANCELLED] Setup cancelled by user{Colors.ENDC}")
            sys.exit(0)

class HardwareDetector:
    """Detect system hardware capabilities"""
    
    def __init__(self):
        self.system_info = {
            'os': platform.system(),
            'os_version': platform.version(),
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'ram_gb': 0,
            'gpu_vendor': None,
            'gpu_name': None,
            'gpu_memory_gb': 0,
            'cuda_available': False,
            'rocm_available': False,
        }
        
    def detect_system_ram(self) -> float:
        """Detect total system RAM in GB"""
        try:
            import psutil
            ram_bytes = psutil.virtual_memory().total
            ram_gb = ram_bytes / (1024**3)
            self.system_info['ram_gb'] = round(ram_gb, 2)
            return ram_gb
        except ImportError:
            print(f"{Colors.YELLOW}[WARNING] psutil not installed, installing...{Colors.ENDC}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil", "-q"])
            import psutil
            ram_bytes = psutil.virtual_memory().total
            ram_gb = ram_bytes / (1024**3)
            self.system_info['ram_gb'] = round(ram_gb, 2)
            return ram_gb
    
    def detect_nvidia_gpu(self) -> bool:
        """Detect NVIDIA GPU and get details"""
        try:
            # Try pynvml first
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            
            if device_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                gpu_name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(gpu_name, bytes):
                    gpu_name = gpu_name.decode('utf-8')
                
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_memory_gb = mem_info.total / (1024**3)
                
                self.system_info['gpu_vendor'] = 'NVIDIA'
                self.system_info['gpu_name'] = gpu_name
                self.system_info['gpu_memory_gb'] = round(gpu_memory_gb, 2)
                self.system_info['cuda_available'] = True
                
                pynvml.nvmlShutdown()
                return True
                
        except ImportError:
            # Try nvidia-smi as fallback
            try:
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                if result.stdout:
                    parts = result.stdout.strip().split(',')
                    gpu_name = parts[0].strip()
                    gpu_memory_mb = int(parts[1].strip().split()[0])
                    gpu_memory_gb = gpu_memory_mb / 1024
                    
                    self.system_info['gpu_vendor'] = 'NVIDIA'
                    self.system_info['gpu_name'] = gpu_name
                    self.system_info['gpu_memory_gb'] = round(gpu_memory_gb, 2)
                    self.system_info['cuda_available'] = True
                    return True
                    
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        except Exception:
            pass
            
        return False
    
    def detect_amd_gpu(self) -> bool:
        """Detect AMD GPU (basic detection)"""
        try:
            # Try rocm-smi
            result = subprocess.run(
                ['rocm-smi', '--showproductname'],
                capture_output=True,
                text=True,
                check=True
            )
            
            if result.stdout and 'GPU' in result.stdout:
                # Basic AMD detection
                self.system_info['gpu_vendor'] = 'AMD'
                self.system_info['gpu_name'] = 'AMD Radeon (ROCm Compatible)'
                self.system_info['rocm_available'] = True
                return True
                
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Check Windows for AMD GPU
        if self.system_info['os'] == 'Windows':
            try:
                result = subprocess.run(
                    ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                if 'AMD' in result.stdout or 'Radeon' in result.stdout:
                    for line in result.stdout.split('\n'):
                        if 'AMD' in line or 'Radeon' in line:
                            self.system_info['gpu_vendor'] = 'AMD'
                            self.system_info['gpu_name'] = line.strip()
                            return True
            except:
                pass
                
        return False
    
    def detect_hardware(self) -> Dict:
        """Run full hardware detection"""
        print(f"\n{Colors.CYAN}[→] Detecting system hardware...{Colors.ENDC}")
        
        # Detect RAM
        self.detect_system_ram()
        print(f"{Colors.GREEN}[✓] RAM: {self.system_info['ram_gb']} GB{Colors.ENDC}")
        
        # Detect GPU
        if self.detect_nvidia_gpu():
            print(f"{Colors.GREEN}[✓] GPU: {self.system_info['gpu_name']} ({self.system_info['gpu_memory_gb']} GB){Colors.ENDC}")
        elif self.detect_amd_gpu():
            print(f"{Colors.GREEN}[✓] GPU: {self.system_info['gpu_name']}{Colors.ENDC}")
        else:
            print(f"{Colors.YELLOW}[!] No compatible GPU detected - CPU mode available{Colors.ENDC}")
            self.system_info['gpu_vendor'] = 'CPU'
            self.system_info['gpu_name'] = 'CPU Only'
        
        return self.system_info

class HardwareProfile:
    """Hardware configuration profiles"""
    
    PROFILES = {
        'nvidia_rtx_50': {
            'name': 'NVIDIA RTX 50 Series (8GB+)',
            'vram_min': 8,
            'recommended_model': 'llama3-8b-q4',
            'context_window': 8192,
            'expected_speed': '45-55 t/s',
            'backend': 'cuda',
        },
        'nvidia_rtx_40': {
            'name': 'NVIDIA RTX 40 Series (8GB+)',
            'vram_min': 8,
            'recommended_model': 'llama3-8b-q4',
            'context_window': 8192,
            'expected_speed': '50-70 t/s',
            'backend': 'cuda',
        },
        'nvidia_rtx_30': {
            'name': 'NVIDIA RTX 30 Series (6-8GB)',
            'vram_min': 6,
            'recommended_model': 'llama3-8b-q4',
            'context_window': 8192,
            'expected_speed': '40-60 t/s',
            'backend': 'cuda',
        },
        'nvidia_rtx_20': {
            'name': 'NVIDIA RTX 20 Series (6-8GB)',
            'vram_min': 6,
            'recommended_model': 'llama3-8b-q4',
            'context_window': 4096,
            'expected_speed': '30-45 t/s',
            'backend': 'cuda',
        },
        'nvidia_gtx_16': {
            'name': 'NVIDIA GTX 16 Series (4-6GB)',
            'vram_min': 4,
            'recommended_model': 'llama3-8b-q3',
            'context_window': 4096,
            'expected_speed': '25-35 t/s',
            'backend': 'cuda',
        },
        'amd_rdna3': {
            'name': 'AMD RDNA3 (RX 7000 Series)',
            'vram_min': 8,
            'recommended_model': 'llama3-8b-q4',
            'context_window': 8192,
            'expected_speed': '35-50 t/s',
            'backend': 'rocm',
        },
        'amd_rdna2': {
            'name': 'AMD RDNA2 (RX 6000 Series)',
            'vram_min': 6,
            'recommended_model': 'llama3-8b-q4',
            'context_window': 4096,
            'expected_speed': '30-45 t/s',
            'backend': 'rocm',
        },
        'cpu_high_end': {
            'name': 'CPU Only (High-End)',
            'vram_min': 0,
            'recommended_model': 'phi3-mini-q4',
            'context_window': 2048,
            'expected_speed': '8-15 t/s',
            'backend': 'cpu',
        },
        'cpu_standard': {
            'name': 'CPU Only (Standard)',
            'vram_min': 0,
            'recommended_model': 'phi3-mini-q4',
            'context_window': 2048,
            'expected_speed': '5-10 t/s',
            'backend': 'cpu',
        },
    }
    
    MODELS = {
        'llama3-8b-q4': {
            'name': 'Llama-3-8B-Instruct (Q4_K_M)',
            'file': 'Meta-Llama-3-8B-Instruct.Q4_K_M.gguf',
            'url': 'https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF/resolve/main/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf',
            'size_gb': 4.7,
            'vram_required': 6,
            'description': 'Best quality for 6GB+ VRAM',
        },
        'llama3-8b-q3': {
            'name': 'Llama-3-8B-Instruct (Q3_K_M)',
            'file': 'Meta-Llama-3-8B-Instruct.Q3_K_M.gguf',
            'url': 'https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF/resolve/main/Meta-Llama-3-8B-Instruct-Q3_K_M.gguf',
            'size_gb': 3.5,
            'vram_required': 4,
            'description': 'Balanced quality for 4-6GB VRAM',
        },
        'phi3-mini-q4': {
            'name': 'Phi-3-Mini-4K-Instruct (Q4_K_M)',
            'file': 'Phi-3-mini-4k-instruct.Q4_K_M.gguf',
            'url': 'https://huggingface.co/bartowski/Phi-3-mini-4k-instruct-GGUF/resolve/main/Phi-3-mini-4k-instruct-Q4_K_M.gguf',
            'size_gb': 2.4,
            'vram_required': 2,
            'description': 'Lightweight for CPU or low VRAM',
        },
    }
    
    @staticmethod
    def auto_select_profile(system_info: Dict) -> str:
        """Automatically select best profile based on detected hardware"""
        gpu_name = system_info.get('gpu_name', '').upper()
        gpu_memory = system_info.get('gpu_memory_gb', 0)
        gpu_vendor = system_info.get('gpu_vendor')
        
        if gpu_vendor == 'NVIDIA':
            if 'RTX 50' in gpu_name or 'RTX50' in gpu_name:
                return 'nvidia_rtx_50'
            elif 'RTX 40' in gpu_name or 'RTX40' in gpu_name:
                return 'nvidia_rtx_40'
            elif 'RTX 30' in gpu_name or 'RTX30' in gpu_name:
                return 'nvidia_rtx_30'
            elif 'RTX 20' in gpu_name or 'RTX20' in gpu_name:
                return 'nvidia_rtx_20'
            elif 'GTX 16' in gpu_name or 'GTX16' in gpu_name:
                return 'nvidia_gtx_16'
            elif gpu_memory >= 8:
                return 'nvidia_rtx_30'
            elif gpu_memory >= 6:
                return 'nvidia_rtx_20'
            elif gpu_memory >= 4:
                return 'nvidia_gtx_16'
                
        elif gpu_vendor == 'AMD':
            if 'RX 7' in gpu_name or 'RX7' in gpu_name:
                return 'amd_rdna3'
            elif 'RX 6' in gpu_name or 'RX6' in gpu_name:
                return 'amd_rdna2'
            else:
                return 'amd_rdna2'
        
        # Default to CPU mode
        ram_gb = system_info.get('ram_gb', 0)
        if ram_gb >= 16:
            return 'cpu_high_end'
        else:
            return 'cpu_standard'

def select_peridot_directory() -> Path:
    """Interactive directory selection for Peridot installation"""
    clear_screen()
    print_banner()
    print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}STEP 1: SELECT PERIDOT INSTALLATION DIRECTORY{Colors.ENDC}")
    print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}\n")
    
    # Get current directory
    current_dir = Path.cwd()
    
    print(f"{Colors.YELLOW}Current directory: {Colors.ENDC}{current_dir}")
    print(f"\n{Colors.GREEN}Options:{Colors.ENDC}")
    print(f"  1. Use current directory (recommended)")
    print(f"  2. Enter custom path")
    
    choice = get_numeric_choice("Select installation directory option:", 1, 2)
    
    if choice == 1:
        install_dir = current_dir
    else:
        while True:
            custom_path = input(f"\n{Colors.GREEN}Enter full path to Peridot directory: {Colors.ENDC}").strip()
            install_dir = Path(custom_path)
            
            if install_dir.exists():
                break
            else:
                print(f"{Colors.RED}[ERROR] Directory does not exist: {install_dir}{Colors.ENDC}")
                create = input(f"{Colors.YELLOW}Create this directory? (y/n): {Colors.ENDC}").lower()
                if create == 'y':
                    try:
                        install_dir.mkdir(parents=True, exist_ok=True)
                        break
                    except Exception as e:
                        print(f"{Colors.RED}[ERROR] Could not create directory: {e}{Colors.ENDC}")
    
    # Confirm directory
    print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.YELLOW}Installation directory selected:{Colors.ENDC}")
    print(f"{Colors.BOLD}{install_dir}{Colors.ENDC}")
    print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}")
    
    if not wait_for_enter("Confirm installation directory?"):
        print(f"{Colors.RED}[CANCELLED] Setup cancelled by user{Colors.ENDC}")
        sys.exit(0)
    
    return install_dir

def download_model(model_id: str, install_dir: Path) -> bool:
    """Download model file with progress bar"""
    model_info = HardwareProfile.MODELS[model_id]
    models_dir = install_dir / 'models'
    models_dir.mkdir(exist_ok=True)
    
    model_path = models_dir / model_info['file']
    
    # Check if model already exists
    if model_path.exists():
        print(f"{Colors.GREEN}[✓] Model already exists: {model_info['name']}{Colors.ENDC}")
        return True
    
    print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.YELLOW}Downloading model: {model_info['name']}{Colors.ENDC}")
    print(f"{Colors.YELLOW}Size: {model_info['size_gb']} GB{Colors.ENDC}")
    print(f"{Colors.YELLOW}This may take 10-30 minutes depending on your connection...{Colors.ENDC}")
    print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}\n")
    
    if not wait_for_enter("Start download?"):
        print(f"{Colors.RED}[CANCELLED] Download cancelled{Colors.ENDC}")
        return False
    
    try:
        def download_progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = min(100, (downloaded / total_size) * 100)
            bar_length = 50
            filled_length = int(bar_length * downloaded // total_size)
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            
            print(f'\r{Colors.GREEN}[↓] Progress: |{bar}| {percent:.1f}% ({downloaded_mb:.1f}/{total_mb:.1f} MB){Colors.ENDC}', end='')
        
        print(f"{Colors.CYAN}[→] Downloading from HuggingFace...{Colors.ENDC}")
        urllib.request.urlretrieve(model_info['url'], model_path, download_progress)
        print(f"\n{Colors.GREEN}[✓] Download complete!{Colors.ENDC}")
        return True
        
    except Exception as e:
        print(f"\n{Colors.RED}[ERROR] Download failed: {e}{Colors.ENDC}")
        if model_path.exists():
            model_path.unlink()
        return False

def install_dependencies(profile_id: str, install_dir: Path) -> bool:
    """Install Python dependencies based on hardware profile"""
    profile = HardwareProfile.PROFILES[profile_id]
    backend = profile['backend']
    
    print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}INSTALLING DEPENDENCIES{Colors.ENDC}")
    print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}\n")
    
    print(f"{Colors.YELLOW}Backend: {backend.upper()}{Colors.ENDC}")
    print(f"{Colors.YELLOW}This will install required Python packages...{Colors.ENDC}\n")
    
    if not wait_for_enter("Begin dependency installation?"):
        print(f"{Colors.RED}[CANCELLED] Installation cancelled{Colors.ENDC}")
        return False
    
    try:
        # Core dependencies
        print(f"\n{Colors.CYAN}[→] Installing core dependencies...{Colors.ENDC}")
        core_packages = [
            'flask',
            'flask-cors',
            'requests',
            'psutil',
            'pynvml',
            'websocket-client',
            'filelock',
            'diskcache',
            'Pillow',
        ]
        
        for package in core_packages:
            print(f"{Colors.GREEN}  [→] Installing {package}...{Colors.ENDC}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])
        
        # Backend-specific installations
        if backend == 'cuda':
            print(f"\n{Colors.CYAN}[→] Installing CUDA-accelerated llama-cpp-python...{Colors.ENDC}")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "llama-cpp-python",
                "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cu121",
                "-q"
            ])
            
        elif backend == 'rocm':
            print(f"\n{Colors.CYAN}[→] Installing ROCm-accelerated llama-cpp-python...{Colors.ENDC}")
            print(f"{Colors.YELLOW}[!] ROCm support requires manual compilation{Colors.ENDC}")
            print(f"{Colors.YELLOW}[!] Installing CPU version as fallback...{Colors.ENDC}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "llama-cpp-python", "-q"])
            
        else:  # CPU
            print(f"\n{Colors.CYAN}[→] Installing CPU-optimized llama-cpp-python...{Colors.ENDC}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "llama-cpp-python", "-q"])
        
        # Optional: RAG dependencies
        print(f"\n{Colors.CYAN}[→] Installing RAG pipeline dependencies...{Colors.ENDC}")
        rag_packages = ['faiss-cpu', 'sentence-transformers', 'torch', 'pymupdf']
        for package in rag_packages:
            print(f"{Colors.GREEN}  [→] Installing {package}...{Colors.ENDC}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])
        
        print(f"\n{Colors.GREEN}[✓] All dependencies installed successfully!{Colors.ENDC}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n{Colors.RED}[ERROR] Dependency installation failed: {e}{Colors.ENDC}")
        return False

def create_config(profile_id: str, model_id: str, install_dir: Path) -> bool:
    """Create Peridot configuration file"""
    profile = HardwareProfile.PROFILES[profile_id]
    model_info = HardwareProfile.MODELS[model_id]
    
    config = {
        "version": "1.3",
        "hardware_profile": profile_id,
        "model": {
            "name": model_info['name'],
            "file": model_info['file'],
            "path": f"models/{model_info['file']}",
            "context_window": profile['context_window'],
        },
        "inference": {
            "backend": profile['backend'],
            "gpu_layers": -1 if profile['backend'] in ['cuda', 'rocm'] else 0,
            "threads": os.cpu_count() or 4,
        },
        "server": {
            "host": "localhost",
            "port": 5000,
            "api_key": "08101954",
        },
        "constitution": {
            "allow_file_read": True,
            "allow_file_write": False,
            "allow_code_execute": False,
            "allow_web_fetch": True,
        }
    }
    
    config_path = install_dir / 'config.json'
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"{Colors.GREEN}[✓] Configuration file created: config.json{Colors.ENDC}")
        return True
        
    except Exception as e:
        print(f"{Colors.RED}[ERROR] Could not create config: {e}{Colors.ENDC}")
        return False

def create_constitution(install_dir: Path) -> bool:
    """Create default constitution.json"""
    constitution = {
        "system_prompt": "You are Peridot, a sovereign AI assistant running entirely on local hardware. You have no connection to external servers or cloud services. You respect user privacy and operate transparently within the permissions granted to you.",
        "allow_file_read": True,
        "allow_file_write": False,
        "allow_code_execute": False,
        "allow_web_fetch": True,
        "approved_domains": ["arxiv.org", "pubmed.ncbi.nlm.nih.gov"],
        "blocked_domains": []
    }
    
    constitution_path = install_dir / 'constitution.json'
    
    try:
        with open(constitution_path, 'w') as f:
            json.dump(constitution, f, indent=2)
        
        print(f"{Colors.GREEN}[✓] Constitution file created: constitution.json{Colors.ENDC}")
        return True
        
    except Exception as e:
        print(f"{Colors.RED}[ERROR] Could not create constitution: {e}{Colors.ENDC}")
        return False

def display_hardware_summary(system_info: Dict):
    """Display detected hardware in formatted table"""
    print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}DETECTED HARDWARE{Colors.ENDC}")
    print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}\n")
    
    print(f"{Colors.GREEN}Operating System:{Colors.ENDC}  {system_info['os']} {system_info['architecture']}")
    print(f"{Colors.GREEN}Python Version:{Colors.ENDC}    {system_info['python_version']}")
    print(f"{Colors.GREEN}RAM:{Colors.ENDC}               {system_info['ram_gb']} GB")
    
    if system_info['gpu_vendor'] in ['NVIDIA', 'AMD']:
        print(f"{Colors.GREEN}GPU:{Colors.ENDC}               {system_info['gpu_name']}")
        if system_info['gpu_memory_gb'] > 0:
            print(f"{Colors.GREEN}VRAM:{Colors.ENDC}              {system_info['gpu_memory_gb']} GB")
        if system_info['cuda_available']:
            print(f"{Colors.GREEN}CUDA:{Colors.ENDC}              Available")
        if system_info['rocm_available']:
            print(f"{Colors.GREEN}ROCm:{Colors.ENDC}              Available")
    else:
        print(f"{Colors.YELLOW}GPU:{Colors.ENDC}               None detected - CPU mode")
    
    print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}")

def display_profile_selection(profiles: Dict, current_selection: str):
    """Display hardware profile selection menu"""
    print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}SELECT HARDWARE PROFILE{Colors.ENDC}")
    print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}\n")
    
    print(f"{Colors.GREEN}Available profiles:{Colors.ENDC}\n")
    
    profile_list = list(profiles.items())
    for idx, (profile_id, profile) in enumerate(profile_list, 1):
        selected = " ← RECOMMENDED" if profile_id == current_selection else ""
        print(f"  {idx}. {profile['name']}")
        print(f"     Expected speed: {profile['expected_speed']}")
        print(f"     Model: {HardwareProfile.MODELS[profile['recommended_model']]['name']}{Colors.YELLOW}{selected}{Colors.ENDC}")
        print()
    
    return profile_list

def main():
    """Main setup wizard flow"""
    try:
        # Welcome screen
        clear_screen()
        print_banner()
        print(f"{Colors.YELLOW}Welcome to the Peridot Setup Wizard!{Colors.ENDC}\n")
        print(f"This wizard will:")
        print(f"  • Detect your hardware")
        print(f"  • Select optimal configuration")
        print(f"  • Download the AI model")
        print(f"  • Install dependencies")
        print(f"  • Configure Peridot for your system\n")
        
        if not wait_for_enter("Ready to begin?"):
            print(f"{Colors.RED}[CANCELLED] Setup cancelled{Colors.ENDC}")
            sys.exit(0)
        
        # Step 1: Select installation directory
        install_dir = select_peridot_directory()
        
        # Step 2: Hardware detection
        clear_screen()
        print_banner()
        print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
        print(f"{Colors.BOLD}STEP 2: HARDWARE DETECTION{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}")
        
        detector = HardwareDetector()
        system_info = detector.detect_hardware()
        
        display_hardware_summary(system_info)
        
        wait_for_enter("Hardware detection complete. Continue?", allow_cancel=False)
        
        # Step 3: Profile selection
        clear_screen()
        print_banner()
        
        auto_profile = HardwareProfile.auto_select_profile(system_info)
        
        print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
        print(f"{Colors.BOLD}STEP 3: CONFIGURATION MODE{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}\n")
        
        print(f"{Colors.GREEN}Select configuration mode:{Colors.ENDC}\n")
        print(f"  1. Automatic (Recommended)")
        print(f"  2. Manual selection\n")
        
        mode_choice = get_numeric_choice("Select mode:", 1, 2)
        
        if mode_choice == 1:
            selected_profile = auto_profile
            print(f"\n{Colors.GREEN}[→] Auto-selected: {HardwareProfile.PROFILES[selected_profile]['name']}{Colors.ENDC}")
        else:
            profile_list = display_profile_selection(HardwareProfile.PROFILES, auto_profile)
            choice = get_numeric_choice("Select hardware profile:", 1, len(profile_list))
            selected_profile = profile_list[choice - 1][0]
        
        profile = HardwareProfile.PROFILES[selected_profile]
        
        # Step 4: Model selection confirmation
        clear_screen()
        print_banner()
        
        print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
        print(f"{Colors.BOLD}STEP 4: MODEL SELECTION{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}\n")
        
        model_id = profile['recommended_model']
        model_info = HardwareProfile.MODELS[model_id]
        
        print(f"{Colors.YELLOW}Selected configuration:{Colors.ENDC}\n")
        print(f"  Hardware Profile: {profile['name']}")
        print(f"  Model: {model_info['name']}")
        print(f"  Download Size: {model_info['size_gb']} GB")
        print(f"  Context Window: {profile['context_window']} tokens")
        print(f"  Expected Speed: {profile['expected_speed']}")
        print(f"  Backend: {profile['backend'].upper()}\n")
        
        if not wait_for_enter("Confirm configuration?"):
            print(f"{Colors.RED}[CANCELLED] Setup cancelled{Colors.ENDC}")
            sys.exit(0)
        
        # Step 5: Download model
        clear_screen()
        print_banner()
        
        print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
        print(f"{Colors.BOLD}STEP 5: MODEL DOWNLOAD{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}")
        
        if not download_model(model_id, install_dir):
            print(f"{Colors.RED}[ERROR] Model download failed{Colors.ENDC}")
            sys.exit(1)
        
        # Step 6: Install dependencies
        clear_screen()
        print_banner()
        
        print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
        print(f"{Colors.BOLD}STEP 6: DEPENDENCY INSTALLATION{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}")
        
        if not install_dependencies(selected_profile, install_dir):
            print(f"{Colors.RED}[ERROR] Dependency installation failed{Colors.ENDC}")
            sys.exit(1)
        
        # Step 7: Create configuration files
        clear_screen()
        print_banner()
        
        print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
        print(f"{Colors.BOLD}STEP 7: CONFIGURATION{Colors.ENDC}")
        print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}\n")
        
        print(f"{Colors.CYAN}[→] Creating configuration files...{Colors.ENDC}\n")
        
        if not create_config(selected_profile, model_id, install_dir):
            print(f"{Colors.RED}[ERROR] Configuration creation failed{Colors.ENDC}")
            sys.exit(1)
        
        if not create_constitution(install_dir):
            print(f"{Colors.RED}[ERROR] Constitution creation failed{Colors.ENDC}")
            sys.exit(1)
        
        # Final summary
        clear_screen()
        print_banner()
        
        print(f"\n{Colors.GREEN}{'='*70}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.GREEN}SETUP COMPLETE!{Colors.ENDC}")
        print(f"{Colors.GREEN}{'='*70}{Colors.ENDC}\n")
        
        print(f"{Colors.YELLOW}Installation summary:{Colors.ENDC}\n")
        print(f"  Location: {install_dir}")
        print(f"  Profile: {profile['name']}")
        print(f"  Model: {model_info['name']}")
        print(f"  Expected Performance: {profile['expected_speed']}\n")
        
        print(f"{Colors.GREEN}To launch Peridot:{Colors.ENDC}\n")
        print(f"  {Colors.CYAN}python launcher.py{Colors.ENDC}\n")
        
        print(f"{Colors.YELLOW}Configuration files created:{Colors.ENDC}\n")
        print(f"  • config.json")
        print(f"  • constitution.json")
        print(f"  • models/{model_info['file']}\n")
        
        print(f"{Colors.GREEN}{'='*70}{Colors.ENDC}\n")
        
    except KeyboardInterrupt:
        print(f"\n\n{Colors.RED}[CANCELLED] Setup interrupted by user{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n{Colors.RED}[ERROR] Unexpected error: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
