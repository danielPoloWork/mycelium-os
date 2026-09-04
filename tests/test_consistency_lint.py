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
