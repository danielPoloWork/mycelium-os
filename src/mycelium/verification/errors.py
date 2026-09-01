# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Verification's failure taxonomy (D-021, spec 04 §7.3 gate G7).

Three failures, and the distinction between the first two is the whole design:

- :class:`NotGroundedError` — the document was measured and did not clear gate
  G7. This is a *decision*, not a malfunction: the document stays where it is,
  and `--force` is the human override the spec provides, recorded in the document
  rather than in a log nobody reads.
- :class:`UnmeasurableError` — grounding could not be *computed*. An evidence
  document a citation named has been deleted, the entailment judge could not be
  reached. A number that could not be computed must never be reported as a low
  score: "0.0" and "not measured" lead to opposite actions.
- :class:`PromotionError` — the move itself is impossible: the document is not in
  a status folder, or something already occupies its destination.
"""

__all__ = [
    "NotGroundedError",
    "PromotionError",
    "UnmeasurableError",
    "VerificationError",
]


class VerificationError(RuntimeError):
    """Base of every verification failure."""


class NotGroundedError(VerificationError):
    """The document was measured and does not clear gate G7.

    Carries the blockers so the operator learns *which* component fell short and
    by how much, rather than that "verification failed".
    """

    def __init__(self, message: str, blockers: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.blockers = blockers


class UnmeasurableError(VerificationError):
    """Grounding could not be computed here, and says why."""


class PromotionError(VerificationError):
    """The status move cannot be made."""
