# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Promotion and demotion (roadmap 4.5): a file move, a stamped block, and nothing
left behind that could contradict the folder."""

from datetime import date
from pathlib import Path, PurePosixPath

import pytest

from mycelium.markdown.frontmatter import parse_frontmatter
from mycelium.verification.errors import PromotionError
from mycelium.verification.promotion import author_name, demote, promote, stamp

WHEN = date(2026, 9, 1)

DOCUMENT = """\
---
title: Webhook Retries
origin: synthesized
generated_by: scripted/scripted-1
---

# Webhook Retries

Deliveries are retried five times ([[retries#Backoff]]).
"""


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "knowledge" / "candidate").mkdir(parents=True)
    (tmp_path / "knowledge" / "verified").mkdir(parents=True)
    (tmp_path / "knowledge" / "candidate" / "retries.md").write_text(
        DOCUMENT, encoding="utf-8", newline=""
    )
    return tmp_path


def candidate(name: str = "retries.md") -> PurePosixPath:
    return PurePosixPath("knowledge/candidate") / name


def verified(name: str = "retries.md") -> PurePosixPath:
    return PurePosixPath("knowledge/verified") / name


# ---------------------------------------------------------------------------
# stamp
# ---------------------------------------------------------------------------


def test_stamping_adds_the_three_fields_and_touches_nothing_else() -> None:
    stamped = stamp(DOCUMENT, verified_by="a checker", verified_at=WHEN, grounding=0.97)
    parsed = parse_frontmatter(stamped)
    assert parsed.frontmatter.verified_by == "a checker"
    assert parsed.frontmatter.verified_at == WHEN
    assert parsed.frontmatter.grounding == 0.97
    assert parsed.frontmatter.title == "Webhook Retries"
    assert "Deliveries are retried five times" in parsed.body


def test_stamping_twice_replaces_rather_than_repeats() -> None:
    once = stamp(DOCUMENT, verified_by="first", verified_at=WHEN, grounding=0.5)
    twice = stamp(once, verified_by="second", verified_at=WHEN, grounding=0.9)
    assert twice.count("verified_by:") == 1
    assert parse_frontmatter(twice).frontmatter.verified_by == "second"


def test_clearing_removes_the_whole_block() -> None:
    stamped = stamp(DOCUMENT, verified_by="a checker", verified_at=WHEN, grounding=0.97)
    cleared = stamp(stamped, clear=True)
    parsed = parse_frontmatter(cleared)
    assert parsed.frontmatter.verified_by is None
    assert parsed.frontmatter.verified_at is None
    assert parsed.frontmatter.grounding is None
    assert parsed.frontmatter.origin is not None, "the rest of the block survives"


def test_a_long_forced_reason_stays_on_one_line() -> None:
    """A folded value would leave a continuation line no remover can see.

    This is the shape that corrupted a document during development: PyYAML wrapped
    a long `verified_by`, and clearing it later deleted the first line and orphaned
    the second.
    """
    reason = "Someone With A Long Name (forced: " + "reason " * 30 + ")"
    stamped = stamp(DOCUMENT, verified_by=reason, verified_at=WHEN, grounding=1.0)
    assert len([line for line in stamped.splitlines() if line.startswith("verified_by")]) == 1
    assert parse_frontmatter(stamp(stamped, clear=True)).frontmatter.verified_by is None


# ---------------------------------------------------------------------------
# promote
# ---------------------------------------------------------------------------


def test_promotion_moves_the_file_and_stamps_it(tree: Path) -> None:
    moved = promote(tree, candidate(), verified_by="the gate", grounding=0.97, at=WHEN)
    assert moved.destination == verified()
    assert not (tree / candidate()).exists()
    parsed = parse_frontmatter((tree / verified()).read_text(encoding="utf-8"))
    assert parsed.frontmatter.verified_by == "the gate"
    assert parsed.frontmatter.grounding == 0.97
    assert parsed.frontmatter.verified_at == WHEN


def test_promotion_keeps_a_nested_subtree(tree: Path) -> None:
    nested = tree / "knowledge" / "candidate" / "api"
    nested.mkdir()
    (nested / "retries.md").write_text(DOCUMENT, encoding="utf-8", newline="")
    moved = promote(
        tree,
        PurePosixPath("knowledge/candidate/api/retries.md"),
        verified_by="the gate",
        grounding=1.0,
        at=WHEN,
    )
    assert moved.destination == PurePosixPath("knowledge/verified/api/retries.md")
    assert (tree / moved.destination).is_file()


def test_a_document_outside_the_status_folders_cannot_be_promoted(tree: Path) -> None:
    (tree / "knowledge" / "notes.md").write_text(DOCUMENT, encoding="utf-8", newline="")
    with pytest.raises(PromotionError, match="not under a candidate/ folder"):
        promote(
            tree,
            PurePosixPath("knowledge/notes.md"),
            verified_by="x",
            grounding=1.0,
            at=WHEN,
        )


def test_promotion_refuses_to_overwrite_the_destination(tree: Path) -> None:
    (tree / verified()).write_text("someone else's document\n", encoding="utf-8", newline="")
    with pytest.raises(PromotionError, match="already exists"):
        promote(tree, candidate(), verified_by="x", grounding=1.0, at=WHEN)
    assert (tree / candidate()).is_file(), "the source is left where it was"


def test_promoting_a_file_that_is_not_there_says_so(tree: Path) -> None:
    with pytest.raises(PromotionError, match="is not a file"):
        promote(tree, candidate("absent.md"), verified_by="x", grounding=1.0, at=WHEN)


def test_a_forced_promotion_records_that_it_was_forced(tree: Path) -> None:
    moved = promote(
        tree,
        candidate(),
        verified_by="Daniel Polo (forced: entailment-not-measured)",
        grounding=1.0,
        at=WHEN,
        forced=True,
    )
    assert moved.forced is True
    assert moved.as_dict()["forced"] is True
    # In the document, in Git, forever — not only on someone's terminal.
    text = (tree / verified()).read_text(encoding="utf-8")
    assert "forced: entailment-not-measured" in text


# ---------------------------------------------------------------------------
# demote
# ---------------------------------------------------------------------------


def test_demotion_moves_back_and_removes_the_verification(tree: Path) -> None:
    promote(tree, candidate(), verified_by="the gate", grounding=0.97, at=WHEN)
    moved = demote(tree, verified())
    assert moved.destination == candidate()
    assert not (tree / verified()).exists()
    parsed = parse_frontmatter((tree / candidate()).read_text(encoding="utf-8"))
    assert parsed.frontmatter.verified_by is None
    assert parsed.frontmatter.grounding is None
    assert parsed.frontmatter.origin is not None, "provenance is not verification"


def test_a_promote_demote_round_trip_leaves_the_body_untouched(tree: Path) -> None:
    original = (tree / candidate()).read_text(encoding="utf-8")
    promote(tree, candidate(), verified_by="the gate", grounding=0.97, at=WHEN)
    demote(tree, verified())
    assert (tree / candidate()).read_text(encoding="utf-8") == original


def test_a_candidate_cannot_be_demoted(tree: Path) -> None:
    with pytest.raises(PromotionError, match="not under a verified/ folder"):
        demote(tree, candidate())


# ---------------------------------------------------------------------------
# Who did it
# ---------------------------------------------------------------------------


def test_the_author_name_is_a_non_empty_string() -> None:
    # Git's `user.name` here, an OS user on a machine without one; either way it
    # has to be something a reviewer would recognise in a diff.
    name = author_name()
    assert name
    assert name.strip() == name
