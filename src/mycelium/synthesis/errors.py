# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The synthesis lane's failure taxonomy (spec 02 §5, D-020).

The distinctions exist because the answers differ, and one of them is the whole
point of the lane:

- :class:`ProviderUnavailableError` — no LLM is configured, or the one that is
  cannot be reached from here. Ingestion continues: the evidence lane always
  runs, the synthesis lane is the *additional* one (D-020), and a build that
  failed because an API key was missing would make the optional lane mandatory.
- :class:`ProviderError` — the provider was reached and refused, timed out, or
  answered with something that is not a message. A per-source failure.
- :class:`UngroundedError` — the model wrote prose that does not satisfy the
  citation contract: a wikilink that resolves to nothing, or a document that
  cites nothing at all. **This is a refusal to write the file**, not a warning.
  An uncited claim sitting in `knowledge/candidate/` is exactly what D-020 exists
  to prevent, and a lane that wrote it anyway with a warning attached would be a
  lane that does not work.
"""

__all__ = [
    "ProviderError",
    "ProviderUnavailableError",
    "SynthesisError",
    "UngroundedError",
]


class SynthesisError(RuntimeError):
    """Base of every synthesis-lane failure."""


class ProviderError(SynthesisError):
    """The configured LLM provider failed to answer."""


class ProviderUnavailableError(ProviderError):
    """No provider is configured, or its runtime is not installed here.

    The *degradable* failure, in the sense ADR-0017 gave the word: a caller that
    meets this carries on without a candidate document rather than failing.
    """


class UngroundedError(SynthesisError):
    """The synthesized text does not satisfy the citation contract.

    Carries the specific violations so a repair round-trip can quote them back to
    the model, and so an operator reading the refusal learns which claim was
    unsupported rather than that "validation failed".
    """

    def __init__(self, message: str, violations: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.violations = violations
