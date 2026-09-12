# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The congruence lint's roadmap-numbering check (roadmap 4.27).

`ROADMAP.md` states two rules that only hold together: a new item takes a fresh
`<milestone>.<task>` number, and nothing is ever renumbered. The second is what makes a
collision expensive — `4.23` was issued twice, and by the time anyone unpicked it the number
was cited from a source file, two tests, a tool, three ADRs, the README, `eval/README.md`
and the CHANGELOG. So the rule is enforced rather than remembered.

What is asserted here is what the check refuses *and* what it deliberately allows: a gap is
a legitimate outcome when an item is folded into another, and a lint that failed on one
would teach people to fill holes — which is renumbering under a different name.
"""

import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import consistency_lint as lint  # noqa: E402 - the tool is not an installed package

type Run = Callable[[str], list[str]]


@pytest.fixture
def numbering(monkeypatch: pytest.MonkeyPatch) -> Iterator[Run]:
    """Run the check against a synthetic ROADMAP and return the failure messages."""

    def run(text: str) -> list[str]:
        monkeypatch.setattr(lint, "read", lambda *parts: text)
        lint.failures.clear()
        lint.check_roadmap_numbering()
        return [message for _, message in lint.failures]

    lint.failures.clear()
    yield run
    lint.failures.clear()


MILESTONE = """# Roadmap

## Milestone 4 — Ingestion

- [x] 4.1 The first item
- [ ] 4.2 The second item

---

## Milestone 5 — Structure

- [ ] 5.1 A later item
"""


def test_the_committed_roadmap_passes() -> None:
    """The live file, not a fixture: this is the check's whole point."""
    lint.failures.clear()
    try:
        lint.check_roadmap_numbering()
        assert lint.failures == []
    finally:
        lint.failures.clear()


def test_a_well_formed_roadmap_passes(numbering: Run) -> None:
    assert numbering(MILESTONE) == []


def test_a_duplicate_number_fails_and_names_both_items(numbering: Run) -> None:
    duplicated = MILESTONE.replace("- [ ] 4.2 The second item", "- [ ] 4.1 The second item")
    (message,) = numbering(duplicated)
    assert "4.1 is used twice" in message
    # Both titles, because "4.1 is a duplicate" leaves a reader to go and find out
    # which two, and the fix depends on which one is newer.
    assert "The first item" in message
    assert "The second item" in message
    assert "fresh number" in message


def test_an_item_filed_under_the_wrong_milestone_fails(numbering: Run) -> None:
    misplaced = MILESTONE.replace("- [ ] 5.1 A later item", "- [ ] 4.9 A misplaced item")
    (message,) = numbering(misplaced)
    assert "item 4.9 sits under '## Milestone 5'" in message


def test_a_gap_is_not_a_failure(numbering: Run) -> None:
    # Deliberate: an item folded into another leaves a hole, and the hole is the
    # truth. Failing here would train people to fill it, which is renumbering.
    assert numbering(MILESTONE.replace("- [ ] 4.2 The second item", "- [ ] 4.7 The seventh")) == []


def test_a_roadmap_with_no_items_is_reported(numbering: Run) -> None:
    empty = "# Roadmap\n\n## Milestone 4 — Ingestion\n\nNothing planned yet.\n"
    assert numbering(empty) == ["no numbered ROADMAP items parsed"]


def test_a_roadmap_with_no_milestone_headings_is_reported(numbering: Run) -> None:
    assert numbering("# Roadmap\n\n- [ ] 4.1 An orphan\n") == [
        "no '## Milestone N' sections parsed from ROADMAP.md"
    ]


def test_the_check_is_registered(numbering: Run) -> None:
    # A check nobody runs is a check that does not exist.
    assert lint.check_roadmap_numbering in lint.CHECKS


# ---------------------------------------------------------------------------
# The threat model's boundary ids (roadmap 4.31) — the same defect, one artifact
# along: `B10` was issued twice, so six STRIDE rows citing it meant two things.
# ---------------------------------------------------------------------------

MODEL = """# Threat model

## 1. Scope & trust boundaries

| Boundary | Untrusted inputs | Assumptions |
|---|---|---|
| **B1 — First** (today): a thing | input | assumed |
| **B2 — Second** (today): another | input | assumed |

## 2. STRIDE pass

| Category | Threat | Boundary / component | Mitigation | Status |
|---|---|---|---|---|
| Spoofing | something | B1 | a control | ✅ |
| Tampering | something else | B1/B2 | a control | ✅ |
"""


@pytest.fixture
def boundaries(monkeypatch: pytest.MonkeyPatch) -> Iterator[Run]:
    def run(text: str) -> list[str]:
        monkeypatch.setattr(lint, "read", lambda *parts: text)
        monkeypatch.setattr(lint, "exists", lambda rel: True)
        lint.failures.clear()
        lint.check_threat_boundaries()
        return [message for _, message in lint.failures]

    lint.failures.clear()
    yield run
    lint.failures.clear()


def test_the_committed_threat_model_passes() -> None:
    lint.failures.clear()
    try:
        lint.check_threat_boundaries()
        assert lint.failures == []
    finally:
        lint.failures.clear()


def test_a_well_formed_threat_model_passes(boundaries: Run) -> None:
    assert boundaries(MODEL) == []


def test_a_duplicate_boundary_id_fails_and_names_both(boundaries: Run) -> None:
    duplicated = MODEL.replace("**B2 — Second**", "**B1 — Second**")
    messages = boundaries(duplicated)
    assert any("boundary B1 is declared twice" in m for m in messages)
    assert any("First" in m and "Second" in m for m in messages)


def test_a_row_citing_a_boundary_that_does_not_exist_fails(boundaries: Run) -> None:
    # Worse than a duplicate: it reads as coverage.
    dangling = MODEL.replace("| Spoofing | something | B1 |", "| Spoofing | something | B99 |")
    assert boundaries(dangling) == ["a STRIDE row cites B99, which no boundary declares"]


def test_a_row_citing_several_boundaries_checks_each(boundaries: Run) -> None:
    dangling = MODEL.replace("| B1/B2 |", "| B2/B98 |")
    assert boundaries(dangling) == ["a STRIDE row cites B98, which no boundary declares"]


def test_a_threat_model_with_no_boundaries_is_reported(boundaries: Run) -> None:
    assert boundaries("# Threat model\n\nNothing yet.\n") == [
        "no '**BN — ...**' boundary rows parsed from the threat model"
    ]


def test_the_boundary_check_is_registered() -> None:
    assert lint.check_threat_boundaries in lint.CHECKS


# ---------------------------------------------------------------------------
# The amendment relation, which stays in prose and is therefore checked (5.21)
# ---------------------------------------------------------------------------

type RunAdrs = Callable[[dict[str, str]], list[str]]


@pytest.fixture
def amendments(monkeypatch: pytest.MonkeyPatch) -> Iterator[RunAdrs]:
    """Run the check against a synthetic `docs/adr/` and return the failures."""

    def run(files: dict[str, str]) -> list[str]:
        monkeypatch.setattr(lint, "exists", lambda *parts: True)
        monkeypatch.setattr(lint.os, "listdir", lambda _: sorted(files))
        monkeypatch.setattr(lint, "read", lambda *parts: files[parts[-1]])
        lint.failures.clear()
        lint.check_amendments()
        return [message for _, message in lint.failures]

    lint.failures.clear()
    yield run
    lint.failures.clear()


def adr(number: str, status: str = "Accepted", body: str = "") -> str:
    return (
        f"# ADR-{number}: A decision\n\n"
        f"- **Status:** {status}\n"
        "- **Date:** 2026-09-12\n\n"
        "## Context\n\n"
        f"{body}\n"
    )


AMENDER = "[ADR-0023](0023-make-the-chunk-target-steer-size.md)"


def test_the_committed_adrs_pass() -> None:
    """The real corpus, whose nine relations are what the rules were derived from."""
    lint.failures.clear()
    lint.check_amendments()
    assert lint.failures == []


def test_an_amendment_in_the_status_line_passes(amendments: RunAdrs) -> None:
    assert (
        amendments(
            {
                "0014-a.md": adr("0014", status=f"Accepted — the ruling is amended by {AMENDER}"),
                "0023-make-the-chunk-target-steer-size.md": adr("0023", body="Amends ADR-0014."),
            }
        )
        == []
    )


def test_an_amendment_noted_at_the_paragraph_it_changes_passes(amendments: RunAdrs) -> None:
    """The second placement the corpus uses, and the one a partial relation needs."""
    assert (
        amendments(
            {
                "0053-a.md": adr("0053", body=f"> **Narrowed at roadmap 4.26 ({AMENDER}).**"),
                "0023-make-the-chunk-target-steer-size.md": adr("0023", body="Narrows ADR-0053."),
            }
        )
        == []
    )


def test_an_unlinked_amender_fails(amendments: RunAdrs) -> None:
    """The premise of the refusal is that a reader can follow the prose."""
    assert amendments(
        {
            "0014-a.md": adr("0014", status="Accepted — the ruling is amended by ADR-0023"),
            "0023-b.md": adr("0023", body="Amends ADR-0014."),
        }
    ) == [
        "0014-a.md names ADR-0023 in an amendment but does not link it; the relation lives "
        "in prose by decision (ADR-0092), so the prose has to be followable"
    ]


def test_an_amender_that_does_not_exist_fails(amendments: RunAdrs) -> None:
    assert amendments(
        {
            "0014-a.md": adr("0014", status="Accepted — amended by [ADR-0999](0999-nothing.md)"),
        }
    ) == ["0014-a.md says it is amended by ADR-0999, which has no file in docs/adr/"]


def test_an_amendment_the_amender_never_acknowledges_fails(amendments: RunAdrs) -> None:
    assert amendments(
        {
            "0014-a.md": adr("0014", status=f"Accepted — the ruling is amended by {AMENDER}"),
            "0023-make-the-chunk-target-steer-size.md": adr("0023", body="About something else."),
        }
    ) == [
        "0014-a.md says it is amended by ADR-0023, but "
        "0023-make-the-chunk-target-steer-size.md never mentions ADR-0014 - one side of a "
        "relation that only prose carries (roadmap 5.21, ADR-0092)"
    ]


def test_one_pair_may_carry_several_amendments(amendments: RunAdrs) -> None:
    """ADR-0053 is narrowed twice by ADR-0056, at two different paragraphs — the
    case a single document-to-document edge could not have represented, which is
    half of why the ninth type was refused (ADR-0092)."""
    body = (
        f"> **Narrowed at roadmap 4.26 ({AMENDER}).**\n\nProse.\n\n"
        f"> **Narrowed at roadmap 4.26 ({AMENDER}).**\n"
    )
    assert (
        amendments(
            {
                "0053-a.md": adr("0053", body=body),
                "0023-make-the-chunk-target-steer-size.md": adr("0023", body="Narrows ADR-0053."),
            }
        )
        == []
    )


def test_an_adr_mentioned_in_the_notes_prose_is_not_a_second_amender(
    amendments: RunAdrs,
) -> None:
    """Only the declaring line is read, so discussion inside the note is prose."""
    body = (
        f"> **Narrowed at roadmap 4.26 ({AMENDER}).**\n"
        "> The reasoning also touches [ADR-0999](0999-nothing.md), which does not exist.\n"
    )
    assert (
        amendments(
            {
                "0053-a.md": adr("0053", body=body),
                "0023-make-the-chunk-target-steer-size.md": adr("0023", body="Narrows ADR-0053."),
            }
        )
        == []
    )


def test_a_supersession_is_not_read_as_an_amendment(amendments: RunAdrs) -> None:
    """`check_supersedes` owns that relation; this one must not double-report it."""
    assert (
        amendments(
            {
                "0002-a.md": adr("0002", status="Superseded by [ADR-0003](0003-b.md) (2026-08-29)"),
                "0003-b.md": adr("0003"),
            }
        )
        == []
    )


def test_the_amendment_check_is_registered() -> None:
    assert lint.check_amendments in lint.CHECKS
