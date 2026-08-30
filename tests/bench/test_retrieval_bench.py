# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Retrieval benchmarks (roadmap 3.3, ADR-0017).

The claim these back is the one that chose an exact scan over sqlite-vec: inside
the v1 corpus envelope (10²–10⁵ chunks, D-002), brute-force cosine meets spec
04 §1's candidate-generation budget of 60 ms, so a loadable SQLite extension —
unavailable in stock Python builds on a supported platform — is not worth its
portability cost yet.

The committed size is 10 000 chunks, which keeps the benchmark job quick. The
scan is linear in the corpus, so the reference profile is a multiplication; the
100 000-chunk measurement behind ADR-0017 was taken by hand with the same code.

Fusion is measured separately because it is pure arithmetic over rank lists: if
it ever shows up next to the scan, something has gone wrong with it.
"""

import random
import struct
from datetime import UTC, datetime

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from mycelium.retrieval import RRF_K, VECTOR_CANDIDATES, reciprocal_rank_fusion
from mycelium.sdk.types import (
    Chunk,
    ChunkKind,
    Document,
    DocumentStats,
    Provenance,
    TrustClass,
    VerificationStatus,
)
from mycelium.store import SearchHit, SqliteStore

DIM = 384
CHUNKS = 10_000
PER_DOC = 100
MODEL_ID = "bench-model"


def _unit(rng: random.Random) -> tuple[float, ...]:
    values = [rng.gauss(0.0, 1.0) for _ in range(DIM)]
    norm = sum(value * value for value in values) ** 0.5
    return tuple(value / norm for value in values)


@pytest.fixture(scope="module")
def vector_store(tmp_path_factory: pytest.TempPathFactory) -> SqliteStore:
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
                    provenance=Provenance(origin="authored"),
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


def test_the_stored_vector_is_fixed_width_float32() -> None:
    """Not a benchmark: the size assumption the scan's cost model rests on."""
    assert struct.calcsize(f"<{DIM}f") == DIM * 4
