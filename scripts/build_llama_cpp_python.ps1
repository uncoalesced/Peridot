# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL
# Build llama-cpp-python from source with native CUDA kernels for this GPU.
# -----------------------------------------------------------------------------
#
# Why this exists: the pinned `llama_cpp_python==0.3.23` wheel (requirements.txt,
# installed via abetlen's cu121 index in install_wizard.py) has two problems:
#   1. Its llama.cpp core predates qwen35/MTP support -- the cause of the
#      "missing tensor 'blk.64.ssm_conv1d.weight'" load failure on Qwen3.8-27B.
#   2. It is built for CUDA 12.1 architectures, so a Blackwell card (sm_120,
#      e.g. RTX 50xx) runs JIT-compiled PTX instead of native kernels.
#
# Source: llama-cpp-python pinned to git commit ea3b56bd (main, 2026-09-22),
# which bundles llama.cpp fb34fc262 (2026-09-21) with matching bindings.
# Why not the 0.3.35 PyPI release: its llama.cpp (4df29be, 2026-08-16) loads
# Qwen3.8-27B-UD-IQ1_S but produces token soup, on GPU and CPU alike. Upstream
# llama.cpp master produces coherent output from the same file (verified
# 2026-09-25); the relevant fixes landed after 4df29be -- 9d817213a "load
# hparams.n_layer_nextn before n_layer() calls" (09-01) and 5fdfa6282 "fix GDN
# normalization" (09-06). Move to a tagged release once one includes them:
#   .\scripts\build_llama_cpp_python.ps1 -Ref v0.3.36
# (The vendored llama.cpp/ checkout, 715b86a3, is older still and not used.)
#
# Requires:
#   - Visual Studio 2022 (Build Tools is enough) with the C++ x64 toolset
#   - CUDA Toolkit 12.8+ (sm_120 support); 13.x recommended
#   - This repo's venv (python install_wizard.py)
#
# Usage, from repo root:
#   .\scripts\build_llama_cpp_python.ps1                 # auto-detect GPU arch
#   .\scripts\build_llama_cpp_python.ps1 -CudaArch 89    # override
#
# Rollback: the script tries to save the previously installed wheel to
# $env:TEMP\peridot-llama-wheel-backup first (it warns if no prebuilt wheel of
# that version exists any more), and keeps every wheel it builds under
# $env:LOCALAPPDATA\peridot\wheels. Reinstall either with:
#   venv\Scripts\python -m pip install --force-reinstall --no-deps <wheel>

param(
    # A git ref (commit/tag/branch) of abetlen/llama-cpp-python.
    [string]$Ref = "ea3b56bdc386d5a6f31120338ffe907211b0907c",  # pragma: allowlist secret
    [string]$CudaArch = "",
    [string]$CudaRoot = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python   = Join-Path $repoRoot "venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "venv not found at $python -- run install_wizard.py first." }

# --- GPU architecture -------------------------------------------------------
if (-not $CudaArch) {
    $cap = (& nvidia-smi --query-gpu=compute_cap --format=csv,noheader | Select-Object -First 1).Trim()
    if (-not $cap) { throw "nvidia-smi returned no compute capability; pass -CudaArch." }
    $CudaArch = $cap.Replace(".", "")
}
Write-Host "Target CUDA architecture: sm_$CudaArch"

# --- CUDA toolkit: newest installed unless overridden -------------------------
# Toolkits known to produce broken kernels. CUDA 13.2 (V13.2.51) + MSVC,
# sm_120: every IQ-family quant (IQ1_S, IQ3_XXS, IQ3_M) decodes to garbage on
# GPU while Q4_K_M/Q8_0 are fine and the same source built with 13.1 is
# correct (verified 2026-09-25 on an RTX 5050 Laptop). Pass -CudaRoot to force one.
$KnownBadCuda = @("v13.2")
if (-not $CudaRoot) {
    $CudaRoot = Get-ChildItem "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA" -Directory |
        Where-Object { $KnownBadCuda -notcontains $_.Name } |
        Sort-Object { [version]($_.Name.TrimStart("v")) } -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
$nvcc = Join-Path $CudaRoot "bin\nvcc.exe"
if (-not (Test-Path $nvcc)) { throw "nvcc not found under $CudaRoot" }
Write-Host "CUDA toolkit: $CudaRoot"

# --- MSVC environment (vcvars64) --------------------------------------------
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vsPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsPath) { throw "No Visual Studio install with the C++ x64 toolset found." }
$vcvars = Join-Path $vsPath "VC\Auxiliary\Build\vcvars64.bat"
cmd /c "`"$vcvars`" >nul && set" | ForEach-Object {
    if ($_ -match "^([^=]+)=(.*)$") { Set-Item -Path "env:$($matches[1])" -Value $matches[2] }
}
Write-Host "MSVC: $vsPath"

# --- Back up the currently installed wheel ----------------------------------
$backup = Join-Path $env:TEMP "peridot-llama-wheel-backup"
New-Item -ItemType Directory -Force $backup | Out-Null
$installed = (& $python -c "import llama_cpp; print(llama_cpp.__version__)" 2>$null)
if ($installed) {
    Write-Host "Backing up installed llama_cpp_python $installed -> $backup"
    & $python -m pip download "llama_cpp_python==$installed" --no-deps -d $backup `
        --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121 --only-binary=:all: -q
    if ($LASTEXITCODE -ne 0) {
        # Observed 2026-09-25: the cu121 index no longer serves 0.3.23 for cp311/win.
        Write-Warning "No prebuilt wheel for $installed could be downloaded -- rollback will need a source build of that version."
    }
}

# --- Build --------------------------------------------------------------------
# Ninja instead of the Visual Studio generator: the VS generator needs CUDA's
# MSBuild integration installed into this exact VS edition, Ninja does not.
& $python -m pip install -q ninja cmake

$env:CUDA_PATH       = $CudaRoot
$env:CUDACXX         = $nvcc
$env:CMAKE_GENERATOR = "Ninja"
$env:CMAKE_BUILD_PARALLEL_LEVEL = "$([Environment]::ProcessorCount)"
$env:FORCE_CMAKE     = "1"
# GGML_CUDA_FA_ALL_QUANTS: flash-attention kernels for every KV-cache type, so
# quantized KV (KV_CACHE_TYPE=q8_0/q4_0 in config.py) stays on the FA path.
$env:CMAKE_ARGS = "-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=$CudaArch -DGGML_CUDA_FA_ALL_QUANTS=on -DLLAMA_BUILD_EXAMPLES=off -DLLAMA_BUILD_TESTS=off"

# Clone here rather than letting pip do it: pip's temp checkout path plus
# llama.cpp's deep tools/ui tree exceeds Windows MAX_PATH ("unable to create
# file ..." during submodule update). core.longpaths lifts that limit for git.
$src = Join-Path $env:TEMP "plcp-src"
if (Test-Path $src) { Remove-Item -Recurse -Force $src }
git -c core.longpaths=true clone --quiet https://github.com/abetlen/llama-cpp-python $src
if ($LASTEXITCODE -ne 0) { throw "git clone failed." }
git -C $src -c core.longpaths=true checkout --quiet $Ref
git -C $src -c core.longpaths=true submodule update --init --recursive --depth 1
if ($LASTEXITCODE -ne 0) { throw "git submodule update failed for $Ref." }
$spec = $src
Write-Host "Building llama-cpp-python @ $Ref from source (several minutes)..."
# Build to a kept wheel first, then install it: a later reinstall (new venv,
# rollback from an experiment) takes seconds instead of a full CUDA compile.
$wheelDir = Join-Path $env:LOCALAPPDATA "peridot\wheels\llama-cpp-python-$($Ref.Substring(0, [Math]::Min(12, $Ref.Length)))-sm$CudaArch"
New-Item -ItemType Directory -Force $wheelDir | Out-Null
& $python -m pip wheel $spec `
    --no-deps --no-cache-dir -w $wheelDir -v
if ($LASTEXITCODE -ne 0) { throw "Build failed (exit $LASTEXITCODE). Nothing was installed." }
$wheel = Get-ChildItem $wheelDir -Filter "llama_cpp_python-*.whl" | Select-Object -First 1
& $python -m pip install $wheel.FullName --force-reinstall --no-deps
if ($LASTEXITCODE -ne 0) { throw "Install of $($wheel.FullName) failed (exit $LASTEXITCODE)." }
Write-Host "Wheel kept at $($wheel.FullName)"

& $python -c "import llama_cpp; print('llama_cpp', llama_cpp.__version__, 'gpu_offload', llama_cpp.llama_supports_gpu_offload())"
Write-Host ""
Write-Host "Build complete. requirements.txt's llama_cpp_python pin describes the PyPI"
Write-Host "fallback; this source build is what's installed."
