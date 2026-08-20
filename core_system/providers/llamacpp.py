# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.x | TURBOQUANT / LLAMA-CPP-PYTHON PROVIDER
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
The permanent default inference path.

This provider wraps llama-cpp-python with exactly the call signature server.py
has always used, so moving the kernel onto the provider abstraction is a
refactor rather than a behaviour change.

It runs the model IN-PROCESS. That is deliberate for the default single-model
case and for benchmarking, but it carries a known ceiling: llama-cpp-python's
CUDA context does not reliably release VRAM without a process exit, so unload()
cannot fully guarantee reclamation. The child-process provider exists for model
swapping, where that guarantee is required.
"""

from __future__ import annotations

import gc
import logging
from pathlib import Path
from typing import Any, Iterator

from core_system.providers.base import (
    BaseInferenceProvider,
    ProviderCapabilities,
    ProviderLoadError,
)

logger = logging.getLogger("Peridot-Provider-LlamaCpp")

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


class LlamaCppProvider(BaseInferenceProvider):
    """GGUF inference via llama-cpp-python (cuBLAS build)."""

    ENGINE = "llama-cpp-python"

    def __init__(
        self,
        model_path: Path | str,
        n_ctx: int = 4096,
        n_gpu_layers: int = 0,
        n_threads: int = 8,
        n_batch: int = 1024,
        flash_attn: bool = True,
        verbose: bool = False,
        supports_thinking: bool = False,
        supports_vision: bool = False,
        **engine_options: Any,
    ):
        super().__init__(model_path, **engine_options)
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.n_threads = n_threads
        self.n_batch = n_batch
        self.flash_attn = flash_attn
        self.verbose = verbose
        self._supports_thinking = supports_thinking
        self._supports_vision = supports_vision
        self._llm: Any = None

    # --- lifecycle -----------------------------------------------------------

    def load(self) -> None:
        if self._loaded:
            return

        if not self.model_path.exists():
            raise ProviderLoadError(f"Model file not found: {self.model_path}")

        try:
            from llama_cpp import Llama
        except Exception as e:
            raise ProviderLoadError(f"llama-cpp-python unavailable: {e}") from e

        _audit("info", f"PROVIDER | Loading {self.model_path.name} via {self.ENGINE}.")
        logger.info("Loading %s (n_gpu_layers=%s, n_ctx=%s)", self.model_path.name, self.n_gpu_layers, self.n_ctx)

        try:
            self._llm = Llama(
                model_path=str(self.model_path),
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                n_gpu_layers=self.n_gpu_layers,
                n_gpu=1 if self.n_gpu_layers != 0 else 0,
                n_batch=self.n_batch,
                flash_attn=self.flash_attn,
                verbose=self.verbose,
            )
        except Exception as e:
            # Surfaced as a recoverable error so the kernel stays up. A malformed
            # or unsupported GGUF (e.g. an MTP head the runtime cannot build)
            # must never terminate the server.
            self._llm = None
            _audit("error", f"PROVIDER | Load FAILED for {self.model_path.name}: {e}")
            raise ProviderLoadError(f"Failed to load {self.model_path.name}: {e}") from e

        self._loaded = True
        _audit("info", f"PROVIDER | {self.model_path.name} online.")

    def unload(self) -> None:
        if not self._loaded:
            return

        _audit("info", f"PROVIDER | Unloading {self.model_path.name}.")
        try:
            if self._llm is not None and hasattr(self._llm, "close"):
                self._llm.close()
        except Exception as e:
            logger.warning("close() failed during unload: %s", e)

        self._llm = None
        self._loaded = False
        gc.collect()
        # ponytail: in-process unload cannot guarantee VRAM reclamation --
        # llama.cpp's CUDA context outlives the Python object. Use the
        # child-process provider when a hard guarantee is required.

    # --- inference -----------------------------------------------------------

    def tokenize(self, text: str) -> list[int]:
        if not self._loaded or self._llm is None:
            raise ProviderLoadError("tokenize() called before load().")
        return list(self._llm.tokenize(text.encode("utf-8")))

    def generate_stream(self, prompt: str, **params: Any) -> Iterator[str]:
        if not self._loaded or self._llm is None:
            raise ProviderLoadError("generate_stream() called before load().")

        call_params: dict[str, Any] = {
            "max_tokens": params.get("max_tokens", 512),
            "temperature": params.get("temperature", 0.1),
            "top_p": params.get("top_p", 0.9),
            "repeat_penalty": params.get("repeat_penalty", 1.1),
            "echo": False,
            "stream": True,
        }
        stop = params.get("stop")
        if stop:
            call_params["stop"] = stop

        for piece in self._llm(prompt, **call_params):
            text = piece.get("choices", [{}])[0].get("text", "")
            if text:
                yield text

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            engine=self.ENGINE,
            context_window=self.n_ctx,
            supports_thinking=self._supports_thinking,
            supports_vision=self._supports_vision,
            supports_streaming=True,
        )
