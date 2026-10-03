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
    HF folder (config.json + *.safetensors) -> transformers (v1.6.1)

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
from core_system.providers.transformers_hf import TransformersProvider

__all__ = [
    "BaseInferenceProvider",
    "GenerationResult",
    "ProviderCapabilities",
    "ProviderLoadError",
    "LlamaCppProvider",
    "TransformersProvider",
    "UnsupportedModelFormat",
    "is_hf_model_dir",
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
}


def supported_extensions() -> tuple[str, ...]:
    return tuple(sorted(EXTENSION_MAP))


def is_hf_model_dir(path: Path | str) -> bool:
    """A Hugging Face model folder: config.json plus at least one *.safetensors."""
    path = Path(path)
    return (path / "config.json").is_file() and any(path.glob("*.safetensors"))


def provider_for(model_path: Path | str, **options: Any) -> BaseInferenceProvider:
    """
    Construct (but do not load) the right provider for this model file or folder.

    Raises UnsupportedModelFormat for unknown or planned-but-unbuilt formats.
    """
    path = Path(model_path)
    if is_hf_model_dir(path):
        return TransformersProvider(path, **options)

    ext = path.suffix.lower()
    if ext == ".safetensors":
        raise UnsupportedModelFormat(
            f"{path.name} is one shard of a Hugging Face model. Select the model's "
            "folder (the one containing config.json), not the .safetensors file."
        )

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
