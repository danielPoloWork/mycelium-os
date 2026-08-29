# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Store hot-path benchmarks (roadmap 2.6).

Lexical search is the first stage of every query, and its stage budget is 60 ms of
the 150 ms p95 (RFC-0001). This records a baseline on a small corpus; the real
gate is measured against the 10^5-chunk reference profile at roadmap 3.7.
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from mycelium.sdk.types import Chunk, Document, DocumentStats, Provenance, TrustClass
from mycelium.store import SqliteStore

DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
DIGEST = "sha256:" + "6f2a" * 16
TERMS = ("retry", "backoff", "event", "bus", "snapshot", "digest", "anchor", "chunk")


def _chunks(count: int) -> list[Chunk]:
    return [
        Chunk(
            anchor=f"knowledge/doc.md#section-{index}/0",
            doc_id=DOC_ID,
            chunk_digest=DIGEST,
            heading_path=("Document", f"Section {index}"),
            kir_nodes=(f"n{index}",),
            text=f"The {TERMS[index % len(TERMS)]} policy for section {index} "
            "describes how failed deliveries are handled and retried later.",
            tokens=20,
            lines=(index, index + 3),
        )
        for index in range(count)
    ]


@pytest.fixture(scope="module")
def populated_store(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SqliteStore]:
    root = tmp_path_factory.mktemp("bench-store")
    with SqliteStore.open(root) as store:
        with store.transaction():
            store.put_document(
                Document(
                    doc_id=DOC_ID,
                    path="knowledge/doc.md",
                    title="Document",
                    content_digest=DIGEST,
                    trust_class=TrustClass.AUTHORED,
                    verification_status="verified",
                    provenance=Provenance(),
                    stats=DocumentStats(tokens=0, headings=0, chunks=0, links_out=0),
                    created_at=datetime(2026, 7, 31, tzinfo=UTC),
                    updated_at=datetime(2026, 7, 31, tzinfo=UTC),
                )
            )
            store.put_chunks(_chunks(1000))
        yield store


def test_search_chunks(populated_store: SqliteStore, benchmark: BenchmarkFixture) -> None:
    benchmark(populated_store.search_chunks, "retry policy", limit=10)


def test_get_chunk(populated_store: SqliteStore, benchmark: BenchmarkFixture) -> None:
    benchmark(populated_store.get_chunk, "knowledge/doc.md#section-500/0")


def test_put_chunks(tmp_path_factory: pytest.TempPathFactory, benchmark: BenchmarkFixture) -> None:
    root = tmp_path_factory.mktemp("bench-write")
    store = SqliteStore.open(root)
    with store.transaction():
        store.put_document(
            Document(
                doc_id=DOC_ID,
                path="knowledge/doc.md",
                title="Document",
                content_digest=DIGEST,
                trust_class=TrustClass.AUTHORED,
                verification_status="verified",
                provenance=Provenance(),
                stats=DocumentStats(tokens=0, headings=0, chunks=0, links_out=0),
                created_at=datetime(2026, 7, 31, tzinfo=UTC),
                updated_at=datetime(2026, 7, 31, tzinfo=UTC),
            )
        )
    batch = _chunks(100)

    def write() -> None:
        with store.transaction():
            store.put_chunks(batch)

    benchmark(write)
    store.close()
