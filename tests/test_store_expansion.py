# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The stem-expanded lexical index (roadmap 4.19, ADR-0048; 4.23, ADR-0054).

Three properties, and they are the three the item was filed for:

**Reach, once a query has a foothold.** A query that inflects a word differently from the
document finds it — `release signs` reaches a document that says `release signed`, which
`unicode61` alone cannot do. Since roadmap 4.23 that reach extends to a document sharing
*only* a stem with the query, which the old expression excluded from the candidate set.

**The literal edge.** A document spelling the query's word exactly outranks one that only
inflects it, because it matches a surface column *and* a stem column while the other
matches the stem column alone. This is what a `porter` tokenizer gives up, and giving it
up costs the `exact` slice.

**Abstention.** A query none of whose words the corpus contains as written gets silence.
Porter conflates `escapement` with `escape`, so without that gate a query about watchmaking
answers out of a corpus with no watchmaking in it — which gate G4 counts as a false answer,
correctly.

ADR-0048 enforced the third property with a clause inside the MATCH expression, and that
clause held a second rule with it: every *candidate document* also had to carry a surface
hit. Roadmap 4.23 separated them — the gate is one `LIMIT 1` probe of the corpus, and the
search that follows is open — because only the first rule bought the safety while the
second cost reach. :func:`test_a_query_with_no_literal_foothold_still_misses` is still the
bound, and it is deliberate rather than incidental: nothing in the index distinguishes such
a query from one about something the corpus does not hold.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from mycelium.store import SqliteStore, expanded_query, foothold_query
from mycelium.store.schema import SCHEMA_VERSION
from mycelium.store.stemming import stem
from test_store import make_chunk, make_document, seed


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteStore]:
    with SqliteStore.open(tmp_path) as opened:
        yield opened


def anchors(store: SqliteStore, query: str) -> list[str]:
    return [hit.chunk.anchor for hit in store.search_chunks(query, limit=10)]


# ---------------------------------------------------------------------------
# Reach
# ---------------------------------------------------------------------------


def test_an_inflected_query_reaches_a_differently_inflected_document(
    store: SqliteStore,
) -> None:
    seed(
        store,
        make_chunk("d.md#a/0", "The maintainer signed off on the contribution."),
        document=make_document(),
    )
    # `maintainer` is the foothold; `signs` and `contributed` appear nowhere as
    # the query spells them. Before roadmap 4.19 the inflected words contributed
    # nothing to the ranking — the mechanism ADR-0044 traced one judged case's
    # collapse to, where a query reached its answer through one unrelated word.
    assert anchors(store, "maintainer signs") == ["d.md#a/0"]
    assert anchors(store, "maintainer contributed") == ["d.md#a/0"]


def test_a_query_with_no_literal_foothold_still_misses(store: SqliteStore) -> None:
    """The bound on the reach, stated as a test rather than as a caveat.

    Nothing in the query is spelled the way the corpus spells it, so the foothold
    gate closes and the stems never speak — and a query like this is
    indistinguishable from one about something the corpus simply does not hold,
    which is the watchmaking case below. Silence is the same answer to both, and
    it is the right answer to only one of them. Roadmap 4.23 measured what
    lifting it would cost and kept it: nothing in the index tells the two apart,
    and G4 is what pays when a retriever guesses (ADR-0054).
    """
    seed(
        store,
        make_chunk("d.md#a/0", "The maintainer signed off on the contribution."),
        document=make_document(),
    )
    assert anchors(store, "signs") == []
    assert anchors(store, "signs contributed") == []


def test_a_document_sharing_only_a_stem_is_now_reachable(store: SqliteStore) -> None:
    """The reach roadmap 4.23 bought, and the only thing that actually changed.

    `maintainer` is the query's foothold and it appears in one chunk only. The
    other shares nothing with the query as written — `signs` against `signed` —
    so ADR-0048's expression excluded it from the candidate set entirely. It is a
    candidate now, and it still ranks below the literal match.
    """
    seed(
        store,
        make_chunk("foothold.md#a/0", "The maintainer approved the release."),
        make_chunk("stem-only.md#a/0", "Contributions are signed by their authors."),
        document=make_document(),
    )
    found = anchors(store, "maintainer signs")
    assert set(found) == {"foothold.md#a/0", "stem-only.md#a/0"}
    assert found[0] == "foothold.md#a/0", "the literal foothold still leads"


def test_the_surface_form_still_matches_itself(store: SqliteStore) -> None:
    seed(
        store,
        make_chunk("d.md#a/0", "The maintainer signed off on the contribution."),
        document=make_document(),
    )
    assert anchors(store, "signed") == ["d.md#a/0"]
    assert anchors(store, "contribution") == ["d.md#a/0"]


def test_a_word_sharing_no_stem_still_misses(store: SqliteStore) -> None:
    seed(store, make_chunk("d.md#a/0", "Exponential backoff."), document=make_document())
    assert anchors(store, "tourbillon") == []


# ---------------------------------------------------------------------------
# The literal edge
# ---------------------------------------------------------------------------


def test_a_literal_match_outranks_an_inflection_only_match(store: SqliteStore) -> None:
    """The whole reason the surface columns stay (ADR-0048).

    Both documents are about signing and one uses the query's exact word. Under a
    `porter` tokenizer the two would be indistinguishable — both reduce to the
    same token — and the slice that pays for that is `exact`.
    """
    seed(
        store,
        make_chunk("literal.md#a/0", "A maintainer signs the release."),
        make_chunk("inflected.md#a/0", "A maintainer signed the release."),
        document=make_document(),
    )
    # `maintainer` is the foothold both share, so both are candidates and the
    # question is only which comes first.
    assert anchors(store, "maintainer signs") == ["literal.md#a/0", "inflected.md#a/0"]


def test_the_stem_side_cannot_outrank_a_surface_hit_on_its_own(store: SqliteStore) -> None:
    """The stem weight is an order of magnitude below the weakest surface field.

    The document that merely inflects the word repeats it ten times; the one that
    spells it exactly says it once. The surface hit still wins, which is the
    property that keeps `conceptual` from paying for the stems — ADR-0048
    measured the cliff at a stem weight of 0.35.
    """
    seed(
        store,
        make_chunk("literal.md#a/0", "Maintainer signs."),
        make_chunk(
            "inflected.md#a/0",
            "Maintainer signed signed signed signed signed signed signed signed signed.",
        ),
        document=make_document(),
    )
    assert anchors(store, "maintainer signs")[0] == "literal.md#a/0"


# ---------------------------------------------------------------------------
# Abstention — the precondition
# ---------------------------------------------------------------------------


def test_a_stem_alone_never_introduces_a_document(store: SqliteStore) -> None:
    """Gate G4's regression test.

    `escapement` and `escape hatch` share the Porter stem `escap`. This corpus
    has no watchmaking in it, so the honest answer to a watchmaking query is
    silence — and silence is exactly what G4 measures, since a retriever abstains
    by returning nothing.
    """
    seed(
        store,
        make_chunk("d.md#a/0", "`mycelium build --clean` is the escape hatch."),
        document=make_document(),
    )
    assert stem("escapement") == stem("escape") == "escap", "the conflation is real"
    assert anchors(store, "escapement tourbillon mainspring") == []
    # …and the surface word still reaches it, so the precondition removed the
    # false answer without removing the document.
    assert anchors(store, "escape") == ["d.md#a/0"]


def test_one_surface_hit_is_enough_to_let_the_stems_speak(store: SqliteStore) -> None:
    seed(
        store,
        make_chunk("both.md#a/0", "The build signed the manifest."),
        make_chunk("surface.md#a/0", "The build published a manifest."),
        document=make_document(),
    )
    # `build` is literal in both; `signs` reaches only the first, through its stem.
    found = anchors(store, "build signs")
    assert found[0] == "both.md#a/0"
    assert set(found) == {"both.md#a/0", "surface.md#a/0"}


# ---------------------------------------------------------------------------
# The expression, and the schema behind it
# ---------------------------------------------------------------------------


def test_the_expression_is_open_and_the_gate_is_a_separate_query() -> None:
    """Roadmap 4.23. The two rules ADR-0048's single expression held are now apart.

    The expression asks "does this document match, literally or by stem"; the gate
    asks, once and of the whole corpus, "does this query have any literal footing
    here". Holding both in one clause made the second imply a third nobody wanted
    — that every candidate carry a surface hit — which cost reach and bought no
    safety (ADR-0054).
    """
    match = expanded_query("signs off")
    assert match.startswith("{text title heading_path} : ")
    assert " AND " not in match, "the surface side is an alternative, not a filter"
    assert '"sign"' in match
    assert '"signs"' in match

    gate = foothold_query("signs off")
    assert gate == '{text title heading_path} : ("signs" OR "off")'
    assert "text_stem" not in gate, "a stem cannot authorise its own expansion"


def test_the_gate_asks_about_the_corpus_not_about_one_document() -> None:
    # Even for a caller that wants conjunction, the foothold question stays
    # disjunctive: "did the author write any of these words" is what abstention
    # needs, and "all of them, in one chunk" is the search's own question.
    assert foothold_query("signs contributed") == (
        '{text title heading_path} : ("signs" OR "contributed")'
    )
    assert foothold_query("   ") == ""


def test_a_prefix_query_is_not_stemmed() -> None:
    # `sign*` already reaches signs, signed and signature; stemming it would add
    # candidates the caller did not ask for.
    assert expanded_query("sign", prefix=True) == '"sign"*'
    assert "text_stem" not in expanded_query("sign", prefix=True)


def test_match_all_conjoins_within_each_side() -> None:
    match = expanded_query("signs contributed", match_all=True)
    assert '"signs" "contributed"' in match
    assert '"sign" "contribut"' in match


def test_an_empty_query_expands_to_nothing() -> None:
    assert expanded_query("   ") == ""
    assert expanded_query("!!!") == ""


def test_two_query_words_sharing_a_stem_are_stated_once() -> None:
    # Determinism: the same query must build the same expression, and a set would
    # not promise that.
    assert expanded_query("signs signed signing").count('"sign"') == 1


def test_the_schema_version_records_the_new_index(store: SqliteStore) -> None:
    assert SCHEMA_VERSION == "mycelium/store/v4"
    columns = {
        row[1] for row in store._connection.execute("PRAGMA table_info(chunks_fts)").fetchall()
    }
    assert {"text", "title", "heading_path"} <= columns
    assert {"text_stem", "title_stem", "heading_path_stem"} <= columns


def test_the_stem_columns_are_populated_from_the_chunk(store: SqliteStore) -> None:
    seed(
        store,
        make_chunk("d.md#a/0", "The maintainer signed the contribution."),
        document=make_document(),
    )
    row = store._connection.execute(
        "SELECT text, text_stem FROM chunks_fts WHERE anchor = ?", ("d.md#a/0",)
    ).fetchone()
    assert "signed" in row["text"]
    assert "sign" in row["text_stem"].split()
    assert "signed" not in row["text_stem"].split()
