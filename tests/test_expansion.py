# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Graph expansion (roadmap 5.3, spec 04 §5, ADR-0075).

The claims under test, in the order they matter:

**Off by default, and the default is the ablation's verdict.** The gate decides
this setting, so a change that flips it without re-running the measurement is
the one mistake this file exists to catch.

**Expansion adds; it never promotes.** A passage the lexical leg already
returned keeps the rank the ranking gave it. The first implementation let both
contributions sum and a passage at lexical rank 40 leapfrogged rank 1 — the
defect that cost up to 56 % overall before it was found.

**The budget is spent breadth-first across seeds.** One densely linked seed may
not fill it, because the seeds that reach an answer are often not the first one.

**Every proposed passage earns its rank against the same BM25** as everything
else, is labelled with the edge that reached it, and is refused by the serving
policy exactly as a directly retrieved one would be.

Since roadmap 5.11 the leg is *routed*: `[retrieval] graph_expansion` permits it
and spec 04 §2's relationship rule decides whether a given query gets it. The
query these tests use carries no relationship phrasing, so they ask for the leg
the way a caller does — `related=True`, which is `mycelium search --related`.
What is under test here is the mechanism; the routing is
`tests/test_planner.py`.
"""

from collections.abc import Mapping
from pathlib import Path

import pytest

from mycelium.build import build
from mycelium.config import RetrievalConfig
from mycelium.graph import nodes_of_anchor
from mycelium.retrieval import (
    GRAPH_DISCOUNT,
    GRAPH_NODES,
    GRAPH_SEEDS,
    RRF_K,
    retrieval_identity,
    search,
)
from mycelium.store import SearchFilters, SqliteStore

FILLER = 70
"""How many also-ran documents the corpus carries.

Not padding. Expansion adds only passages the other legs did not return, and the
lexical leg is :data:`~mycelium.retrieval.VECTOR_CANDIDATES` deep, so on a corpus
of five chunks the ranking already holds everything and the graph has nothing
left to contribute. That is a real property of the mechanism — it reaches past
the depth the ranking stops at, and nowhere else (ADR-0075) — and a fixture
smaller than that depth would test a configuration the product never meets."""

QUERY = "ferret"


def corpus() -> dict[str, str]:
    """A hub that ranks, a neighbour one link away that ranks too low to be seen,
    a look-alike linked to nothing, and enough competition to bury both."""
    files = {
        # Says the word often, so it ranks near the top and becomes a seed.
        "knowledge/hub.md": (
            "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5H01\n---\n\n"
            "# Ferret husbandry\n\nFerret, ferret, ferret. A ferret needs company, "
            "and a ferret needs room. See [[neighbour]].\n"
        ),
        # Says it once, in a long paragraph, so it sits far below the depth the
        # lexical leg stops at — reachable only through the link from the hub.
        "knowledge/neighbour.md": (
            "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5H02\n---\n\n"
            "# Enrichment\n\nA tunnel keeps one busy for hours, and so does a ball "
            "pit, a paper bag, a cardboard box, a length of drainpipe, a knotted "
            "towel, a hammock, a digging tray, a wobble board and a foraging mat. "
            "One ferret is mentioned here.\n"
        ),
        # The same words, linked to nothing: a hit here would mean the index
        # found it rather than the walk.
        "knowledge/stranger.md": (
            "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5H03\n---\n\n"
            "# Unrelated\n\nA tunnel keeps one busy for hours, and so does a ball "
            "pit, a paper bag, a cardboard box, a length of drainpipe, a knotted "
            "towel, a hammock, a digging tray, a wobble board and a foraging mat. "
            "One ferret is mentioned here too.\n"
        ),
    }
    for index in range(FILLER):
        files[f"knowledge/filler{index:02d}.md"] = (
            f"---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5F{index:02d}\n---\n\n"
            f"# Note {index}\n\nFerret care note {index}. A ferret is a ferret.\n"
        )
    return files


def repo(tmp_path: Path, files: Mapping[str, str] | None = None, name: str = "repo") -> Path:
    root = tmp_path / name
    for relative, text in (files or corpus()).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    build(root)
    return root


def anchors(outcome: object) -> list[str]:
    return [hit.hit.chunk.anchor for hit in outcome.hits]  # type: ignore[attr-defined]


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    """Built once: seventy-three documents is a second, and every test that uses
    it only reads."""
    root = repo(tmp_path_factory.mktemp("expansion"))
    with SqliteStore.open(root, read_only=True) as opened:
        yield opened


# ---------------------------------------------------------------------------
# The default is the ablation's verdict
# ---------------------------------------------------------------------------


def test_expansion_is_off_by_default_because_the_ablation_said_so() -> None:
    """Spec 04 §5 decides this setting by measurement, not by preference.

    Roadmap 5.3 ran the ablation on six case sets and expansion cleared the bar
    on none. Flipping this without re-running `tools/measure_graph_expansion.py`
    would ship a default no measurement supports, which is what the tool's
    `--check` refuses and what this asserts in the suite.
    """
    assert RetrievalConfig().graph_expansion is False


def test_the_constants_are_the_ones_the_ablation_was_run_at() -> None:
    """A verdict is about the configuration it was measured under (ADR-0064).

    ADR-0075 reports one ablation at these three values. Changing one without
    re-measuring detaches the recorded numbers from the code they describe.
    """
    assert (GRAPH_SEEDS, GRAPH_NODES, GRAPH_DISCOUNT) == (10, 10, 0.9)


def test_the_discount_sits_inside_the_window_rrf_leaves_it() -> None:
    """The arithmetic ADR-0075 derives, asserted rather than described.

    Below ``1/70 * 61`` a graph-only passage cannot reach a ten-deep window at
    all and the leg is inert; at 1.0 it ties the best direct hit. The shipped
    value has to be strictly inside, or the mechanism is either invisible or
    unfair to the ranking.
    """
    inert_at_or_below = 61 / 70
    assert inert_at_or_below < GRAPH_DISCOUNT < 1.0
    # The leg's best is worth less than the lexical leg's best...
    assert GRAPH_DISCOUNT / (RRF_K + 1) < 1 / (RRF_K + 1)
    # ...and more than its tenth, or it could never change an answer.
    assert GRAPH_DISCOUNT / (RRF_K + 1) > 1 / (RRF_K + 10)


def test_the_graph_constants_are_part_of_the_retrieval_fingerprint() -> None:
    """They decide a ranking, so a verdict measured under one set is not about
    another — the rule `retrieval_identity` states about itself (ADR-0064)."""
    import mycelium.retrieval as module

    before = retrieval_identity()
    original = module.GRAPH_DISCOUNT
    try:
        module.GRAPH_DISCOUNT = 0.5  # type: ignore[misc]
        assert retrieval_identity() != before
    finally:
        module.GRAPH_DISCOUNT = original  # type: ignore[misc]
    assert retrieval_identity() == before


# ---------------------------------------------------------------------------
# What the leg does
# ---------------------------------------------------------------------------


def test_expansion_reaches_a_passage_the_ranking_buried(store: SqliteStore) -> None:
    """The whole mechanism, on the shape it exists for: the answer is one link
    from a strong hit and too far down the ranking to be served."""
    plain = search(store, QUERY, limit=10, config=RetrievalConfig())
    expanded = search(
        store, QUERY, limit=10, config=RetrievalConfig(graph_expansion=True), related=True
    )

    reached = set(anchors(expanded)) - set(anchors(plain))
    assert reached, "expansion added nothing"
    assert any(anchor.startswith("knowledge/neighbour.md") for anchor in reached)
    # `stranger.md` says much the same thing and is linked to nothing, so
    # reaching it would mean the result came from the index and not the walk.
    assert not any(anchor.startswith("knowledge/stranger.md") for anchor in reached)


def test_every_expanded_passage_is_labelled_with_the_edge_that_reached_it(
    store: SqliteStore,
) -> None:
    """Spec 04 §5 requires the `via_edge` label, and `--explain` renders it."""
    outcome = search(
        store, QUERY, limit=10, config=RetrievalConfig(graph_expansion=True), related=True
    )
    labelled = [hit for hit in outcome.hits if hit.via_edge]
    assert labelled
    for hit in labelled:
        assert " from " in hit.via_edge
        assert hit.explain()["via_edge"] == hit.via_edge
        assert "graph" in hit.legs
    # A directly retrieved passage carries no label and no key.
    direct = [hit for hit in outcome.hits if not hit.via_edge]
    assert direct and all("via_edge" not in hit.explain() for hit in direct)


def test_expansion_adds_and_never_promotes(store: SqliteStore) -> None:
    """The defect that cost up to 56 % overall: a passage the lexical leg
    already ranked must not also vote in the graph leg (ADR-0075)."""
    plain = search(store, QUERY, limit=50, config=RetrievalConfig())
    expanded = search(
        store, QUERY, limit=50, config=RetrievalConfig(graph_expansion=True), related=True
    )

    already = set(anchors(plain))
    for hit in expanded.hits:
        if hit.via_edge:
            assert hit.hit.chunk.anchor not in already, (
                "a passage the ranking already found was voted for twice"
            )
    # And the *order* of what was already found is untouched. Not the set: a
    # window is a fixed size, so what expansion adds at the top displaces the
    # tail — but nothing directly retrieved may overtake anything else.
    kept = [anchor for anchor in anchors(expanded) if anchor in already]
    before = [anchor for anchor in anchors(plain) if anchor in already]
    assert kept == [anchor for anchor in before if anchor in set(kept)]


def test_the_budget_is_spread_across_seeds_not_spent_on_the_first(tmp_path: Path) -> None:
    """A hub that links to more documents than the budget must not consume it.

    The measurement that forced this: on `r-0018` the top hit linked to a dozen
    ADRs and filled all ten places, so the seeds at ranks 3 and 4 — the two that
    reach the answer — proposed nothing (ADR-0075).
    """
    files = corpus()
    # The hub now links to a dozen documents of its own, so a depth-first budget
    # would be exhausted by it before any other seed proposed anything.
    files["knowledge/hub.md"] = (
        files["knowledge/hub.md"].rstrip("\n")
        + " "
        + " ".join(f"[[filler{index:02d}]]" for index in range(12))
        + "\n"
    )
    # A second strong hit, one link from a passage buried as deep as the first.
    files["knowledge/second.md"] = (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5H11\n---\n\n"
        "# Ferret feeding\n\nFerret, ferret, ferret. Feeding a ferret is a ferret "
        "question. See [[answer]].\n"
    )
    files["knowledge/answer.md"] = (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5H12\n---\n\n"
        "# Whole prey\n\nA rabbit, a chick, a mouse, a quail, a rat, a pigeon, a "
        "gerbil, a hamster and a vole are all eaten entire. One ferret eats them.\n"
    )
    with SqliteStore.open(repo(tmp_path, files), read_only=True) as store:
        outcome = search(
            store, QUERY, limit=10, config=RetrievalConfig(graph_expansion=True), related=True
        )

    # `answer.md` is reachable only from `second.md`, which is never the first
    # seed. Depth-first through the hub's twelve links would exhaust the budget
    # before reaching it, so its presence is the round-robin working.
    reached = {hit.hit.chunk.anchor: hit.via_edge for hit in outcome.hits if hit.via_edge}
    assert any("answer.md" in anchor for anchor in reached), (
        f"the budget never reached a later seed; proposals were {reached}"
    )
    assert all("second.md" in via for anchor, via in reached.items() if "answer.md" in anchor)


def test_a_proposed_passage_that_matches_nothing_is_dropped(tmp_path: Path) -> None:
    """The graph proposes and BM25 disposes: adjacency alone is not evidence."""
    files = corpus()
    files["knowledge/hub.md"] = files["knowledge/hub.md"].replace("[[neighbour]]", "[[silent]]")
    del files["knowledge/neighbour.md"]
    files["knowledge/silent.md"] = (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5H21\n---\n\n"
        "# Bridges\n\nSuspension spans and their cables.\n"
    )
    with SqliteStore.open(repo(tmp_path, files), read_only=True) as store:
        outcome = search(
            store, QUERY, limit=10, config=RetrievalConfig(graph_expansion=True), related=True
        )
    assert not any("silent.md" in anchor for anchor in anchors(outcome))


def test_expansion_respects_the_serving_policy(tmp_path: Path) -> None:
    """A passage the configuration would not serve may not arrive through the
    graph either — the one seam ADR-0024 puts the rule at."""
    files = corpus()
    files["knowledge/candidate/neighbour.md"] = files.pop("knowledge/neighbour.md")
    with SqliteStore.open(repo(tmp_path, files), read_only=True) as store:
        served = search(
            store, QUERY, limit=10, config=RetrievalConfig(graph_expansion=True), related=True
        )
        withheld = search(
            store,
            QUERY,
            limit=10,
            config=RetrievalConfig(graph_expansion=True, include_candidate=False),
            related=True,
        )
    assert any("candidate/neighbour.md" in anchor for anchor in anchors(served))
    assert not any("candidate/neighbour.md" in anchor for anchor in anchors(withheld))


def test_the_leg_is_reported_in_timings_and_notes(store: SqliteStore) -> None:
    """`mycelium_explain` promises per-stage timings (spec 05 §3.4), and the
    graph leg is budgeted at 30 ms by spec 04 §5 — so it has to be visible."""
    outcome = search(
        store, QUERY, limit=10, config=RetrievalConfig(graph_expansion=True), related=True
    )
    assert "graph" in outcome.timings_ms
    assert "graph" in outcome.legs
    assert any(note.startswith("graph leg:") for note in outcome.notes)


def test_a_query_the_corpus_cannot_answer_opens_no_door(store: SqliteStore) -> None:
    """Expansion runs on fused candidates, so a query with none expands nothing:
    abstention survives the extra leg (ADR-0025's precondition, one level up)."""
    outcome = search(
        store, "quantum chromodynamics", limit=10, config=RetrievalConfig(graph_expansion=True)
    )
    assert outcome.hits == ()
    assert "graph" not in outcome.legs


def test_expansion_is_deterministic(store: SqliteStore) -> None:
    config = RetrievalConfig(graph_expansion=True)
    first = search(store, QUERY, limit=10, config=config)
    second = search(store, QUERY, limit=10, config=config)
    assert anchors(first) == anchors(second)
    assert [hit.via_edge for hit in first.hits] == [hit.via_edge for hit in second.hits]


# ---------------------------------------------------------------------------
# The pieces underneath
# ---------------------------------------------------------------------------


def test_a_chunk_reaches_the_graph_through_its_section_and_its_document() -> None:
    assert nodes_of_anchor("docs/a.md#retries/2") == ("doc:docs/a.md#retries", "doc:docs/a.md")
    # A preamble chunk has no heading, so the document is its only node.
    assert nodes_of_anchor("docs/a.md#/0") == ("doc:docs/a.md",)
    assert nodes_of_anchor("") == ()


def test_rank_anchors_scores_only_what_it_is_given(store: SqliteStore) -> None:
    every = [chunk.anchor for doc_id in store.document_ids() for chunk in store.chunks_of(doc_id)]
    mustelid = [anchor for anchor in every if "neighbour.md" in anchor]
    ranked = store.rank_anchors(QUERY, mustelid, limit=len(mustelid))
    assert ranked and all(hit.chunk.anchor in mustelid for hit in ranked)
    # Descending, like every other candidate generator.
    assert [hit.score for hit in ranked] == sorted((hit.score for hit in ranked), reverse=True)
    # A word the named chunks do not contain returns nothing rather than
    # abstaining loudly: an empty proposal is the expected outcome.
    assert store.rank_anchors("chromodynamics", mustelid) == ()
    assert store.rank_anchors(QUERY, []) == ()


def test_anchors_of_paths_groups_by_document(store: SqliteStore) -> None:
    grouped = store.anchors_of_paths(["knowledge/hub.md", "knowledge/absent.md"])
    assert set(grouped) == {"knowledge/hub.md"}
    assert all(anchor.startswith("knowledge/hub.md#") for anchor in grouped["knowledge/hub.md"])
    assert store.anchors_of_paths([]) == {}


def test_fusion_weights_scale_one_leg(store: SqliteStore) -> None:
    """The discount is applied in fusion, so it is testable there rather than
    only through its effect on a corpus."""
    from mycelium.retrieval import reciprocal_rank_fusion

    hits = store.search_chunks(QUERY, limit=5)
    assert len(hits) >= 2
    full = reciprocal_rank_fusion([("a", hits)], k=RRF_K, limit=5)
    halved = reciprocal_rank_fusion([("a", hits)], k=RRF_K, limit=5, weights={"a": 0.5})
    assert [hit.score for hit in halved] == pytest.approx([hit.score * 0.5 for hit in full])
    # An unnamed leg is unscaled.
    assert reciprocal_rank_fusion([("a", hits)], k=RRF_K, limit=5, weights={"b": 0.1}) == full


def test_a_filtered_search_still_expands(store: SqliteStore) -> None:
    """Expansion composes with filters rather than bypassing or defeating them."""
    outcome = search(
        store,
        QUERY,
        limit=10,
        config=RetrievalConfig(graph_expansion=True),
        related=True,
        filters=SearchFilters(path_prefix="knowledge/"),
    )
    assert all(anchor.startswith("knowledge/") for anchor in anchors(outcome))
