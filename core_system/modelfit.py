# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.1 | MODEL FIT
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
#
# Fit / scoring / hardware logic ported from LLMFit (llmfit-core: hardware.rs,
# models.rs, fit.rs), MIT, Copyright (c) 2026 Alex Jones. See THIRD_PARTY_NOTICES.md.
# -----------------------------------------------------------------------------

"""
Does this model fit this machine?

    detect()                    -> Hardware (never raises)
    recommend(hw, n=3)          -> top-n catalog models, one per family
    check_repo(repo_id, hw)     -> per-file verdicts for any Hugging Face repo (live)
    download(url, dest)         -> resumable, cancellable streaming download
    download_repo_files(...)    -> several files from one repo, confined to dest_dir

STDLIB ONLY: the install wizard imports this before requirements.txt is installed.
It also runs in the wizard process, never in the air-gapped kernel.

Units: every memory figure is GiB (2^30). Upstream adds params_b * bpp (decimal GB)
to a KV cache in GiB; here weights are converted to GiB too, which makes them ~7%
smaller than upstream's figure for the same quant.

CLI:  python -m core_system.modelfit [--use-case coding] [--resolve]
      python -m core_system.modelfit --check bartowski/Qwen2.5-7B-Instruct-GGUF
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import platform
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

GIB = 1024 ** 3
HF = "https://huggingface.co"
UA = {"User-Agent": "Peridot"}
CATALOG_PATH = Path(__file__).resolve().parent.parent / "config" / "model_catalog.json"
OVERHEAD_GB = 0.5          # runtime context + buffers (models.rs estimate_memory_gb)
MAX_CTX = 8192             # estimation context cap (fit.rs)
REPO_RE = re.compile(r"^(?!\.)[\w.-]+/(?!\.)[\w.-]+$")  # no leading dot: blocks "." / ".." segments

# ── Quant tables (models.rs) ────────────────────────────────────────────────
LADDER = ["Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "Q3_K_M", "Q2_K"]
QUANT_BPP = {"F16": 2.0, "BF16": 2.0, "Q8_0": 1.05, "Q6_K": 0.80, "Q5_K_M": 0.68,
             "Q4_K_M": 0.58, "Q4_0": 0.58, "Q3_K_M": 0.48, "Q2_K": 0.37}
QUANT_BYTES = {"F16": 2.0, "BF16": 2.0, "Q8_0": 1.0, "Q6_K": 0.75, "Q5_K_M": 0.625,
               "Q4_K_M": 0.5, "Q4_0": 0.5, "Q3_K_M": 0.375, "Q2_K": 0.25}
QUANT_SPEED = {"F16": 0.6, "BF16": 0.6, "Q8_0": 0.8, "Q6_K": 0.95, "Q5_K_M": 1.0,
               "Q4_K_M": 1.15, "Q4_0": 1.15, "Q3_K_M": 1.25, "Q2_K": 1.35}
QUANT_PENALTY = {"F16": 0, "BF16": 0, "Q8_0": 0, "Q6_K": -1, "Q5_K_M": -2,
                 "Q4_K_M": -5, "Q4_0": -5, "Q3_K_M": -8, "Q2_K": -12}
# Preference order when picking a concrete GGUF file from a live repo.
QUANT_PREF = ["Q8_0", "Q6_K", "Q6_K_L", "Q5_K_M", "Q5_K_S", "Q4_K_M", "Q4_K_S", "Q4_0",
              "Q3_K_M", "Q3_K_S", "Q2_K", "IQ4_XS", "IQ3_M", "IQ2_M", "IQ1_M"]
QUANT_RE = re.compile(r"(?<![a-z0-9])(IQ\d_(?:XXS|XS|S|M|NL)|Q\d_K(?:_[SML])?|Q\d_\d|BF16|F16|F32)(?![a-z0-9])", re.I)
SHARD_RE = re.compile(r"^(.*)-(\d{5})-of-(\d{5})\.gguf$", re.I)


def _family_quant(q: str) -> str:
    """Map a file quant (Q4_K_S, IQ4_XS...) onto the nearest table key."""
    q = q.upper()
    if q in QUANT_BPP:
        return q
    m = re.match(r"I?Q(\d)", q)
    return {"8": "Q8_0", "6": "Q6_K", "5": "Q5_K_M", "4": "Q4_K_M", "3": "Q3_K_M"}.get(
        m.group(1) if m else "", "Q2_K" if m else "Q4_K_M")


# ── Run modes / fit levels (fit.rs) ─────────────────────────────────────────
GPU, MOE_OFFLOAD, CPU_OFFLOAD, CPU_ONLY = "Gpu", "MoeOffload", "CpuOffload", "CpuOnly"
PERFECT, GOOD, MARGINAL, TOO_TIGHT = "Perfect", "Good", "Marginal", "TooTight"
MODE_FACTOR = {GPU: 1.0, MOE_OFFLOAD: 0.8, CPU_OFFLOAD: 0.5, CPU_ONLY: 0.3}
BACKEND_K = {"cuda": 220, "rocm": 180, "vulkan": 150, "sycl": 100, "metal": 160,
             "cpu_x86": 70, "cpu_arm": 90}
WEIGHTS = {"general": (.45, .30, .15, .10), "coding": (.50, .20, .15, .15),
           "chat": (.40, .35, .15, .10), "reasoning": (.55, .15, .15, .15)}

# ponytail: trimmed copy of hardware.rs gpu_memory_bandwidth_gbps (desktop RTX 20-50,
# datacenter, RX 6000/7000, Apple M1-M4); unknown cards fall back to the K constants.
BANDWIDTH = [
    ("5090", 1792), ("5080", 960), ("5070 ti", 896), ("5070", 672), ("5060 ti", 448), ("5060", 256),
    ("4090", 1008), ("4080 super", 736), ("4080", 717), ("4070 ti super", 672), ("4070", 504),
    ("4060 ti", 288), ("4060", 272), ("3090 ti", 1008), ("3090", 936), ("3080 ti", 912),
    ("3080", 760), ("3070 ti", 608), ("3070", 448), ("3060 ti", 448), ("3060", 360),
    ("2080 ti", 616), ("2080", 448), ("2070", 448), ("2060 super", 448), ("2060", 336),
    ("h100", 2039), ("a100", 1555), ("l40", 864), ("l4", 300), ("t4", 320),
    ("7900 xtx", 960), ("7900 xt", 800), ("7900 gre", 576), ("7800 xt", 624), ("7600", 288),
    ("6900 xt", 512), ("6800", 512),
    ("m4 max", 546), ("m4 pro", 273), ("m4", 120), ("m3 ultra", 800), ("m3 max", 400),
    ("m3 pro", 150), ("m3", 100), ("m2 ultra", 800), ("m2 max", 400), ("m2 pro", 200),
    ("m2", 100), ("m1 ultra", 800), ("m1 max", 400), ("m1 pro", 200), ("m1", 68),
]


def gpu_bandwidth(name: str) -> float | None:
    low = name.lower()
    if any(w in low for w in ("laptop", "mobile", "max-q")):
        return None  # mobile SKUs share a number, not a memory bus (upstream #919)
    return next((float(bw) for key, bw in BANDWIDTH if key in low), None)


# ── Hardware ────────────────────────────────────────────────────────────────
@dataclass
class Hardware:
    gpu_name: str = ""
    vram_gb: float = 0.0
    vram_free_gb: float = 0.0
    backend: str = "cpu_x86"
    ram_gb: float = 0.0
    ram_avail_gb: float = 0.0
    cores: int = 1
    unified: bool = False
    bandwidth_gbps: float | None = None

    @property
    def has_gpu(self) -> bool:
        return self.unified or self.vram_gb > 0

    def summary(self) -> str:
        gpu = (f"{self.gpu_name} ({self.vram_gb:.1f} GiB{', unified' if self.unified else ''}, {self.backend})"
               if self.has_gpu else "none (CPU only)")
        return (f"GPU: {gpu}\nRAM: {self.ram_gb:.1f} GiB total, {self.ram_avail_gb:.1f} GiB available"
                f" | {self.cores} threads")


def _run(cmd: list[str], timeout: int = 8) -> str:
    kw = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout, **kw)
        return p.stdout if p.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError, ValueError):
        return ""


def parse_nvidia_smi(text: str) -> list[tuple[str, float, float]]:
    """`memory.total,memory.free,name` csv (MiB) -> [(name, total_gib, free_gib)]."""
    out = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",", 2)]
        try:
            out.append((parts[2], float(parts[0]) / 1024, float(parts[1]) / 1024))
        except (IndexError, ValueError):
            continue
    return out


def parse_meminfo(text: str) -> tuple[float, float]:
    """/proc/meminfo -> (total_gib, available_gib)."""
    kb = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        if rest.split():
            kb[key] = float(rest.split()[0])
    total = kb.get("MemTotal", 0) / 1024 ** 2
    return total, kb.get("MemAvailable", kb.get("MemFree", 0)) / 1024 ** 2 or total


# hardware.rs WINDOWS_REGISTRY_VRAM_PS_COMMAND: true VRAM of non-NVIDIA adapters
# (Win32_VideoController.AdapterRAM is a uint32 and caps at 4 GiB).
_WIN_VRAM_PS = (
    r"Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\*'"
    r" -ErrorAction SilentlyContinue | ForEach-Object { $d = $_.DriverDesc; $m = $_.'HardwareInformation.qwMemorySize';"
    r" if ($null -eq $m) { $m = $_.'HardwareInformation.MemorySize' }; if ($m -is [byte[]]) { if ($m.Length -ge 8)"
    r" { $m = [System.BitConverter]::ToUInt64($m, 0) } elseif ($m.Length -ge 4) { $m = [System.BitConverter]::ToUInt32($m, 0) }"
    r" else { $m = $null } } elseif ($m -is [int] -and $m -lt 0) { $m = [long]$m + 4294967296 };"
    r" if ($d -and $m) { $d + '|' + $m } }"
)


def parse_windows_registry_vram(text: str) -> list[tuple[str, float]]:
    out = []
    for line in text.splitlines():
        name, _, size = line.strip().rpartition("|")
        low = name.lower()
        if not name or any(w in low for w in ("microsoft basic", "virtual", "remote", "parsec", "idd")):
            continue
        try:
            out.append((name, int(size) / GIB))
        except ValueError:
            continue
    return out


def _backend_for(name: str) -> str:
    low = name.lower()
    if "nvidia" in low or "geforce" in low or "rtx" in low:
        return "cuda"
    if "amd" in low or "radeon" in low:
        return "rocm" if sys.platform.startswith("linux") else "vulkan"
    return "sycl" if "intel" in low else "vulkan"


def _ram(hw: Hardware) -> None:
    if os.name == "nt":
        import ctypes

        class MemStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MemStatus()
        st.dwLength = ctypes.sizeof(MemStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            hw.ram_gb, hw.ram_avail_gb = st.ullTotalPhys / GIB, st.ullAvailPhys / GIB
    elif sys.platform == "darwin":
        total = _run(["sysctl", "-n", "hw.memsize"]).strip()
        # ponytail: macOS available RAM = total (no vm_stat parse); unified pool uses total anyway.
        hw.ram_gb = hw.ram_avail_gb = int(total) / GIB if total.isdigit() else 0.0
    else:
        hw.ram_gb, hw.ram_avail_gb = parse_meminfo(Path("/proc/meminfo").read_text())


def detect() -> Hardware:
    """Best-effort hardware scan. Never raises; unknown fields stay at their defaults."""
    hw = Hardware(cores=os.cpu_count() or 1)
    arm = platform.machine().lower() in ("arm64", "aarch64")
    hw.backend = "cpu_arm" if arm else "cpu_x86"
    try:
        _ram(hw)
    except Exception:
        pass
    try:
        gpus = parse_nvidia_smi(_run(["nvidia-smi", "--query-gpu=memory.total,memory.free,name",
                                      "--format=csv,noheader,nounits"]))
        if gpus:
            # ponytail: largest single GPU only; multi-GPU pooling not modelled.
            hw.gpu_name, hw.vram_gb, hw.vram_free_gb = max(gpus, key=lambda g: g[1])
            hw.backend = "cuda"
        elif os.name == "nt":
            # ponytail: adapters under 1 GiB are iGPUs sharing RAM; treated as no GPU.
            cards = [c for c in parse_windows_registry_vram(_run(["powershell", "-NoProfile", "-Command",
                                                                   _WIN_VRAM_PS], 15)) if c[1] >= 1]
            if cards:
                hw.gpu_name, hw.vram_gb = max(cards, key=lambda c: c[1])
                hw.vram_free_gb = hw.vram_gb
                hw.backend = _backend_for(hw.gpu_name)
        elif sys.platform == "darwin" and arm:
            hw.gpu_name = _run(["sysctl", "-n", "machdep.cpu.brand_string"]).strip() or "Apple Silicon"
            hw.unified, hw.backend = True, "metal"
            hw.vram_gb = hw.vram_free_gb = hw.ram_gb
        # ponytail: Linux AMD (rocm-smi) / Intel GPUs not probed; they fall back to CPU-only.
        hw.bandwidth_gbps = gpu_bandwidth(hw.gpu_name) if hw.has_gpu else None
    except Exception:
        pass
    return hw


# ── Memory, speed, scoring ──────────────────────────────────────────────────
def kv_gb(m: dict, ctx: int) -> float:
    if m.get("layers") and m.get("head_dim"):
        kv_heads = m.get("kv_heads") or m.get("heads") or 8
        return 2 * kv_heads * m["head_dim"] * ctx * 2 * m["layers"] / GIB
    return 0.000008 * m["params_b"] * ctx  # upstream coarse fallback (fp16 KV)


def weights_gb(params_b: float, quant: str) -> float:
    return params_b * 1e9 * QUANT_BPP.get(quant, 0.58) / GIB


def mem_gb(m: dict, quant: str, ctx: int) -> float:
    return weights_gb(m["params_b"], quant) + kv_gb(m, ctx) + OVERHEAD_GB


def best_quant(m: dict, budget: float, ctx: int) -> tuple[str, float, int] | None:
    """First ladder quant whose memory fits the budget; retry once at half context."""
    for c in [ctx] + ([ctx // 2] if ctx // 2 >= 1024 else []):
        for q in LADDER:
            mem = mem_gb(m, q, c)
            if mem <= budget:
                return q, mem, c
    return None


def fit_level(mem: float, pool: float, mode: str) -> str:
    ratio = mem / pool if pool > 0 else math.inf
    level = PERFECT if ratio <= .60 else GOOD if ratio <= .85 else MARGINAL if ratio <= .98 else TOO_TIGHT
    return GOOD if level == PERFECT and mode != GPU else level


def estimate_tps(params_b: float, quant: str, hw: Hardware, mode: str) -> float:
    params_b = max(params_b, 0.1)
    q = _family_quant(quant)
    if mode != CPU_ONLY and hw.bandwidth_gbps:
        return max(0.1, hw.bandwidth_gbps / (params_b * QUANT_BYTES[q]) * 0.55 * MODE_FACTOR[mode])
    # ponytail: MoeOffload uses the generic formula, not upstream's DDR expert-read model.
    k = (90 if hw.backend == "cpu_arm" else 70) if mode == CPU_ONLY else BACKEND_K.get(hw.backend, 70)
    tps = k / params_b * QUANT_SPEED[q] * (1.1 if hw.cores >= 8 else 1.0)
    return max(0.1, tps * MODE_FACTOR[mode])


def _months_since(date: str | None) -> int | None:
    try:
        y, mo = (int(x) for x in (date or "").split("-")[:2])
    except ValueError:
        return None
    now = datetime.date.today()
    return max(0, (now.year - y) * 12 + now.month - mo)


def score(m: dict, quant: str, tps: float, mem: float, pool: float, level: str, use_case: str) -> float:
    name = m["name"].lower()
    qp = m.get("active_b") or m["params_b"]
    base = 30 if qp < 1 else 45 if qp < 3 else 60 if qp < 7 else 75 if qp < 10 else 82 if qp < 20 else 89 if qp < 40 else 95
    bump = next((b for k, b in (("qwen", 2), ("deepseek", 3), ("llama", 2), ("mistral", 1), ("mixtral", 1),
                                 ("gemma", 1), ("starcoder", 1)) if k in name), 0)
    months = _months_since(m.get("date"))
    recency = 0 if months is None else 3 if months < 3 else 1.5 if months < 9 else 0
    # ponytail: no generation bonus / task_bench table; upstream's name heuristics only.
    task = 6 if use_case == "coding" and ("code" in name or "starcoder" in name) else \
        5 if use_case == "reasoning" and m["params_b"] >= 13 else 0
    quality = min(100, max(0, base + bump + recency + QUANT_PENALTY.get(_family_quant(quant), 0) + task))
    speed = min(100, tps / (25 if use_case == "reasoning" else 40) * 100)
    z = max(0.0, (mem / pool - 0.70) / 0.20) if pool > 0 else 0
    fit = 0 if level == TOO_TIGHT else 100 * math.exp(-0.5 * z * z)
    target = 8192 if use_case in ("coding", "reasoning") else 4096
    context = 100 if m["ctx"] >= target else 70 if m["ctx"] >= target // 2 else 30
    wq, ws, wf, wc = WEIGHTS.get(use_case, WEIGHTS["general"])
    return round(quality * wq + speed * ws + fit * wf + context * wc, 1)


@dataclass
class Fit:
    name: str
    quant: str
    mode: str
    level: str
    mem_gb: float
    pool_gb: float
    tps: float
    score: float = 0.0
    ctx: int = 0
    repo: str = ""
    files: list[str] = field(default_factory=list)
    size_gb: float = 0.0

    @property
    def file(self) -> str:
        """Primary file: the GGUF (first shard), or the first weights file of a snapshot."""
        return next((p for p in self.files if p.endswith((".gguf", ".safetensors"))), "")

    def row(self) -> str:
        size = f"{self.size_gb:5.1f} GiB file" if self.size_gb else f"{self.mem_gb:5.1f} GiB need"
        label = self.file or self.name
        return (f"{label[:52]:<52} {self.quant:<8} {size}  {self.level:<8} {self.mode:<10}"
                f" ~{self.tps:4.0f} tok/s" + (f"  score {self.score}" if self.score else ""))


def _pools(hw: Hardware) -> list[tuple[str, float]]:
    """Memory pools to try, best first (VRAM-first like upstream)."""
    if not hw.has_gpu:
        return [(CPU_ONLY, hw.ram_avail_gb)]
    if hw.unified:
        return [(GPU, hw.ram_gb)]
    return [(GPU, hw.vram_gb), (CPU_OFFLOAD, hw.ram_avail_gb)]


def analyze(m: dict, hw: Hardware, use_case: str = "general") -> Fit:
    ctx = min(m.get("ctx") or 4096, MAX_CTX)
    pools = _pools(hw)
    hit = None
    for i, (mode, pool) in enumerate(pools):
        hit = best_quant(m, pool, ctx)
        if hit:
            break
        if i == 0 and mode == GPU and not hw.unified and m.get("active_b"):
            for q in LADDER:  # MoE: active experts in VRAM, the rest in RAM
                active = max(0.5, m["active_b"] * 1e9 * QUANT_BPP[q] / GIB * 1.1)
                if active <= hw.vram_gb and weights_gb(m["params_b"] - m["active_b"], q) <= hw.ram_avail_gb:
                    mode, hit = MOE_OFFLOAD, (q, active, ctx)
                    break
            if hit:
                break
    quant, mem, _ = hit or ("Q4_K_M", mem_gb(m, "Q4_K_M", ctx), ctx)
    level = fit_level(mem, pool, mode) if hit else TOO_TIGHT
    speed_params = m.get("active_b") or m["params_b"]
    tps = estimate_tps(speed_params, quant, hw, mode)
    return Fit(m["name"], quant, mode, level, mem, pool, tps,
               score(m, quant, tps, mem, pool, level, use_case), ctx, (m.get("repos") or [""])[0])


def load_catalog(path: Path = CATALOG_PATH) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["models"]


FAMILIES = ("qwen", "llama", "mistral", "mixtral", "gemma", "phi", "deepseek", "granite", "starcoder",
            "smollm", "lfm", "falcon", "olmo", "glm", "command", "hermes", "yi")


def family(name: str) -> str:
    """'Qwen/CodeQwen1.5-7B' -> 'qwen'. ponytail: known-name match, else leading letters."""
    base = name.split("/")[-1].lower()
    known = next((f for f in FAMILIES if f in base), None)
    m = re.match(r"[a-z]+", base)
    return known or (m.group(0) if m else base)


# First-run picks come from the model makers themselves, not re-uploads or merges.
OFFICIAL_ORGS = {"qwen", "meta-llama", "google", "mistralai", "microsoft", "ibm-granite", "deepseek-ai",
                 "huggingfacetb", "liquidai", "allenai", "nvidia", "zai-org", "thudm", "coherelabs",
                 "cohereforai", "nousresearch", "tiiuae", "openai"}
_CHAT_TUNED = re.compile(r"instruct|chat|-it\b|-it-|granite-[34]|thinking|hermes", re.I)
_VISION = re.compile(r"-vl\b|-vl-|vision|omni|audio", re.I)


def first_run_ok(m: dict, use_case: str = "general") -> bool:
    """Official, chat-tuned, and text-only unless the use case asks for vision."""
    name = m["name"]
    if name.split("/")[0].lower() not in OFFICIAL_ORGS or not _CHAT_TUNED.search(name):
        return False
    return use_case == "multimodal" or not (_VISION.search(name) or "vision" in (m.get("use_case") or "").lower())


def recommend(hw: Hardware, n: int = 3, use_case: str = "general", resolve: bool = False,
              catalog: list[dict] | None = None, min_downloads: int = 10_000) -> list[Fit]:
    """Top-n fitting catalog models, one per family. resolve=True asks HF for the concrete file."""
    # ponytail: org allowlist + min_downloads keep re-uploads/fine-tunes out of a first-run pick;
    # upstream ranks all. Any other repo is still reachable through check_repo().
    models = [m for m in (catalog if catalog is not None else load_catalog())
              if m.get("downloads", 0) >= min_downloads and first_run_ok(m, use_case)]
    fits = [f for f in (analyze(m, hw, use_case) for m in models) if f.level != TOO_TIGHT]
    fits.sort(key=lambda f: (-f.score, f.name))
    picks, seen = [], set()
    for f in fits:
        if family(f.name) not in seen:
            seen.add(family(f.name))
            picks.append(f)
        if len(picks) == n:
            break
    if resolve:
        for i, f in enumerate(picks):
            try:
                chosen = check_repo(f.repo, hw).chosen
            except (OSError, ValueError):
                continue  # offline / HF error: keep the catalog-level estimate
            if chosen:
                chosen.name, chosen.score = f.name, f.score
                picks[i] = chosen
    return picks


# ── Live Hugging Face check ─────────────────────────────────────────────────
def _get_json(url: str, timeout: int = 20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)


def safe_path(p: str) -> bool:
    """Relative POSIX path with no traversal, drive letter or backslash."""
    return bool(p) and not p.startswith("/") and "\\" not in p and ":" not in p and ".." not in p.split("/")


def hf_url(repo: str, path: str) -> str:
    return f"{HF}/{repo}/resolve/main/{urllib.parse.quote(path)}"


@dataclass
class RepoCheck:
    repo: str
    kind: str                       # "gguf" | "safetensors" | "none"
    params_b: float
    ctx: int
    candidates: list[Fit]
    chosen: Fit | None


def _config_meta(repo: str) -> dict:
    """Layers / heads / ctx from a transformers config.json, or {} when unreachable."""
    try:
        c = _get_json(hf_url(repo, "config.json"))
    except (OSError, ValueError):
        return {}
    c = c.get("text_config", c)
    heads = c.get("num_attention_heads")
    head_dim = c.get("head_dim") or (c["hidden_size"] // heads if heads and c.get("hidden_size") else None)
    return {"layers": c.get("num_hidden_layers"), "heads": heads, "kv_heads": c.get("num_key_value_heads"),
            "head_dim": head_dim, "ctx": c.get("max_position_embeddings")}


def collapse_ggufs(tree: list[dict]) -> dict[str, tuple[list[str], int]]:
    """Group shard sets (-00001-of-00003.gguf) into one candidate: {key: (paths, total_bytes)}."""
    groups: dict[str, tuple[list[str], int]] = {}
    for e in tree:
        path = e.get("path", "")
        if e.get("type") != "file" or not path.lower().endswith(".gguf") or not safe_path(path) \
                or "mmproj" in path.lower():
            continue
        size = (e.get("lfs") or {}).get("size") or e.get("size") or 0
        m = SHARD_RE.match(path)
        key = m.group(1) + ".gguf" if m else path
        paths, total = groups.get(key, ([], 0))
        groups[key] = (sorted(paths + [path]), total + size)
    return groups


def _quant_rank(q: str) -> int:
    return QUANT_PREF.index(q) if q in QUANT_PREF else len(QUANT_PREF)


def check_repo(repo_id: str, hw: Hardware, info: dict | None = None, tree: list | None = None) -> RepoCheck:
    """Live verdict for any HF repo. info/tree may be injected (tests)."""
    if not REPO_RE.match(repo_id or ""):
        raise ValueError(f"Invalid Hugging Face repo id: {repo_id!r}")
    info = info if info is not None else _get_json(f"{HF}/api/models/{repo_id}")
    # ponytail: first page of the tree only (HF pages at 1000 entries).
    tree = tree if tree is not None else _get_json(f"{HF}/api/models/{repo_id}/tree/main?recursive=true")
    gguf_meta = info.get("gguf") or {}
    params_b = (gguf_meta.get("total") or (info.get("safetensors") or {}).get("total") or 0) / 1e9
    files = {e["path"]: (e.get("lfs") or {}).get("size") or e.get("size") or 0
             for e in tree if e.get("type") == "file" and safe_path(e.get("path", ""))}
    groups = collapse_ggufs(tree)
    kind = "gguf" if groups else "safetensors" if "config.json" in files and \
        any(p.endswith(".safetensors") for p in files) else "none"

    base = (info.get("cardData") or {}).get("base_model") or ""
    base = base[0] if isinstance(base, list) and base else base
    meta = _config_meta(repo_id if kind == "safetensors" else base) \
        if kind == "safetensors" or (isinstance(base, str) and REPO_RE.match(base)) else {}
    ctx = min(gguf_meta.get("context_length") or meta.get("ctx") or 4096, MAX_CTX)

    if kind == "gguf":
        cands = [(key, paths, size, (QUANT_RE.search(key) or [None, "?"])[1].upper())
                 for key, (paths, size) in groups.items()]
    elif kind == "safetensors":
        snap = sorted(snapshot_files(files))  # weights + config/tokenizer; memory counts weights only
        cands = [(repo_id.split("/")[1], snap, sum(files[p] for p in snap if p.endswith(".safetensors")), "BF16")]
    else:
        cands = []

    fits, pools = [], _pools(hw)
    for key, paths, size, quant in cands:
        p_b = params_b or size / 1e9 / QUANT_BYTES[_family_quant(quant)]
        m = {"name": key, "params_b": p_b, **{k: v for k, v in meta.items() if v}}
        mem = size / GIB + kv_gb(m, ctx) + OVERHEAD_GB
        rank, mode, pool, level = len(pools), *pools[-1], TOO_TIGHT
        for i, (md, pl) in enumerate(pools):
            if fit_level(mem, pl, md) != TOO_TIGHT:
                rank, mode, pool, level = i, md, pl, fit_level(mem, pl, md)
                break
        f = Fit(key, quant, mode, level, mem, pool, estimate_tps(p_b, quant, hw, mode), ctx=ctx,
                repo=repo_id, files=paths, size_gb=size / GIB)
        fits.append((rank, _quant_rank(quant), -size, f))
    fits.sort(key=lambda t: t[:3])
    # Best pool first (VRAM over spill-to-RAM), then the QUANT_PREF order.
    chosen = next((f for r, *_, f in fits if r < len(pools)), None)
    return RepoCheck(repo_id, kind, params_b, ctx, [f for *_, f in fits], chosen)


def snapshot_files(paths) -> list[str]:
    """Files worth fetching for a safetensors snapshot."""
    return [p for p in paths if p.endswith((".safetensors", ".json", ".txt")) or p.endswith("tokenizer.model")]


# ── Download ────────────────────────────────────────────────────────────────
class Cancelled(Exception):
    """Download cancelled; the .part file is kept so the next call resumes."""


def download(url: str, dest, progress=None, cancel=None, timeout: int = 30) -> Path:
    """Stream url -> dest via dest.part, resuming with a Range request when .part exists."""
    dest = Path(dest)
    if dest.exists():
        return dest
    part = dest.with_name(dest.name + ".part")
    done = part.stat().st_size if part.exists() else 0
    headers = dict(UA, **({"Range": f"bytes={done}-"} if done else {}))
    try:
        resp = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 416 and done:  # range starts at EOF: the .part is already complete
            os.replace(part, dest)
            return dest
        raise
    with resp:
        if done and resp.status != 206:
            done = 0  # server ignored Range: start over
        length = int(resp.headers.get("Content-Length") or 0)
        total = length + done if length else 0
        with open(part, "ab" if done else "wb") as f:
            while True:
                if cancel is not None and cancel.is_set():
                    raise Cancelled(str(part))
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    if total and done < total:
        raise OSError(f"Incomplete download ({done}/{total} bytes); rerun to resume.")
    os.replace(part, dest)
    return dest


def download_repo_files(repo: str, files: list[str], dest_dir, progress=None, cancel=None,
                        total_bytes: int = 0) -> list[Path]:
    """Fetch several files of one repo into dest_dir; progress gets running totals across files."""
    if not REPO_RE.match(repo or ""):
        raise ValueError(f"Invalid Hugging Face repo id: {repo!r}")
    root = Path(dest_dir).resolve()
    out, base = [], 0
    for path in files:
        target = (root / path).resolve()
        if not safe_path(path) or not target.is_relative_to(root):
            raise ValueError(f"Refusing unsafe path: {path!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        cb = (lambda d, t, b=base: progress(b + d, total_bytes or t)) if progress else None
        out.append(download(hf_url(repo, path), target, cb, cancel))
        base += target.stat().st_size
    return out


# ── CLI ─────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m core_system.modelfit")
    ap.add_argument("--check", metavar="REPO", help="check a Hugging Face repo against this machine")
    ap.add_argument("--use-case", default="general", choices=sorted(WEIGHTS))
    ap.add_argument("--resolve", action="store_true", help="resolve concrete GGUF files (network)")
    ap.add_argument("-n", type=int, default=3)
    args = ap.parse_args(argv)
    hw = detect()
    print(hw.summary())
    if args.check:
        try:
            res = check_repo(args.check, hw)
        except (OSError, ValueError) as e:
            print(f"[FAILED] {args.check}: {e}")
            return 1
        print(f"\n{res.repo} [{res.kind}] params={res.params_b:.2f}B ctx={res.ctx}")
        for f in res.candidates:
            print(("* " if f is res.chosen else "  ") + f.row())
        if not res.chosen:
            print("Nothing in this repo fits this machine.")
    else:
        print(f"\nTop {args.n} ({args.use_case}):")
        for f in recommend(hw, args.n, args.use_case, resolve=args.resolve):
            print(f"  {f.name}\n    {f.row()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
