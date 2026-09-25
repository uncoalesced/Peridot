# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | SHARED BENCHMARK HELPER TESTS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""Behaviour of the consolidated benchmarking helpers.

These helpers were each duplicated across benchmarking/ -- the NVML query in
seven places, the token estimator in four, the memory probe in two (with two
different return types), the statistics block in four. Collapsing copies onto
one implementation is exactly where behaviour drifts silently, so the contracts
the call sites depend on are pinned here.
"""

import json

import pytest

from benchmarking.utils import benchmark_utils as bu


# --- count_tokens_rough ------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("", 0),
        ("one", 1),            # 1 * 1.3 -> 1
        ("one two three", 3),  # 3 * 1.3 = 3.9 -> 3
        ("a b c d", 5),        # 4 * 1.3 = 5.2 -> 5
    ],
)
def test_count_tokens_rough_is_words_times_1_3_truncated(text, expected):
    assert bu.count_tokens_rough(text) == expected


def test_count_tokens_rough_ignores_whitespace_runs():
    # str.split() collapses runs; callers feed it generated context blocks.
    assert bu.count_tokens_rough("a   b\n\nc") == bu.count_tokens_rough("a b c")


# --- get_vram_mb -------------------------------------------------------------

def test_get_vram_mb_always_returns_the_full_contract():
    """Callers index these keys without guarding, so all five must be present."""
    vram = bu.get_vram_mb()
    for key in ("name", "total", "used", "free", "count"):
        assert key in vram, f"get_vram_mb() must always return {key!r}"
    assert isinstance(vram["total"], int)
    assert isinstance(vram["count"], int)


def test_get_vram_mb_degrades_to_zeros_without_nvml(monkeypatch):
    """No GPU must not raise: seven call sites rely on the zero fallback."""
    import builtins

    real_import = builtins.__import__

    def refuse_pynvml(name, *args, **kwargs):
        if name == "pynvml":
            raise ImportError("simulated: no pynvml")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse_pynvml)

    vram = bu.get_vram_mb()
    assert vram == {"name": "Unknown", "total": 0, "used": 0, "free": 0, "count": 0}


def test_vram_handoff_adapter_returns_none_when_no_gpu(monkeypatch):
    """benchmark_vram_handoff.get_vram_info() tests falsiness, not keys."""
    from benchmarking import benchmark_vram_handoff as handoff

    monkeypatch.setattr(
        handoff, "get_vram_mb",
        lambda: {"name": "Unknown", "total": 0, "used": 0, "free": 0, "count": 0},
    )
    assert handoff.get_vram_info() is None

    monkeypatch.setattr(
        handoff, "get_vram_mb",
        lambda: {"name": "X", "total": 8151, "used": 241, "free": 7910, "count": 1},
    )
    assert handoff.get_vram_info() == {
        "free_mb": 7910, "used_mb": 241, "total_mb": 8151
    }


# --- get_peridot_memory ------------------------------------------------------

def test_get_peridot_memory_returns_none_when_no_server(monkeypatch):
    """Must be None, not a zero-filled dict: call sites do `if not mem`."""
    monkeypatch.setattr(bu, "find_peridot_processes", lambda: [])
    assert bu.get_peridot_memory() is None


def test_get_peridot_memory_reports_rss_vms_and_pid(monkeypatch):
    class FakeProc:
        pid = 4321

        def memory_info(self):
            return type("M", (), {"rss": 100 * 1024 * 1024,
                                  "vms": 200 * 1024 * 1024})()

    monkeypatch.setattr(bu, "find_peridot_processes", lambda: [FakeProc()])
    mem = bu.get_peridot_memory()
    assert mem == {"rss_mb": 100.0, "vms_mb": 200.0, "pid": 4321}


def test_sustained_load_adapter_flattens_to_float(monkeypatch):
    """benchmark_sustained_load treats the value as a bare float."""
    from benchmarking import benchmark_sustained_load as sustained

    monkeypatch.setattr(
        sustained, "shared_peridot_memory",
        lambda: {"rss_mb": 123.5, "vms_mb": 200.0, "pid": 1},
    )
    assert sustained.get_peridot_memory() == 123.5

    monkeypatch.setattr(sustained, "shared_peridot_memory", lambda: None)
    assert sustained.get_peridot_memory() is None


# --- BenchmarkResult ---------------------------------------------------------

def test_benchmark_result_statistics_are_empty_without_measurements():
    assert bu.BenchmarkResult("n", "d").get_statistics() == {}


def test_benchmark_result_statistics_single_measurement_has_zero_stdev():
    """stdev of one sample must not raise -- several benchmarks record one run."""
    result = bu.BenchmarkResult("n", "d")
    result.add_measurement(4.0)
    stats = result.get_statistics()
    assert stats["count"] == 1
    assert stats["stdev"] == 0.0
    assert stats["min"] == stats["max"] == stats["mean"] == stats["median"] == 4.0


def test_benchmark_result_statistics_match_expected_values():
    result = bu.BenchmarkResult("n", "d")
    for value in (1.0, 2.0, 3.0, 4.0):
        result.add_measurement(value)
    stats = result.get_statistics()
    assert stats["min"] == 1.0
    assert stats["max"] == 4.0
    assert stats["mean"] == 2.5
    assert stats["median"] == 2.5
    assert stats["count"] == 4


def test_benchmark_result_save_writes_the_schema_generate_report_reads(tmp_path):
    """generate_report.load_latest_result() consumes exactly these keys."""
    result = bu.BenchmarkResult("decode_rate", "isolated decode rate")
    result.add_measurement(3.998)
    result.add_metadata("model", "unit-test.gguf")

    filepath = result.save(tmp_path)
    assert filepath.exists()
    assert filepath.name.startswith("decode_rate_")

    payload = json.loads(filepath.read_text(encoding="utf-8"))
    for key in ("name", "description", "timestamp", "measurements",
                "statistics", "metadata"):
        assert key in payload
    assert payload["name"] == "decode_rate"
    assert payload["metadata"]["model"] == "unit-test.gguf"
    assert payload["statistics"]["count"] == 1


def test_results_dir_is_the_single_shared_location():
    """RESULTS_DIR was recomputed in ten files; every consumer must agree."""
    from benchmarking import (
        benchmark_cold_start,
        benchmark_gpu_utilization,
        benchmark_inference,
        benchmark_memory_stability,
        benchmark_vram_hammer,
    )

    assert bu.RESULTS_DIR.name == "results"
    assert bu.RESULTS_DIR.parent.name == "benchmarking"
    for module in (benchmark_cold_start, benchmark_gpu_utilization,
                   benchmark_inference, benchmark_memory_stability,
                   benchmark_vram_hammer):
        assert module.RESULTS_DIR == bu.RESULTS_DIR


def test_aether_client_sends_only_query(monkeypatch):
    """The client must not send a chat template.

    server.py builds the prompt with build_full_context() for the loaded
    model's own format; this used to ship hardcoded Llama-3 header tokens while
    the shipped default model is Qwen/chatml.
    """
    sent = {}

    class FakeSession:
        headers = {}

        def post(self, url, json=None, timeout=None):
            sent["payload"] = json

            class R:
                status_code = 200

                @staticmethod
                def raise_for_status():
                    pass

                @staticmethod
                def json():
                    return {"response": "ok"}

            return R()

        def update(self, *_a, **_kw):
            pass

    monkeypatch.setattr(bu, "get_ephemeral_key", lambda: "test-key")
    client = bu.AetherClient()
    client.session = FakeSession()

    client.send_query("hello")
    assert sent["payload"] == {"query": "hello"}
    assert "prompt" not in sent["payload"]
