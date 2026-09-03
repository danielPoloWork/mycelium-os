# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What each query term reached (roadmap 4.21).

Ranking is silent about what it did not find: a word the corpus does not contain
contributes nothing, and a query carried by one of its five words looks exactly like a
query carried by all five. That silence cost roadmap 4.17 an afternoon and a leave-one-out
script — a judged case had been scoring 0.395 on the strength of the single word `off`,
because `signs` and `contributed` matched nothing (ADR-0044).

These tests are the end of it. They fix the three answers the report has to keep apart —
matched as written, reached only by its stem, reaches nothing at all — because since
roadmap 4.19 the index carries both forms and collapsing them would hide the very change
that made the second answer possible (ADR-0048).
"""

from collections.abc import Iterator

import pytest

from mycelium.build import build
from mycelium.retrieval import search
from mycelium.sdk.types import TrustClass
from mycelium.store import SearchFilters, SqliteStore, TermHits

CORPUS = {
    "knowledge/verified/dco.md": (
        "# Sign-off\n\nEvery commit is signed off by its author, and the signature "
        "records a contribution to the project.\n"
    ),
    "knowledge/verified/retries.md": (
        "# Retries\n\nFailed deliveries retry with exponential backoff.\n"
    ),
    "knowledge/verified/delivery.md": (
        "# Delivery\n\nA delivery is attempted once.\n\n"
        "## Failure\n\nA delivery that fails is queued again.\n"
    ),
    "knowledge/candidate/draft.md": (
        "# Draft\n\nA candidate note about contributions and escape hatches.\n"
    ),
}


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SqliteStore]:
    root = tmp_path_factory.mktemp("terms")
    for relative, text in CORPUS.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    build(root, pin_identity=False)
    with SqliteStore.open(root, read_only=True) as opened:
        yield opened


def by_term(hits: tuple[TermHits, ...]) -> dict[str, TermHits]:
    return {item.term: item for item in hits}


# ---------------------------------------------------------------------------
# The three answers, kept apart
# ---------------------------------------------------------------------------


def test_a_word_the_author_wrote_is_matched(store: SqliteStore) -> None:
    hit = by_term(store.term_hits("retry"))["retry"]
    assert hit.matched
    assert hit.documents == 1
    assert hit.chunks >= 1
    assert not hit.stem_only
    assert not hit.unmatched


def test_a_word_only_an_inflection_of_which_exists_is_reached_by_its_stem(
    store: SqliteStore,
) -> None:
    """The case roadmap 4.19 exists for, and the reason the two counts stay apart.

    The corpus says *signed* and *signature*; the query says *signs*. Before the
    stem columns that was a miss, and reporting one number would make it look
    like a hit now.
    """
    hit = by_term(store.term_hits("signs"))["signs"]
    assert hit.documents == 0, "nothing spells it that way"
    assert hit.stem_documents >= 1, "but the stemmer reaches it"
    assert hit.stem_only
    assert not hit.unmatched
    assert hit.stem == "sign"


def test_a_word_the_corpus_does_not_contain_at_all_is_unmatched(store: SqliteStore) -> None:
    hit = by_term(store.term_hits("kubernetes"))["kubernetes"]
    assert hit.documents == 0
    assert hit.stem_documents == 0
    assert hit.unmatched
    assert not hit.matched
    assert not hit.stem_only


# ---------------------------------------------------------------------------
# The shape of the report
# ---------------------------------------------------------------------------


def test_terms_come_back_in_query_order(store: SqliteStore) -> None:
    hits = store.term_hits("retry signature kubernetes")
    assert [item.term for item in hits] == ["retry", "signature", "kubernetes"]


def test_a_repeated_word_is_reported_once(store: SqliteStore) -> None:
    # A query that says a word twice is not standing on two pieces of evidence.
    assert [item.term for item in store.term_hits("retry retry")] == ["retry"]


def test_a_query_with_nothing_searchable_reports_nothing(store: SqliteStore) -> None:
    assert store.term_hits("!!! ???") == ()


def test_documents_and_chunks_are_counted_separately(store: SqliteStore) -> None:
    # `delivery` is written twice in one document, in two different sections, so
    # the two counts must disagree. One number would answer neither question:
    # "how much of the corpus is about this" and "how many passages can rank".
    hit = by_term(store.term_hits("delivery"))["delivery"]
    assert hit.documents == 1
    assert hit.chunks == 2


def test_the_report_is_taken_under_the_search_filters(store: SqliteStore) -> None:
    """Otherwise the count answers a question nobody asked.

    `contributions` is in the candidate document only. An operator whose search
    excluded candidates and got nothing needs the count to agree with the search
    they actually ran, not with the corpus in general.
    """
    unfiltered = by_term(store.term_hits("candidate"))["candidate"]
    filtered = by_term(
        store.term_hits(
            "candidate", filters=SearchFilters(trust_classes=frozenset({TrustClass.CURATED}))
        )
    )["candidate"]
    assert unfiltered.documents >= 1
    assert filtered.documents == 0


def test_as_dict_carries_the_verdicts_not_only_the_counts(store: SqliteStore) -> None:
    # A machine consumer should not have to re-derive "this matched nothing"
    # from two integers and a rule it read in our source.
    payload = by_term(store.term_hits("kubernetes"))["kubernetes"].as_dict()
    assert payload["unmatched"] is True
    assert payload["matched"] is False
    assert payload["term"] == "kubernetes"


# ---------------------------------------------------------------------------
# Through the search seam
# ---------------------------------------------------------------------------


def test_the_report_costs_nothing_unless_it_is_asked_for(store: SqliteStore) -> None:
    # The evaluation harness runs thousands of queries and measures p95; a
    # diagnostic that taxes the number it explains is a bad diagnostic.
    outcome = search(store, "signed off contribution")
    assert outcome.terms == ()
    assert "terms" not in outcome.timings_ms
    assert outcome.explain()["terms"] == []


def test_asking_for_it_populates_the_outcome_and_times_it(store: SqliteStore) -> None:
    outcome = search(store, "signed off contribution", explain=True)
    assert [item.term for item in outcome.terms] == ["signed", "off", "contribution"]
    assert "terms" in outcome.timings_ms
    assert len(outcome.explain()["terms"]) == 3  # type: ignore[arg-type]


def test_a_dead_term_becomes_a_note_on_the_outcome(store: SqliteStore) -> None:
    """The one line an operator reads even when they skim the table."""
    outcome = search(store, "kubernetes retry", explain=True)
    assert [item.term for item in outcome.dead_terms] == ["kubernetes"]
    assert any("match nothing in this corpus" in note for note in outcome.notes)
    assert any("kubernetes" in note for note in outcome.notes)


def test_a_query_whose_words_all_land_earns_no_note(store: SqliteStore) -> None:
    outcome = search(store, "retry backoff", explain=True)
    assert outcome.dead_terms == ()
    assert not any("match nothing" in note for note in outcome.notes)


def test_a_term_rescued_by_its_stem_is_not_reported_as_dead(store: SqliteStore) -> None:
    # It found the document; saying it matched nothing would be false.
    outcome = search(store, "signs", explain=True)
    assert outcome.dead_terms == ()
    assert outcome.terms[0].stem_only
