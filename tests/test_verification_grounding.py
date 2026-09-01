# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Gate G7's measurement (roadmap 4.5).

The load-bearing tests here are the two that say what the number *means*:
:func:`test_unmeasured_entailment_is_not_a_zero` and
:func:`test_the_recorded_score_is_the_weakest_measured_component`. Everything else
in this milestone rests on grounding being a number an operator can act on, and
both of those are ways it could quietly stop being one.
"""

from pathlib import PurePosixPath

import pytest

from mycelium.markdown.adapter import parse_markdown
from mycelium.sdk.protocols import EvidenceDocument
from mycelium.sdk.types import KirDocument, NodeKind, SourceTrust
from mycelium.verification.grounding import Grounding, Thresholds, measure, section_text

EVIDENCE_TEXT = """\
# Retry Policy

## Backoff

Deliveries are retried five times, and backoff doubles after every failed attempt.

## Limits

The maximum payload size is 256 KiB.
"""

CANDIDATE = """\
# Webhook Retries

Deliveries are retried up to five times before the system gives up ([[retries#Backoff]]).

Each attempt waits twice as long as the one before it ([[retries#Backoff]]).
"""


class Judge:
    """A judge that answers from a dict, so entailment is decided by the test."""

    def __init__(self, verdicts: dict[str, bool], *, identity: str = "test/judge") -> None:
        self._verdicts = verdicts
        self.identity = identity
        self.asked: list[tuple[str, str]] = []

    def judge(self, claim: str, evidence: str) -> tuple[bool, str]:
        self.asked.append((claim, evidence))
        for fragment, verdict in self._verdicts.items():
            if fragment in claim:
                return verdict, f"matched {fragment!r}"
        return True, "default"


def evidence(text: str = EVIDENCE_TEXT, *, name: str = "retries", trust: SourceTrust | None = None):
    parsed = parse_markdown(text)
    headings = tuple(
        node.text for node in parsed.kir.nodes if node.kind is NodeKind.HEADING and node.text
    )
    return EvidenceDocument(
        path=PurePosixPath(f"knowledge/evidence/{name}.md"),
        title=headings[0] if headings else name,
        kir=parsed.kir,
        headings=headings,
        source_uri=f"https://docs.example.com/{name}",
        source_trust=trust,
    )


def candidate(text: str = CANDIDATE) -> KirDocument:
    return parse_markdown(text).kir


# ---------------------------------------------------------------------------
# Coverage, and the drift it exists to catch
# ---------------------------------------------------------------------------


def test_a_fully_cited_document_covers_completely() -> None:
    grounding = measure(PurePosixPath("c.md"), candidate(), [evidence()])
    assert grounding.coverage == 1.0
    assert grounding.claims == 2
    assert grounding.cited_claims == 2
    assert grounding.violations == ()


def test_evidence_renamed_underneath_a_candidate_is_a_blocker() -> None:
    """The whole reason `verify` recomputes instead of reading the record.

    The document was accepted against `retries.md`; the projection is now called
    something else. Nothing about the candidate changed, and it is no longer
    grounded.
    """
    grounding = measure(PurePosixPath("c.md"), candidate(), [evidence(name="retry-policy")])
    assert grounding.coverage == 0.0
    codes = [item.code for item in grounding.blockers(Thresholds())]
    assert "citations-unresolved" in codes
    assert "coverage-below-threshold" in codes


def test_a_section_that_no_longer_exists_is_a_blocker() -> None:
    trimmed = EVIDENCE_TEXT.replace("## Backoff", "## Retry Backoff")
    grounding = measure(PurePosixPath("c.md"), candidate(), [evidence(trimmed)])
    assert [item.code for item in grounding.blockers(Thresholds())][0] == "citations-unresolved"


def test_an_uncited_claim_lowers_coverage() -> None:
    text = CANDIDATE + "\nRetries are also logged to the delivery journal every time.\n"
    grounding = measure(PurePosixPath("c.md"), candidate(text), [evidence()])
    assert grounding.claims == 3
    assert grounding.cited_claims == 2
    assert grounding.coverage == pytest.approx(2 / 3)


def test_a_document_that_asserts_nothing_scores_one_rather_than_dividing_by_zero() -> None:
    grounding = measure(PurePosixPath("c.md"), candidate("# Title\n\nNotes\n"), [evidence()])
    assert grounding.claims == 0
    assert grounding.coverage == 1.0


# ---------------------------------------------------------------------------
# What the number means
# ---------------------------------------------------------------------------


def test_unmeasured_entailment_is_not_a_zero() -> None:
    """`None` and `0.0` lead to opposite actions, so they must not be confused.

    With no judge the score is coverage alone, and the *gate* still refuses —
    which is what keeps "we could not check" from reading as "we checked and it
    was fine".
    """
    grounding = measure(PurePosixPath("c.md"), candidate(), [evidence()])
    assert grounding.entailment is None
    assert grounding.score == 1.0
    assert grounding.as_dict()["entailment"] is None
    assert not grounding.passes(Thresholds())
    assert [item.code for item in grounding.blockers(Thresholds())] == ["entailment-not-measured"]


def test_the_recorded_score_is_the_weakest_measured_component() -> None:
    # An average would let perfect citations hide a failed entailment.
    judge = Judge({"Each attempt": False})
    grounding = measure(PurePosixPath("c.md"), candidate(), [evidence()], judge=judge)
    assert grounding.coverage == 1.0
    assert grounding.entailment == 0.5
    assert grounding.score == 0.5


def test_an_unmeasured_entailment_does_not_fail_the_ci_gate() -> None:
    grounding = measure(PurePosixPath("c.md"), candidate(), [evidence()])
    assert grounding.blockers(Thresholds(), require_entailment=False) == ()


def test_a_measured_shortfall_fails_the_ci_gate_too() -> None:
    grounding = measure(
        PurePosixPath("c.md"), candidate(), [evidence()], judge=Judge({"Each attempt": False})
    )
    codes = [item.code for item in grounding.blockers(Thresholds(), require_entailment=False)]
    assert codes == ["entailment-below-threshold"]


# ---------------------------------------------------------------------------
# Entailment: what the judge is shown
# ---------------------------------------------------------------------------


def test_the_judge_sees_the_cited_section_not_the_whole_document() -> None:
    judge = Judge({})
    measure(PurePosixPath("c.md"), candidate(), [evidence()], judge=judge)
    shown = judge.asked[0][1]
    assert "backoff doubles" in shown
    assert "256 KiB" not in shown, "the Limits section was not cited by this claim"


def test_every_judgement_is_reported_with_its_reason() -> None:
    grounding = measure(
        PurePosixPath("c.md"), candidate(), [evidence()], judge=Judge({"Each attempt": False})
    )
    assert grounding.sampled == 2
    assert grounding.entailed == 1
    refused = [item for item in grounding.judgements if not item.entailed]
    assert len(refused) == 1
    assert refused[0].citations == ("knowledge/evidence/retries.md#Backoff",)
    assert refused[0].reason.startswith("matched")


def test_an_uncited_claim_is_not_judged() -> None:
    """One defect is charged once.

    An uncited claim has already failed coverage; spending a model call to learn
    that it is also unsupported would count the same problem against both halves
    of the gate.
    """
    text = CANDIDATE + "\nRetries are also logged to the delivery journal every time.\n"
    judge = Judge({})
    grounding = measure(PurePosixPath("c.md"), candidate(text), [evidence()], judge=judge)
    assert grounding.sampled == 2
    assert all("delivery journal" not in claim for claim, _ in judge.asked)


def test_a_document_with_no_cited_claims_reports_entailment_as_unmeasured() -> None:
    judge = Judge({})
    grounding = measure(
        PurePosixPath("c.md"),
        candidate("# T\n\nNothing here cites anything at all.\n"),
        [evidence()],
        judge=judge,
    )
    assert judge.asked == []
    assert grounding.entailment is None


def test_the_sample_size_bounds_the_number_of_calls() -> None:
    body = "# T\n\n" + "\n\n".join(
        f"Claim number {index} about retries and backoff ([[retries#Backoff]])."
        for index in range(12)
    )
    judge = Judge({})
    grounding = measure(
        PurePosixPath("c.md"), candidate(body), [evidence()], judge=judge, sample_size=4
    )
    assert grounding.sampled == 4
    assert len(judge.asked) == 4


def test_self_judgement_is_recorded_rather_than_hidden() -> None:
    grounding = measure(
        PurePosixPath("c.md"), candidate(), [evidence()], judge=Judge({}), self_judged=True
    )
    assert grounding.self_judged is True
    assert grounding.as_dict()["self_judged"] is True
    assert grounding.judge == "test/judge"


# ---------------------------------------------------------------------------
# Trust, reported and not gated
# ---------------------------------------------------------------------------


def test_the_weakest_cited_trust_is_reported() -> None:
    grounding = measure(PurePosixPath("c.md"), candidate(), [evidence(trust=SourceTrust.MEDIUM)])
    assert grounding.weakest_trust is SourceTrust.MEDIUM


def test_trust_is_never_a_blocker() -> None:
    # Deciding whose documentation is trustworthy is the operator's call.
    grounding = measure(
        PurePosixPath("c.md"),
        candidate(),
        [evidence(trust=SourceTrust.UNKNOWN)],
        judge=Judge({}),
    )
    assert grounding.weakest_trust is SourceTrust.UNKNOWN
    assert grounding.passes(Thresholds())


def test_uncited_evidence_does_not_drag_the_reported_trust_down() -> None:
    grounding = measure(
        PurePosixPath("c.md"),
        candidate(),
        [
            evidence(trust=SourceTrust.HIGH),
            evidence(name="unrelated", trust=SourceTrust.UNKNOWN),
        ],
    )
    assert grounding.weakest_trust is SourceTrust.HIGH


# ---------------------------------------------------------------------------
# section_text
# ---------------------------------------------------------------------------


def test_section_text_returns_a_heading_and_its_content() -> None:
    text = section_text(parse_markdown(EVIDENCE_TEXT).kir, "Limits")
    assert "256 KiB" in text
    assert "backoff doubles" not in text


def test_section_text_with_no_fragment_returns_the_whole_document() -> None:
    text = section_text(parse_markdown(EVIDENCE_TEXT).kir, "")
    assert "256 KiB" in text
    assert "backoff doubles" in text


def test_section_text_for_a_heading_that_is_gone_is_empty() -> None:
    assert section_text(parse_markdown(EVIDENCE_TEXT).kir, "Nowhere") == ""


def test_an_empty_grounding_still_renders() -> None:
    grounding = Grounding(
        path=PurePosixPath("c.md"),
        coverage=1.0,
        claims=0,
        cited_claims=0,
        citations=(),
        violations=(),
    )
    payload = grounding.as_dict()
    assert payload["document"] == "c.md"
    assert payload["judgements"] == []
