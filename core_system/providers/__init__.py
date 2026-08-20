# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.x | INFERENCE PROVIDER REGISTRY
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Provider selection.

Backend choice is automatic by file extension -- there is deliberately no manual
backend picker, per spec:

    .gguf -> llama-cpp-python (TurboQuant; permanent default path)
    .exl2 -> ExLlamaV2        (v1.6.x item 2, not yet implemented)

An unknown or not-yet-implemented extension raises UnsupportedModelFormat, which
callers must treat as recoverable: a bad or unrecognised model file must never
take the kernel down.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core_system.providers.base import (
    BaseInferenceProvider,
    GenerationResult,
    ProviderCapabilities,
    ProviderLoadError,
)
from core_system.providers.llamacpp import LlamaCppProvider

__all__ = [
    "BaseInferenceProvider",
    "GenerationResult",
    "ProviderCapabilities",
    "ProviderLoadError",
    "LlamaCppProvider",
    "UnsupportedModelFormat",
    "provider_for",
    "supported_extensions",
    "EXTENSION_MAP",
]


class UnsupportedModelFormat(ProviderLoadError):
    """No provider is registered for this model file's extension."""


# Engines that exist today. ExLlamaV2/vLLM register themselves here when built;
# until then .exl2 raises a clear "not implemented yet" rather than a KeyError.
EXTENSION_MAP: dict[str, type[BaseInferenceProvider]] = {
    ".gguf": LlamaCppProvider,
}

_PLANNED: dict[str, str] = {
    ".exl2": "ExLlamaV2 (v1.6.x item 2)",
    ".safetensors": "vLLM (v1.6.x item 2)",
}


def supported_extensions() -> tuple[str, ...]:
    return tuple(sorted(EXTENSION_MAP))


def provider_for(model_path: Path | str, **options: Any) -> BaseInferenceProvider:
    """
    Construct (but do not load) the right provider for this model file.

    Raises UnsupportedModelFormat for unknown or planned-but-unbuilt formats.
    """
    path = Path(model_path)
    ext = path.suffix.lower()

    provider_cls = EXTENSION_MAP.get(ext)
    if provider_cls is not None:
        return provider_cls(path, **options)

    if ext in _PLANNED:
        raise UnsupportedModelFormat(
            f"{ext} requires {_PLANNED[ext]}, which is not implemented yet. "
            f"Supported now: {', '.join(supported_extensions())}"
        )

    raise UnsupportedModelFormat(
        f"No inference provider for '{ext or path.name}'. "
        f"Supported: {', '.join(supported_extensions())}"
    )
