# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""`mycelium verify` end to end (roadmap 4.5): what gets verified, what gets written,
and what has to change before anything is written at all."""

from datetime import date
from pathlib import Path, PurePosixPath

import pytest

from mycelium.corpus import CorpusScope
from mycelium.markdown.frontmatter import parse_frontmatter
from mycelium.verification.grounding import Thresholds
from mycelium.verification.lane import evidence_set, subjects, verify_tree

WHEN = date(2026, 9, 1)
LATER = date(2026, 10, 1)

EVIDENCE = """\
---
title: Retry Policy
origin: ingested
source: https://docs.example.com/retries
source_trust: high
---

# Retry Policy

## Backoff

Deliveries are retried five times, and backoff doubles after every failed attempt.
"""

CANDIDATE = """\
---
title: Webhook Retries
origin: synthesized
generated_by: scripted/scripted-1
---

# Webhook Retries

Deliveries are retried up to five times before the system gives up ([[retry-policy#Backoff]]).
"""

AUTHORED = """\
---
title: Hand-Written Notes
---

# Hand-Written Notes

Someone typed this out by hand, and it cites nothing at all.
"""


class Judge:
    identity = "test/judge"

    def __init__(self, *, entailed: bool = True) -> None:
        self._entailed = entailed
        self.calls = 0

    def judge(self, claim: str, evidence: str) -> tuple[bool, str]:
        self.calls += 1
        return self._entailed, "because the test said so"


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    knowledge = tmp_path / "knowledge"
    (knowledge / "evidence").mkdir(parents=True)
    (knowledge / "candidate").mkdir(parents=True)
    (knowledge / "verified").mkdir(parents=True)
    (knowledge / "evidence" / "retry-policy.md").write_text(EVIDENCE, encoding="utf-8", newline="")
    (knowledge / "candidate" / "webhook-retries.md").write_text(
        CANDIDATE, encoding="utf-8", newline=""
    )
    (knowledge / "verified" / "notes.md").write_text(AUTHORED, encoding="utf-8", newline="")
    return tmp_path


SCOPE = CorpusScope()


def run(tree: Path, **kwargs: object) -> tuple:
    defaults: dict[str, object] = {"thresholds": Thresholds(), "today": WHEN}
    defaults.update(kwargs)
    return verify_tree(tree, SCOPE, **defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# What is a subject
# ---------------------------------------------------------------------------


def test_only_synthesized_documents_are_verified(tree: Path) -> None:
    """A hand-written note has no citations, so a grounding score for it means nothing.

    Gate G7's own words are about a *synthesized* document, and provenance — not
    the folder — is what says which those are.
    """
    found = [subject.path.as_posix() for subject in subjects(tree, SCOPE)]
    assert found == ["knowledge/candidate/webhook-retries.md"]


def test_a_promoted_synthetic_document_is_still_verified(tree: Path) -> None:
    # The one most worth re-checking: its evidence has had time to move under it.
    (tree / "knowledge" / "verified" / "promoted.md").write_text(
        CANDIDATE, encoding="utf-8", newline=""
    )
    found = {subject.path.as_posix() for subject in subjects(tree, SCOPE)}
    assert "knowledge/verified/promoted.md" in found


def test_the_evidence_layer_is_not_its_own_subject(tree: Path) -> None:
    paths = {subject.path.as_posix() for subject in subjects(tree, SCOPE)}
    assert not any("evidence" in path for path in paths)
    assert [item.path.name for item in evidence_set(tree, SCOPE)] == ["retry-policy.md"]


def test_only_names_the_documents_asked_for(tree: Path) -> None:
    (tree / "knowledge" / "candidate" / "other.md").write_text(
        CANDIDATE, encoding="utf-8", newline=""
    )
    results = run(tree, only=[PurePosixPath("knowledge/candidate/other.md")])
    assert [item.grounding.path.name for item in results] == ["other.md"]


# ---------------------------------------------------------------------------
# Stamping
# ---------------------------------------------------------------------------


def test_the_score_lands_in_frontmatter_with_the_checker_that_computed_it(tree: Path) -> None:
    (result,) = run(tree)
    assert result.stamped is True
    parsed = parse_frontmatter(
        (tree / "knowledge/candidate/webhook-retries.md").read_text(encoding="utf-8")
    )
    assert parsed.frontmatter.grounding == 1.0
    assert parsed.frontmatter.verified_at == WHEN
    assert parsed.frontmatter.verified_by is not None
    assert "coverage only" in parsed.frontmatter.verified_by


def test_the_checker_names_the_judge_when_there_was_one(tree: Path) -> None:
    (result,) = run(tree, judge=Judge())
    assert "entailment via test/judge" in result.checker


def test_self_judgement_is_named_in_the_document(tree: Path) -> None:
    (result,) = run(tree, judge=Judge(), self_judged=True)
    assert "self-judged" in result.checker


def test_a_second_run_that_measures_the_same_thing_writes_nothing(tree: Path) -> None:
    """A nightly `verify` over a corpus nothing happened to must produce no diff.

    Otherwise every run rewrites every candidate, every rewrite dirties the
    document, and the next build recompiles a corpus that did not change.
    """
    run(tree)
    before = (tree / "knowledge/candidate/webhook-retries.md").read_text(encoding="utf-8")
    (again,) = run(tree, today=LATER)
    after = (tree / "knowledge/candidate/webhook-retries.md").read_text(encoding="utf-8")
    assert again.stamped is False
    assert after == before, "verified_at records when the score moved, not when it was read"


def test_a_changed_score_is_written_with_a_new_date(tree: Path) -> None:
    run(tree)
    (tree / "knowledge/candidate/webhook-retries.md").write_text(
        (tree / "knowledge/candidate/webhook-retries.md")
        .read_text(encoding="utf-8")
        .replace("([[retry-policy#Backoff]])", ""),
        encoding="utf-8",
        newline="",
    )
    (again,) = run(tree, today=LATER)
    assert again.stamped is True
    parsed = parse_frontmatter(
        (tree / "knowledge/candidate/webhook-retries.md").read_text(encoding="utf-8")
    )
    assert parsed.frontmatter.grounding == 0.0
    assert parsed.frontmatter.verified_at == LATER


def test_dry_run_writes_nothing(tree: Path) -> None:
    before = (tree / "knowledge/candidate/webhook-retries.md").read_text(encoding="utf-8")
    (result,) = run(tree, write=False)
    assert result.stamped is False
    assert (tree / "knowledge/candidate/webhook-retries.md").read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# Auto-promotion
# ---------------------------------------------------------------------------


def test_auto_promotion_is_off_unless_asked_for(tree: Path) -> None:
    (result,) = run(tree, judge=Judge())
    assert result.promoted is None
    assert (tree / "knowledge/candidate/webhook-retries.md").is_file()


def test_auto_promotion_moves_a_document_that_clears_the_whole_gate(tree: Path) -> None:
    (result,) = run(tree, judge=Judge(), auto_promote=True)
    assert result.blockers == ()
    assert result.promoted is not None
    assert (tree / "knowledge/verified/webhook-retries.md").is_file()
    assert not (tree / "knowledge/candidate/webhook-retries.md").exists()


def test_auto_promotion_will_not_move_a_document_it_could_not_fully_measure(
    tree: Path,
) -> None:
    # No judge, so half of G7 is unmeasured — and an automatic promotion on half a
    # gate is exactly what D-021 keeps out of a machine's hands.
    (result,) = run(tree, auto_promote=True)
    assert result.promoted is None
    assert (tree / "knowledge/candidate/webhook-retries.md").is_file()


def test_auto_promotion_refuses_a_failed_entailment(tree: Path) -> None:
    (result,) = run(tree, judge=Judge(entailed=False), auto_promote=True)
    assert [item.code for item in result.blockers] == ["entailment-below-threshold"]
    assert result.promoted is None


def test_auto_promotion_does_not_re_promote_something_already_verified(tree: Path) -> None:
    (tree / "knowledge" / "verified" / "promoted.md").write_text(
        CANDIDATE, encoding="utf-8", newline=""
    )
    results = run(
        tree,
        judge=Judge(),
        auto_promote=True,
        only=[PurePosixPath("knowledge/verified/promoted.md")],
    )
    assert results[0].promoted is None


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def test_the_json_shape_carries_the_gate_decision(tree: Path) -> None:
    (result,) = run(tree, judge=Judge(entailed=False))
    payload = result.as_dict()
    assert payload["passes"] is False
    assert payload["document"] == "knowledge/candidate/webhook-retries.md"
    assert payload["entailment"] == 0.0
    assert payload["blockers"][0]["code"] == "entailment-below-threshold"
    assert payload["checker"].startswith("mycelium verify")


def test_an_empty_tree_verifies_nothing_without_complaining(tmp_path: Path) -> None:
    assert verify_tree(tmp_path, SCOPE, thresholds=Thresholds()) == ()
