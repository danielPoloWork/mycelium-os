# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Stale-anchor handling, proven on a heavily refactored corpus (roadmap 5.6).

The Milestone 5 exit gate asks for exactly this, and the promise under test is
spec 03 §3.1's: a citation into a document that has since been refactored gets a
typed `ANCHOR_GONE` with the nearest surviving ancestor *"rather than silently
wrong content"*.

So this module does not test a function. It builds a corpus, mints **every**
citation a consumer could be holding, applies one named refactoring, rebuilds,
and says what became of each:

| outcome    | the consumer's citation…                                       |
|------------|----------------------------------------------------------------|
| `SURVIVED` | resolves, and is still current                                 |
| `MOVED`    | resolves, and the response says the passage has moved          |
| `GONE`     | `ANCHOR_GONE`, naming a nearest ancestor that really resolves  |
| `MISSING`  | `NOT_FOUND` — the document itself is gone                      |

:data:`EXPECTED` pins the whole map per refactoring, which is what makes this a
gate rather than an anecdote: a change to the chunker, the anchor scheme or the
slug rule shows up here as a **named citation** moving between columns.

**Two axes, not one.** *Moved* and *changed* are different questions, and the
proof keeps them apart. Deleting a paragraph from the top of a document moves
every section below it without changing a word of them — those citations are
`MOVED` and their text is intact. Rewriting a sentence in place changes a
passage without moving it. The contract this module enforces is about the
second: :func:`test_a_changed_passage_is_never_served_in_silence` asserts that
**no citation may resolve to changed content without saying so** — with exactly
one exception, an in-place rewrite of identical length, which a positional check
cannot see and which is filed as roadmap 5.17.

Before roadmap 5.6 there was no exception list, because there was no reporting
at all: six citations across five of these refactorings resolved to a different
passage in silence (ADR-0078).
"""

from collections.abc import Mapping
from enum import Enum
from pathlib import Path

import pytest

from mycelium.build import build
from mycelium.citations import chunk_uri
from mycelium.mcp.errors import ErrorCode, McpToolError
from mycelium.mcp.tools import handle_fetch
from mycelium.sdk.identity import parse_citation_uri
from mycelium.store import SqliteStore

# ---------------------------------------------------------------------------
# The corpus
# ---------------------------------------------------------------------------

ARCHITECTURE = """---
mycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5F01
---

# Architecture

## Event bus

The bus is asynchronous.

Delivery is at-least-once, so consumers must be idempotent.

Back-pressure is applied at the publisher.

## Retries

Retries use exponential backoff.

The ceiling is five attempts.

## Storage

Everything derived lives under the store.
"""

GUIDE = """---
mycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5F02
---

# Guide

## Getting started

Install and run.

## Troubleshooting

Read the journal.
"""

COLLIDE = """---
mycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5F03
---

# Collide

## Event bus

The first bus section.

## Retries

Unrelated.

## Event bus

The second bus section.
"""

ARCH = "knowledge/verified/architecture.md"
GUIDE_PATH = "knowledge/verified/guide.md"
COLLIDE_PATH = "knowledge/verified/collide.md"

CORPUS: Mapping[str, str] = {
    ARCH: ARCHITECTURE,
    GUIDE_PATH: GUIDE,
    COLLIDE_PATH: COLLIDE,
}

# ---------------------------------------------------------------------------
# The refactorings — a path maps to its new text, or to None to delete it
# ---------------------------------------------------------------------------

REFACTORINGS: Mapping[str, Mapping[str, str | None]] = {
    "rename a heading": {ARCH: ARCHITECTURE.replace("## Event bus", "## The event bus")},
    "nest a section one level deeper": {ARCH: ARCHITECTURE.replace("## Retries", "### Retries")},
    "delete a paragraph mid-section": {
        ARCH: ARCHITECTURE.replace(
            "Delivery is at-least-once, so consumers must be idempotent.\n\n", ""
        )
    },
    "insert a paragraph mid-section": {
        ARCH: ARCHITECTURE.replace(
            "The bus is asynchronous.\n",
            "The bus is asynchronous.\n\nOrdering is per-partition only.\n",
        )
    },
    "reorder two sections": {
        ARCH: ARCHITECTURE.replace("## Event bus", "@@")
        .replace("## Retries", "## Event bus")
        .replace("@@", "## Retries")
    },
    "edit prose in place, keeping every heading": {
        ARCH: ARCHITECTURE.replace("The ceiling is five attempts.", "The ceiling is ten attempts.")
    },
    "rename the first of two headings that slugify alike": {
        COLLIDE_PATH: COLLIDE.replace(
            "## Event bus\n\nThe first bus section.", "## Message bus\n\nThe first bus section."
        )
    },
    "rename the file": {GUIDE_PATH: None, "knowledge/verified/handbook.md": GUIDE},
    "demote verified to candidate": {GUIDE_PATH: None, "knowledge/candidate/guide.md": GUIDE},
    "delete a document": {GUIDE_PATH: None},
    "split a document in two": {
        ARCH: ARCHITECTURE.split("## Storage")[0],
        "knowledge/verified/storage.md": """---
mycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5F04
---

# Storage

## Storage

Everything derived lives under the store.
""",
    },
}


class Outcome(Enum):
    """What became of one held citation after the corpus moved under it."""

    SURVIVED = "survived"
    MOVED = "moved"
    GONE = "gone"
    MISSING = "missing"


# The outcome map, per refactoring. A citation absent from a case `SURVIVED`;
# spelling three documents' worth of those out per case would bury the rows that
# matter, and `test_the_outcome_table_is_honest` checks the other direction.
#
# Citations are named by the anchor they were minted from, because a URI carries
# a ULID and a line range and this table is meant to be *read*.
EXPECTED: Mapping[str, Mapping[str, Outcome]] = {
    # --- the designed outcome: the heading path is the anchor ----------------
    "rename a heading": {f"{ARCH}#event-bus/0": Outcome.GONE},
    "nest a section one level deeper": {f"{ARCH}#retries/0": Outcome.GONE},
    "split a document in two": {f"{ARCH}#storage/0": Outcome.GONE},
    "delete a document": {
        f"{GUIDE_PATH}#/0": Outcome.MISSING,
        f"{GUIDE_PATH}#getting-started/0": Outcome.MISSING,
        f"{GUIDE_PATH}#troubleshooting/0": Outcome.MISSING,
    },
    # --- D-021: a citation keys on `doc_id`, so a move is free ---------------
    "rename the file": {},
    "demote verified to candidate": {},
    # --- the ordinal is a position, so passages slide under their anchors ----
    # `#event-bus/0` is the one whose *content* changes; the two below it merely
    # shift down the file, which is still worth reporting because the line range
    # in the consumer's URI is now wrong.
    "delete a paragraph mid-section": {
        f"{ARCH}#event-bus/0": Outcome.MOVED,
        f"{ARCH}#retries/0": Outcome.MOVED,
        f"{ARCH}#storage/0": Outcome.MOVED,
    },
    "insert a paragraph mid-section": {
        f"{ARCH}#event-bus/0": Outcome.MOVED,
        f"{ARCH}#retries/0": Outcome.MOVED,
        f"{ARCH}#storage/0": Outcome.MOVED,
    },
    "reorder two sections": {
        f"{ARCH}#event-bus/0": Outcome.MOVED,
        f"{ARCH}#retries/0": Outcome.MOVED,
    },
    # The nastiest row in the table: rename the *first* of two headings that
    # slugify alike and the second inherits the unsuffixed slug, so a citation
    # to the first silently resolved to the second until ADR-0078.
    "rename the first of two headings that slugify alike": {
        f"{COLLIDE_PATH}#event-bus/0": Outcome.MOVED,
        f"{COLLIDE_PATH}#event-bus-2/0": Outcome.GONE,
    },
    # The blind spot, as a row: same anchor, same line range, different words.
    # `SURVIVED` is the wrong answer and it is the one a positional check gives
    # (roadmap 5.17). `test_an_in_place_edit_is_the_blind_spot` is its receipt.
    "edit prose in place, keeping every heading": {},
}

BLIND_SPOT = "edit prose in place, keeping every heading"
"""The single refactoring whose changed passage is *not* reported (roadmap 5.17)."""


# ---------------------------------------------------------------------------
# The harness
# ---------------------------------------------------------------------------


def write(root: Path, files: Mapping[str, str | None]) -> None:
    for relative, text in files.items():
        target = root / relative
        if text is None:
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)


def mint(root: Path) -> dict[str, tuple[str, str]]:
    """Every citation a consumer could hold: anchor -> (uri, the text behind it)."""
    held: dict[str, tuple[str, str]] = {}
    with SqliteStore.open(root, read_only=True) as store:
        for doc_id in store.document_ids():
            for chunk in store.chunks_of(doc_id):
                held[chunk.anchor] = (chunk_uri(chunk), chunk.text)
    return held


def classify(root: Path, held: Mapping[str, tuple[str, str]]) -> dict[str, tuple[Outcome, bool]]:
    """Fetch every held citation: anchor -> (outcome, did its text change).

    The contract is asserted on the way through — a dead anchor must name a
    survivor that really resolves, and a `stale` block must agree with the
    response it travels in.
    """
    outcomes: dict[str, tuple[Outcome, bool]] = {}
    for held_anchor, (uri, before) in held.items():
        try:
            payload = handle_fetch(root, {"uri": uri})
        except McpToolError as error:
            if error.code is ErrorCode.NOT_FOUND:
                outcomes[held_anchor] = (Outcome.MISSING, True)
                continue
            assert error.code is ErrorCode.ANCHOR_GONE, error.code
            nearest = error.fields["nearest"]
            assert handle_fetch(root, {"uri": nearest})["content"], (
                f"{held_anchor}: ANCHOR_GONE named {nearest}, which does not resolve"
            )
            outcomes[held_anchor] = (Outcome.GONE, True)
            continue

        changed = payload["content"][0]["text"] != before
        stale = payload["stale"]
        if stale is None:
            outcomes[held_anchor] = (Outcome.SURVIVED, changed)
            continue

        assert stale["cited_lines"] == list(parse_citation_uri(uri).lines or ())
        assert stale["current_lines"] == payload["content"][0]["lines"]
        assert stale["current_lines"] != stale["cited_lines"]
        # The citation it offers instead is real, and fetching it is clean.
        assert handle_fetch(root, {"uri": stale["uri"]})["stale"] is None
        outcomes[held_anchor] = (Outcome.MOVED, changed)
    return outcomes


def refactor(tmp_path: Path, name: str) -> dict[str, tuple[Outcome, bool]]:
    """Build the corpus, hold every citation, apply `name`, rebuild, classify."""
    root = tmp_path / "repo"
    write(root, CORPUS)
    build(root)
    held = mint(root)
    write(root, REFACTORINGS[name])
    build(root)
    return classify(root, held)


# ---------------------------------------------------------------------------
# The proof
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(REFACTORINGS))
def test_every_refactoring_has_the_outcome_the_table_records(tmp_path: Path, name: str) -> None:
    outcomes = refactor(tmp_path, name)
    observed = {anchor: outcome for anchor, (outcome, _) in outcomes.items()}
    expected = {anchor: EXPECTED[name].get(anchor, Outcome.SURVIVED) for anchor in observed}
    assert observed == expected


@pytest.mark.parametrize("name", list(REFACTORINGS))
def test_a_changed_passage_is_never_served_in_silence(tmp_path: Path, name: str) -> None:
    """The contract, and the reason this module exists (spec 03 §3.1).

    A citation whose passage has changed must come back as `ANCHOR_GONE`,
    `NOT_FOUND`, or with a `stale` block. `SURVIVED` plus changed content is
    silently wrong content, which is what the spec forbids and what roadmap 5.6
    found happening six times.
    """
    silent = [
        anchor
        for anchor, (outcome, changed) in refactor(tmp_path, name).items()
        if changed and outcome is Outcome.SURVIVED
    ]
    if name == BLIND_SPOT:
        # Stated, bounded, and filed — never discovered by a user.
        assert silent == [f"{ARCH}#retries/0"], "the blind spot moved (roadmap 5.17)"
        return
    assert silent == []


def test_the_outcome_table_is_honest() -> None:
    """Every refactoring is in the table, and the table lists no `SURVIVED`."""
    assert set(EXPECTED) == set(REFACTORINGS)
    assert BLIND_SPOT in REFACTORINGS
    for name, case in EXPECTED.items():
        assert Outcome.SURVIVED not in case.values(), (
            f"{name}: SURVIVED is the default; listing it hides the rows that matter"
        )
        assert all(anchor.startswith("knowledge/") for anchor in case)


def test_a_citation_survives_a_rename_and_a_promotion(tmp_path: Path) -> None:
    """D-021's promise, as its own test, because it is *why* a citation keys on
    `doc_id` rather than on a path: moving a document must cost nothing."""
    for index, name in enumerate(("rename the file", "demote verified to candidate")):
        outcomes = refactor(tmp_path / f"case{index}", name)
        assert {outcome for outcome, _ in outcomes.values()} == {Outcome.SURVIVED}


def test_a_moved_passage_is_never_served_in_silence(tmp_path: Path) -> None:
    """The defect roadmap 5.6 found, at its sharpest.

    Before ADR-0078 this fetch returned the *second* bus section under the
    *first* one's citation, with nothing in the response to distinguish it from
    a hit — the agent would have re-quoted it as the passage it cited.
    """
    root = tmp_path / "repo"
    write(root, CORPUS)
    build(root)
    uri, before = mint(root)[f"{COLLIDE_PATH}#event-bus/0"]
    write(root, REFACTORINGS["rename the first of two headings that slugify alike"])
    build(root)

    payload = handle_fetch(root, {"uri": uri})

    assert payload["content"][0]["text"] != before
    assert "The second bus section." in payload["content"][0]["text"]
    stale = payload["stale"]
    assert stale is not None
    assert "has moved since the citation was made" in stale["reason"]
    assert "re-read it before re-quoting it" in stale["reason"]


def test_an_unmoved_citation_is_never_called_stale(tmp_path: Path) -> None:
    """The other direction, and what makes `stale` worth reading: a rebuild that
    changes nothing, and an edit *below* the cited section, both leave it None."""
    root = tmp_path / "repo"
    write(root, CORPUS)
    build(root)
    uri = mint(root)[f"{ARCH}#event-bus/0"][0]
    assert handle_fetch(root, {"uri": uri})["stale"] is None

    build(root)
    assert handle_fetch(root, {"uri": uri})["stale"] is None

    write(root, {ARCH: ARCHITECTURE.replace("Everything derived", "All derived data")})
    build(root)
    assert handle_fetch(root, {"uri": uri})["stale"] is None


def test_an_in_place_edit_is_the_blind_spot(tmp_path: Path) -> None:
    """The stated limit, pinned so it cannot be forgotten or silently closed.

    A passage rewritten without changing its length keeps its line range, so a
    positional check cannot see it. Closing this needs *content* identity in the
    citation, which changes a contract that freezes at 1.0 (spec 02 §10) — filed
    as roadmap 5.17. If this test starts failing, that item landed, and this is
    the receipt it has to update.
    """
    root = tmp_path / "repo"
    write(root, CORPUS)
    build(root)
    uri, before = mint(root)[f"{ARCH}#retries/0"]
    write(root, REFACTORINGS[BLIND_SPOT])
    build(root)

    payload = handle_fetch(root, {"uri": uri})

    assert payload["content"][0]["text"] != before, "the passage did change"
    assert payload["content"][0]["lines"] == list(parse_citation_uri(uri).lines or ())
    assert payload["stale"] is None, "and a line range cannot tell (roadmap 5.17)"


def test_a_hand_written_citation_carries_nothing_to_check(tmp_path: Path) -> None:
    """A URI without `?lines=` is not evidence of anything, so it is not judged."""
    root = tmp_path / "repo"
    write(root, CORPUS)
    build(root)
    uri = mint(root)[f"{ARCH}#retries/0"][0]
    write(root, REFACTORINGS["insert a paragraph mid-section"])
    build(root)

    assert handle_fetch(root, {"uri": uri})["stale"] is not None
    assert handle_fetch(root, {"uri": uri.split("?", 1)[0]})["stale"] is None
