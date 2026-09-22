# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The congruence lint's roadmap-delivery-checkbox check (roadmap 6.34).

PR #163 merged on 2026-09-18 and wrote a full delivery record onto roadmap item
6.18 — the ADR, the before-and-after numbers, the follow-ups it filed — while
leaving the checkbox at `- [ ]`. Nothing caught it: the PR template's *ROADMAP.md
checkbox flipped* is a box a human ticks, and the congruence lint had no opinion
about the mismatch between an item's own prose and its checkbox.

`delivered by PR #<digits>` is the phrase every closed item since M1 uses, so
this check is a lint on a convention rather than a new invention: an item whose
text records a delivery is checked, full stop.
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
def delivery(monkeypatch: pytest.MonkeyPatch) -> Iterator[Run]:
    """Run the check against a synthetic ROADMAP and return the failure messages."""

    def run(text: str) -> list[str]:
        monkeypatch.setattr(lint, "read", lambda *parts: text)
        lint.failures.clear()
        lint.check_roadmap_delivery_checkbox()
        return [message for _, message in lint.failures]

    lint.failures.clear()
    yield run
    lint.failures.clear()


MILESTONE = """# Roadmap

## Milestone 6 — Retrieval

- [x] 6.1 Closed and delivered — size: S · route: fast / low — delivered by PR #100
- [ ] 6.2 Still open, no delivery prose
"""


def test_the_committed_roadmap_passes() -> None:
    """The live file, not a fixture: this is the check's whole point."""
    lint.failures.clear()
    try:
        lint.check_roadmap_delivery_checkbox()
        assert lint.failures == []
    finally:
        lint.failures.clear()


def test_a_well_formed_roadmap_passes(delivery: Run) -> None:
    assert delivery(MILESTONE) == []


def test_an_unchecked_item_that_records_a_delivery_fails(delivery: Run) -> None:
    mismatched = MILESTONE.replace(
        "- [ ] 6.2 Still open, no delivery prose",
        "- [ ] 6.2 Actually done — delivered by PR #200",
    )
    (message,) = delivery(mismatched)
    assert "item 6.2 records a delivery" in message
    assert "flip it to '- [x]'" in message


def test_a_checked_item_with_no_delivery_prose_is_not_a_failure(delivery: Run) -> None:
    # The mirror rule was considered and rejected when this item was filed:
    # plenty of items close on other grounds (an owner action, a sibling item's
    # evidence, work folded into another item) with no "delivered by PR #N" of
    # their own, and there is no unambiguous phrase to require there.
    unexplained = MILESTONE.replace(
        "- [x] 6.1 Closed and delivered — size: S · route: fast / low — delivered by PR #100",
        "- [x] 6.1 Closed by owner action, no PR",
    )
    assert delivery(unexplained) == []


def test_a_bare_hash_n_placeholder_is_not_a_delivery(delivery: Run) -> None:
    # This item's own ROADMAP prose quotes the convention as "delivered by PR
    # #N" — a placeholder, not a real number. Matching only digits keeps the
    # check from failing on the item that describes the rule.
    placeholder = MILESTONE.replace(
        "- [ ] 6.2 Still open, no delivery prose",
        "- [ ] 6.2 Describes the convention as 'delivered by PR #N'",
    )
    assert delivery(placeholder) == []


def test_several_unchecked_deliveries_are_each_named(delivery: Run) -> None:
    both = MILESTONE.replace(
        "- [ ] 6.2 Still open, no delivery prose",
        "- [ ] 6.2 One — delivered by PR #201\n- [ ] 6.3 Two — delivered by PR #202",
    )
    messages = delivery(both)
    assert len(messages) == 2
    assert any("item 6.2" in message for message in messages)
    assert any("item 6.3" in message for message in messages)


def test_a_roadmap_with_no_items_is_not_a_failure(delivery: Run) -> None:
    # Unlike roadmap-numbering, an empty roadmap has nothing to mismatch.
    empty = "# Roadmap\n\n## Milestone 4 — Ingestion\n\nNothing planned yet.\n"
    assert delivery(empty) == []


def test_the_check_is_registered(delivery: Run) -> None:
    # A check nobody runs is a check that does not exist.
    assert lint.check_roadmap_delivery_checkbox in lint.CHECKS
