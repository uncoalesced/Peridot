# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | v1.6.x PROVIDER ABSTRACTION TESTS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""
Coverage for the BaseInferenceProvider contract and the provider registry.

Deliberately runs without loading a real model: a fake provider exercises the
timing/counting logic, so these run on the GPU-less CI runner. Real-model
behaviour is covered by benchmarking/benchmark_decode_rate.py and manual runs.
"""

import sys
import time
from pathlib import Path

import pytest

PERIDOT_ROOT = Path(__file__).parent.parent.absolute()
if str(PERIDOT_ROOT) not in sys.path:
    sys.path.insert(0, str(PERIDOT_ROOT))

from core_system.providers import (  # noqa: E402
    EXTENSION_MAP,
    LlamaCppProvider,
    ProviderLoadError,
    UnsupportedModelFormat,
    provider_for,
    supported_extensions,
)
from core_system.providers.base import (  # noqa: E402
    BaseInferenceProvider,
    GenerationResult,
    ProviderCapabilities,
)


class FakeProvider(BaseInferenceProvider):
    """Deterministic provider: 1 char per 'token', fixed delays."""

    def __init__(self, path="fake.gguf", chunks=None, prefill_delay=0.05, decode_delay=0.01):
        super().__init__(path)
        self._chunks = chunks if chunks is not None else ["a", "b", "c", "d", "e"]
        self._prefill_delay = prefill_delay
        self._decode_delay = decode_delay

    def load(self):
        self._loaded = True

    def unload(self):
        self._loaded = False

    def tokenize(self, text):
        return list(range(len(text)))

    def generate_stream(self, prompt, **params):
        time.sleep(self._prefill_delay)
        for c in self._chunks:
            yield c
            time.sleep(self._decode_delay)

    @property
    def capabilities(self):
        return ProviderCapabilities(engine="fake", context_window=128)


# --- registry ----------------------------------------------------------------


def test_gguf_routes_to_llamacpp():
    p = provider_for("models/whatever.gguf", n_ctx=512, n_gpu_layers=0)
    assert isinstance(p, LlamaCppProvider)
    assert not p.is_loaded, "provider_for must construct, not load"


def test_extension_match_is_case_insensitive():
    assert isinstance(provider_for("models/WHATEVER.GGUF"), LlamaCppProvider)


def test_planned_backend_raises_clear_not_implemented():
    with pytest.raises(UnsupportedModelFormat, match="ExLlamaV2"):
        provider_for("model.exl2")


def test_unknown_extension_is_rejected():
    with pytest.raises(UnsupportedModelFormat):
        provider_for("model.bin")


def test_unsupported_format_is_recoverable():
    """Must subclass ProviderLoadError so callers keep the kernel up."""
    assert issubclass(UnsupportedModelFormat, ProviderLoadError)


def test_gguf_is_registered():
    assert ".gguf" in EXTENSION_MAP
    assert ".gguf" in supported_extensions()


# --- timing / counting contract ----------------------------------------------


def test_prefill_and_decode_are_timed_separately():
    p = FakeProvider(prefill_delay=0.20, decode_delay=0.0)
    p.load()
    r = p.generate("prompt")
    assert r.prefill_seconds >= 0.19, "prefill must capture time before first token"
    assert r.decode_seconds < 0.19, "decode must exclude prefill"


def test_decode_rate_excludes_the_first_token():
    """First token comes from prefill; counting it inflates short generations."""
    r = GenerationResult(
        text="abcde",
        prompt_tokens=3,
        completion_tokens=5,
        prefill_seconds=1.0,
        decode_seconds=2.0,
    )
    assert r.decode_tokens_per_second == pytest.approx(4 / 2.0)
    assert r.end_to_end_tokens_per_second == pytest.approx(5 / 3.0)


def test_decode_rate_is_zero_for_single_token():
    r = GenerationResult("a", 1, 1, prefill_seconds=1.0, decode_seconds=0.5)
    assert r.decode_tokens_per_second == 0.0


def test_decode_rate_handles_zero_duration():
    r = GenerationResult("abc", 1, 3, prefill_seconds=0.0, decode_seconds=0.0)
    assert r.decode_tokens_per_second == 0.0
    assert r.end_to_end_tokens_per_second == 0.0


def test_generate_uses_real_tokenizer_not_word_estimates():
    """
    Guards the exact defect that made benchmark_inference.py wrong: token counts
    must come from the tokenizer, never from splitting on whitespace.
    """
    p = FakeProvider(chunks=["hello world"])
    p.load()
    r = p.generate("xy")
    assert r.completion_tokens == len("hello world")  # 11, not 2 words
    assert r.prompt_tokens == 2


def test_empty_stream_does_not_crash():
    p = FakeProvider(chunks=[])
    p.load()
    r = p.generate("prompt")
    assert r.text == ""
    assert r.completion_tokens == 0
    assert r.decode_seconds >= 0.0


# --- lifecycle ---------------------------------------------------------------


def test_generate_before_load_raises():
    with pytest.raises(ProviderLoadError):
        FakeProvider().generate("x")


def test_load_and_unload_are_idempotent():
    p = FakeProvider()
    p.load()
    p.load()
    assert p.is_loaded
    p.unload()
    p.unload()
    assert not p.is_loaded


def test_context_manager_loads_and_unloads():
    p = FakeProvider()
    with p as active:
        assert active.is_loaded
    assert not p.is_loaded


def test_missing_model_file_raises_recoverable_error():
    p = LlamaCppProvider(PERIDOT_ROOT / "models" / "does-not-exist.gguf")
    with pytest.raises(ProviderLoadError, match="not found"):
        p.load()
    assert not p.is_loaded, "failed load must leave provider unloaded, not half-loaded"


def test_capabilities_expose_the_full_contract():
    caps = LlamaCppProvider("x.gguf", n_ctx=8192).capabilities
    assert caps.context_window == 8192
    assert caps.engine == "llama-cpp-python"
    for flag in ("supports_thinking", "supports_vision", "supports_streaming"):
        assert isinstance(getattr(caps, flag), bool)


def test_capabilities_are_immutable():
    caps = ProviderCapabilities(engine="x", context_window=1)
    with pytest.raises(Exception):
        caps.context_window = 2


# --- benchmark integrity -----------------------------------------------------


def test_benchmark_api_client_has_no_hardcoded_key():
    """
    v1.5.1 eliminated the hardcoded default key (08101954) from the kernel, but
    benchmarking/api_client.py kept a copy as a fallback and printed the live key
    to stdout on every run. Guard both.
    """
    src = (PERIDOT_ROOT / "benchmarking" / "api_client.py").read_text(encoding="utf-8")
    assert "08101954" not in src, "hardcoded default API key must not be reintroduced"
    assert "Using API Key" not in src, "API key must never be echoed to stdout"


def test_no_hardcoded_default_key_anywhere_in_tree():
    offenders = []
    for path in PERIDOT_ROOT.rglob("*.py"):
        if "venv" in path.parts or "__pycache__" in path.parts:
            continue
        if path.name == "test_v16_providers.py":
            continue
        try:
            if "08101954" in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(PERIDOT_ROOT)))
        except (UnicodeDecodeError, OSError):
            continue
    assert not offenders, f"hardcoded key present in: {offenders}"
