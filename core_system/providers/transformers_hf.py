# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.1 | HUGGING FACE TRANSFORMERS PROVIDER
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
.safetensors inference via Hugging Face transformers.

A model is a FOLDER (config.json + *.safetensors + tokenizer files), not a
single file -- providers.is_hf_model_dir() decides that. Additive to the
llama.cpp default path, never a replacement for it.

Weights load in the folder's own dtype (dtype="auto"), whole-model onto CUDA
when available, else CPU. No accelerate/device_map offload and no
bitsandbytes quantisation: a model that does not fit in VRAM fails to load
with a recoverable ProviderLoadError.
"""

from __future__ import annotations

import gc
import json
import logging
import threading
from pathlib import Path
from typing import Any, Iterator

from core_system.providers.base import (
    BaseInferenceProvider,
    GenerationResult,
    ProviderCapabilities,
    ProviderLoadError,
)

logger = logging.getLogger("Peridot-Provider-Transformers")

try:
    from core_system.audit import ghost
except Exception:  # pragma: no cover - audit is optional at import time
    ghost = None


def _audit(level: str, message: str) -> None:
    """GhostLogger is mandatory for new subsystems, but must never be fatal."""
    if ghost is None:
        return
    try:
        getattr(ghost, level)(message)
    except Exception:
        pass


def _cuda_usable(torch: Any) -> bool:
    """
    CUDA is present AND this torch build has kernels for the GPU.

    is_available() alone is not enough: a cu124 wheel on an sm_120 (RTX 50xx)
    card reports True, loads fine, then dies on the first kernel launch with
    "no kernel image is available". Fall back to CPU instead.
    """
    if not torch.cuda.is_available():
        return False
    major, minor = torch.cuda.get_device_capability()
    if f"sm_{major}{minor}" in torch.cuda.get_arch_list():
        return True
    logger.warning("torch %s has no kernels for sm_%s%s; transformers provider runs on CPU.",
                   torch.__version__, major, minor)
    _audit("warning", f"PROVIDER | torch lacks sm_{major}{minor} kernels; using CPU.")
    return False


class StopTrimmer:
    """
    Cuts streamed text at the first stop string, never leaking a partial one.

    Text that could still be the start of a stop string is held back until the
    next chunk proves otherwise (or flush() at the end of the stream).
    """

    def __init__(self, stops: list[str]):
        self.stops = [s for s in stops if s]
        self.buf = ""
        self.hit = False

    def feed(self, text: str) -> str:
        if self.hit:
            return ""
        self.buf += text
        cuts = [i for i in (self.buf.find(s) for s in self.stops) if i >= 0]
        if cuts:
            self.hit = True
            out, self.buf = self.buf[:min(cuts)], ""
            return out
        held = max((n for s in self.stops for n in range(1, len(s))
                    if self.buf.endswith(s[:n])), default=0)
        cut = len(self.buf) - held
        out, self.buf = self.buf[:cut], self.buf[cut:]
        return out

    def flush(self) -> str:
        out, self.buf = ("" if self.hit else self.buf), ""
        return out


class TransformersProvider(BaseInferenceProvider):
    """HF transformers causal LM loaded from a local model folder."""

    ENGINE = "transformers"

    def __init__(
        self,
        model_path: Path | str,
        n_ctx: int | None = None,
        supports_thinking: bool = False,
        supports_vision: bool = False,
        **engine_options: Any,
    ):
        # llama.cpp-only knobs (n_gpu_layers, n_batch, kv_cache_type, ...) land
        # in engine_options and are ignored, so server.py's boot call works as-is.
        super().__init__(model_path, **engine_options)
        self.n_ctx = n_ctx
        self._supports_thinking = supports_thinking
        self._supports_vision = supports_vision
        self._model: Any = None
        self._tokenizer: Any = None
        self._gen_thread: threading.Thread | None = None
        self._last_finish_reason: str | None = None

    # --- lifecycle -----------------------------------------------------------

    def load(self) -> None:
        if self._loaded:
            return

        if not (self.model_path / "config.json").is_file():
            raise ProviderLoadError(f"Not a Hugging Face model folder: {self.model_path}")

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except Exception as e:
            raise ProviderLoadError(f"transformers/torch unavailable: {e}") from e

        device = "cuda" if _cuda_usable(torch) else "cpu"
        _audit("info", f"PROVIDER | Loading {self.model_path.name} via {self.ENGINE} ({device}).")
        logger.info("Loading %s on %s", self.model_path.name, device)
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
            # ponytail: whole model on one device; no accelerate offload, so a
            # model larger than VRAM fails here. Add device_map when accelerate ships.
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_path, dtype="auto", local_files_only=True,
            ).to(device)
            self._model.eval()
        except Exception as e:
            self._model = self._tokenizer = None
            _audit("error", f"PROVIDER | Load FAILED for {self.model_path.name}: {e}")
            raise ProviderLoadError(f"Failed to load {self.model_path.name}: {e}") from e

        self._loaded = True
        _audit("info", f"PROVIDER | {self.model_path.name} online.")

    def unload(self) -> None:
        if not self._loaded:
            return
        _audit("info", f"PROVIDER | Unloading {self.model_path.name}.")
        self._model = self._tokenizer = None
        self._loaded = False
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:
            logger.warning("empty_cache() failed during unload: %s", e)

    # --- inference -----------------------------------------------------------

    def tokenize(self, text: str) -> list[int]:
        if not self._loaded or self._tokenizer is None:
            raise ProviderLoadError("tokenize() called before load().")
        return list(self._tokenizer.encode(text, add_special_tokens=False))

    def generate_stream(self, prompt: str, **params: Any) -> Iterator[str]:
        if not self._loaded or self._model is None:
            raise ProviderLoadError("generate_stream() called before load().")

        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList, TextIteratorStreamer

        tok = self._tokenizer
        stops = [s for s in (params.get("stop") or []) if s]
        input_ids = tok(prompt, return_tensors="pt", add_special_tokens=False).input_ids
        input_ids = input_ids.to(self._model.device)
        prompt_len = input_ids.shape[1]
        max_new = params.get("max_tokens", 512)
        temperature = params.get("temperature", 0.1)
        # Each token decodes to >= 1 char, so this many tokens covers any stop.
        tail = max(map(len, stops), default=0)
        halt = threading.Event()

        class _Stop(StoppingCriteria):
            """Stop string seen in the generated tail, or the consumer went away."""

            def __call__(self, ids, scores, **kwargs):
                hit = halt.is_set()
                if not hit and tail:
                    text = tok.decode(ids[0, prompt_len:][-tail:], skip_special_tokens=False)
                    hit = any(s in text for s in stops)
                return torch.full((ids.shape[0],), hit, dtype=torch.bool, device=ids.device)

        # Special tokens stay visible so chat-template stops (<|im_end|>) can be
        # matched; the trimmer below keeps them (and EOS) out of the output.
        streamer = TextIteratorStreamer(tok, skip_prompt=True, skip_special_tokens=False)
        gen_kwargs: dict[str, Any] = {
            "input_ids": input_ids,
            "attention_mask": torch.ones_like(input_ids),
            "max_new_tokens": max_new,
            "repetition_penalty": params.get("repeat_penalty", 1.1),
            "stopping_criteria": StoppingCriteriaList([_Stop()]),
            "streamer": streamer,
            "pad_token_id": tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id,
        }
        if temperature and temperature > 0:
            gen_kwargs.update(do_sample=True, temperature=temperature,
                              top_p=params.get("top_p", 0.9), top_k=params.get("top_k", 40))
        else:
            gen_kwargs.update(do_sample=False, temperature=None, top_p=None, top_k=None)

        outcome: dict[str, Any] = {}

        def _run() -> None:
            try:
                with torch.inference_mode():
                    outcome["n_new"] = self._model.generate(**gen_kwargs).shape[1] - prompt_len
            except Exception as e:
                outcome["error"] = e
                streamer.end()  # unblock the consumer; error re-raised below

        trimmer = StopTrimmer(stops + ([tok.eos_token] if tok.eos_token else []))
        self._last_finish_reason = None
        thread = threading.Thread(target=_run, name="peridot-hf-generate", daemon=True)
        self._gen_thread = thread
        thread.start()
        try:
            for piece in streamer:
                text = trimmer.feed(piece)
                if text:
                    yield text
                if trimmer.hit:
                    break
            text = trimmer.flush()
            if text:
                yield text
        finally:
            # Runs on normal end, on early break, and when the consumer abandons
            # the generator (on_chunk raised -> generator closed): stop the
            # worker instead of letting it decode to max_new_tokens.
            halt.set()
            thread.join()

        if "error" in outcome:
            raise outcome["error"]
        if trimmer.hit or outcome.get("n_new", 0) < max_new:
            self._last_finish_reason = "stop"
        else:
            self._last_finish_reason = "length"

    def generate(self, prompt: str, **params: Any) -> GenerationResult:
        """Base timing loop plus the real finish_reason (see LlamaCppProvider)."""
        result = super().generate(prompt, **params)
        if self._last_finish_reason:
            result.finish_reason = self._last_finish_reason
        return result

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            engine=self.ENGINE,
            context_window=self.n_ctx or self._config_context_window(),
            supports_thinking=self._supports_thinking,
            supports_vision=self._supports_vision,
            supports_streaming=True,
        )

    def _config_context_window(self) -> int:
        try:
            cfg = json.loads((self.model_path / "config.json").read_text(encoding="utf-8"))
            return int(cfg.get("max_position_embeddings") or 4096)
        except Exception:
            return 4096
