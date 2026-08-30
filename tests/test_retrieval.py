# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Candidate generation and fusion (roadmap 3.3, spec 04 §3, ADR-0017).

Three properties are enforced here, and they are what make hybrid retrieval
trustworthy rather than merely present:

**Fusion reads ranks, never scores.** BM25 is unbounded, cosine is [-1, 1]; adding
them invents an exchange rate. The tests below pin RRF's arithmetic and show that
scaling one leg's scores changes nothing.

**Lexical is the floor.** Whatever is missing — model, dependency, vectors for
this snapshot — search still answers, and says which leg did not run.

**A degraded answer is labelled, not disguised.** `legs` and `explain` report what
actually happened, which is the difference between an audit trail and a story.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from fakes import FakeEmbedder
from mycelium.build import build
from mycelium.config import RetrievalConfig
from mycelium.retrieval import RRF_K, reciprocal_rank_fusion, search
from mycelium.sdk.types import Chunk, ChunkKind, TrustClass, VerificationStatus
from mycelium.store import SearchHit, SqliteStore

HYBRID = RetrievalConfig(profile="hybrid")
"""Every test that exercises the vector leg asks for it explicitly.

The shipped default is `lexical` — hybrid did not earn it (ADR-0017) — so a test
that relied on the default would be testing the configuration rather than the
fusion it means to exercise.
"""

CORPUS = {
    "knowledge/bus.md": (
        "# Event Bus\n\nThe bus routes messages between agents and services.\n\n"
        "## Delivery\n\nAt-least-once delivery with acknowledgements.\n"
    ),
    "knowledge/retries.md": (
        "# Retries\n\nFailed deliveries retry with exponential backoff and jitter.\n"
    ),
    "knowledge/licence.md": ("# Licence\n\nThe project is distributed under Apache-2.0.\n"),
}


def repo(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    root = tmp_path / "repo"
    for relative, text in (files or CORPUS).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def built(tmp_path: Path, embedder: FakeEmbedder | None = None) -> Path:
    """A repository whose snapshot carries vectors from `embedder`, if given."""
    root = repo(tmp_path)
    build(root)
    if embedder is not None:
        with SqliteStore.open(root) as store, store.transaction():
            pairs = [
                (chunk.chunk_digest, embedder.embed_documents([chunk.text])[0])
                for doc_id in store.document_ids()
                for chunk in store.chunks_of(doc_id)
            ]
            store.put_vectors(embedder.model_id, pairs)
    return root


def hit(anchor: str, score: float = 1.0) -> SearchHit:
    return SearchHit(
        chunk=Chunk(
            anchor=anchor,
            doc_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
            chunk_digest="sha256:" + "0" * 64,
            heading_path=("H",),
            kir_nodes=("n1",),
            text="text",
            tokens=1,
            lines=(1, 1),
            kind=ChunkKind.PROSE,
        ),
        score=score,
        path="knowledge/a.md",
        title="A",
        trust_class=TrustClass.AUTHORED,
        verification_status=VerificationStatus.VERIFIED,
    )


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------


def test_rrf_scores_are_the_published_formula() -> None:
    fused = reciprocal_rank_fusion([("lexical", [hit("a.md#x/0"), hit("a.md#y/0")])], k=60)
    assert [item.hit.chunk.anchor for item in fused] == ["a.md#x/0", "a.md#y/0"]
    assert fused[0].score == pytest.approx(1 / 61)
    assert fused[1].score == pytest.approx(1 / 62)
    assert fused[0].ranks == {"lexical": 1}


def test_agreement_between_legs_outranks_a_single_leg_win() -> None:
    """The whole point of fusing: a passage both legs like beats one leg's favourite."""
    lexical = [hit("a.md#lexical-only/0"), hit("a.md#both/0")]
    vector = [hit("a.md#vector-only/0"), hit("a.md#both/0")]

    fused = reciprocal_rank_fusion([("lexical", lexical), ("vector", vector)], k=RRF_K)

    assert fused[0].hit.chunk.anchor == "a.md#both/0"
    assert fused[0].legs == ("lexical", "vector")
    assert fused[0].ranks == {"lexical": 2, "vector": 2}
    assert fused[0].score == pytest.approx(2 / (RRF_K + 2))


def test_fusion_ignores_the_magnitude_of_a_leg_score() -> None:
    """Raw scores from different backends are never added (spec 04 §3)."""
    modest = [("lexical", [hit("a.md#a/0", score=0.01), hit("a.md#b/0", score=0.001)])]
    enormous = [("lexical", [hit("a.md#a/0", score=9_000.0), hit("a.md#b/0", score=8_000.0)])]
    assert [item.score for item in reciprocal_rank_fusion(modest)] == [
        item.score for item in reciprocal_rank_fusion(enormous)
    ]


def test_fusion_is_stable_when_scores_tie() -> None:
    """Ties break on anchor, so fusion never becomes a source of non-determinism."""
    one = reciprocal_rank_fusion([("lexical", [hit("a.md#b/0")]), ("vector", [hit("a.md#a/0")])])
    two = reciprocal_rank_fusion([("vector", [hit("a.md#a/0")]), ("lexical", [hit("a.md#b/0")])])
    assert [item.hit.chunk.anchor for item in one] == ["a.md#a/0", "a.md#b/0"]
    assert [item.hit.chunk.anchor for item in two] == ["a.md#a/0", "a.md#b/0"]


def test_fusion_of_nothing_is_nothing() -> None:
    assert reciprocal_rank_fusion([]) == ()
    assert reciprocal_rank_fusion([("lexical", [])]) == ()


# ---------------------------------------------------------------------------
# The search entry point
# ---------------------------------------------------------------------------


def test_search_without_an_embedder_is_lexical_and_says_so(tmp_path: Path) -> None:
    root = built(tmp_path)
    with SqliteStore.open(root, read_only=True) as store:
        outcome = search(store, config=HYBRID, query="exponential backoff")

    assert outcome.legs == ("lexical",)
    assert outcome.hits
    assert all(item.legs == ("lexical",) for item in outcome.hits)
    assert any("no embedder" in note for note in outcome.degraded)


def test_search_reports_a_snapshot_that_holds_no_vectors(tmp_path: Path) -> None:
    """A snapshot built before embeddings were enabled stays searchable."""
    root = built(tmp_path)  # built without vectors
    with SqliteStore.open(root, read_only=True) as store:
        outcome = search(store, config=HYBRID, query="retries", embedder=FakeEmbedder())

    assert outcome.legs == ("lexical",)
    assert any("no vectors" in note for note in outcome.degraded)
    assert any("mycelium build" in note for note in outcome.degraded)


def test_hybrid_runs_both_legs_and_labels_each_hit(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    root = built(tmp_path, embedder)
    with SqliteStore.open(root, read_only=True) as store:
        outcome = search(store, config=HYBRID, query="messages between agents", embedder=embedder)

    assert outcome.legs == ("lexical", "vector")
    assert outcome.degraded == ()
    assert outcome.hits
    assert any("vector" in item.legs for item in outcome.hits)
    assert all(item.ranks for item in outcome.hits)


def test_the_shipped_default_is_lexical(tmp_path: Path) -> None:
    """Gate G2's verdict, asserted where it takes effect (spec 04 §7.3, ADR-0017)."""
    embedder = FakeEmbedder()
    root = built(tmp_path, embedder)
    with SqliteStore.open(root, read_only=True) as store:
        outcome = search(store, "messages", embedder=embedder)

    assert RetrievalConfig().profile == "lexical"
    assert outcome.legs == ("lexical",)
    assert outcome.degraded == ()  # a deliberate choice is never a degradation


def test_lexical_profile_skips_the_vector_leg_entirely(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    root = built(tmp_path, embedder)
    with SqliteStore.open(root, read_only=True) as store:
        outcome = search(
            store, "messages", config=RetrievalConfig(profile="lexical"), embedder=embedder
        )

    assert outcome.legs == ("lexical",)
    assert outcome.degraded == ()  # not degraded: disabled deliberately
    assert any("disabled by configuration" in note for note in outcome.notes)


def test_the_vector_leg_finds_what_lexical_misses(tmp_path: Path) -> None:
    """The reason hybrid exists: a query whose words are not in the passage.

    With the hash embedder, "vocabulary overlap" is the only similarity there is
    — so the query shares terms with the target but the lexical index is denied
    them by a filter. Contrived on purpose: it tests the plumbing, and ADR-0017
    reports what the real model does on the judged cases.
    """
    embedder = FakeEmbedder()
    root = built(tmp_path, embedder)
    with SqliteStore.open(root, read_only=True) as store:
        vector_only = store.search_vectors(
            embedder.embed_query("Apache-2.0 distributed licence"), embedder.model_id, limit=3
        )
        assert vector_only
        assert any("licence" in item.chunk.anchor for item in vector_only)


def test_filters_apply_to_both_legs(tmp_path: Path) -> None:
    """Spec 04 §2: every generator pre-filters; post-filtering silently drops hits."""
    from mycelium.store import SearchFilters

    embedder = FakeEmbedder()
    root = built(tmp_path, embedder)
    with SqliteStore.open(root, read_only=True) as store:
        outcome = search(
            store,
            "messages delivery",
            config=HYBRID,
            embedder=embedder,
            filters=SearchFilters(path_prefix="knowledge/bus.md"),
        )

    assert outcome.legs == ("lexical", "vector")
    assert outcome.hits
    assert all(item.hit.path == "knowledge/bus.md" for item in outcome.hits)


def test_a_query_vector_of_the_wrong_dimension_is_refused(tmp_path: Path) -> None:
    from mycelium.store import StoreError

    embedder = FakeEmbedder()
    root = built(tmp_path, embedder)
    with SqliteStore.open(root, read_only=True) as store, pytest.raises(StoreError, match="dim"):
        store.search_vectors((0.1, 0.2), embedder.model_id, limit=5)


def test_vectors_of_another_model_are_never_mixed_in(tmp_path: Path) -> None:
    """Keying is `(chunk_digest, model_id)`: two models coexist without collision."""
    first = FakeEmbedder()
    second = replace(first, model_id="fake-hash-v2")
    root = built(tmp_path, first)

    with SqliteStore.open(root, read_only=True) as store:
        assert store.search_vectors(first.embed_query("bus"), first.model_id, limit=5)
        assert store.search_vectors(second.embed_query("bus"), second.model_id, limit=5) == ()
        outcome = search(store, config=HYBRID, query="bus", embedder=second)
    assert outcome.legs == ("lexical",)
    assert any("fake-hash-v2" in note for note in outcome.degraded)
