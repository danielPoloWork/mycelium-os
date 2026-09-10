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
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # the hit record lives beside the implementation that builds it
    from mycelium.store.sqlite import SearchHit

from mycelium.sdk.types import (
    Chunk,
    Document,
    Edge,
    EdgeType,
    Entity,
    ProvenanceOrigin,
    Sha256Digest,
    Symbol,
)

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

    ``links``, ``aliases`` and ``headings`` are the document's contribution to
    the link graph (roadmap 3.4). They live here because edge *resolution* is
    global — what `[[api]]` means depends on every other document's path,
    aliases, and headings — while extraction is per-document and cached. Holding
    them lets a build re-resolve the whole graph without re-parsing one unchanged
    document, which is what keeps "add a file and every dangling link to it
    resolves" true without giving up incrementality (ADR-0018).

    ``symbols``, ``symbol_uses`` and ``symbol_gaps`` are the same arrangement for
    the symbol table (roadmap 5.1/5.2): what this document defines, what its
    fences use, and which of its code fences no installed grammar could read. One
    symbol may be defined by several documents, so both the record and the typed
    edges over it are folded globally from these on every build (ADR-0073,
    ADR-0074).

    ``entities`` is the third of these (roadmap 5.4): the named things this
    document *declares* through its tags and aliases. It is cached here whether
    or not the optional stage is switched on, because the extraction is a few
    frontmatter fields — so turning the stage on costs no recompile, and the
    corpus-wide vocabulary a mention resolves against is available the moment it
    is (ADR-0076).

    ``origin`` is the document's `provenance.origin`, and it is here for the one
    edge type that cannot be derived without it: a `derived_from` edge says a
    *synthesized* document was written from its evidence, which is a different
    assertion from an authored document citing the same evidence (ADR-0018
    deferred the type for exactly this reason; roadmap 5.2).
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
    symbols: tuple[Mapping[str, object], ...] = ()
    """The definitions this document makes, as extracted from its KIR."""
    symbol_uses: tuple[Mapping[str, object], ...] = ()
    """The symbols its fences use — the input to the `references` edges."""
    symbol_gaps: tuple[str, ...] = ()
    """Fence languages whose grammar was not installed when it was compiled."""
    entities: tuple[Mapping[str, str], ...] = ()
    """The named things this document declares — its tags and aliases (5.4)."""
    origin: str = ProvenanceOrigin.AUTHORED.value
    """`authored`, `ingested`, or `synthesized` — absent frontmatter is authored."""


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

    def put_symbols(self, symbols: Iterable[Symbol]) -> int: ...

    def clear_symbols(self) -> None: ...

    def put_entities(self, entities: Iterable[Entity]) -> int: ...

    def clear_entities(self) -> None: ...

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

    def all_edges(self) -> tuple[Edge, ...]: ...

    def all_symbols(self) -> tuple[Symbol, ...]: ...

    def all_entities(self) -> tuple[Entity, ...]: ...

    def rank_anchors(
        self, query: str, anchors: Sequence[str], *, limit: int = 1
    ) -> tuple["SearchHit", ...]: ...

    def anchors_of_paths(self, paths: Sequence[str]) -> dict[str, tuple[str, ...]]: ...

    def get_symbol(self, symbol: str) -> Symbol | None: ...

    def edges_of(
        self, ref: str, types: Sequence[EdgeType] | None = None
    ) -> tuple[tuple[Edge, str], ...]: ...

    def snapshot_states(self) -> tuple[SnapshotState, ...]: ...

    def get_snapshot_state(self, snapshot_id: str) -> SnapshotState | None: ...
