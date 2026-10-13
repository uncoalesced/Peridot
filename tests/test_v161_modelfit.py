"""
v1.6.1 core_system.modelfit: LLMFit port (fit math, live-repo selection, download).

No network: HF responses are injected as fixtures, subprocess is monkeypatched,
and downloads hit a local http.server with Range support.
"""

import http.server
import json
import threading
from pathlib import Path

import pytest

from core_system import modelfit as mf

GIB = 1024 ** 3
ROOT = Path(__file__).resolve().parent.parent


def hw(vram=8.0, ram_avail=16.0, bandwidth=None, backend="cuda", cores=16, unified=False):
    return mf.Hardware(gpu_name="Test GPU", vram_gb=vram, vram_free_gb=vram, backend=backend,
                       ram_gb=ram_avail * 2, ram_avail_gb=ram_avail, cores=cores, unified=unified,
                       bandwidth_gbps=bandwidth)


# ── memory formula ──────────────────────────────────────────────────────────
QWEN7 = {"name": "Qwen/Qwen2.5-7B-Instruct", "params_b": 7.616, "ctx": 32768,
         "layers": 28, "kv_heads": 4, "heads": 28, "head_dim": 128}


def test_memory_precise_kv():
    # kv = 2 * 4 kv_heads * 128 head_dim * 8192 ctx * 2 B * 28 layers = 469,762,048 B = 0.4375 GiB
    assert mf.kv_gb(QWEN7, 8192) == pytest.approx(0.4375)
    # weights = 7.616e9 * 0.58 / 2^30 = 4.11391 GiB ; + 0.4375 kv + 0.5 overhead = 5.05141
    assert mf.mem_gb(QWEN7, "Q4_K_M", 8192) == pytest.approx(5.05141, abs=1e-4)


def test_memory_fallback_kv():
    m = {"name": "x/y", "params_b": 10.0, "ctx": 4096}
    # kv = 0.000008 * 10 * 4096 = 0.32768 ; weights = 10e9 * 1.05 / 2^30 = 9.77889
    assert mf.kv_gb(m, 4096) == pytest.approx(0.32768)
    assert mf.mem_gb(m, "Q8_0", 4096) == pytest.approx(9.77889 + 0.32768 + 0.5, abs=1e-4)


def test_moe_offload_when_dense_does_not_fit():
    # Dense Q2_K: 30e9*0.37/2^30 = 10.3 GiB > 8 VRAM. Active Q8_0: 3e9*1.05/2^30*1.1 = 3.2265 GiB.
    m = {"name": "x/Big-MoE", "params_b": 30.0, "active_b": 3.0, "ctx": 4096, "downloads": 10**6}
    f = mf.analyze(m, hw(vram=8, ram_avail=64))
    assert (f.mode, f.quant) == (mf.MOE_OFFLOAD, "Q8_0")
    assert f.mem_gb == pytest.approx(3.2265, abs=1e-3)
    assert f.level == mf.GOOD  # ratio 0.40 would be Perfect; MoeOffload caps at Good


# ── fit levels ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("mem,mode,level", [
    (6.0, mf.GPU, mf.PERFECT), (6.01, mf.GPU, mf.GOOD), (8.5, mf.GPU, mf.GOOD),
    (8.51, mf.GPU, mf.MARGINAL), (9.79, mf.GPU, mf.MARGINAL), (9.81, mf.GPU, mf.TOO_TIGHT),
    (1.0, mf.CPU_ONLY, mf.GOOD), (1.0, mf.CPU_OFFLOAD, mf.GOOD), (1.0, mf.MOE_OFFLOAD, mf.GOOD),
    (9.0, mf.CPU_ONLY, mf.MARGINAL),
])
def test_fit_level_boundaries_and_caps(mem, mode, level):
    assert mf.fit_level(mem, 10.0, mode) == level


def test_fit_level_zero_pool_is_too_tight():
    assert mf.fit_level(1.0, 0.0, mf.GPU) == mf.TOO_TIGHT


# ── quant search ────────────────────────────────────────────────────────────
def test_best_quant_takes_highest_fitting_rung():
    q, mem, ctx = mf.best_quant(QWEN7, 8.0, 8192)
    # Q8_0 = 7.4475+0.9375 > 8 ; Q6_K = 7.616e9*0.8/2^30 = 5.6743 + 0.9375 = 6.6118
    assert (q, ctx) == ("Q6_K", 8192)
    assert mem == pytest.approx(6.6118, abs=1e-3)


def test_best_quant_half_ctx_retry():
    m = {"name": "x/y", "params_b": 1.0, "ctx": 8192}
    # ctx 8192: Q2_K = 0.344589 + 0.065536 + 0.5 = 0.910 > 0.89
    # ctx 4096: Q2_K = 0.344589 + 0.032768 + 0.5 = 0.877 <= 0.89 (Q3_K_M = 0.980 does not)
    q, mem, ctx = mf.best_quant(m, 0.89, 8192)
    assert (q, ctx) == ("Q2_K", 4096)
    assert mem == pytest.approx(0.87736, abs=1e-4)
    assert mf.best_quant(m, 0.5, 8192) is None
    # 1500 // 2 < 1024: no retry, so the 0.877-at-half-ctx answer is not available
    assert mf.best_quant(m, 0.88, 1500)[2] == 1500 and mf.best_quant(m, 0.85, 1500) is None


# ── throughput ──────────────────────────────────────────────────────────────
def test_tps_bandwidth_branch():
    # 1008 / (7 * 0.5 B/param) * 0.55 efficiency * 1.0 Gpu = 158.4
    assert mf.estimate_tps(7, "Q4_K_M", hw(bandwidth=1008), mf.GPU) == pytest.approx(158.4)


def test_tps_constant_branch():
    # CUDA K=220: 220 / 7 * 1.15 (Q4_K_M) * 1.1 (>=8 cores) = 39.757 ; CpuOffload x0.5
    assert mf.estimate_tps(7, "Q4_K_M", hw(), mf.GPU) == pytest.approx(39.757, abs=1e-3)
    assert mf.estimate_tps(7, "Q4_K_M", hw(), mf.CPU_OFFLOAD) == pytest.approx(19.879, abs=1e-3)
    # CpuOnly ignores GPU bandwidth and uses x86 K=70: 70/7*1.15*1.1*0.3 = 3.795
    assert mf.estimate_tps(7, "Q4_K_M", hw(bandwidth=1008), mf.CPU_ONLY) == pytest.approx(3.795)
    # no thread bonus under 8 cores
    assert mf.estimate_tps(7, "Q4_K_M", hw(cores=4), mf.GPU) == pytest.approx(220 / 7 * 1.15)


def test_bandwidth_table_skips_laptop_parts():
    assert mf.gpu_bandwidth("NVIDIA GeForce RTX 4090") == 1008
    assert mf.gpu_bandwidth("NVIDIA GeForce RTX 5050 Laptop GPU") is None
    assert mf.gpu_bandwidth("Mystery GPU") is None


# ── live repo selection (fixture tree) ──────────────────────────────────────
TREE = [
    {"type": "directory", "path": "Q6_K"},
    {"type": "file", "path": "M-Q8_0.gguf", "size": 9 * 10 ** 9},
    {"type": "file", "path": "M-Q4_K_M.gguf", "size": int(4.5 * GIB)},
    {"type": "file", "path": "Q6_K/M-Q6_K-00002-of-00002.gguf", "size": 3 * GIB},
    {"type": "file", "path": "Q6_K/M-Q6_K-00001-of-00002.gguf", "size": 3 * GIB},
    {"type": "file", "path": "mmproj-M-F16.gguf", "size": GIB},
    {"type": "file", "path": "../evil.gguf", "size": 1},
    {"type": "file", "path": "README.md", "size": 10},
]
INFO = {"gguf": {"total": 7e9, "context_length": 32768}, "cardData": {}}


def test_shard_collapse():
    groups = mf.collapse_ggufs(TREE)
    assert set(groups) == {"M-Q8_0.gguf", "M-Q4_K_M.gguf", "Q6_K/M-Q6_K.gguf"}
    paths, size = groups["Q6_K/M-Q6_K.gguf"]
    assert paths == ["Q6_K/M-Q6_K-00001-of-00002.gguf", "Q6_K/M-Q6_K-00002-of-00002.gguf"]
    assert size == 6 * GIB


def test_check_repo_prefers_vram_then_quant_order():
    res = mf.check_repo("org/M-GGUF", hw(vram=8, ram_avail=32), info=INFO, tree=TREE)
    assert res.kind == "gguf" and res.ctx == 8192 and len(res.candidates) == 3
    # Q6_K shards: 6 GiB + kv 0.000008*7*8192=0.459 + 0.5 = 6.96/8 = 0.87 -> Marginal on GPU.
    # Q8_0 (8.38 GiB file) only fits by spilling to RAM, so the GPU-resident Q6_K wins.
    assert res.chosen.quant == "Q6_K" and res.chosen.mode == mf.GPU and res.chosen.level == mf.MARGINAL
    assert res.chosen.file == "Q6_K/M-Q6_K-00001-of-00002.gguf" and len(res.chosen.files) == 2
    q8 = next(f for f in res.candidates if f.quant == "Q8_0")
    assert (q8.mode, q8.level) == (mf.CPU_OFFLOAD, mf.GOOD)


def test_check_repo_nothing_fits():
    res = mf.check_repo("org/M-GGUF", hw(vram=2, ram_avail=2), info=INFO, tree=TREE)
    assert res.chosen is None and all(f.level == mf.TOO_TIGHT for f in res.candidates)


def test_check_repo_safetensors(monkeypatch):
    cfg = {"num_hidden_layers": 24, "num_attention_heads": 14, "num_key_value_heads": 2,
           "hidden_size": 896, "max_position_embeddings": 32768}
    monkeypatch.setattr(mf, "_get_json", lambda url, timeout=20: cfg)
    tree = [{"type": "file", "path": p, "size": s} for p, s in
            [("config.json", 600), ("model.safetensors", GIB), ("tokenizer.json", 7000),
             ("merges.txt", 1000), ("onnx/model.onnx", 5 * GIB)]]
    res = mf.check_repo("Qwen/Tiny", hw(), info={"safetensors": {"total": 5e8}}, tree=tree)
    assert res.kind == "safetensors" and res.chosen.quant == "BF16"
    assert res.chosen.size_gb == pytest.approx(1.0)
    assert sorted(res.chosen.files) == ["config.json", "merges.txt", "model.safetensors", "tokenizer.json"]


@pytest.mark.parametrize("repo", ["../etc", "a/b/c", "a\\b/c", "", "./x", "org/..", "no-slash"])
def test_bad_repo_ids_rejected(repo):
    with pytest.raises(ValueError):
        mf.check_repo(repo, hw(), info={}, tree=[])


@pytest.mark.parametrize("path", ["../x.gguf", "/abs.gguf", "a\\b.gguf", "C:/x.gguf", "a/../../b"])
def test_traversal_paths_rejected(tmp_path, path):
    assert not mf.safe_path(path)
    with pytest.raises(ValueError):
        mf.download_repo_files("org/repo", [path], tmp_path)


# ── recommend ───────────────────────────────────────────────────────────────
CATALOG = [
    {"name": "Qwen/Qwen2.5-7B-Instruct", "params_b": 7.6, "ctx": 32768, "downloads": 10**6, "repos": ["b/q7"]},
    {"name": "Qwen/Qwen2.5-3B-Instruct", "params_b": 3.1, "ctx": 32768, "downloads": 10**6, "repos": ["b/q3"]},
    {"name": "Qwen/CodeQwen1.5-7B", "params_b": 7.3, "ctx": 32768, "downloads": 10**6, "repos": ["b/cq"]},
    {"name": "meta-llama/Llama-3.1-8B-Instruct", "params_b": 8.0, "ctx": 131072, "downloads": 10**6, "repos": ["b/l8"]},
    {"name": "google/gemma-2-9b-it", "params_b": 9.2, "ctx": 8192, "downloads": 10**6, "repos": ["b/g9"]},
    {"name": "mistralai/Mistral-7B-Instruct-v0.3", "params_b": 7.2, "ctx": 32768, "downloads": 10**6, "repos": ["b/m7"]},
    {"name": "deepseek-ai/DeepSeek-V3", "params_b": 671.0, "ctx": 131072, "downloads": 10**7, "repos": ["b/ds"]},
    {"name": "nobody/Obscure-7B", "params_b": 7.0, "ctx": 32768, "downloads": 5, "repos": ["b/o"]},
]


def test_recommend_three_distinct_families_no_too_tight():
    picks = mf.recommend(hw(vram=8, ram_avail=16), 3, catalog=CATALOG)
    assert len(picks) == 3
    assert len({mf.family(p.name) for p in picks}) == 3
    assert all(p.level != mf.TOO_TIGHT for p in picks)
    assert not any("DeepSeek-V3" in p.name or "Obscure" in p.name for p in picks)
    assert [p.score for p in picks] == sorted((p.score for p in picks), reverse=True)


def test_recommend_resolve_falls_back_offline(monkeypatch):
    def offline(*a, **kw):
        raise OSError("offline")
    monkeypatch.setattr(mf, "_get_json", offline)
    picks = mf.recommend(hw(), 3, catalog=CATALOG, resolve=True)
    assert len(picks) == 3 and all(not p.files for p in picks)


def test_first_run_filter_official_chat_text_only():
    ok = mf.first_run_ok
    assert ok({"name": "Qwen/Qwen2.5-3B-Instruct"})
    assert ok({"name": "google/gemma-2-9b-it"})
    assert not ok({"name": "Qwen/Qwen2.5-3B"})                        # base model
    assert not ok({"name": "empero-ai/Qwen3.8-4B-Distill-Instruct"})  # re-upload
    assert not ok({"name": "Qwen/Qwen2.5-VL-3B-Instruct"})            # vision
    assert ok({"name": "Qwen/Qwen2.5-VL-3B-Instruct"}, "multimodal")


def test_needs_source_build():
    import install_wizard
    assert install_wizard.needs_source_build("Qwen3.8-27B-UD-IQ1_S.gguf")
    assert install_wizard.needs_source_build("Qwen/Qwen3.5-9B-Instruct")
    assert not install_wizard.needs_source_build("Qwen2.5-3B-Instruct-Q8_0.gguf")
    assert not install_wizard.needs_source_build("Qwen/Qwen3-8B")


def test_family_heuristic():
    assert mf.family("Qwen/CodeQwen1.5-7B") == mf.family("Qwen/Qwen2.5-3B") == "qwen"
    assert mf.family("meta-llama/Meta-Llama-3-8B") == "llama"


# ── download ────────────────────────────────────────────────────────────────
DATA = bytes(range(256)) * (4096 * 3)  # 3 MiB -> three 1 MiB chunks


class _Handler(http.server.BaseHTTPRequestHandler):
    ignore_range = False
    ranges: list = []

    def do_GET(self):
        rng = None if self.ignore_range else self.headers.get("Range")
        _Handler.ranges.append(self.headers.get("Range"))
        start = int(rng.split("=")[1].split("-")[0]) if rng else 0
        if start >= len(DATA):
            self.send_response(416)
            self.end_headers()
            return
        body = DATA[start:]
        self.send_response(206 if rng else 200)
        self.send_header("Content-Length", str(len(body)))
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{len(DATA) - 1}/{len(DATA)}")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    _Handler.ranges, _Handler.ignore_range = [], False
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/f.bin"
    srv.shutdown()


def test_download_resumes_from_part(server, tmp_path):
    dest = tmp_path / "f.bin"
    (tmp_path / "f.bin.part").write_bytes(DATA[:1000])
    seen = []
    mf.download(server, dest, progress=lambda d, t: seen.append((d, t)))
    assert dest.read_bytes() == DATA and not (tmp_path / "f.bin.part").exists()
    assert _Handler.ranges == ["bytes=1000-"] and seen[-1] == (len(DATA), len(DATA))


def test_download_restarts_when_range_ignored(server, tmp_path):
    _Handler.ignore_range = True
    dest = tmp_path / "f.bin"
    (tmp_path / "f.bin.part").write_bytes(b"garbage")
    mf.download(server, dest)
    assert dest.read_bytes() == DATA


def test_download_cancel_keeps_part_then_resumes(server, tmp_path):
    dest, cancel = tmp_path / "f.bin", threading.Event()
    with pytest.raises(mf.Cancelled):
        mf.download(server, dest, progress=lambda d, t: cancel.set(), cancel=cancel)
    part = tmp_path / "f.bin.part"
    assert not dest.exists() and 0 < part.stat().st_size < len(DATA)
    mf.download(server, dest)
    assert dest.read_bytes() == DATA and _Handler.ranges[-1] == f"bytes={1 << 20}-"


def test_download_416_completes_full_part(server, tmp_path):
    (tmp_path / "f.bin.part").write_bytes(DATA)
    assert mf.download(server, tmp_path / "f.bin").read_bytes() == DATA


# ── catalog ─────────────────────────────────────────────────────────────────
def test_catalog_schema_and_size():
    path = ROOT / "config" / "model_catalog.json"
    assert path.stat().st_size < 1_000_000
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert "MIT" in doc["_license"] and "llmfit" in doc["_source"].lower()
    models = doc["models"]
    assert len(models) > 1000
    for m in models:
        assert m["name"] and m["params_b"] > 0 and m["ctx"] > 0 and m["repos"]
        assert "embed" not in m["name"].lower()
    assert len({m["name"] for m in models}) == len(models)


# ── hardware parsers / detect ───────────────────────────────────────────────
def test_parse_nvidia_smi():
    out = mf.parse_nvidia_smi("8151, 7827, NVIDIA GeForce RTX 5050 Laptop GPU\nN/A, N/A, broken\n\n")
    assert len(out) == 1
    name, total, free = out[0]
    assert name == "NVIDIA GeForce RTX 5050 Laptop GPU"
    assert total == pytest.approx(8151 / 1024) and free == pytest.approx(7827 / 1024)


def test_parse_meminfo():
    total, avail = mf.parse_meminfo("MemTotal:       32768000 kB\nMemFree:  1000 kB\nMemAvailable:   16384000 kB\n")
    assert total == pytest.approx(32768000 / 1024 ** 2) and avail == pytest.approx(16384000 / 1024 ** 2)


def test_parse_windows_registry_vram():
    out = mf.parse_windows_registry_vram(
        "Microsoft Basic Display Adapter|0\nAMD Radeon RX 7900 XTX|25753026560\nnoise\nIntel(R) UHD|x\n")
    assert out == [("AMD Radeon RX 7900 XTX", pytest.approx(25753026560 / GIB))]


def test_detect_never_raises(monkeypatch):
    def boom(*a, **kw):
        raise OSError("no such binary")

    def ram_boom(hw):
        raise RuntimeError("ctypes exploded")
    monkeypatch.setattr(mf.subprocess, "run", boom)
    monkeypatch.setattr(mf, "_ram", ram_boom)
    hw_ = mf.detect()
    assert isinstance(hw_, mf.Hardware) and not hw_.has_gpu and hw_.cores >= 1


def test_detect_parses_nvidia(monkeypatch):
    class P:
        returncode, stdout = 0, "8151, 7827, NVIDIA GeForce RTX 5050 Laptop GPU\n"
    monkeypatch.setattr(mf.subprocess, "run", lambda *a, **kw: P())
    hw_ = mf.detect()
    assert hw_.backend == "cuda" and hw_.vram_gb == pytest.approx(7.96, abs=0.01) and hw_.bandwidth_gbps is None


# ── wizard integration ──────────────────────────────────────────────────────
def test_wizard_offline_falls_back_to_profile_default(monkeypatch):
    import install_wizard as w

    monkeypatch.setattr(w.modelfit, "recommend", lambda *a, **kw: [])
    monkeypatch.setattr(w, "get_numeric_choice", lambda prompt, lo, hi: 1)  # 0 picks -> 1 = profile default
    plan = w.choose_model(hw(), "qwen2.5-3b")
    assert plan == {"kind": "legacy", "model_id": "qwen2.5-3b", "active": "qwen2.5-3b-instruct-q4_k_m.gguf"}


def test_wizard_plan_from_shard_pick():
    import install_wizard as w

    res = mf.check_repo("org/M-GGUF", hw(), info=INFO, tree=TREE)
    plan = w._plan_from_fit(res.chosen)
    assert plan["active"] == "Q6_K/M-Q6_K-00001-of-00002.gguf" and plan["subdir"] == ""
    assert len(plan["files"]) == 2
