# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Test doubles that satisfy a product protocol without a product dependency."""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = ["FakeEmbedder", "hash_token"]


def hash_token(token: str) -> int:
    """A stable hash — Python's own is salted per process (PYTHONHASHSEED)."""
    value = 0
    for char in token:
        value = (value * 131 + ord(char)) & 0xFFFFFFFF
    return value


@dataclass(frozen=True, slots=True)
class FakeEmbedder:
    """A deterministic, dependency-free embedder for testing the vector path.

    It hashes tokens into a small fixed space and L2-normalises the result, so
    similarity tracks vocabulary overlap. That is not semantics — no test claims
    it is — but it is exactly what the *mechanics* under test need: a stable
    model identity, unit vectors of a declared dimension, and rankings that
    respond to content. The real model's retrieval quality is measured against
    the judged cases in `eval/` and recorded in ADR-0017.

    It also keeps the vector leg covered on every CI platform, where no model is
    present and the ONNX embedder cannot run.
    """

    model_id: str = "fake-hash-v1"
    provider: str = "test"
    dim: int = 32
    deterministic: bool = True

    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> tuple[float, ...]:
        return self._vector(text)

    def _vector(self, text: str) -> tuple[float, ...]:
        weights = [0.0] * self.dim
        for token in re.findall(r"\w+", text.lower()):
            weights[hash_token(token) % self.dim] += 1.0
        norm = math.sqrt(sum(value * value for value in weights))
        if not norm:
            # A vector of zeros has no direction; give it one so cosine is defined.
            return tuple(1.0 if index == 0 else 0.0 for index in range(self.dim))
        return tuple(value / norm for value in weights)
