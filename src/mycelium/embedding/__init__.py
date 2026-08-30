# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Embedding: the compiler's one declared non-deterministic stage (D-013, ADR-0017).

- :mod:`mycelium.embedding.base` — the :class:`Embedder` protocol and its failure
  taxonomy, of which :class:`EmbedderUnavailableError` is the *degradable* one.
- :mod:`mycelium.embedding.models` — the pinned model registry, the local cache,
  and the opt-in verified download (D-017: no network call unless configured).
- :mod:`mycelium.embedding.onnx` — the v1 default: a local ONNX encoder, zero
  keys, behind the optional ``embeddings`` dependency set.

Vectors are keyed ``(chunk_digest, model_id)``, so unchanged text is never
re-embedded and switching models adds rows instead of destroying them (D-013).
"""

from pathlib import Path

from mycelium.embedding.base import Embedder, EmbedderUnavailableError, EmbeddingError
from mycelium.embedding.models import (
    CACHE_ENV_VAR,
    DEFAULT_MODEL_ID,
    MODELS,
    ModelFile,
    ModelSpec,
    cache_root,
    model_spec,
    resolve_model,
)
from mycelium.embedding.onnx import PROVIDER, LocalOnnxEmbedder

__all__ = [
    "CACHE_ENV_VAR",
    "DEFAULT_MODEL_ID",
    "MODELS",
    "PROVIDER",
    "Embedder",
    "EmbedderUnavailableError",
    "EmbeddingError",
    "LocalOnnxEmbedder",
    "ModelFile",
    "ModelSpec",
    "build_embedder",
    "cache_root",
    "model_spec",
    "resolve_model",
]

PROVIDER_NONE = "none"
"""Configured provider that means "publish no vectors" — not a failure, a choice."""


def build_embedder(
    *,
    provider: str,
    model_id: str,
    model_path: Path | None = None,
    allow_download: bool = False,
) -> Embedder | None:
    """Resolve the configured embedder, or ``None`` when vectors are switched off.

    ``None`` and :class:`EmbedderUnavailableError` are deliberately different
    answers: the first is an operator saying they do not want vectors, the second
    is an operator who wants them and cannot have them yet. A build reports the
    second as a degraded snapshot and stays silent about the first.
    """
    if provider == PROVIDER_NONE:
        return None
    if provider != PROVIDER:
        known = f"{PROVIDER}, {PROVIDER_NONE}"
        msg = (
            f"unknown embedding provider {provider!r}; v1 ships: {known}. "
            "API providers are an opt-in plugin surface, not a v1 default (D-013)."
        )
        raise EmbedderUnavailableError(msg)
    return LocalOnnxEmbedder.load(
        model_id=model_id, model_path=model_path, allow_download=allow_download
    )
