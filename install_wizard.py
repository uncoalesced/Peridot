#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

# NOTE: this file was named setup.py until the v1.5.4 cleanup. It is an
# interactive first-run installer, not packaging metadata -- it contains no
# setuptools.setup() call. Because pyproject.toml declares
# build-backend = "setuptools.build_meta", setuptools' run_setup() exec'd this
# file with __name__ == "__main__" on every wheel build, which launched the
# wizard mid-build and failed with a UnicodeEncodeError on the banner.
# Renaming it fixes the build. Run it directly:  python install_wizard.py

"""
PERIDOT SETUP WIZARD v1.6.1-beta
Hardware detection, model selection, engine build, and first-run configuration.
Supports NVIDIA GPUs and CPU-only fallback.

Steps: hardware scan -> profile -> model pick (core_system.modelfit: top 3
for this machine, a live Hugging Face repo check, or the built-in list) ->
dependencies (requirements.txt, then the engine: source build for the 27B or
the stock wheel) -> resumable model download ->
optional web search plugin -> .env -> summary with launch and
Sovereign Invocation (MCP) instructions.
"""

import os
import re
import sys
import platform
import subprocess
import secrets
import shutil
from pathlib import Path
from typing import Dict, Optional

# modelfit is stdlib-only, so it is importable before requirements.txt installs.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core_system import modelfit  # noqa: E402

class Colors:
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
{Colors.GREEN}     SETUP WIZARD v1.6.1-beta [AGENTIC] - SOVEREIGN LOCAL AI KERNEL{Colors.ENDC}
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
    """Thin wrapper over core_system.modelfit.detect() (stdlib only: no psutil/pynvml)."""

    def detect_hardware(self) -> Dict:
        print(f"\n{Colors.CYAN}[SYS] Detecting system hardware...{Colors.ENDC}")
        hw = modelfit.detect()
        nvidia = hw.backend == 'cuda'
        self.system_info = {
            'os': platform.system(),
            'architecture': platform.machine(),
            'python_version': platform.python_version(),
            'ram_gb': round(hw.ram_gb, 2),
            'gpu_vendor': 'NVIDIA' if nvidia else ('GPU' if hw.has_gpu else 'CPU'),
            'gpu_name': hw.gpu_name or 'CPU Only',
            'gpu_memory_gb': round(hw.vram_gb, 2),
            'cuda_available': nvidia,
            'hw': hw,
        }
        print(f"{Colors.GREEN}[OK] RAM: {hw.ram_gb:.1f} GB ({hw.ram_avail_gb:.1f} GB free){Colors.ENDC}")
        if hw.has_gpu:
            print(f"{Colors.GREEN}[OK] GPU: {hw.gpu_name} ({hw.vram_gb:.1f} GB, {hw.backend}){Colors.ENDC}")
        if not nvidia:
            print(f"{Colors.YELLOW}[WARN] No NVIDIA GPU detected - Falling back to CPU mode{Colors.ENDC}")
        return self.system_info

class HardwareProfile:
    PROFILES = {
        'nvidia_8gb_deep': {
            'name': 'NVIDIA 8GB+ (Deep Thinker Profile)',
            'vram_min': 8,
            'recommended_model': 'qwen3.8-27b-iq1s',
            'expected_speed': '~24 t/s',
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
            'recommended_model': 'qwen3.8-27b-iq1s',
            'expected_speed': '~24 t/s',
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
        'qwen3.8-27b-iq1s': {
            'name': 'Qwen 3.8 27B (UD-IQ1_S) [Deep Thinker]',
            'file': 'Qwen3.8-27B-UD-IQ1_S.gguf',
            'url': 'https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-UD-IQ1_S.gguf',
            'size_gb': 6.2,
            'description': 'Kernel default. Needs the source-built llama-cpp-python (scripts/build_llama_cpp_python.ps1).',
        },
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

def _progress(done: int, total: int) -> None:
    if not total:
        print(f'\r{Colors.GREEN}[DL] {done / 1024**3:.2f} GB{Colors.ENDC}', end='')
        return
    pct = min(100.0, done * 100 / total)
    bar = '█' * int(pct / 2) + '-' * (50 - int(pct / 2))
    print(f'\r{Colors.GREEN}[DL] |{bar}| {pct:.1f}%{Colors.ENDC}', end='')

def _plan_from_fit(fit, kind: str = 'gguf') -> dict:
    """Download plan for a modelfit result. GGUFs land flat in models/; snapshots in models/<name>/."""
    if kind == 'safetensors':
        folder = fit.repo.split('/')[1]
        return {'kind': 'hf', 'repo': fit.repo, 'files': fit.files, 'size_gb': fit.size_gb,
                'subdir': folder, 'active': folder, 'name': fit.repo}
    return {'kind': 'hf', 'repo': fit.repo, 'files': fit.files, 'size_gb': fit.size_gb,
            'subdir': '', 'active': fit.file, 'name': fit.name}

def _legacy_plan(model_id: str) -> dict:
    return {'kind': 'legacy', 'model_id': model_id, 'active': HardwareProfile.MODELS[model_id]['file']}

def _manual_plan() -> dict:
    models = list(HardwareProfile.MODELS.items())
    print()
    for idx, (_, m) in enumerate(models, 1):
        print(f" {idx}. {m['name']} ({m['size_gb']} GB)")
    print(f" {len(models) + 1}. None - I will put my own GGUF in models/")
    choice = get_numeric_choice("Select Model:", 1, len(models) + 1)
    if choice <= len(models):
        return _legacy_plan(models[choice - 1][0])
    name = input(f"{Colors.GREEN}GGUF filename (inside models/): {Colors.ENDC}").strip()
    return {'kind': 'none', 'active': name or HardwareProfile.MODELS['qwen2.5-3b']['file']}

def _check_repo_plan(hw) -> Optional[dict]:
    repo = input(f"{Colors.GREEN}Hugging Face repo id (e.g. bartowski/Qwen2.5-7B-Instruct-GGUF): {Colors.ENDC}").strip()
    try:
        res = modelfit.check_repo(repo, hw)
    except (OSError, ValueError) as e:
        print(f"{Colors.RED}[ERROR] {e}{Colors.ENDC}")
        return None
    print(f"\n{res.repo} [{res.kind}]")
    for f in res.candidates[:12]:
        print(('* ' if f is res.chosen else '  ') + f.row())
    if not res.chosen:
        print(f"{Colors.YELLOW}[WARN] Nothing in this repo fits this machine (or it has no GGUF/safetensors).{Colors.ENDC}")
        return None
    if res.kind == 'safetensors':
        print(f"{Colors.YELLOW}Note: safetensors models run on the transformers engine (beta, unquantized); "
              f"a -GGUF repo is faster and smaller.{Colors.ENDC}")
    if not wait_for_enter(f"Use {res.chosen.file}?"):
        return None
    return _plan_from_fit(res.chosen, res.kind)

def choose_model(hw, default_model_id: str) -> dict:
    """Model step: modelfit's top 3 for this machine, the profile default, a live repo check, or manual."""
    print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}MODEL SELECTION{Colors.ENDC}")
    print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}\n")
    print(hw.summary())
    print(f"\n{Colors.CYAN}[SYS] Ranking models for this machine (asks Hugging Face for the exact files)...{Colors.ENDC}")
    try:
        picks = [p for p in modelfit.recommend(hw, 3, resolve=True) if p.files]
    except Exception as e:  # catalog missing/corrupt: the built-in list still works
        print(f"{Colors.YELLOW}[WARN] Recommendation failed: {e}{Colors.ENDC}")
        picks = []
    if not picks:
        print(f"{Colors.YELLOW}[WARN] Hugging Face unreachable - use the profile default or the built-in list.{Colors.ENDC}")
    print()
    for idx, p in enumerate(picks, 1):
        print(f" {idx}. {Colors.BOLD}{p.name}{Colors.ENDC}")
        print(f"    {p.file} | {p.size_gb:.1f} GB | fit: {p.level} ({p.mode}) | ~{p.tps:.0f} tok/s")
    n = len(picks)
    print(f" {n + 1}. Profile default: {HardwareProfile.MODELS[default_model_id]['name']}")
    print(f" {n + 2}. Check a Hugging Face repo id")
    print(f" {n + 3}. Skip / manual (built-in list or your own file)")
    while True:
        choice = get_numeric_choice("Select Model:", 1, n + 3)
        if choice <= n:
            return _plan_from_fit(picks[choice - 1])
        if choice == n + 1:
            return _legacy_plan(default_model_id)
        if choice == n + 3:
            return _manual_plan()
        plan = _check_repo_plan(hw)
        if plan:
            return plan

def download_model(plan: dict, install_dir: Path) -> bool:
    """
    First-run model acquisition.

    This is the installer, not the kernel: it runs once, in its own process,
    before dependencies (including huggingface_hub) are guaranteed present, so
    it fetches over plain urllib via core_system.modelfit (resumable: a failed or
    interrupted download keeps its .part file). The running kernel never
    downloads anything -- see core_system/model_fetch.py for the
    subprocess-isolated path used after install.
    """
    if plan['kind'] == 'none':
        return True
    models_dir = install_dir / 'models'
    models_dir.mkdir(exist_ok=True)
    if plan['kind'] == 'legacy':
        info = HardwareProfile.MODELS[plan['model_id']]
        name, size_gb, targets = info['name'], info['size_gb'], [models_dir / info['file']]
    else:
        dest = models_dir / plan['subdir']
        name, size_gb, targets = plan['name'], plan['size_gb'], [dest / f for f in plan['files']]

    if all(t.exists() for t in targets):
        print(f"{Colors.GREEN}[OK] Model already exists: {name}{Colors.ENDC}")
        return True

    print(f"\n{Colors.YELLOW}Downloading: {name} ({size_gb:.1f} GB){Colors.ENDC}")
    if not wait_for_enter("Start download?"): return False

    try:
        if plan['kind'] == 'legacy':
            modelfit.download(info['url'], targets[0], progress=_progress)
        else:
            modelfit.download_repo_files(plan['repo'], plan['files'], dest, progress=_progress,
                                         total_bytes=int(plan['size_gb'] * 1024**3))
        print(f"\n{Colors.GREEN}[OK] Download complete!{Colors.ENDC}")
        return True
    except (OSError, ValueError) as e:
        print(f"\n{Colors.RED}[ERROR] Download failed: {e}{Colors.ENDC}")
        print(f"{Colors.YELLOW}Partial data kept as .part - rerun the wizard to resume.{Colors.ENDC}")
        return False

def build_llama_from_source(install_dir: Path) -> bool:
    """The 27B default needs the source build; the PyPI wheel cannot load it."""
    if os.name != 'nt':
        return False
    print(f"\n{Colors.YELLOW}The 27B model needs llama-cpp-python built from source (~20-25 min, needs CUDA toolkit + MSVC).{Colors.ENDC}")
    if not wait_for_enter("Build now? (cancel = fall back to Qwen 2.5 3B)"):
        return False
    try:
        subprocess.check_call([
            "powershell", "-ExecutionPolicy", "Bypass",
            "-File", str(install_dir / "scripts" / "build_llama_cpp_python.ps1"),
        ])
        return True
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"{Colors.RED}[ERROR] Source build failed: {e}{Colors.ENDC}")
        return False

def needs_source_build(name: str) -> bool:
    """Qwen3.5+ (GGUF arch qwen35) is newer than the stock llama-cpp-python wheel."""
    # ponytail: name match; read general.architecture from the GGUF header if more archs need it.
    return bool(re.search(r"qwen3\.[5-9]", name.lower()))

def install_dependencies(profile_id: str, model_id: Optional[str], install_dir: Path,
                         source_build: bool = False) -> Optional[str]:
    """Installs deps; returns the model to use (falls back to the 3B if a needed source build fails).
    model_id is None when the model came from modelfit / a repo check; source_build marks such a
    pick as needing the native engine."""
    backend = HardwareProfile.PROFILES[profile_id]['backend']
    print(f"\n{Colors.CYAN}[SYS] Installing Peridot dependencies (requirements.txt)...{Colors.ENDC}")

    # Everything except the engine, which is built or installed below. Installing
    # the pinned stock llama-cpp-python here would overwrite a native build.
    req = install_dir / 'requirements.txt'
    filtered = install_dir / 'storage' / '.requirements.no-engine.txt'
    filtered.parent.mkdir(exist_ok=True)
    lines = [ln for ln in req.read_text(encoding='utf-8').splitlines()
             if not ln.strip().lower().startswith(('llama_cpp_python', 'llama-cpp-python'))]
    filtered.write_text("\n".join(lines) + "\n", encoding='utf-8')
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(filtered), "-q"])

    needs_build = model_id == 'qwen3.8-27b-iq1s' or source_build
    if needs_build and build_llama_from_source(install_dir):
        print(f"{Colors.GREEN}[OK] Dependencies locked.{Colors.ENDC}")
        return model_id
    if needs_build:
        print(f"{Colors.YELLOW}[WARN] Stock wheel cannot load this model. Falling back to Qwen 2.5 3B.{Colors.ENDC}")
        model_id = 'qwen2.5-3b'

    if backend == 'cuda':
        print(f"{Colors.CYAN}[SYS] Binding CUDA acceleration...{Colors.ENDC}")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "llama-cpp-python",
            "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cu124", "-q"
        ])
    else:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "llama-cpp-python", "-q"])

    print(f"{Colors.GREEN}[OK] Dependencies locked.{Colors.ENDC}")
    return model_id

def create_environment(install_dir: Path, model_file: str) -> bool:
    """Generates the .env file with strict OS-level owner-only permissions (0o600)."""
    env_path = install_dir / '.env'
    if env_path.exists():
        # Pin the installed model; config.py's default (27B) needs the source build.
        if 'ACTIVE_MODEL_NAME=' not in env_path.read_text():
            with open(env_path, 'a') as f:
                f.write(f"\nACTIVE_MODEL_NAME={model_file}\n")
        print(f"{Colors.GREEN}[OK] Security perimeter (.env) already exists.{Colors.ENDC}")
        return True
        
    api_key = secrets.token_hex(32)
    env_content = f"""# PERIDOT SOVEREIGN KERNEL - SECURITY PERIMETER
# The kernel is air-gapped: config.py force-sets both flags at boot regardless
# of what is written here. Post-install model fetches run in an isolated child
# process via `python -m core_system.model_fetch <repo_id> <filename>`.
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
API_KEY={api_key}
ACTIVE_MODEL_NAME={model_file}
"""
    try:
        # Security Upgrade: Lock file permissions to Owner Read/Write only (600)
        # This prevents other users or local processes from reading the loopback key.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        mode = 0o600
        fd = os.open(env_path, flags, mode)
        with os.fdopen(fd, 'w') as f:
            f.write(env_content)
            
        print(f"{Colors.GREEN}[OK] Cryptographic handshake initialized (.env locked to OS user).{Colors.ENDC}")
        return True
    except Exception as e:
        print(f"{Colors.RED}[ERROR] Failed to lock environment: {e}{Colors.ENDC}")
        return False

def _approve_bundled_plugin(name: str) -> bool:
    """Pre-approve a plugin we ship; the registry owns the hash + storage/settings.json write."""
    try:
        from core_system.extensions.registry import approve
        if approve(name):
            return True
        reason = "plugin not found by the registry"
    except Exception as e:  # registry missing/older, or config import failed this early
        reason = str(e)
    print(f"{Colors.YELLOW}[WARN] Could not pre-approve '{name}' ({reason}). Approve it in the Extensions tab.{Colors.ENDC}")
    return False

def setup_web_search(install_dir: Path) -> None:
    """Optional opt-in: copy the bundled web_search plugin. It stays off until web.enabled is turned on."""
    print(f"\n{Colors.CYAN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}OPTIONAL: WEB SEARCH (BETA){Colors.ENDC}")
    print(f"{Colors.CYAN}{'='*70}{Colors.ENDC}\n")
    print("Lets the model search the web (DuckDuckGo, or your own SearXNG) and read public pages.")
    print(f"{Colors.YELLOW}Off by default even when installed:{Colors.ENDC} turn it on later with the web.enabled setting.")
    print(f"{Colors.RED}When enabled, your search queries and fetched URLs leave this machine.{Colors.ENDC}")
    print("It runs in the plugin sandbox with network access only, no file access.")
    if not wait_for_enter("Install web search? ENTER = install"):
        print(f"{Colors.YELLOW}[SKIP] Web search not installed. Peridot stays fully offline.{Colors.ENDC}")
        return
    src = install_dir / 'core_system' / 'extensions' / 'bundled' / 'web_search'
    dst = install_dir / 'extensions' / 'plugins' / 'web_search'
    try:
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    except OSError as e:
        print(f"{Colors.RED}[ERROR] Could not install web search plugin: {e}{Colors.ENDC}")
        return
    print(f"{Colors.GREEN}[OK] Web search plugin installed to {dst} (disabled until web.enabled is on).{Colors.ENDC}")
    if _approve_bundled_plugin('web_search'):
        print(f"{Colors.GREEN}[OK] Web search plugin pre-approved.{Colors.ENDC}")

def print_summary(install_dir: Path, model_file: str) -> None:
    """Closing screen: what was set up and how to use the v1.6.0 features."""
    web = (install_dir / 'extensions' / 'plugins' / 'web_search').is_dir()
    mcp_cmd = f'claude mcp add peridot -- "{sys.executable}" "{install_dir / "mcp" / "peridot_mcp.py"}"'
    print(f"{Colors.BOLD}{Colors.GREEN}SETUP COMPLETE{Colors.ENDC}\n")
    print(f"Active model:  {Colors.CYAN}{model_file}{Colors.ENDC}  (change it later in Settings -> Model swap)")
    print(f"Web search:    {Colors.CYAN}{'installed, off until you switch WEB on' if web else 'not installed (Extensions tab -> Install bundled web search)'}{Colors.ENDC}")
    print(f"Extensions:    {Colors.CYAN}{install_dir / 'extensions'}{Colors.ENDC}  (skills/ and plugins/; plugins need approval)\n")
    print(f"{Colors.GREEN}Start Peridot:{Colors.ENDC}  {sys.executable} launcher.py\n")
    print(f"{Colors.YELLOW}Sovereign Invocation (optional):{Colors.ENDC} let Claude Code, Codex or Gemini CLI hand")
    print("private-data jobs to your local model. Allowlist a folder in Settings, then run:")
    print(f"  {Colors.CYAN}{mcp_cmd}{Colors.ENDC}")
    print("Codex / Gemini CLI setup: mcp/README.md\n")


def main():
    try:
        clear_screen()
        print_banner()
        if not wait_for_enter("Initialize Setup?"): sys.exit(0)

        if sys.prefix == sys.base_prefix:
            print(f"\n{Colors.YELLOW}[WARN] Not running inside a virtual environment. Peridot's packages will go into")
            print(f"your global Python. Recommended: python -m venv venv, activate it, then rerun this wizard.{Colors.ENDC}")
            if not wait_for_enter("Continue anyway?"): sys.exit(0)

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
            print(f"    {Colors.CYAN}Engine:{Colors.ENDC} Qwen 3.8 27B (UD-IQ1_S) | ~24 t/s decode, ~500 t/s prefill | ~6GB VRAM")
            print(f"    {Colors.GREEN}Pros:{Colors.ENDC} Largest model that fits fully on an 8GB card. Native reasoning and tool use (skills, plugins, web search).")
            print(f"    {Colors.RED}Cons:{Colors.ENDC} ~20-25 min source build of llama-cpp-python. 1.6-bit quant: occasional slips. Little VRAM left for Folding@home while loaded.\n")
            
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

        clear_screen()
        print_banner()
        plan = choose_model(sys_info['hw'], profile['recommended_model'])

        clear_screen()
        print_banner()
        if plan['kind'] == 'legacy':
            # The 27B needs the source-built engine; install_dependencies may fall back to 3B.
            plan = _legacy_plan(install_dependencies(selected, plan['model_id'], install_dir))
        else:
            fallback = install_dependencies(selected, None, install_dir,
                                            source_build=needs_source_build(plan['name'] + plan['active']))
            if fallback:
                plan = _legacy_plan(fallback)
        if not download_model(plan, install_dir): sys.exit(1)
        setup_web_search(install_dir)
        if not create_environment(install_dir, plan['active']): sys.exit(1)

        clear_screen()
        print_banner()
        print_summary(install_dir, plan['active'])
        
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}[CANCELLED] Setup interrupted.{Colors.ENDC}")
        sys.exit(0)

if __name__ == "__main__":
    main()