# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Test doubles that satisfy a product protocol without a product dependency."""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mycelium.synthesis.provider import Completion

__all__ = ["FakeEmbedder", "ScriptedProvider", "hash_token"]


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


class ScriptedProvider:
    """An LLM that answers from a list, in order — the synthesis lane's test double.

    It satisfies :class:`~mycelium.synthesis.provider.LlmProvider` in a dozen
    lines, which is the check that the seam is a seam: everything the lane
    decides — the prompt, the citation contract, the repair round-trip, the
    refusal — is decided around this object, and none of it needs a network.

    `prompts` records what it was asked, so a test can assert that the citable
    vocabulary reached the model and that the second attempt carried the first
    attempt's violations.
    """

    def __init__(self, *answers: str, model: str = "scripted-1") -> None:
        self._answers = list(answers)
        self._model = model
        self.prompts: list[str] = []
        self.systems: list[str] = []

    @property
    def name(self) -> str:
        return "scripted"

    @property
    def model(self) -> str:
        return self._model

    def complete(self, *, system: str, prompt: str) -> "Completion":
        from mycelium.synthesis.provider import Completion

        self.prompts.append(prompt)
        self.systems.append(system)
        if not self._answers:
            msg = "the scripted provider ran out of answers"
            raise AssertionError(msg)
        return Completion(
            text=self._answers.pop(0), model=self._model, parameters={"effort": "high"}
        )
