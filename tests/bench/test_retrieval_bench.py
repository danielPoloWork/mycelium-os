# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Retrieval benchmarks (roadmap 3.3, ADR-0017).

The claim these back is the one that chose an exact scan over sqlite-vec: inside
the v1 corpus envelope (10²–10⁵ chunks, D-002), brute-force cosine meets spec
04 §1's candidate-generation budget of 60 ms, so a loadable SQLite extension —
unavailable in stock Python builds on a supported platform — is not worth its
portability cost yet.

That claim was **false when ADR-0017 made it** and is true now. The scan cost
92 ms over 10 000 chunks against the 60 ms budget, and ADR-0026 found the cost
was never the arithmetic: 79 of those milliseconds were reading vectors out of
SQLite row by row and joining their blobs, and 10 more were ranking the scores in
Python. Against the packed matrix the same query is **2.9 ms**, and a fresh
process — what a CLI invocation is — pays 23 ms including opening the store,
against 108 ms before.

The committed size is 10 000 chunks, which keeps the benchmark job quick. The
scan is linear in the corpus, so the reference profile is a multiplication: the
packed matrix at 100 000 chunks measures ~70 ms for the first query in a fresh
process and ~1 ms for every query after it, which is the honest limit ADR-0026
records rather than a budget it claims to meet.

Fusion is measured separately because it is pure arithmetic over rank lists: if
it ever shows up next to the scan, something has gone wrong with it.
"""

import random
import struct
import time
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from mycelium.retrieval import (
    MAX_QUERY_TERMS,
    RRF_K,
    VECTOR_CANDIDATES,
    bound_query,
    query_terms,
    reciprocal_rank_fusion,
    search,
)
from mycelium.sdk.types import (
    Chunk,
    ChunkKind,
    Document,
    DocumentStats,
    Provenance,
    ProvenanceOrigin,
    TrustClass,
    VerificationStatus,
)
from mycelium.store import SearchHit, SqliteStore

DIM = 384
CHUNKS = 10_000
PER_DOC = 100
MODEL_ID = "bench-model"
CANDIDATE_BUDGET_MS = 60
"""Spec 04 §1's candidate-generation budget."""


def _unit(rng: random.Random) -> tuple[float, ...]:
    values = [rng.gauss(0.0, 1.0) for _ in range(DIM)]
    norm = sum(value * value for value in values) ** 0.5
    return tuple(value / norm for value in values)


@pytest.fixture(scope="module")
def vector_store(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SqliteStore]:
    """A store holding `CHUNKS` chunks and one vector each."""
    root = tmp_path_factory.mktemp("bench-vectors")
    rng = random.Random(20260830)
    now = datetime.now(tz=UTC)

    with SqliteStore.open(root) as writer, writer.transaction():
        for doc_index in range(CHUNKS // PER_DOC):
            doc_id = f"01ARZ3NDEKTSV4RRFFQ69G{doc_index:04d}"[:26]
            writer.put_document(
                Document(
                    doc_id=doc_id,
                    path=f"knowledge/doc-{doc_index}.md",
                    title=f"Document {doc_index}",
                    content_digest="sha256:" + "0" * 64,
                    trust_class=TrustClass.AUTHORED,
                    verification_status=VerificationStatus.VERIFIED,
                    provenance=Provenance(origin=ProvenanceOrigin.AUTHORED),
                    stats=DocumentStats(tokens=1, headings=1, chunks=PER_DOC, links_out=0),
                    created_at=now,
                    updated_at=now,
                )
            )
            writer.put_chunks(
                Chunk(
                    anchor=f"knowledge/doc-{doc_index}.md#section/{index}",
                    doc_id=doc_id,
                    chunk_digest=f"sha256:{doc_index:032d}{index:032d}",
                    heading_path=("Section",),
                    kir_nodes=("n1",),
                    text=f"passage {doc_index}-{index} about compilers and retrieval",
                    tokens=10,
                    lines=(1, 2),
                    kind=ChunkKind.PROSE,
                )
                for index in range(PER_DOC)
            )
            writer.put_vectors(
                MODEL_ID,
                ((f"sha256:{doc_index:032d}{index:032d}", _unit(rng)) for index in range(PER_DOC)),
            )

    store = SqliteStore.open(root, read_only=True)
    yield store
    store.close()


def test_vector_scan_over_10k_chunks(
    vector_store: SqliteStore, benchmark: BenchmarkFixture
) -> None:
    query = _unit(random.Random(1))
    vector_store.search_vectors(query, MODEL_ID, limit=VECTOR_CANDIDATES)  # warm the cache
    benchmark(vector_store.search_vectors, query, MODEL_ID, limit=VECTOR_CANDIDATES)


def test_the_packed_matrix_is_the_one_being_measured(vector_store: SqliteStore) -> None:
    """Not a benchmark: without this, a silent fallback to the SQL scan would
    show up as a slow machine rather than as a broken pack (ADR-0026)."""
    assert vector_store._pack_for(MODEL_ID) is not None


def test_the_vector_scan_meets_the_candidate_budget(vector_store: SqliteStore) -> None:
    """The budget spec 04 §1 sets, asserted rather than described.

    Deliberately generous against the measured 2.9 ms: this guards the
    *representation* — a regression to row-by-row reading costs 30x and would
    blow through it — not the machine it runs on.
    """
    query = _unit(random.Random(2))
    vector_store.search_vectors(query, MODEL_ID, limit=VECTOR_CANDIDATES)  # map the pack
    started = time.perf_counter()
    vector_store.search_vectors(query, MODEL_ID, limit=VECTOR_CANDIDATES)
    assert (time.perf_counter() - started) * 1000 < CANDIDATE_BUDGET_MS


def test_lexical_search_over_10k_chunks(
    vector_store: SqliteStore, benchmark: BenchmarkFixture
) -> None:
    """The other leg, at the same scale — the comparison that matters."""
    benchmark(vector_store.search_chunks, "compilers retrieval", limit=VECTOR_CANDIDATES)


def test_rank_fusion_of_two_full_candidate_lists(benchmark: BenchmarkFixture) -> None:
    def hit(anchor: str) -> SearchHit:
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
            score=1.0,
            path="knowledge/a.md",
            title="A",
            trust_class=TrustClass.AUTHORED,
            verification_status=VerificationStatus.VERIFIED,
        )

    lexical = [hit(f"a.md#s/{index}") for index in range(VECTOR_CANDIDATES)]
    vector = [hit(f"a.md#s/{index}") for index in range(VECTOR_CANDIDATES // 2, 150)]
    benchmark(reciprocal_rank_fusion, [("lexical", lexical), ("vector", vector)], k=RRF_K)


def test_a_pasted_document_costs_what_a_question_costs(
    vector_store: SqliteStore, benchmark: BenchmarkFixture
) -> None:
    """The claim roadmap 6.17 makes: the server's cost is a function of the corpus,
    not of what a caller pasted.

    Before the bound, the lexical leg cost 3-4 ms a term with nothing above it —
    this repository's own README as a query held the server for **146 s** (62 KB,
    7 384 terms), `AGENTS.md` for 25 s, and a 9 KB page for 5 s. Bounded, all three
    cost ~94 ms, which is what a normal question costs on that corpus.

    What is benchmarked is `search`, the path a caller reaches — not
    `search_chunks`, the unbounded primitive underneath it. That distinction is
    the whole subject: the same document through the primitive is what used to
    cost 146 s.
    """
    pasted = " ".join(["compilers retrieval documents"] * 600)
    assert bound_query(pasted)[1] > 0, "the fixture must be long enough to be bounded"
    benchmark(search, vector_store, pasted)


def test_the_bound_is_what_makes_that_true(vector_store: SqliteStore) -> None:
    """Not a benchmark: the mechanism behind the number above, measured once.

    `search` bounds the question; `search_chunks` is the unbounded primitive, and
    measuring both on the same text is what shows the bound is doing the work
    rather than the fixture being small.
    """
    pasted = " ".join(["compilers retrieval documents"] * 200)
    read, unread = bound_query(pasted)
    assert unread > 0
    assert len(query_terms(read)) <= MAX_QUERY_TERMS

    started = time.perf_counter()
    bounded = search(vector_store, pasted)
    with_bound = (time.perf_counter() - started) * 1000
    assert any("bounded" in note for note in bounded.notes)

    started = time.perf_counter()
    vector_store.search_chunks(pasted, limit=VECTOR_CANDIDATES)
    without_bound = (time.perf_counter() - started) * 1000

    # Generous by design: this guards the *bound*, not the machine. At 600 terms
    # against 64 the unbounded path costs roughly nine times as much, and the
    # ratio grows without limit in the length of what was pasted.
    assert with_bound * 3 < without_bound, (
        f"bounded {with_bound:.0f} ms vs unbounded {without_bound:.0f} ms - "
        "the bound is not binding"
    )


def test_the_stored_vector_is_fixed_width_float32() -> None:
    """Not a benchmark: the size assumption the scan's cost model rests on."""
    assert struct.calcsize(f"<{DIM}f") == DIM * 4
