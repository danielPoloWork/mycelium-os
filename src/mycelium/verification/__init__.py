# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Verification: the workflow that decides what counts as truth (D-021).

The synthesis lane may write prose (D-020). This package is what stands between
that prose and the `verified/` folder, and it is deliberately the smallest thing
that can hold that position:

- :mod:`mycelium.verification.grounding` — gate G7's two components, and the
  refusal to invent the one that needs a judge.
- :mod:`mycelium.verification.entailment` — the judge: a sampled, deterministic,
  fail-closed LLM check, or nothing at all.
- :mod:`mycelium.verification.promotion` — the status change, which is a file move
  in Git and stamps its own evidence into the document.
- :mod:`mycelium.verification.lane` — `mycelium verify` end to end.
- :mod:`mycelium.verification.errors` — the taxonomy, because "did not pass" and
  "could not be measured" lead to opposite actions.

Two things this package never does. It never moves a document without being asked
— auto-promotion is opt-in configuration and off by default, because D-021 makes
promotion a human act. And it never writes an index: the store learns a document's
new status from the next `mycelium build`, the same way it learns about any edit,
so a promotion cannot leave the served snapshot disagreeing with the tree.
"""

from typing import TYPE_CHECKING

from mycelium.verification.entailment import (
    DEFAULT_SAMPLE_SIZE,
    EntailmentJudge,
    Judgement,
    LlmEntailmentJudge,
    sample_claims,
)
from mycelium.verification.errors import (
    NotGroundedError,
    PromotionError,
    UnmeasurableError,
    VerificationError,
)
from mycelium.verification.grounding import (
    Blocker,
    Grounding,
    Thresholds,
    measure,
    section_text,
)
from mycelium.verification.lane import (
    EVIDENCE_DIRNAME,
    Subject,
    Verified,
    checker_identity,
    evidence_set,
    subjects,
    verify_document,
    verify_tree,
)
from mycelium.verification.promotion import (
    VERIFIED_DIRNAME,
    Moved,
    author_name,
    demote,
    promote,
    stamp,
)

if TYPE_CHECKING:  # pragma: no cover - resolved lazily; see `build_judge`
    from mycelium.config import SynthesisConfig, VerificationConfig

__all__ = [
    "DEFAULT_SAMPLE_SIZE",
    "EVIDENCE_DIRNAME",
    "VERIFIED_DIRNAME",
    "Blocker",
    "EntailmentJudge",
    "Grounding",
    "Judgement",
    "LlmEntailmentJudge",
    "Moved",
    "NotGroundedError",
    "PromotionError",
    "Subject",
    "Thresholds",
    "UnmeasurableError",
    "VerificationError",
    "Verified",
    "author_name",
    "build_judge",
    "checker_identity",
    "demote",
    "evidence_set",
    "measure",
    "promote",
    "sample_claims",
    "section_text",
    "stamp",
    "subjects",
    "verify_document",
    "verify_tree",
]


def build_judge(
    synthesis: "SynthesisConfig", verification: "VerificationConfig"
) -> tuple[LlmEntailmentJudge | None, bool, str]:
    """Resolve the entailment judge, and say whether it grades its own homework.

    Returns ``(judge, self_judged, reason)``. A ``None`` judge is not a failure —
    it is the offline default (D-013), and `reason` is the sentence a command
    prints so the operator knows *why* half of gate G7 was not measured.

    The judge rides on `[synthesis]`'s provider because that is where this
    project's single LLM consent lives (D-017): one credential, one place an
    operator says "yes, call out". `[verification] model_id` points the judge at a
    different *model* through that same provider, which is the knob that matters —
    a writer grading its own work is a known bias, and naming it is cheaper than
    pretending the score is independent.
    """
    from mycelium.synthesis import build_provider  # noqa: PLC0415 - avoids an import cycle
    from mycelium.synthesis.errors import ProviderError  # noqa: PLC0415

    if not synthesis.provider:
        return (
            None,
            False,
            (
                "entailment was not measured: no LLM provider is configured, so gate G7's "
                'second component has no judge (set [synthesis] provider = "anthropic")'
            ),
        )
    wanted = verification.model_id or synthesis.model_id
    self_judged = verification.model_id is None
    try:
        provider = build_provider(synthesis.model_copy(update={"model_id": wanted}))
    except ProviderError as error:
        return None, False, f"entailment was not measured: {error}"
    return LlmEntailmentJudge(provider), self_judged, ""
