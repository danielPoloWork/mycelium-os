# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The store interface (spec 02 §10).

SQLite is a *secondary store component*, explicitly replaceable — a claim that is
worth nothing unless something states what a replacement must do. This protocol is
that statement: every operation the compiler and the serving layer need, expressed
in records rather than rows, with no SQL in the signatures.

A Postgres/OpenSearch store at the platform phase (D-019) implements this and
nothing else changes. Anything that reaches for `SqliteStore` directly, rather than
for this protocol, is what would make that phase a rewrite.
"""

from collections.abc import Iterable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from mycelium.sdk.types import Chunk, Document, Edge, EdgeType, Sha256Digest

__all__ = ["CacheEntry", "DocState", "SnapshotState", "Store"]


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """One row of the build-cache index (roadmap 3.1), as garbage collection sees it."""

    build_key: str
    artifact_digest: Sha256Digest
    created_at: str


@dataclass(frozen=True, slots=True)
class SnapshotState:
    """A published snapshot's pointer to the state it can be restored from (3.2).

    ``state_blob`` addresses a CAS blob holding the snapshot's whole
    :class:`DocState` table in canonical JSON — the Memento that makes
    ``mycelium rollback`` restore data rather than merely repoint a name
    (ADR-0016).
    """

    snapshot_id: str
    state_blob: Sha256Digest
    created_at: str


@dataclass(frozen=True, slots=True)
class DocState:
    """What the store's index currently holds for one document (roadmap 3.1).

    The incremental build's dirty detector compares a discovered file against
    this row: same ``source_digest``, same ``source_mtime`` (mtime is an input —
    it becomes ``created_at``, ADR-0009), same ``env_digest`` (stage versions,
    schema versions, config slices, namespace) ⇒ the document needs no work.
    ``document_digest``/``chunks_digest`` are the per-document artifact digests
    the snapshot manifest's corpus digests are folded from, and ``warnings`` are
    replayed into the manifest so a cached document warns exactly like a
    recompiled one.

    The last three fields are the document's contribution to the link graph
    (roadmap 3.4). They live here because edge *resolution* is global — what
    `[[api]]` means depends on every other document's path, aliases, and headings
    — while extraction is per-document and cached. Holding them lets a build
    re-resolve the whole graph without re-parsing one unchanged document, which
    is what keeps "add a file and every dangling link to it resolves" true
    without giving up incrementality (ADR-0018).
    """

    doc_id: str
    path: str
    source_digest: Sha256Digest
    source_mtime: str
    env_digest: Sha256Digest
    document_digest: Sha256Digest
    chunks_digest: Sha256Digest
    warnings: tuple[str, ...]
    links: tuple[Mapping[str, str], ...] = ()
    """The authored references this document makes, as extracted from its KIR."""
    aliases: tuple[str, ...] = ()
    """Frontmatter aliases — what *other* documents may call this one."""
    headings: tuple[str, ...] = ()
    """This document's heading slugs, so `[[doc#Heading]]` can target a section."""


@runtime_checkable
class Store(Protocol):
    """What the pipeline requires of a store, and all it may assume."""

    def transaction(self) -> AbstractContextManager[None]:
        """Run a unit of work, rolled back whole if it raises."""
        ...

    def close(self) -> None: ...

    # -- writes ------------------------------------------------------------

    def put_document(self, document: Document) -> None: ...

    def put_chunks(self, chunks: Iterable[Chunk]) -> int: ...

    def delete_document(self, doc_id: str) -> None: ...

    def set_meta(self, key: str, value: str) -> None: ...

    def put_doc_state(self, state: DocState) -> None: ...

    def cache_put(self, build_key: str, artifact_digest: str, created_at: str) -> None: ...

    def put_snapshot_state(self, state: SnapshotState) -> None: ...

    def delete_snapshot_state(self, snapshot_id: str) -> None: ...

    def delete_cache_entries(self, build_keys: Iterable[str]) -> int: ...

    def clear_documents(self) -> None: ...

    def put_edges(self, edges: Iterable[Edge]) -> int: ...

    def clear_edges(self) -> None: ...

    # -- reads -------------------------------------------------------------

    def get_document(self, doc_id: str) -> Document | None: ...

    def document_ids(self) -> tuple[str, ...]: ...

    def get_document_by_path(self, path: str) -> Document | None: ...

    def get_chunk(self, anchor: str) -> Chunk | None: ...

    def chunks_of(self, doc_id: str) -> tuple[Chunk, ...]: ...

    def get_meta(self, key: str) -> str | None: ...

    def counts(self) -> dict[str, int]: ...

    def doc_states(self) -> tuple[DocState, ...]: ...

    def cache_get(self, build_key: str) -> str | None: ...

    def cache_entries(self) -> tuple[CacheEntry, ...]: ...

    def edges_of(
        self, ref: str, types: Sequence[EdgeType] | None = None
    ) -> tuple[tuple[Edge, str], ...]: ...

    def snapshot_states(self) -> tuple[SnapshotState, ...]: ...

    def get_snapshot_state(self, snapshot_id: str) -> SnapshotState | None: ...
