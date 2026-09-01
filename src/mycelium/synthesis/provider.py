# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The LLM seam: one call, text in, text out.

Deliberately *not* in :mod:`mycelium.sdk.protocols`. That module holds the
contracts spec 05 §4.1 names — `Connector`, `Parser`, `Synthesizer` and the rest
of the plugin list — and a provider is not on it: it sits *inside* a synthesizer,
the way the ONNX encoder sits inside the embedder (ADR-0017). Putting it here
keeps the frozen contract surface exactly as large as the spec says it is.

The seam earns its place three times over:

1. **The lane is testable without a network.** Every rule that matters — the
   prompt, the citation contract, the repair round-trip, the candidate document —
   is exercised against a scripted provider that returns fixed text. What is left
   untested offline is one HTTP call, and that is the honest boundary rather than
   a mocked pretence of one.
2. **A second provider is a class, not a refactor.** `[synthesis] provider` is
   pinned and resolved exactly like a parser (spec 05 §4.2): named, or nothing.
3. **The network stays where the config put it.** Nothing here imports a client;
   construction is the only place a provider can appear, and it happens only when
   an operator named one (D-013/D-017).
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from pydantic import JsonValue

__all__ = ["Completion", "LlmProvider"]


@dataclass(frozen=True, slots=True)
class Completion:
    """One model response, plus what a manifest has to record about it."""

    text: str
    model: str
    """The model that actually answered — read back from the response, not from
    the request. A provider that silently routed elsewhere must not be recorded
    as the model that was asked for."""

    parameters: dict[str, JsonValue] = field(default_factory=dict)
    """The request parameters that shaped the output: effort, thinking mode,
    token ceiling. Recorded in the synthesis record so a document can be
    explained, never to make it reproducible — it is not."""


@runtime_checkable
class LlmProvider(Protocol):
    """Sends one prompt and returns one completion."""

    @property
    def name(self) -> str:
        """The provider id from `[synthesis] provider` — `anthropic`, and so on."""
        ...

    @property
    def model(self) -> str:
        """The model this provider was configured to ask for."""
        ...

    def complete(self, *, system: str, prompt: str) -> Completion:
        """Answer `prompt` under `system`, or raise a provider error.

        One call, no streaming, no tools, no conversation. The synthesis lane
        writes one document from one prompt, and a seam wide enough for an agent
        loop would be a seam nobody can reason about (D-001: Mycelium serves
        agents, it is not one).

        Raises :class:`~mycelium.synthesis.errors.ProviderError` for anything the
        caller cannot work around.
        """
        ...
