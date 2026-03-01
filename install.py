import os
import sys
import subprocess
import platform
import shutil

# --- CONFIGURATION ---
MODELS = {
    "1": {
        "name": "Peridot Lite (Phi-3 Mini)",
        "repo": "microsoft/Phi-3-mini-4k-instruct-gguf",
        "filename": "Phi-3-mini-4k-instruct-q4.gguf",
        "min_vram": 2,
        "desc": "Fastest. Best for Intel UHD, Iris Xe, or non-NVIDIA GPUs.",
    },
    "2": {
        "name": "Peridot Standard (Llama-3 8B Quantized)",
        "repo": "QuantFactory/Meta-Llama-3-8B-Instruct-GGUF",
        "filename": "Meta-Llama-3-8B-Instruct.Q4_K_M.gguf",
        "min_vram": 6,
        "desc": "Balanced. The Gold Standard for RTX 3060/4060/5050.",
    },
    "3": {
        "name": "Peridot Pro (Mistral 7B v0.3)",
        "repo": "MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF",
        "filename": "Mistral-7B-Instruct-v0.3.Q6_K.gguf",
        "min_vram": 10,
        "desc": "High Fidelity. Requires 12GB+ VRAM (RTX 3080/4090).",
    },
}


def check_engine_installed():
    """Checks if the Inference Engine is already working."""
    try:
        import llama_cpp

        return True
    except ImportError:
        return False


def install_deps(has_nvidia):
    print(">> [1/4] Checking Core Dependencies...")

    # Base packages (install only if missing)
    pkgs = [
        "huggingface_hub",
        "requests",
        "colorama",
        "pynvml",
        "psutil",
        "sounddevice",
        "numpy",
        "pillow",
        "flask",
        "flask-cors",
    ]
    subprocess.check_call([sys.executable, "-m", "pip", "install"] + pkgs)

    # Llama-cpp-python (Hardware Accelerated)
    print(">> [2/4] Verifying Inference Engine...")

    if check_engine_installed():
        print("   [SKIP] Engine already installed. Skipping to prevent conflicts.")
        return

    if has_nvidia:
        print("   [GPU] NVIDIA Detected. Attempting binary install...")
        # Use --prefer-binary to avoid compilation errors
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "llama-cpp-python",
            "--prefer-binary",
            "--extra-index-url",
            "https://abetlen.github.io/llama-cpp-python/whl/cu124",
            "--no-cache-dir",
        ]
        try:
            subprocess.check_call(cmd)
        except:
            print("   [WARN] CUDA 12.4 install failed. Trying CUDA 12.1 fallback...")
            cmd[6] = "https://abetlen.github.io/llama-cpp-python/whl/cu121"
            subprocess.check_call(cmd)
    else:
        print("   [CPU] No NVIDIA GPU. Installing CPU backend...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "llama-cpp-python"]
        )


def detect_gpu():
    try:
        import pynvml

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        name = pynvml.nvmlDeviceGetName(handle)
        return {"name": name, "vram": round(mem.total / (1024**3), 1)}
    except:
        return None


def main():
    print(f"\n{'='*50}")
    print("   PERIDOT SOVEREIGN KERNEL | SETUP WIZARD")
    print(f"{'='*50}\n")

    # 1. Hardware Scan
    print(">> Scanning Hardware...")
    gpu = detect_gpu()

    rec_model = "1"
    if gpu:
        print(f"   [DETECTED] GPU: {gpu['name']} ({gpu['vram']} GB VRAM)")
        if gpu["vram"] >= 10:
            rec_model = "3"
        elif gpu["vram"] >= 6:
            rec_model = "2"
    else:
        print("   [DETECTED] Integrated Graphics / CPU Mode")
        print("   [NOTE] Running in Lite Mode.")

    # 2. Install Deps
    install_deps(has_nvidia=bool(gpu))

    # 3. Model Selection
    print("\n>> Select Inference Engine:")
    for k, v in MODELS.items():
        tag = " <--- RECOMMENDED" if k == rec_model else ""
        print(f"   [{k}] {v['name']}{tag}")
        print(f"       {v['desc']}")

    choice = input("\n   Enter Choice (1-3): ").strip()
    if choice not in MODELS:
        choice = rec_model

    selected = MODELS[choice]
    print(f"\n>> [3/4] Downloading {selected['name']}...")

    from huggingface_hub import hf_hub_download

    os.makedirs("models", exist_ok=True)

    try:
        path = hf_hub_download(
            selected["repo"], selected["filename"], local_dir="models"
        )

        # Rename to generic 'brain.gguf' so server.py finds it
        dest = os.path.join("models", "brain.gguf")
        if os.path.exists(dest):
            os.remove(dest)
        os.rename(path, dest)

        print(f"\n[SUCCESS] Engine Installed: {selected['filename']}")
        print(f"{'='*50}")
        print("SETUP COMPLETE. Run 'python launcher.py' to begin.")
        print(f"{'='*50}")

    except Exception as e:
        print(f"[ERROR] Download failed: {e}")


if __name__ == "__main__":
    main()
