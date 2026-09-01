# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Grounding: what gate G7 measures, and what it refuses to guess (D-021).

G7 has two components and they are not the same kind of thing:

============  =========================================  ==========  ==========
Component     Question                                   Decidable?  Threshold
============  =========================================  ==========  ==========
coverage      does every claim point at evidence?        yes, here   ≥ 0.95
entailment    does that evidence say this?               only by a   ≥ 0.90
                                                         judge
============  =========================================  ==========  ==========

Coverage is recomputed here rather than read from the synthesis record, and that
is the point of the command existing. The record holds what was true when the
document was written; the corpus has moved since. An evidence document that was
edited, re-projected under a different heading, or deleted leaves a candidate
citing something that no longer says what it said — and no amount of care at
write time can catch that. Verification is the drift check.

**A single recorded number, and why `min`.** Frontmatter carries one `grounding`
float (spec 03 §3), and this module reports ``min(coverage, entailment)`` for it.
An average would let a document with perfect citations and 0.4 entailment record
0.7 and look healthy; the minimum cannot hide a failed component. The *gate* is
still per-component against its own threshold — the recorded number is a summary,
never the test.

**Unmeasured is not zero.** With no judge configured, `entailment` is ``None``,
the score falls back to coverage alone, and `verified_by` says only coverage was
measured. Promotion then needs the human's `--force`, which is exactly the
authority D-021 gives them.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

from mycelium.sdk.identity import heading_slug
from mycelium.sdk.protocols import EvidenceDocument
from mycelium.sdk.types import KirDocument, KirNode, NodeKind, SourceTrust
from mycelium.synthesis.citations import (
    claim_blocks,
    index_evidence,
    resolve_target,
    review,
)
from mycelium.verification.entailment import (
    DEFAULT_SAMPLE_SIZE,
    EntailmentJudge,
    Judgement,
    sample_claims,
)

__all__ = [
    "Blocker",
    "Grounding",
    "Thresholds",
    "measure",
    "section_text",
]

_TRUST_ORDER: Final[dict[SourceTrust, int]] = {
    SourceTrust.UNKNOWN: 0,
    SourceTrust.LOW: 1,
    SourceTrust.MEDIUM: 2,
    SourceTrust.HIGH: 3,
}


@dataclass(frozen=True, slots=True)
class Blocker:
    """One reason a document may not be promoted.

    A code as well as a sentence, because the two go to different readers. The
    sentence is for the operator at the terminal; the code is what a forced
    promotion writes into `verified_by`, where it has to stay short enough to read
    in a diff and stable enough to grep for a year later.
    """

    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True, slots=True)
class Thresholds:
    """Gate G7's two floors (spec 04 §7.3, `[verification]`)."""

    coverage: float = 0.95
    entailment: float = 0.90


@dataclass(frozen=True, slots=True)
class Grounding:
    """One document's grounding, as measured against the corpus as it is now."""

    path: PurePosixPath
    coverage: float
    claims: int
    cited_claims: int
    citations: tuple[str, ...]
    violations: tuple[str, ...]
    entailment: float | None = None
    """``None`` means *not measured* — never "measured as zero"."""

    sampled: int = 0
    entailed: int = 0
    judge: str | None = None
    self_judged: bool = False
    """Whether the model that judged is the model that wrote (ADR-0036)."""

    judgements: tuple[Judgement, ...] = ()
    weakest_trust: SourceTrust | None = None
    """The least trusted origin among the cited evidence (`[sources]`).

    Reported, never gated: G7 is about whether a claim is supported, and by what
    is a separate question the operator answers. A document grounded entirely in
    `unknown` sources can be perfectly grounded and still worth a second look."""

    @property
    def score(self) -> float:
        """The number written to frontmatter: the weakest measured component."""
        if self.entailment is None:
            return self.coverage
        return min(self.coverage, self.entailment)

    def blockers(
        self, thresholds: Thresholds, *, require_entailment: bool = True
    ) -> tuple[Blocker, ...]:
        """Why this document may not be promoted, in the order they matter.

        `require_entailment=False` is what `verify --gate` uses in CI, and the
        asymmetry with promotion is deliberate. A CI gate asks "has any document's
        grounding *regressed*", and a run with no provider can answer that for
        coverage; failing it for the component it cannot measure would make the
        gate red on every offline checkout and teach everyone to ignore it.
        Promotion asks "may this become truth", which is a stronger question — so
        there, an unmeasured half is a blocker, and `--force` is the human's
        answer to it (D-021).
        """
        reasons: list[Blocker] = []
        unresolved = tuple(item for item in self.violations if item.startswith("[["))
        if unresolved:
            reasons.append(
                Blocker(
                    "citations-unresolved",
                    f"{len(unresolved)} citation(s) no longer resolve: the evidence they "
                    "name has been renamed, re-projected or deleted",
                )
            )
        if self.coverage < thresholds.coverage:
            reasons.append(
                Blocker(
                    "coverage-below-threshold",
                    f"citation coverage {self.coverage:.2f} is below "
                    f"{thresholds.coverage:.2f} ({self.claims - self.cited_claims} of "
                    f"{self.claims} claim-bearing blocks cite nothing)",
                )
            )
        if self.entailment is None:
            if require_entailment:
                reasons.append(
                    Blocker(
                        "entailment-not-measured",
                        "entailment was not measured: no LLM provider is configured, so "
                        "the second half of gate G7 has no judge",
                    )
                )
        elif self.entailment < thresholds.entailment:
            reasons.append(
                Blocker(
                    "entailment-below-threshold",
                    f"sampled entailment {self.entailment:.2f} is below "
                    f"{thresholds.entailment:.2f} ({self.sampled - self.entailed} of "
                    f"{self.sampled} sampled claims are not supported by what they cite)",
                )
            )
        return tuple(reasons)

    def passes(self, thresholds: Thresholds) -> bool:
        """Whether gate G7 is satisfied — both components, both measured."""
        return not self.blockers(thresholds)

    def as_dict(self) -> dict[str, object]:
        return {
            "document": self.path.as_posix(),
            "coverage": round(self.coverage, 4),
            "claims": self.claims,
            "cited_claims": self.cited_claims,
            "entailment": None if self.entailment is None else round(self.entailment, 4),
            "sampled": self.sampled,
            "entailed": self.entailed,
            "judge": self.judge,
            "self_judged": self.self_judged,
            "grounding": round(self.score, 4),
            "weakest_trust": None if self.weakest_trust is None else self.weakest_trust.value,
            "citations": list(self.citations),
            "violations": list(self.violations),
            "judgements": [item.as_dict() for item in self.judgements],
        }


def section_text(kir: KirDocument, fragment: str) -> str:
    """The text of one section of an evidence document, or of all of it.

    A citation may name a heading (`[[retries#Backoff]]`), and the judge must see
    *that* section rather than the whole document: handing a model twenty pages
    and asking whether one sentence is in there somewhere is not the question G7
    asks, and it is the question a model answers most charitably.
    """
    if not fragment:
        return "\n\n".join(node.text for node in kir.nodes if node.text)

    wanted = heading_slug(fragment)
    heading = next(
        (
            node
            for node in kir.nodes
            if node.kind is NodeKind.HEADING and heading_slug(node.text or "") == wanted
        ),
        None,
    )
    if heading is None:
        return ""
    children: dict[str | None, list[KirNode]] = {}
    for node in kir.nodes:
        children.setdefault(node.parent, []).append(node)
    collected: list[str] = []
    stack = [heading]
    while stack:
        node = stack.pop(0)
        if node.text:
            collected.append(node.text)
        stack = children.get(node.id, []) + stack
    return "\n\n".join(collected)


def _weakest(evidence: Sequence[EvidenceDocument], cited: Sequence[str]) -> SourceTrust | None:
    """The least trusted origin among the documents actually cited."""
    paths = {PurePosixPath(item).as_posix() for item in cited}
    trusts = [
        item.source_trust
        for item in evidence
        if item.path.as_posix() in paths and item.source_trust is not None
    ]
    if not trusts:
        return None
    return min(trusts, key=lambda trust: _TRUST_ORDER[trust])


def measure(
    path: PurePosixPath,
    kir: KirDocument,
    evidence: Sequence[EvidenceDocument],
    *,
    judge: EntailmentJudge | None = None,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    self_judged: bool = False,
) -> Grounding:
    """Measure one document's grounding against `evidence`.

    Pure but for the judge: with `judge=None` this is deterministic, offline, and
    the same function gate G7 runs in CI. The judge is the only non-deterministic
    input, and it is a parameter rather than a lookup so the whole measurement is
    testable without a model.
    """
    report = review(kir, evidence)
    grounding = Grounding(
        path=path,
        coverage=report.coverage,
        claims=report.claims,
        cited_claims=report.cited_claims,
        citations=report.citations,
        violations=report.violations,
        weakest_trust=_weakest(evidence, report.cited_documents),
    )
    if judge is None:
        return grounding

    judgements = _judge_sample(
        kir, evidence, report.claim_citations, judge=judge, sample_size=sample_size
    )
    entailed = sum(1 for item in judgements if item.entailed)
    return Grounding(
        path=grounding.path,
        coverage=grounding.coverage,
        claims=grounding.claims,
        cited_claims=grounding.cited_claims,
        citations=grounding.citations,
        violations=grounding.violations,
        weakest_trust=grounding.weakest_trust,
        entailment=(entailed / len(judgements)) if judgements else None,
        sampled=len(judgements),
        entailed=entailed,
        judge=judge.identity,
        self_judged=self_judged,
        judgements=judgements,
    )


def _judge_sample(
    kir: KirDocument,
    evidence: Sequence[EvidenceDocument],
    claim_citations: Mapping[str, tuple[str, ...]],
    *,
    judge: EntailmentJudge,
    sample_size: int,
) -> tuple[Judgement, ...]:
    """Judge a deterministic sample of the document's *cited* claims.

    Only cited claims are sampled: an uncited claim has already failed coverage,
    and spending a model call to discover that it is also unsupported would charge
    one defect twice, once against each component of the gate.

    The claim → citation mapping comes from the citation report rather than being
    rebuilt here. One walk of the tree, one answer about which block a citation
    belongs to (ADR-0036).
    """
    index = index_evidence(evidence)
    cited = [node for node in claim_blocks(kir.nodes) if claim_citations.get(node.id)]
    if not cited:
        return ()

    judgements: list[Judgement] = []
    for node in sample_claims(cited, seed=kir.source_digest, size=sample_size):
        citations = claim_citations[node.id]
        quoted: list[str] = []
        for citation in citations:
            document, fragment, _reason = resolve_target(citation, index)
            if document is not None:
                quoted.append(f"[{citation}]\n{section_text(document.kir, fragment)}")
        entailed, reason = judge.judge(node.text or "", "\n\n".join(quoted))
        judgements.append(
            Judgement(
                claim_id=node.id,
                claim=node.text or "",
                citations=citations,
                entailed=entailed,
                reason=reason,
            )
        )
    return tuple(judgements)
