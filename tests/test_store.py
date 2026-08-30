# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""SQLite store (roadmap 2.6): records round-trip through rows without loss, the
lexical index ranks by the spec's field weights, and a store from another schema
version is refused rather than reinterpreted."""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mycelium.chunking import chunk_document
from mycelium.markdown import parse_markdown
from mycelium.sdk.types import (
    Chunk,
    ChunkKind,
    Document,
    DocumentStats,
    Provenance,
    ProvenanceOrigin,
    SourceTrust,
    TrustClass,
    Verification,
    VerificationStatus,
)
from mycelium.store import (
    SCHEMA_VERSION,
    SearchFilters,
    SqliteStore,
    Store,
    StoreError,
    StoreVersionError,
    fts_query,
)
from mycelium.store.schema import META_SCHEMA_VERSION

DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
OTHER_ID = "01J1ZF8Q4R6XKQ3F0V9T8B2M7N"
DIGEST = "sha256:" + "6f2a" * 16


def make_document(
    doc_id: str = DOC_ID,
    path: str = "knowledge/verified/architecture.md",
    title: str = "Architecture",
    **overrides: object,
) -> Document:
    fields: dict[str, object] = {
        "doc_id": doc_id,
        "path": path,
        "title": title,
        "content_digest": DIGEST,
        "trust_class": TrustClass.AUTHORED,
        "verification_status": VerificationStatus.VERIFIED,
        "provenance": Provenance(),
        "stats": DocumentStats(tokens=100, headings=2, chunks=3, links_out=1),
        "created_at": datetime(2026, 7, 31, 10, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 7, 31, 10, 0, tzinfo=UTC),
    }
    fields.update(overrides)
    return Document.model_validate(fields)


def make_chunk(anchor: str, text: str, doc_id: str = DOC_ID, **overrides: object) -> Chunk:
    fields: dict[str, object] = {
        "anchor": anchor,
        "doc_id": doc_id,
        "chunk_digest": DIGEST,
        "heading_path": ("Architecture", "Event Bus"),
        "kir_nodes": ("n1", "n2"),
        "text": text,
        "tokens": len(text.split()),
        "lines": (1, 4),
        "kind": ChunkKind.PROSE,
    }
    fields.update(overrides)
    return Chunk.model_validate(fields)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteStore]:
    with SqliteStore.open(tmp_path) as opened:
        yield opened


def seed(store: SqliteStore, *chunks: Chunk, document: Document | None = None) -> None:
    with store.transaction():
        store.put_document(document or make_document())
        store.put_chunks(chunks)


# ---------------------------------------------------------------------------
# Schema, layout, and version discipline
# ---------------------------------------------------------------------------


def test_open_creates_the_store_under_dot_mycelium(tmp_path: Path) -> None:
    with SqliteStore.open(tmp_path) as store:
        assert store.get_meta(META_SCHEMA_VERSION) == SCHEMA_VERSION
    assert (tmp_path / ".mycelium" / "store.db").exists()


def test_wal_and_foreign_keys_are_on(tmp_path: Path) -> None:
    with SqliteStore.open(tmp_path) as store:
        connection = store._connection  # noqa: SLF001 - asserting the pragmas we set
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_reopening_is_idempotent(tmp_path: Path) -> None:
    with SqliteStore.open(tmp_path) as store:
        seed(store, make_chunk("a.md#x/0", "first"))
    with SqliteStore.open(tmp_path) as store:
        assert store.get_chunk("a.md#x/0") is not None


def test_a_foreign_schema_version_is_refused_not_reinterpreted(tmp_path: Path) -> None:
    """D-016: rebuild is the migration; silent reinterpretation never is."""
    with SqliteStore.open(tmp_path) as store, store.transaction():
        store.set_meta(META_SCHEMA_VERSION, "mycelium/store/v99")
    with pytest.raises(StoreVersionError, match="mycelium build"):
        SqliteStore.open(tmp_path)


def test_read_only_open_requires_an_existing_store(tmp_path: Path) -> None:
    with pytest.raises(StoreError, match="mycelium build"):
        SqliteStore.open(tmp_path, read_only=True)


def test_read_only_stores_serve_reads_and_refuse_writes(tmp_path: Path) -> None:
    with SqliteStore.open(tmp_path) as writer:
        seed(writer, make_chunk("a.md#x/0", "readable text"))
    with SqliteStore.open(tmp_path, read_only=True) as reader:
        assert reader.get_chunk("a.md#x/0") is not None
        assert reader.search_chunks("readable")
        with pytest.raises(StoreError, match="read-only"), reader.transaction():
            pass  # pragma: no cover - the guard raises on entry


def test_sqlite_store_satisfies_the_store_protocol(store: SqliteStore) -> None:
    assert isinstance(store, Store)


# ---------------------------------------------------------------------------
# Records round-trip through rows without loss
# ---------------------------------------------------------------------------


def test_document_round_trips_with_every_field(store: SqliteStore) -> None:
    document = make_document(
        namespace="team-a",
        collection="core-docs",
        tags=("architecture", "event-bus"),
        curated=True,
        verification_status=VerificationStatus.CANDIDATE,
        verification=Verification(verified_by="daniel", verified_at="2026-07-31", grounding=0.97),
        provenance=Provenance(
            origin=ProvenanceOrigin.INGESTED,
            source_uri="https://example.invalid/doc",
            source_digest=DIGEST,
            source_trust=SourceTrust.MEDIUM,
            connector="docling",
            connector_version="1.2.3",
            ingested_at=datetime(2026, 7, 30, 9, 0, tzinfo=UTC),
        ),
        fidelity_report=DIGEST,
        secret_flags=("aws_key",),
    )
    with store.transaction():
        store.put_document(document)
    assert store.get_document(DOC_ID) == document
    assert store.get_document_by_path(document.path) == document


def test_chunk_round_trips_with_every_field(store: SqliteStore) -> None:
    chunk = make_chunk(
        "a.md#x/0",
        "chunk text",
        heading_path=("A", "B", "C"),
        kir_nodes=("n1", "n2", "n3"),
        kind=ChunkKind.CODE,
        lines=(88, 141),
        namespace="team-a",
        tokens=412,
    )
    seed(store, chunk)
    assert store.get_chunk("a.md#x/0") == chunk
    assert store.chunks_of(DOC_ID) == (chunk,)


def test_missing_records_are_none_not_errors(store: SqliteStore) -> None:
    assert store.get_document("01J1ZZZZZZZZZZZZZZZZZZZZZZ") is None
    assert store.get_document_by_path("nope.md") is None
    assert store.get_chunk("nope.md#x/0") is None
    assert store.chunks_of(DOC_ID) == ()


def test_a_chunk_without_its_document_is_refused(store: SqliteStore) -> None:
    with pytest.raises(StoreError, match="unknown document"), store.transaction():
        store.put_chunks([make_chunk("a.md#x/0", "orphan", doc_id=OTHER_ID)])


def test_writes_are_idempotent(store: SqliteStore) -> None:
    chunk = make_chunk("a.md#x/0", "text")
    seed(store, chunk)
    seed(store, chunk)
    assert store.counts()["chunks"] == 1
    assert len(store.search_chunks("text")) == 1  # the index does not double-count


def test_a_transaction_rolls_back_whole(store: SqliteStore) -> None:
    with pytest.raises(RuntimeError, match="boom"), store.transaction():
        store.put_document(make_document())
        raise RuntimeError("boom")
    assert store.get_document(DOC_ID) is None
    assert store.counts()["documents"] == 0


def test_deleting_a_document_removes_its_chunks_and_index_entries(store: SqliteStore) -> None:
    seed(store, make_chunk("a.md#x/0", "findable text"))
    with store.transaction():
        store.delete_document(DOC_ID)
    assert store.counts() == {"documents": 0, "chunks": 0, "symbols": 0, "edges": 0, "vectors": 0}
    assert store.search_chunks("findable") == ()


def test_meta_is_readable_and_writable(store: SqliteStore) -> None:
    with store.transaction():
        store.set_meta("current_snapshot", "01J1ZF8Q4R6XKQ3F0V9T8B2M7N")
    assert store.get_meta("current_snapshot") == "01J1ZF8Q4R6XKQ3F0V9T8B2M7N"
    assert store.get_meta("absent") is None


def test_json_columns_are_canonical(store: SqliteStore) -> None:
    """Two stores built from the same records hold byte-identical column values."""
    seed(store, make_chunk("a.md#x/0", "text"))
    row = store._connection.execute(  # noqa: SLF001 - asserting the storage form
        "SELECT heading_path_json, lines_json FROM chunks"
    ).fetchone()
    assert row["heading_path_json"] == '["Architecture","Event Bus"]'
    assert row["lines_json"] == "[1,4]"


# ---------------------------------------------------------------------------
# Lexical search (spec 04 §3)
# ---------------------------------------------------------------------------


def test_search_ranks_by_the_specified_field_weights(store: SqliteStore) -> None:
    """title 3.0 > heading_path 2.0 > body 1.0, so a title match outranks a body one."""
    with store.transaction():
        store.put_document(make_document(title="Retries", path="a.md"))
        store.put_document(make_document(doc_id=OTHER_ID, title="Unrelated", path="b.md"))
        store.put_chunks(
            [
                make_chunk("a.md#x/0", "body text", heading_path=("Retries",)),
                make_chunk(
                    "b.md#x/0",
                    "retries appear only in this body",
                    doc_id=OTHER_ID,
                    heading_path=("Other",),
                ),
            ]
        )
    hits = store.search_chunks("retries")
    assert [hit.chunk.anchor for hit in hits] == ["a.md#x/0", "b.md#x/0"]
    assert hits[0].score > hits[1].score


def test_hits_carry_the_document_context_a_citation_needs(store: SqliteStore) -> None:
    seed(store, make_chunk("a.md#x/0", "searchable content"))
    (hit,) = store.search_chunks("searchable")
    assert hit.path == "knowledge/verified/architecture.md"
    assert hit.title == "Architecture"
    assert hit.trust_class is TrustClass.AUTHORED
    assert hit.verification_status is VerificationStatus.VERIFIED
    assert hit.score > 0  # positive and descending, unlike SQLite's raw bm25


def test_search_respects_the_limit_and_finds_nothing_gracefully(store: SqliteStore) -> None:
    seed(
        store,
        *[make_chunk(f"a.md#x/{i}", f"repeated term number {i}") for i in range(5)],
    )
    assert len(store.search_chunks("repeated", limit=2)) == 2
    assert store.search_chunks("absent") == ()
    assert store.search_chunks("") == ()


@pytest.mark.parametrize(
    "filters",
    [
        SearchFilters(namespace="other"),
        SearchFilters(collection="other"),
        SearchFilters(trust_class=TrustClass.EXTERNAL),
        SearchFilters(verification_status=VerificationStatus.CANDIDATE),
        SearchFilters(path_prefix="sources/"),
    ],
)
def test_filters_exclude_non_matching_documents(store: SqliteStore, filters: SearchFilters) -> None:
    seed(
        store,
        make_chunk("a.md#x/0", "filtered content"),
        document=make_document(collection="core-docs"),
    )
    assert store.search_chunks("filtered") != ()
    assert store.search_chunks("filtered", filters=filters) == ()


def test_matching_filters_keep_the_hit(store: SqliteStore) -> None:
    seed(
        store,
        make_chunk("a.md#x/0", "filtered content"),
        document=make_document(collection="core-docs"),
    )
    filters = SearchFilters(
        namespace="default",
        collection="core-docs",
        trust_class=TrustClass.AUTHORED,
        verification_status=VerificationStatus.VERIFIED,
        path_prefix="knowledge/verified/",
    )
    assert len(store.search_chunks("filtered", filters=filters)) == 1


def test_path_prefix_wildcards_are_matched_literally(store: SqliteStore) -> None:
    seed(store, make_chunk("a.md#x/0", "wildcard content"))
    assert store.search_chunks("wildcard", filters=SearchFilters(path_prefix="k%")) == ()


def test_prefix_search_finds_identifier_stems(store: SqliteStore) -> None:
    seed(store, make_chunk("a.md#x/0", "the BuildKey class"))
    assert store.search_chunks("buildk") == ()
    assert store.search_chunks("buildk", prefix=True) != ()


# ---------------------------------------------------------------------------
# Query text is data, not syntax (D-017)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        'unbalanced "quote',
        "text OR chunks_fts",
        "NEAR(a b)",
        "title:secret",
        "*",
        "^prefix",
        "a AND (b OR c)",
        "-negated",
        "'; DROP TABLE chunks; --",
    ],
)
def test_operator_laden_queries_are_matched_as_words(store: SqliteStore, query: str) -> None:
    seed(store, make_chunk("a.md#x/0", "ordinary content"))
    store.search_chunks(query)  # no syntax error, no injection
    assert store.counts()["chunks"] == 1


@given(query=st.text(max_size=60))
def test_any_query_text_is_safe(tmp_path_factory: pytest.TempPathFactory, query: str) -> None:
    root = tmp_path_factory.mktemp("store")
    with SqliteStore.open(root) as store:
        seed(store, make_chunk("a.md#x/0", "content"))
        store.search_chunks(query)


def test_fts_query_quotes_every_term() -> None:
    assert fts_query("event bus") == '"event" OR "bus"'
    assert fts_query("event bus", prefix=True) == '"event"* OR "bus"*'
    assert fts_query("event bus", match_all=True) == '"event" "bus"'
    assert fts_query("  ") == ""
    assert fts_query('"NEAR" OR *') == '"NEAR" OR "OR"'


def test_a_query_term_the_corpus_lacks_does_not_zero_the_query(store: SqliteStore) -> None:
    """BUG-0005: under FTS5's implicit AND, one unmatched word returned nothing.

    Ranking is the point of BM25 — a partial match is a result to be ranked, not a
    reason to answer "nothing found" to a natural-language question.
    """
    seed(store, make_chunk("a.md#x/0", "the retry policy uses exponential backoff"))
    assert store.search_chunks("retry policy") != ()
    assert store.search_chunks("retry policy kubernetes") != ()
    assert store.search_chunks("kubernetes helm istio") == ()  # nothing matches at all


# ---------------------------------------------------------------------------
# The store against real compiled documents
# ---------------------------------------------------------------------------

SOURCE = """# Architecture

The event bus routes messages between components.

## Retry Policy

Failed deliveries retry with exponential backoff.

```python
retries = 3
```
"""


def test_a_compiled_document_is_storable_and_searchable(tmp_path: Path) -> None:
    parsed = parse_markdown(SOURCE)
    chunks = chunk_document(parsed.kir, doc_path="knowledge/architecture.md")
    document = make_document(doc_id=parsed.kir.doc_id, path="knowledge/architecture.md")

    with SqliteStore.open(tmp_path) as store:
        with store.transaction():
            store.put_document(document)
            assert store.put_chunks(chunks) == len(chunks)

        assert store.counts()["chunks"] == len(chunks)
        assert store.chunks_of(parsed.kir.doc_id) == tuple(
            sorted(chunks, key=lambda chunk: chunk.anchor)
        )
        (hit,) = store.search_chunks("exponential backoff")
        assert "exponential backoff" in hit.chunk.text
        assert hit.chunk.heading_path == ("Architecture", "Retry Policy")


def test_rebuilding_a_document_replaces_its_chunks(tmp_path: Path) -> None:
    with SqliteStore.open(tmp_path) as store:
        seed(store, make_chunk("a.md#x/0", "original text"))
        with store.transaction():
            store.delete_document(DOC_ID)
            store.put_document(make_document())
            store.put_chunks([make_chunk("a.md#y/0", "replacement text")])
        assert store.search_chunks("original") == ()
        assert len(store.search_chunks("replacement")) == 1


def test_concurrent_readers_see_committed_writes(tmp_path: Path) -> None:
    """WAL: a reader on its own connection is not blocked by the writer (D-015)."""
    with SqliteStore.open(tmp_path) as writer:
        seed(writer, make_chunk("a.md#x/0", "committed text"))
        with SqliteStore.open(tmp_path, read_only=True) as reader:
            assert len(reader.search_chunks("committed")) == 1
            with writer.transaction():
                writer.put_chunks([make_chunk("a.md#y/0", "second text")])
            assert len(reader.search_chunks("second")) == 1


def test_the_store_file_is_a_plain_sqlite_database(tmp_path: Path) -> None:
    """No custom container: `sqlite3` on the file is a supported way to look inside."""
    with SqliteStore.open(tmp_path) as store:
        seed(store, make_chunk("a.md#x/0", "text"))
    with sqlite3.connect(tmp_path / ".mycelium" / "store.db") as raw:
        tables = {
            row[0] for row in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {"documents", "chunks", "vectors", "symbols", "edges", "build_cache", "meta"} <= tables
