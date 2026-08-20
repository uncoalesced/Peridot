# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.x | INFERENCE PROVIDER CONTRACT
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
BaseInferenceProvider -- the engine-agnostic inference contract.

Defined with its full surface from day one even though llama-cpp-python is the
only implementation initially, so that adding ExLlamaV2 (v1.6.x item 2) or a
WebUI-only cloud backend (v1.8.x) is an additive change rather than a breaking
interface revision.

Standing rule: TurboQuant / llama-cpp-python is the permanent, hardcoded default
path. Every other provider is additive and never replaces it.

Timing model
------------
`generate()` is deliberately implemented here on top of the abstract
`generate_stream()` rather than left to each engine. That gives one
engine-agnostic definition of prefill vs decode:

    prefill_seconds = time until the FIRST token arrives
    decode_seconds  = time from the first token to the last

Measuring from the stream works identically for llama.cpp, ExLlamaV2 and vLLM.
Relying on llama.cpp's internal perf counters would not -- other engines do not
expose them, and the first cross-engine comparison would be measuring different
things on each side.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class ProviderCapabilities:
    """
    What an engine/model pair can actually do.

    Consumed by v1.7.x FreeThink (`supports_thinking` decides whether the manual
    [ANALYSIS]/[KERNEL_RESPONSE] scaffold is bypassed) and by image input
    (`supports_vision`).
    """

    engine: str
    context_window: int
    supports_thinking: bool = False
    supports_vision: bool = False
    supports_streaming: bool = True


@dataclass
class GenerationResult:
    """One completed generation, with prefill and decode timed separately."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    prefill_seconds: float
    decode_seconds: float
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_seconds(self) -> float:
        return self.prefill_seconds + self.decode_seconds

    @property
    def decode_tokens_per_second(self) -> float:
        """
        Pure generation rate: excludes prefill entirely.

        The first token is not counted -- it is produced by prefill, and
        including it would inflate the rate on short generations.
        """
        billable = max(0, self.completion_tokens - 1)
        if self.decode_seconds <= 0 or billable == 0:
            return 0.0
        return billable / self.decode_seconds

    @property
    def prefill_tokens_per_second(self) -> float:
        if self.prefill_seconds <= 0 or self.prompt_tokens == 0:
            return 0.0
        return self.prompt_tokens / self.prefill_seconds

    @property
    def end_to_end_tokens_per_second(self) -> float:
        """Comparable to the historical benchmark metric, for continuity."""
        if self.total_seconds <= 0:
            return 0.0
        return self.completion_tokens / self.total_seconds


class ProviderLoadError(RuntimeError):
    """
    Raised when a model cannot be loaded.

    Callers must treat this as recoverable: a bad model file must never take the
    kernel down. server.py stays up on the previous model, or on no model.
    """


class BaseInferenceProvider(ABC):
    """
    One loaded model, behind one engine.

    Lifecycle: construct -> load() -> generate()/generate_stream()* -> unload().
    Implementations must tolerate load() on an already-loaded provider (no-op)
    and unload() on an unloaded one (no-op), so callers do not have to track it.
    """

    def __init__(self, model_path: Path | str, **engine_options: Any):
        self.model_path = Path(model_path)
        self.engine_options = engine_options
        self._loaded = False

    # --- lifecycle -----------------------------------------------------------

    @abstractmethod
    def load(self) -> None:
        """Bring the model into memory. Raises ProviderLoadError on failure."""

    @abstractmethod
    def unload(self) -> None:
        """
        Release the model and its VRAM.

        In-process engines cannot fully guarantee this -- llama-cpp-python's CUDA
        context does not reliably release VRAM without a process exit, which is
        precisely why the child-process provider exists.
        """

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # --- inference -----------------------------------------------------------

    @abstractmethod
    def generate_stream(self, prompt: str, **params: Any) -> Iterator[str]:
        """Yield generated text incrementally. Must yield at least once."""

    @abstractmethod
    def tokenize(self, text: str) -> list[int]:
        """Real tokenizer output. Never an approximation."""

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        ...

    def token_count(self, text: str) -> int:
        return len(self.tokenize(text))

    def generate(self, prompt: str, **params: Any) -> GenerationResult:
        """
        Run a full generation, timing prefill and decode separately.

        Concrete on purpose -- see the module docstring. Engines override this
        only if they can measure the split more accurately themselves.
        """
        if not self.is_loaded:
            raise ProviderLoadError(f"{type(self).__name__} is not loaded.")

        prompt_tokens = self.token_count(prompt)

        start = time.perf_counter()
        first_token_at: float | None = None
        chunks: list[str] = []

        for chunk in self.generate_stream(prompt, **params):
            if first_token_at is None:
                first_token_at = time.perf_counter()
            chunks.append(chunk)

        end = time.perf_counter()
        text = "".join(chunks)

        # A stream that yielded nothing: all time counts as prefill.
        if first_token_at is None:
            first_token_at = end

        completion_tokens = self.token_count(text) if text else 0

        return GenerationResult(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            prefill_seconds=first_token_at - start,
            decode_seconds=end - first_token_at,
            metadata={"engine": self.capabilities.engine},
        )

    # --- context manager -----------------------------------------------------

    def __enter__(self) -> "BaseInferenceProvider":
        self.load()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.unload()

    def __repr__(self) -> str:
        state = "loaded" if self._loaded else "unloaded"
        return f"<{type(self).__name__} {self.model_path.name} [{state}]>"
