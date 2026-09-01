# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Synthesis: the LLM lane of ingestion (D-020, spec 02 §5).

Ingestion is dual-lane. The **evidence lane** always runs, is deterministic, and
produces a verbatim projection with a fidelity report (roadmap 4.1-4.3). This
package is the **synthesis lane**: it authors a *readable* document from that
evidence, in which every claim carries a wikilink citation into it.

The lane is allowed to exist because the citations can be checked. That check —
:mod:`mycelium.synthesis.citations` — is the deterministic half, and it is what
separates "an LLM wrote documentation" from "an LLM wrote documentation you can
verify". A document that fails it is not written.

- :mod:`mycelium.synthesis.provider` — the LLM seam; one call, text in, text out.
- :mod:`mycelium.synthesis.providers.anthropic` — the v1 backend, opt-in.
- :mod:`mycelium.synthesis.wiki` — the `wiki` plugin (D-026): the prompt, the
  closed citable vocabulary, the one repair round-trip, and the refusal.
- :mod:`mycelium.synthesis.citations` — the contract, and the coverage number
  gate G7 will read (roadmap 4.5).
- :mod:`mycelium.synthesis.candidate` — the file that lands in
  `knowledge/candidate/`, and the provenance it declares.
- :mod:`mycelium.synthesis.lane` — the four steps in the one order they happen.

Nothing here runs unless `[synthesis]` names a provider. A default install
synthesizes nothing and makes no network call (D-013/D-017).
"""

from typing import TYPE_CHECKING

from mycelium.synthesis.candidate import CANDIDATE_DIRNAME, Candidate, candidate_path, render
from mycelium.synthesis.citations import CitationReport, check, review
from mycelium.synthesis.errors import (
    ProviderError,
    ProviderUnavailableError,
    SynthesisError,
    UngroundedError,
)
from mycelium.synthesis.lane import (
    Synthesized,
    encode_record,
    evidence_of,
    synthesize_candidate,
    topic_of,
    write_candidate,
)
from mycelium.synthesis.provider import Completion, LlmProvider
from mycelium.synthesis.wiki import PLUGIN_ID, WikiSynthesizer

if TYPE_CHECKING:
    from mycelium.config import SynthesisConfig

__all__ = [
    "CANDIDATE_DIRNAME",
    "PLUGIN_ID",
    "Candidate",
    "CitationReport",
    "Completion",
    "LlmProvider",
    "ProviderError",
    "ProviderUnavailableError",
    "SynthesisError",
    "Synthesized",
    "UngroundedError",
    "WikiSynthesizer",
    "build_provider",
    "build_synthesizer",
    "candidate_path",
    "check",
    "encode_record",
    "evidence_of",
    "render",
    "review",
    "synthesize_candidate",
    "topic_of",
    "write_candidate",
]

PROVIDERS = ("anthropic",)
"""Provider ids v1 resolves. Pinned by name, never chosen (spec 05 §4.2)."""


def build_provider(settings: "SynthesisConfig") -> LlmProvider:
    """Resolve the configured provider, or say precisely why it cannot be used.

    Raises :class:`ProviderUnavailableError` — the *degradable* failure — when no
    provider is named, when its id is unknown, when its SDK is not installed, or
    when it has no credential. The caller reports and carries on: the evidence
    lane has already produced everything the compiler needs (D-020).
    """
    from mycelium.synthesis.providers import anthropic as anthropic_provider

    if not settings.provider:
        msg = (
            "no LLM provider is configured, so the synthesis lane does not run; "
            'set [synthesis] provider = "anthropic" to enable it'
        )
        raise ProviderUnavailableError(msg)
    if settings.provider != anthropic_provider.PROVIDER_ID:
        known = ", ".join(PROVIDERS)
        msg = (
            f"unknown synthesis provider {settings.provider!r}; v1 resolves: {known}. "
            "A provider is pinned by name, never chosen for being installed."
        )
        raise ProviderUnavailableError(msg)
    return anthropic_provider.build(
        model=settings.model_id or anthropic_provider.DEFAULT_MODEL,
        max_tokens=settings.max_output_tokens,
        effort=settings.effort,
        timeout_s=anthropic_provider.DEFAULT_TIMEOUT_S,
    )


def build_synthesizer(settings: "SynthesisConfig") -> WikiSynthesizer:
    """Resolve the configured synthesizer over its configured provider.

    One plugin ships (`wiki`, D-026) and the configuration validator already
    refuses any other name, so this reads as a single construction rather than a
    registry — the registry arrives with the third-party plugin that needs it.
    """
    return WikiSynthesizer(build_provider(settings), min_coverage=settings.min_citation_coverage)
