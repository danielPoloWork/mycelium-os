# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The entailment judge (roadmap 4.5): the sample is deterministic, the verdict is
fail-closed, and a judge that cannot be understood never raises the score."""

from fakes import ScriptedProvider
from mycelium.sdk.types import KirNode, NodeKind
from mycelium.verification.entailment import (
    SYSTEM_PROMPT,
    EntailmentJudge,
    LlmEntailmentJudge,
    sample_claims,
)

DIGEST = "sha256:" + "ab" * 32
OTHER = "sha256:" + "cd" * 32


def claims(count: int) -> list[KirNode]:
    return [
        KirNode(id=f"n{index}", kind=NodeKind.PARAGRAPH, ord=index, text=f"claim {index}")
        for index in range(count)
    ]


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------


def test_the_same_document_samples_the_same_claims() -> None:
    """A recorded score has to be reproducible, so the sample cannot be random."""
    first = sample_claims(claims(20), seed=DIGEST, size=5)
    second = sample_claims(list(reversed(claims(20))), seed=DIGEST, size=5)
    assert [node.id for node in first] == [node.id for node in second]


def test_a_different_document_samples_differently() -> None:
    # Not a requirement in itself — the point is that the sample is a function of
    # the document, so an edited document has not been sampled yet.
    assert sample_claims(claims(20), seed=DIGEST, size=5) != sample_claims(
        claims(20), seed=OTHER, size=5
    )


def test_the_sample_is_bounded_by_the_size_and_by_the_document() -> None:
    assert len(sample_claims(claims(20), seed=DIGEST, size=5)) == 5
    assert len(sample_claims(claims(3), seed=DIGEST, size=5)) == 3
    assert sample_claims(claims(3), seed=DIGEST, size=0) == ()


# ---------------------------------------------------------------------------
# The verdict, fail-closed
# ---------------------------------------------------------------------------


def test_a_clean_verdict_is_read_with_its_reason() -> None:
    judge = LlmEntailmentJudge(ScriptedProvider("ENTAILED\nthe evidence states it directly"))
    entailed, reason = judge.judge("a claim", "the evidence")
    assert entailed is True
    assert reason == "the evidence states it directly"


def test_not_entailed_is_not_read_as_entailed() -> None:
    # `NOT_ENTAILED` contains `ENTAILED`; a substring match would invert every
    # negative verdict, which is the worst possible direction for this bug.
    judge = LlmEntailmentJudge(ScriptedProvider("NOT_ENTAILED\nthe evidence is silent"))
    entailed, reason = judge.judge("a claim", "the evidence")
    assert entailed is False
    assert reason == "the evidence is silent"


def test_a_verdict_after_the_model_thinks_aloud_is_still_read() -> None:
    answer = "Let me consider the evidence carefully.\nNOT_ENTAILED\nnothing supports it"
    entailed, reason = LlmEntailmentJudge(ScriptedProvider(answer)).judge("c", "e")
    assert entailed is False
    assert reason == "nothing supports it"


def test_an_answer_with_no_verdict_is_not_entailed() -> None:
    entailed, reason = LlmEntailmentJudge(ScriptedProvider("I'd rather not say.")).judge("c", "e")
    assert entailed is False
    assert "no verdict" in reason
    assert "I'd rather not say." in reason


def test_an_empty_answer_is_not_entailed() -> None:
    entailed, _reason = LlmEntailmentJudge(ScriptedProvider("")).judge("c", "e")
    assert entailed is False


def test_a_verdict_with_no_reason_still_carries_one() -> None:
    _entailed, reason = LlmEntailmentJudge(ScriptedProvider("ENTAILED")).judge("c", "e")
    assert reason == "(no reason given)"


# ---------------------------------------------------------------------------
# What the judge is asked
# ---------------------------------------------------------------------------


def test_the_judge_is_told_to_treat_the_evidence_as_data() -> None:
    # The evidence is untrusted source material (D-017), and the one place that
    # can say so to a model is the system prompt it is judged under.
    assert "not instructions" in SYSTEM_PROMPT
    assert "Plausibility is not entailment" in SYSTEM_PROMPT


def test_the_prompt_carries_the_claim_and_the_evidence() -> None:
    provider = ScriptedProvider("ENTAILED\nyes")
    LlmEntailmentJudge(provider).judge("retries stop after five", "five attempts, then stop")
    prompt = provider.prompts[0]
    assert "retries stop after five" in prompt
    assert "five attempts, then stop" in prompt
    assert provider.systems[0] == SYSTEM_PROMPT


def test_empty_evidence_is_said_out_loud_rather_than_left_blank() -> None:
    provider = ScriptedProvider("NOT_ENTAILED\nnothing to judge against")
    LlmEntailmentJudge(provider).judge("a claim", "")
    assert "carries no text" in provider.prompts[0]


def test_the_judge_satisfies_the_protocol_and_names_itself() -> None:
    judge = LlmEntailmentJudge(ScriptedProvider("ENTAILED\nok", model="judge-9"))
    assert isinstance(judge, EntailmentJudge)
    assert judge.identity == "scripted/judge-9"
