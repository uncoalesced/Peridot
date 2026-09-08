# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Rebuild llama-cpp-python from source against the vendored llama.cpp/ checkout.
# -----------------------------------------------------------------------------
#
# Why this exists: the pinned `llama_cpp_python==0.3.23` wheel (requirements.txt,
# installed via abetlen's cu121 index in setup.py) bundles an older llama.cpp
# core that predates qwen35/MTP support. That's the entire cause of the
# "missing tensor 'blk.64.ssm_conv1d.weight'" load failure on Qwen3.8-27B --
# not a bad download, not a VRAM issue. The llama.cpp/ checkout already vendored
# in this repo (commit 715b86a3, 2026-06-08) implements qwen35 MTP correctly
# (see llama.cpp/src/models/qwen35.cpp: load_block_mtp vs load_block_trunk).
# Nothing currently builds llama-cpp-python against it -- this script does that.
#
# Requires (on the machine running this script, not this repo):
#   - Visual Studio Build Tools, "Desktop development with C++" workload
#   - CUDA Toolkit 12.4 (matching the torch cu124 wheels in requirements.txt)
#   - This repo's venv already created and active (python setup.py)
#
# Usage: run from repo root with the venv active:
#   .\scripts\build_llama_cpp_python.ps1

$ErrorActionPreference = "Stop"

$repoRoot  = Split-Path -Parent $PSScriptRoot
$vendored  = Join-Path $repoRoot "llama.cpp"
$buildRoot = Join-Path $env:TEMP "peridot-llama-cpp-python-build"

if (-not (Test-Path $vendored)) {
    throw "llama.cpp/ not found at $vendored -- expected the vendored checkout."
}

if (Test-Path $buildRoot) { Remove-Item -Recurse -Force $buildRoot }
git clone --recursive https://github.com/abetlen/llama-cpp-python $buildRoot

# Swap the bundled submodule for this repo's llama.cpp checkout. Copying the
# tree (rather than repointing the submodule commit) sidesteps needing a fork
# just to change one pointer -- CMake only needs the source files.
Remove-Item -Recurse -Force (Join-Path $buildRoot "vendor\llama.cpp")
Copy-Item -Recurse $vendored (Join-Path $buildRoot "vendor\llama.cpp") -Exclude ".git"

Push-Location $buildRoot
try {
    $env:CMAKE_ARGS = "-DGGML_CUDA=on"
    $env:FORCE_CMAKE = "1"
    pip install . --force-reinstall --no-cache-dir --no-deps
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Build complete. Verify with:"
Write-Host "  python -c `"import llama_cpp; print(llama_cpp.__version__)`""
Write-Host ""
Write-Host "requirements.txt's llama_cpp_python==0.3.23 pin now describes the PyPI"
Write-Host "fallback, not what's installed -- see the comment added next to it."
