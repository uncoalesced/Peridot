# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | v1.6.1 TRANSFORMERS (.safetensors) PROVIDER TESTS
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# -----------------------------------------------------------------------------

"""
HF folder-model support: routing, stop trimming, cancellation, and the
constitution's format/thinking detection for folders.

No network: the real-model tests build a tiny random Llama plus a byte-level
BPE tokenizer in tmp_path and skip if torch/transformers are not importable.
"""

import json

import pytest

from core_system.prompting.constitution import (
    build_system_prompt,
    get_model_format,
    model_display_name,
    model_supports_thinking,
)
from core_system.providers import (
    LlamaCppProvider,
    TransformersProvider,
    UnsupportedModelFormat,
    is_hf_model_dir,
    provider_for,
)
from core_system.providers.transformers_hf import StopTrimmer

LLAMA_KWARGS = dict(n_ctx=128, n_threads=4, n_threads_batch=4, n_gpu_layers=99, n_batch=512,
                    n_ubatch=512, kv_cache_type="q8_0", flash_attn=True, verbose=False)


def _hf_dir(path, model_type="qwen2", tokenizer_config=None, weights=True):
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.json").write_text(json.dumps({"model_type": model_type}), encoding="utf-8")
    if tokenizer_config is not None:
        (path / "tokenizer_config.json").write_text(json.dumps(tokenizer_config), encoding="utf-8")
    if weights:
        (path / "model.safetensors").write_bytes(b"")
    return path


# --- routing -------------------------------------------------------------------


def test_is_hf_model_dir(tmp_path):
    assert is_hf_model_dir(_hf_dir(tmp_path / "ok"))
    assert not is_hf_model_dir(_hf_dir(tmp_path / "no_weights", weights=False))
    no_cfg = tmp_path / "no_cfg"
    no_cfg.mkdir()
    (no_cfg / "model.safetensors").write_bytes(b"")
    assert not is_hf_model_dir(no_cfg)
    nested = _hf_dir(tmp_path / "nested", weights=False)
    (nested / "sub").mkdir()
    (nested / "sub" / "model.safetensors").write_bytes(b"")
    assert not is_hf_model_dir(nested), "weights must be in the folder itself"
    assert not is_hf_model_dir(tmp_path / "missing")
    assert not is_hf_model_dir(tmp_path / "ok" / "model.safetensors")


def test_folder_routes_to_transformers_and_ignores_llama_kwargs(tmp_path):
    p = provider_for(_hf_dir(tmp_path / "Qwen3-4B"), supports_thinking=True, **LLAMA_KWARGS)
    assert isinstance(p, TransformersProvider) and not p.is_loaded
    caps = p.capabilities
    assert (caps.engine, caps.context_window, caps.supports_thinking) == ("transformers", 128, True)
    assert isinstance(provider_for(tmp_path / "x.gguf", **LLAMA_KWARGS), LlamaCppProvider)


def test_context_window_falls_back_to_config(tmp_path):
    d = _hf_dir(tmp_path / "m")
    (d / "config.json").write_text(json.dumps({"max_position_embeddings": 32768}), encoding="utf-8")
    assert TransformersProvider(d).capabilities.context_window == 32768


def test_bare_safetensors_file_is_rejected_with_folder_hint(tmp_path):
    shard = _hf_dir(tmp_path / "m") / "model.safetensors"
    with pytest.raises(UnsupportedModelFormat, match="folder"):
        provider_for(shard)


# --- stop trimming -----------------------------------------------------------


def _run_trimmer(stops, chunks):
    t = StopTrimmer(stops)
    out = [t.feed(c) for c in chunks] + [t.flush()]
    return out, t.hit


def test_trimmer_cuts_stop_split_across_chunks():
    out, hit = _run_trimmer(["<|im_end|>"], ["Hel", "lo<|im", "_end|>tail", "more"])
    assert "".join(out) == "Hello" and hit
    assert out[1] == "lo", "partial stop must be held back, not leaked"


def test_trimmer_releases_false_partial():
    out, hit = _run_trimmer(["<|im_end|>"], ["a<|i", "x"])
    assert out == ["a", "<|ix", ""] and not hit


def test_trimmer_earliest_stop_wins_and_no_stops_passthrough():
    out, _ = _run_trimmer(["</s>", "[INST]"], ["x [INST] y </s>"])
    assert "".join(out) == "x "
    assert _run_trimmer([], ["a", "b"]) == (["a", "b", ""], False)


# --- constitution for folders ---------------------------------------------------


def test_constitution_folder_format_thinking_and_name(tmp_path):
    llama3 = _hf_dir(tmp_path / "Llama-3.1-8B-Instruct", "llama",
                     {"added_tokens_decoder": {"128006": {"content": "<|start_header_id|>"}}})
    llama2 = _hf_dir(tmp_path / "Llama-2-7b", "llama", {})
    mistral = _hf_dir(tmp_path / "Mistral-Nemo", "mistral")
    qwen3 = _hf_dir(tmp_path / "Qwen3-4B", "qwen3",
                    {"chat_template": "{{ '<think>\\n' }}{{ messages }}"})
    jinja = _hf_dir(tmp_path / "Qwen3-jinja", "qwen3", {})
    (jinja / "chat_template.jinja").write_text("<think>", encoding="utf-8")

    assert get_model_format(llama3) == "llama3"
    assert get_model_format(llama2) == "chatml"
    assert get_model_format(mistral) == "mistral"
    assert get_model_format(qwen3) == "chatml"
    assert model_supports_thinking(qwen3) and model_supports_thinking(jinja)
    assert not model_supports_thinking(llama3) and not model_supports_thinking(mistral)
    assert model_display_name(qwen3.name) == "Qwen3-4B"
    assert model_display_name(str(qwen3)) == "Qwen3-4B"


def test_system_prompt_names_the_engine():
    assert "via llama.cpp." in build_system_prompt(model_name="Qwen3.8-27B-UD-IQ1_S.gguf")
    assert "Qwen3-4B, running locally via transformers." in build_system_prompt(model_name="Qwen3-4B")
    assert "via exllamav2." in build_system_prompt(model_name="m.exl2", engine="exllamav2")


# --- real tiny model -----------------------------------------------------------


@pytest.fixture(scope="module")
def tiny_model(tmp_path_factory):
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    from tokenizers import Tokenizer, decoders, models, pre_tokenizers, trainers

    d = tmp_path_factory.mktemp("TinyLlama-HF")
    tk = Tokenizer(models.BPE())
    tk.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tk.decoder = decoders.ByteLevel()
    tk.train_from_iterator(
        ["hello world peridot sovereign kernel test"] * 20,
        trainers.BpeTrainer(vocab_size=320, initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
                            special_tokens=["<|endoftext|>", "<|im_start|>", "<|im_end|>"]),
    )
    tok = transformers.PreTrainedTokenizerFast(
        tokenizer_object=tk, eos_token="<|endoftext|>", pad_token="<|endoftext|>")
    tok.save_pretrained(d)
    cfg = transformers.LlamaConfig(
        vocab_size=len(tok), hidden_size=32, num_hidden_layers=2, num_attention_heads=2,
        num_key_value_heads=2, intermediate_size=64, max_position_embeddings=256,
        eos_token_id=tok.eos_token_id, pad_token_id=tok.pad_token_id)
    torch.manual_seed(0)
    transformers.LlamaForCausalLM(cfg).save_pretrained(d, safe_serialization=True)
    assert is_hf_model_dir(d)
    return d


GREEDY = dict(temperature=0.0, repeat_penalty=1.0)


def test_load_generate_unload(tiny_model):
    p = provider_for(tiny_model, **LLAMA_KWARGS)
    p.load()
    p.load()  # idempotent
    try:
        assert p.token_count("hello world") > 0
        r = p.generate("hello world", max_tokens=6, **GREEDY)
        assert r.text, "tiny model should produce some text"
        assert r.finish_reason in ("stop", "length")
        assert r.metadata["engine"] == "transformers"
        assert p.generate("hello", max_tokens=6, temperature=0.8).finish_reason in ("stop", "length")
    finally:
        p.unload()
    p.unload()  # idempotent
    assert not p.is_loaded


def test_stop_string_halts_generation(tiny_model):
    with provider_for(tiny_model) as p:
        free = p.generate("hello world", max_tokens=12, **GREEDY)
        assert len(free.text) >= 2
        stopped = p.generate("hello world", max_tokens=12, stop=[free.text[:2]], **GREEDY)
        assert stopped.text == "" and stopped.finish_reason == "stop"
        assert not p._gen_thread.is_alive()


def test_cancel_from_on_chunk_stops_worker_thread(tiny_model):
    class Cancelled(Exception):
        pass

    def on_chunk(_chunk):
        raise Cancelled()

    with provider_for(tiny_model) as p:
        with pytest.raises(Cancelled):
            p.generate("hello world", max_tokens=200, on_chunk=on_chunk, **GREEDY)
        assert not p._gen_thread.is_alive()
