# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The symbol leg in retrieval (roadmap 5.9, spec 04 §§2-3, ADR-0080).

The claims under test:

**The default is the one the ablation supports**, and the constants are the ones
it was run at — so moving either without re-running
`tools/measure_symbol_leg.py` fails here as well as at `--check`.

**Only identifier-like tokens are looked up, and the lookup is exact.** One rule
decides what a name looks like, shared with the heading rule that creates the
symbols, so the two cannot drift apart and make the leg miss what the extractor
wrote.

**The leg adds and never promotes**, which is ADR-0075's rule; and when it does
add, the passage is labelled with the symbol it defines.

**The mechanism works** — it finds a definition site the ranking did not reach,
ranks it by BM25, honours the serving policy and is deterministic. This matters
because the ablation's result is *no movement at all*, and a null result is only
worth reporting if the thing being measured demonstrably runs.
"""

from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from mycelium import retrieval
from mycelium.build import build
from mycelium.config import RetrievalConfig
from mycelium.eval.retrievers import build_retriever
from mycelium.retrieval import (
    SYMBOL_CANDIDATES,
    SYMBOL_DISCOUNT,
    SYMBOL_LANGUAGES,
    SYMBOL_PROMOTE,
    VECTOR_CANDIDATES,
    FusedHit,
    retrieval_identity,
    search,
    symbol_lookup_ids,
)
from mycelium.store import SearchFilters, SqliteStore
from mycelium.symbols import heading_subject, identifier_like

# One document that defines things, and one that talks about them. `RetryPolicy`
# is defined in a fence; `bus.config` is defined by a heading; the guide mentions
# both without defining either.
CORPUS: Mapping[str, str] = {
    "knowledge/api.md": """---
mycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FA1
---

# API

## RetryPolicy

The policy every connector shares.

```python
class RetryPolicy:
    def delay(self, attempt):
        return attempt
```

## bus.config

Where the bus reads its settings.
""",
    "knowledge/guide.md": """---
mycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FA2
---

# Guide

## Choosing a policy

Every connector shares one RetryPolicy, and the bus reads bus.config at startup.
A longer discussion of retries, attempts, backoff and delay lives here, so this
section mentions the names far more often than the reference does: RetryPolicy,
RetryPolicy, bus.config, bus.config.
""",
}


# The one shape under which the leg can *add*: a definition site the ranking
# pushed past its fifty candidates. Fifty-five notes mention `WidgetFactory`
# repeatedly; the document that defines it says the name once, inside a fence,
# under a heading that does not repeat it, followed by enough prose for BM25's
# length normalisation to sink it. Measured: the definition lands at lexical
# rank 56 (ADR-0080).
_NOISE = """---
mycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5{index:03d}
---

# Notes {index}

## Overview

WidgetFactory is mentioned here. WidgetFactory again, and WidgetFactory once
more, because WidgetFactory comes up constantly in these notes about
WidgetFactory.
"""

_DEFINITION = (
    """---
mycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FB1
---

# Implementation

## Rendering

```python
class WidgetFactory:
    pass
```

"""
    + "Filler prose about rendering pipelines and layout passes. " * 40
    + "\n"
)

OUTRANKED: Mapping[str, str] = {
    **{f"knowledge/notes-{i:03d}.md": _NOISE.format(index=i) for i in range(55)},
    "knowledge/impl.md": _DEFINITION,
}


def repo(tmp_path: Path, files: Mapping[str, str] | None = None, name: str = "repo") -> Path:
    root = tmp_path / name
    for relative, text in (files or CORPUS).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return root


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SqliteStore]:
    root = repo(tmp_path_factory.mktemp("symbol-leg"))
    build(root)
    with SqliteStore.open(root, read_only=True) as opened:
        yield opened


@pytest.fixture
def promoting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spec 04 §2's other reading, which the runner scores and nothing ships."""
    monkeypatch.setattr(retrieval, "SYMBOL_PROMOTE", True)


def anchors(hits: tuple[FusedHit, ...]) -> list[str]:
    return [hit.hit.chunk.anchor for hit in hits]


def on(**extra: bool) -> RetrievalConfig:
    return RetrievalConfig(symbol_lookup=True, **extra)


# ---------------------------------------------------------------------------
# The default, and the constants it was measured at
# ---------------------------------------------------------------------------


def test_the_leg_is_off_by_default_because_the_ablation_said_so() -> None:
    """Measured on six case sets across three corpora, it moved the `symbol`
    slice by +0.0 % on every one of them — it cannot fire on a single judged case
    in that slice. Flipping this without re-running
    `tools/measure_symbol_leg.py` is what this test exists to stop (ADR-0080)."""
    assert RetrievalConfig().symbol_lookup is False


def test_the_constants_are_the_ones_the_ablation_was_run_at() -> None:
    assert SYMBOL_CANDIDATES == 10
    assert SYMBOL_DISCOUNT == 0.9
    assert SYMBOL_PROMOTE is False, "the shipped reading is add-only (ADR-0075's rule)"


def test_the_discount_sits_inside_the_window_rrf_leaves_it() -> None:
    """The arithmetic ADR-0075 derived, asserted for this leg too.

    A leg-only passage must not outrank the lexical leg's first (`d < 1`), and it
    must be able to displace the served window's weakest (`d > 61/70`), or the
    leg cannot change an answer and the ablation measures nothing.
    """
    assert SYMBOL_DISCOUNT / (retrieval.RRF_K + 1) < 1 / (retrieval.RRF_K + 1)
    assert SYMBOL_DISCOUNT / (retrieval.RRF_K + 1) > 1 / (retrieval.RRF_K + 10)


def test_the_symbol_constants_are_part_of_the_retrieval_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate G2's verdict is about the ranking it was measured under (ADR-0064),
    and these constants decide a ranking whenever the flag is on."""
    before = retrieval_identity()
    monkeypatch.setattr(retrieval, "SYMBOL_DISCOUNT", 0.95)
    assert retrieval_identity() != before
    monkeypatch.setattr(retrieval, "SYMBOL_DISCOUNT", SYMBOL_DISCOUNT)
    monkeypatch.setattr(retrieval, "SYMBOL_PROMOTE", True)
    assert retrieval_identity() != before


def test_the_flag_itself_is_not_in_the_fingerprint() -> None:
    """A default flip and a stale measurement are different mistakes with
    different remedies, so they are reported separately (ADR-0064's rule, kept)."""
    before = retrieval_identity()
    assert RetrievalConfig(symbol_lookup=True).symbol_lookup is True
    assert retrieval_identity() == before


# ---------------------------------------------------------------------------
# What gets looked up: identifier-like, and exact
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token",
    ["RetryPolicy", "uv.lock", "mycelium_neighbors", "docs/adr", "std::fmt", "bus.config"],
)
def test_an_identifier_like_token_is_looked_up(token: str) -> None:
    assert identifier_like(token)
    ids = symbol_lookup_ids(f"where is {token} defined")
    assert f"sym:doc:{token}" in ids
    assert f"sym:python:{token}" in ids


@pytest.mark.parametrize(
    "query", ["what is a snapshot", "uv lock --check", "Retries", "v0.4.0", "how do I build"]
)
def test_a_query_with_no_identifier_like_token_looks_nothing_up(query: str) -> None:
    """The common case, and it must cost one regex rather than a store round trip."""
    assert symbol_lookup_ids(query) == ()


def test_every_known_language_is_asked_for_once() -> None:
    ids = symbol_lookup_ids("RetryPolicy")
    assert len(ids) == len(SYMBOL_LANGUAGES) == len(set(SYMBOL_LANGUAGES))
    assert {identity.split(":")[1] for identity in ids} == set(SYMBOL_LANGUAGES)
    assert "doc" in SYMBOL_LANGUAGES and "python" in SYMBOL_LANGUAGES


def test_the_lookup_is_exact_and_never_matches_a_tail(store: SqliteStore) -> None:
    """`lock` must not find `uv.lock`, and `config` must not find `bus.config`.

    Measured on both uv corpora and rejected there (ADR-0080): a tail match is
    what produced three of four firings and every one of them matched a
    *different* thing from the one the query asked about. Resolving a use by its
    last segment is right for an edge, where ambiguity can be refused and the
    claim is only that two names are related (ADR-0074), and wrong for a ranking.
    """
    assert symbol_lookup_ids("config") == ()
    assert store.symbols_by_id(symbol_lookup_ids("bus.config")) != ()
    outcome = search(store, "config", limit=10, config=on())
    assert all(not hit.via_symbol for hit in outcome.hits)


def test_every_name_a_heading_defines_is_a_name_a_query_can_find() -> None:
    """The invariant ADR-0080 is actually about, stated so 5.19's widening
    cannot break it: the extractor may read more *headings* than the planner
    would route, but every *name* it writes is one `identifier_like` accepts —
    so the leg can always reach what the extractor defined (ADR-0091).
    """
    headings = (
        "RetryPolicy",
        "uv.lock",
        "mycelium_neighbors",
        "The pyproject.toml",
        "pylock.toml format",
        "Using requirements.in",
        "Retries",
        "Event Bus",
        "Learn more about uv.",
    )
    for text in headings:
        subject = heading_subject(text)
        assert subject is None or identifier_like(subject[0]), text
    # And a one-word heading is still decided by that rule alone, which is the
    # half of the old equivalence that the widening leaves untouched.
    for text in ("RetryPolicy", "uv.lock", "mycelium_neighbors", "Retries", "Event Bus"):
        assert (heading_subject(text) is not None) is identifier_like(text)


def test_a_name_nothing_defines_offers_nothing(store: SqliteStore) -> None:
    outcome = search(store, "Missing.Symbol", limit=10, config=on())
    assert all(not hit.via_symbol for hit in outcome.hits)
    assert any("names a symbol this snapshot defines" in note for note in outcome.notes)


# ---------------------------------------------------------------------------
# What the leg does with what it found
# ---------------------------------------------------------------------------


def test_the_leg_adds_and_never_promotes(store: SqliteStore) -> None:
    """ADR-0075's load-bearing rule, applied to this leg.

    `RetryPolicy` is defined in `api.md` and the lexical leg finds that chunk, so
    the leg has nothing to add and the results are byte-identical. Letting it
    vote anyway would make RRF pay one piece of evidence twice — measured at 5 %
    to 56 % when the graph leg did it.
    """
    base = search(store, "RetryPolicy", limit=10, config=RetrievalConfig())
    with_leg = search(store, "RetryPolicy", limit=10, config=on())
    assert anchors(with_leg.hits) == anchors(base.hits)
    assert [hit.score for hit in with_leg.hits] == [hit.score for hit in base.hits]
    assert all(not hit.via_symbol for hit in with_leg.hits)


def test_promoting_offers_the_definition_site_and_labels_it(
    store: SqliteStore, promoting: None
) -> None:
    """The other reading of "symbol lookup first", which the runner scores.

    It is also the test that the whole path works — lookup, `doc_refs`
    resolution, BM25 ranking, and the label — because the shipped reading is
    silent on every corpus measured.
    """
    outcome = search(store, "RetryPolicy", limit=10, config=on())
    labelled = [hit for hit in outcome.hits if hit.via_symbol]
    assert labelled, "the definition site is offered"
    assert labelled[0].hit.chunk.anchor.startswith("knowledge/api.md#retrypolicy")
    assert "symbol" in labelled[0].legs
    # One chunk, two symbols: the heading defines a `doc` term and the fence
    # below it defines a `python` class. The label names both, because choosing
    # one would be an arbitrary tie-break reported as a fact.
    assert labelled[0].via_symbol == "defines sym:doc:RetryPolicy, sym:python:RetryPolicy"
    assert labelled[0].explain()["via_symbol"] == labelled[0].via_symbol


def test_a_definition_site_always_matches_its_own_name(store: SqliteStore) -> None:
    """Why the shipped reading is silent, and it is arithmetic rather than luck.

    A symbol's defining chunk *contains the symbol's name* — that is what made
    it a definition — so BM25 always retrieves it for a query naming it, and
    normally first. Under the add-only rule the leg therefore has nothing to
    carry unless fifty chunks outrank the definition of the very name being
    asked about. That is the finding ADR-0080 reports, and it is a property of
    the mechanism, not of these corpora.
    """
    for query in ("RetryPolicy", "bus.config"):
        lexical = search(store, query, limit=10, config=RetrievalConfig())
        definitions = store.symbols_by_id(symbol_lookup_ids(query))
        sites = {ref for symbol in definitions for ref in symbol.doc_refs}
        assert sites, "the corpus defines the name"
        assert sites <= set(anchors(lexical.hits)), "the ranking already has it"
        assert anchors(lexical.hits)[0] in sites, "and puts it first"


def test_the_leg_adds_a_definition_site_the_ranking_outranked(tmp_path: Path) -> None:
    """The add path, on the one corpus shape that produces it.

    This is the condition ADR-0080 names and the three measured corpora never
    meet: more than fifty chunks mention the name more than its own definition
    does, so the definition falls outside the lexical leg's candidates and the
    symbol table is the only thing that can still reach it. Here it sits at
    lexical rank 56, and the leg brings it into a ten-deep window at position 8
    — which is also the discount's derivation in action, since 0.9/61 beats the
    window's weakest at 1/70 and loses to its best at 1/61.
    """
    root = repo(tmp_path, OUTRANKED, name="outranked")
    build(root)
    with SqliteStore.open(root, read_only=True) as store:
        deep = search(store, "WidgetFactory", limit=200, config=RetrievalConfig())
        assert anchors(deep.hits).index("knowledge/impl.md#rendering/0") + 1 > VECTOR_CANDIDATES

        base = search(store, "WidgetFactory", limit=10, config=RetrievalConfig())
        assert "knowledge/impl.md#rendering/0" not in anchors(base.hits)

        with_leg = search(store, "WidgetFactory", limit=10, config=on())
        added = [hit for hit in with_leg.hits if hit.via_symbol]
        assert added, "a definition site the ranking outranked is added"
        assert added[0].hit.chunk.anchor == "knowledge/impl.md#rendering/0"
        assert added[0].via_symbol == "defines sym:python:WidgetFactory"
        assert added[0].legs == ("symbol",), "added, not promoted"
        # It enters the window, and it does not take the top of it.
        assert anchors(with_leg.hits)[0] == anchors(base.hits)[0]


def test_a_definition_site_is_ranked_by_the_same_bm25_as_everything_else(
    store: SqliteStore, promoting: None
) -> None:
    """Membership is the table's decision; order is BM25's (ADR-0075's shape).

    A symbol whose defining chunks hold none of the query's words contributes
    nothing, which is what stops the leg turning a name-drop into a result.
    """
    outcome = search(store, "RetryPolicy quantum chromodynamics", limit=10, config=on())
    assert [hit for hit in outcome.hits if hit.via_symbol], "the name still matches"
    unrelated = search(store, "quantum chromodynamics", limit=10, config=on())
    assert unrelated.hits == ()


def test_the_leg_respects_the_serving_policy(tmp_path: Path, promoting: None) -> None:
    """An offered passage may not reach a caller the configuration would not have
    served it to (ADR-0024's one seam)."""
    root = repo(
        tmp_path,
        {
            "knowledge/candidate/api.md": CORPUS["knowledge/api.md"].replace("69G5FA1", "69G5FC1"),
            **CORPUS,
        },
        name="policy",
    )
    build(root)
    with SqliteStore.open(root, read_only=True) as store:
        served = search(store, "RetryPolicy", limit=10, config=on())
        assert any("candidate/api.md" in anchor for anchor in anchors(served.hits))
        withheld = search(store, "RetryPolicy", limit=10, config=on(include_candidate=False))
        assert not any("candidate/api.md" in anchor for anchor in anchors(withheld.hits))


def test_a_caller_filter_narrows_the_leg_too(store: SqliteStore, promoting: None) -> None:
    outcome = search(
        store,
        "RetryPolicy",
        limit=10,
        config=on(),
        filters=SearchFilters(path_prefix="knowledge/guide"),
    )
    assert all(hit.hit.path.startswith("knowledge/guide") for hit in outcome.hits)


def test_the_leg_is_reported_in_timings_and_notes(store: SqliteStore, promoting: None) -> None:
    outcome = search(store, "RetryPolicy", limit=10, config=on())
    assert "symbol" in outcome.timings_ms
    assert "symbol" in outcome.legs
    assert any(note.startswith("symbol leg: 1 definition site") for note in outcome.notes)


def test_a_silent_leg_says_so_rather_than_saying_nothing(store: SqliteStore) -> None:
    outcome = search(store, "RetryPolicy", limit=10, config=on())
    assert "symbol" not in outcome.legs
    assert any("outside what the other legs already returned" in n for n in outcome.notes)


def test_the_leg_is_deterministic(store: SqliteStore, promoting: None) -> None:
    config = on()
    first = search(store, "RetryPolicy bus.config", limit=10, config=config)
    for _ in range(3):
        again = search(store, "RetryPolicy bus.config", limit=10, config=config)
        assert anchors(again.hits) == anchors(first.hits)
        assert [hit.via_symbol for hit in again.hits] == [hit.via_symbol for hit in first.hits]


def test_the_two_derived_legs_compose(store: SqliteStore, promoting: None) -> None:
    """Both flags on is a supported configuration, and each label survives it."""
    outcome = search(store, "RetryPolicy", limit=10, config=on(graph_expansion=True), related=True)
    assert outcome.hits
    for hit in outcome.hits:
        assert not (hit.via_edge and hit.via_symbol), "a passage is reached one way"


# ---------------------------------------------------------------------------
# The ablation arm
# ---------------------------------------------------------------------------


def test_the_symbol_retriever_is_the_shipped_ranking_plus_the_leg(store: SqliteStore) -> None:
    shipped = build_retriever("mycelium", store)
    arm = build_retriever("symbol", store)
    assert arm.name == "symbol"
    assert arm.config["symbol_lookup"] is True
    assert arm.config["symbol_promote"] is SYMBOL_PROMOTE
    # On this corpus, as on all three measured, the arm and the baseline agree.
    assert arm.search("RetryPolicy", 10) == shipped.search("RetryPolicy", 10)


def test_an_unknown_retriever_is_refused_by_name(store: SqliteStore) -> None:
    with pytest.raises(ValueError, match="'symbol'"):
        build_retriever("symbols", store)
