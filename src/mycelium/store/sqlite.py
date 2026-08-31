# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""SQLite store: the catalog, the lexical index, and the meta table (spec 03 §8).

The store is a *component behind an interface*, not a foundation (spec 02 §10):
SQL never leaves this package, records cross the boundary, and swapping SQLite for
another engine is meant to be an afternoon's work rather than a rewrite. Hence the
:class:`~mycelium.store.base.Store` protocol this class satisfies.

What it is responsible for: mapping records to rows and back without loss, keeping
the FTS5 index in step with the chunks, and refusing to open a store whose schema
it does not understand. What it is *not* responsible for: the single-writer lock
and snapshot publication (roadmap 2.7), and any ranking beyond BM25 (roadmap 3.3).
"""

import json
import re
import sqlite3
import struct
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Final, Self

from mycelium.sdk.identity import canonical_json, digest_json, edge_id
from mycelium.sdk.types import (
    Chunk,
    ChunkKind,
    Document,
    Edge,
    EdgeStatus,
    EdgeType,
    TrustClass,
    VerificationStatus,
)
from mycelium.store.base import CacheEntry, DocState, SnapshotState
from mycelium.store.schema import (
    DDL,
    META_SCHEMA_VERSION,
    META_VECTORS_GENERATION,
    PRAGMAS,
    SCHEMA_VERSION,
)
from mycelium.store.vectorpack import VectorPack, prune_packs, write_pack

__all__ = [
    "STORE_FILENAME",
    "STORE_DIRNAME",
    "SearchFilters",
    "SearchHit",
    "SqliteStore",
    "StoreError",
    "StoreVersionError",
]

STORE_DIRNAME: Final = ".mycelium"
STORE_FILENAME: Final = "store.db"

_FTS_TERM: Final = re.compile(r"\w+", re.UNICODE)
_BM25_WEIGHTS: Final = (0.0, 1.0, 3.0, 2.0)
"""Column order is (anchor, text, title, heading_path); spec 04 §3 sets the weights."""


class StoreError(RuntimeError):
    """The store cannot serve the request."""


class StoreVersionError(StoreError):
    """The store on disk was written by a different schema version.

    v1's migration policy is rebuild (D-016), and the two open modes divide it:
    a *reader* raises this — it says so and points at ``mycelium build`` rather
    than reinterpreting the bytes — while a *writer* acts on it, recreating the
    file and rebuilding from source (the store is derived data, D-005; the old
    refusal message named `mycelium build` as the fix, so `mycelium build` must
    actually be one — ADR-0015).
    """


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Restrictions applied before ranking (spec 05 §4 `filters`).

    The two vocabulary filters take a *set* of admissible values, because the
    questions callers actually ask are set-shaped: spec 05 §4's `trust` is a list,
    and "serve verified and evidence, not candidates" (`include_candidate = false`)
    is the complement of one value rather than the choice of one. A single-value
    filter forced both to be applied after ranking, which spec 04 §2 forbids —
    post-filtering a top-k list silently returns fewer results than were asked for
    (ADR-0024, BUG-0015).

    `None` means unrestricted. An *empty* set is refused rather than read as
    either: a filter that admits nothing is always a construction mistake, and
    these decide what a server is willing to serve.
    """

    namespace: str | None = None
    collection: str | None = None
    trust_classes: frozenset[TrustClass] | None = None
    verification_statuses: frozenset[VerificationStatus] | None = None
    path_prefix: str | None = None

    def __post_init__(self) -> None:
        for name in ("trust_classes", "verification_statuses"):
            value = getattr(self, name)
            if value is not None and not value:
                msg = f"{name} is empty: pass None for 'no restriction'"
                raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One ranked chunk, with the document context a citation needs."""

    chunk: Chunk
    score: float
    path: str
    title: str
    trust_class: TrustClass
    verification_status: VerificationStatus


def fts_query(text: str, *, prefix: bool = False, match_all: bool = False) -> str:
    """Turn user text into a safe FTS5 MATCH expression.

    Query text is untrusted (D-017): every term is extracted and quoted rather
    than passed through, so FTS5 operators, unbalanced quotes, and column filters
    in a query are matched as words instead of executed as syntax. Returns an
    empty string when nothing searchable remains, which callers read as "no hits".

    Terms are combined with ``OR``, because ranking is the whole point of BM25:
    under FTS5's implicit ``AND`` a single unmatched word zeroes an entire query,
    so "what license does the project use" returns nothing while "license"
    returns five results (BUG-0005). ``match_all=True`` restores conjunction for
    callers that genuinely want it — the query planner's precision routes
    (spec 04 §2) will.
    """
    terms = _FTS_TERM.findall(text)
    if not terms:
        return ""
    suffix = "*" if prefix else ""
    quoted = [f'"{term}"{suffix}' for term in terms]
    return (" " if match_all else " OR ").join(quoted)


class SqliteStore:
    """A SQLite-backed catalog and lexical index."""

    def __init__(self, connection: sqlite3.Connection, *, read_only: bool = False) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._read_only = read_only
        self.recreated = False
        """True when opening discarded a foreign-version store (D-016 rebuild)."""
        self._db_path: Path | None = None
        self._packs: dict[str, VectorPack | None] = {}
        """Memory-mapped packed matrices, per model, for the life of this handle."""
        self._vectors_touched = False

    # -- lifecycle ---------------------------------------------------------

    @classmethod
    def open(cls, root: Path, *, read_only: bool = False, create: bool = True) -> Self:
        """Open the store under `root`, i.e. ``<root>/.mycelium/store.db``.

        `read_only` opens a reader that cannot write and never creates the file —
        what an agent's query path uses while a build is in flight (spec 02 §7).
        A reader that meets a foreign schema version raises
        :class:`StoreVersionError`; a writer recreates the file instead — the
        rebuild migration policy (D-016), possible only because every row is
        derived from source (D-005). Check :attr:`recreated` to report it.
        """
        path = root / STORE_DIRNAME / STORE_FILENAME
        if read_only:
            if not path.exists():
                msg = f"no store at {path}; run `mycelium build` first"
                raise StoreError(msg)
            uri = f"file:{path.as_posix()}?mode=ro"
            connection = sqlite3.connect(uri, uri=True, isolation_level=None)
            store = cls(connection, read_only=True)
            store._db_path = path
            store._configure()
            store._check_version()
            return store

        if not path.exists() and not create:
            msg = f"no store at {path}; run `mycelium build` first"
            raise StoreError(msg)
        path.parent.mkdir(parents=True, exist_ok=True)
        store = cls(sqlite3.connect(path, isolation_level=None), read_only=False)
        store._db_path = path
        store._configure()
        store._migrate()
        try:
            store._check_version()
        except StoreVersionError:
            store._recreate()
            store._check_version()
        return store

    def _recreate(self) -> None:
        """Discard a foreign-version store and lay the current schema down fresh.

        In place — dropping every object rather than deleting the file — because
        Windows refuses to unlink a database any concurrent reader still holds
        open, and readers are exactly what a build must coexist with (D-015).
        """
        rows = self._connection.execute(
            "SELECT name, type FROM sqlite_master "
            "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE 'chunks_fts_%'"  # FTS5 shadow tables go with their parent
        ).fetchall()
        self._connection.execute("PRAGMA foreign_keys=OFF")
        try:
            for row in rows:
                self._connection.execute(f'DROP {row["type"]} IF EXISTS "{row["name"]}"')
        finally:
            self._connection.execute("PRAGMA foreign_keys=ON")
        self.recreated = True
        self._migrate()
        if self._db_path is not None:
            # The counter died with the schema, so generation 0 would re-open a
            # pack from a store that no longer exists.
            prune_packs(self._db_path)
            self._packs = {}

    def _configure(self) -> None:
        for pragma in PRAGMAS:
            if self._read_only and "journal_mode" in pragma:
                continue  # a read-only connection may not change the journal
            self._connection.execute(pragma)

    def _migrate(self) -> None:
        """Create the schema if absent. v1 has no forward migration (D-016).

        The DDL runs outside a transaction of ours on purpose: `executescript`
        commits whatever is open before it starts, so wrapping it would leave the
        transaction we think we are in already closed. Every statement is
        ``IF NOT EXISTS``, so the script is safe to re-run.
        """
        self._connection.executescript(DDL)
        if self._meta_get(META_SCHEMA_VERSION) is None:
            with self.transaction():
                self._meta_set(META_SCHEMA_VERSION, SCHEMA_VERSION)

    def _check_version(self) -> None:
        found = self._meta_get(META_SCHEMA_VERSION)
        if found is None:
            msg = "store has no schema version recorded; rebuild it with `mycelium build`"
            raise StoreVersionError(msg)
        if found != SCHEMA_VERSION:
            msg = (
                f"store schema {found} is not {SCHEMA_VERSION}; this Mycelium will not "
                "reinterpret it — rebuild with `mycelium build`"
            )
            raise StoreVersionError(msg)

    def close(self) -> None:
        self.release_packs()
        self._connection.close()

    def release_packs(self) -> None:
        """Unmap the packed matrices this handle holds open.

        Windows refuses to unlink a file another process still has mapped, so a
        long-lived reader would otherwise pin every generation it has ever read.
        `prune_packs` already tolerates the refusal — this is what makes the
        refusal rare.
        """
        self._packs = {}

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Run a unit of work; roll it back whole if anything raises.

        ``BEGIN IMMEDIATE`` takes the write lock up front, so two writers collide
        at the start of their work instead of at the commit that discards it.
        """
        if self._read_only:
            msg = "store is open read-only"
            raise StoreError(msg)
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self._connection.execute("ROLLBACK")
            self._vectors_touched = False
            raise
        self._connection.execute("COMMIT")
        if self._vectors_touched:
            # After the commit, never inside it: the pack is derived from what the
            # transaction published, and a pack written from uncommitted rows
            # would outlive a rollback.
            self._vectors_touched = False
            self.repack_vectors()

    # -- the packed vector matrix (ADR-0026) --------------------------------

    def _vectors_generation(self) -> int:
        """How many times this store's vectors have changed.

        The pack file's name carries the generation it was packed at, so a pack
        whose vectors have since moved is a file nobody opens — staleness is made
        impossible rather than detected.
        """
        raw = self._meta_get(META_VECTORS_GENERATION)
        return int(raw) if raw is not None and raw.isdigit() else 0

    def _bump_vectors_generation(self) -> None:
        self._meta_set(META_VECTORS_GENERATION, str(self._vectors_generation() + 1))
        self._vectors_touched = True

    def _pack_for(self, model_id: str) -> VectorPack | None:
        """The mapped pack for `model_id`, or ``None`` to use the SQL scan."""
        if self._db_path is None:
            return None
        key = f"{model_id}@{self._vectors_generation()}"
        if key not in self._packs:
            self._packs = {  # one generation at a time; older maps are dead weight
                key: VectorPack.open(self._db_path, model_id, self._vectors_generation())
            }
        return self._packs[key]

    def repack_vectors(self) -> None:
        """Rebuild the packed matrix for every model this store holds vectors for.

        Called once when a write transaction that touched vectors commits, so the
        pack is written by the process that already holds the write lock and has
        just paid for the rows anyway.
        """
        if self._db_path is None or self._read_only:
            return
        generation = self._vectors_generation()
        written: list[Path] = []
        for row in self._connection.execute(
            "SELECT model_id, dim, count(*) AS n FROM vectors GROUP BY model_id, dim"
        ).fetchall():
            rows = self._connection.execute(
                "SELECT chunk_digest, vec FROM vectors WHERE model_id = ?", (str(row["model_id"]),)
            ).fetchall()
            path = write_pack(
                self._db_path,
                str(row["model_id"]),
                dim=int(row["dim"]),
                generation=generation,
                rows=[(str(item["chunk_digest"]), bytes(item["vec"])) for item in rows],
            )
            if path is not None:
                written.append(path)
        prune_packs(self._db_path, keep=written)
        self._packs = {}

    # -- meta --------------------------------------------------------------

    def _meta_get(self, key: str) -> str | None:
        row = self._connection.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def _meta_set(self, key: str, value: str) -> None:
        self._connection.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def get_meta(self, key: str) -> str | None:
        """Read a meta value (schema version, current snapshot, …)."""
        return self._meta_get(key)

    def set_meta(self, key: str, value: str) -> None:
        """Write a meta value. Call inside a :meth:`transaction`."""
        self._meta_set(key, value)

    # -- writes ------------------------------------------------------------

    def put_document(self, document: Document) -> None:
        """Insert or replace a document. Call inside a :meth:`transaction`."""
        self._connection.execute(
            """
            INSERT INTO documents(
                doc_id, path, title, namespace, collection, tags_json, trust_class,
                curated, verification_status, verification_json, content_digest,
                provenance_json, fidelity_report, secret_flags_json, stats_json,
                created_at, updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(doc_id) DO UPDATE SET
                path = excluded.path, title = excluded.title,
                namespace = excluded.namespace, collection = excluded.collection,
                tags_json = excluded.tags_json, trust_class = excluded.trust_class,
                curated = excluded.curated,
                verification_status = excluded.verification_status,
                verification_json = excluded.verification_json,
                content_digest = excluded.content_digest,
                provenance_json = excluded.provenance_json,
                fidelity_report = excluded.fidelity_report,
                secret_flags_json = excluded.secret_flags_json,
                stats_json = excluded.stats_json, updated_at = excluded.updated_at
            """,
            (
                document.doc_id,
                document.path,
                document.title,
                document.namespace,
                document.collection,
                canonical_json(list(document.tags)),
                document.trust_class.value,
                int(document.curated),
                document.verification_status.value,
                None
                if document.verification is None
                else canonical_json(document.verification.model_dump(mode="json")),
                document.content_digest,
                canonical_json(document.provenance.model_dump(mode="json")),
                document.fidelity_report,
                canonical_json(list(document.secret_flags)),
                canonical_json(document.stats.model_dump(mode="json")),
                _rfc3339(document.created_at),
                _rfc3339(document.updated_at),
            ),
        )

    def put_chunks(self, chunks: Iterable[Chunk]) -> int:
        """Replace the chunks of the documents these chunks belong to.

        The lexical index is written in the same statement run, so `chunks` and
        `chunks_fts` cannot disagree about what exists.
        """
        written = 0
        for chunk in chunks:
            title = self._document_title(chunk.doc_id)
            self._connection.execute("DELETE FROM chunks_fts WHERE anchor = ?", (chunk.anchor,))
            self._connection.execute(
                """
                INSERT INTO chunks(
                    anchor, doc_id, chunk_digest, heading_path_json, kir_nodes_json,
                    text, tokens, kind, lines_json, namespace)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(anchor) DO UPDATE SET
                    doc_id = excluded.doc_id, chunk_digest = excluded.chunk_digest,
                    heading_path_json = excluded.heading_path_json,
                    kir_nodes_json = excluded.kir_nodes_json, text = excluded.text,
                    tokens = excluded.tokens, kind = excluded.kind,
                    lines_json = excluded.lines_json, namespace = excluded.namespace
                """,
                (
                    chunk.anchor,
                    chunk.doc_id,
                    chunk.chunk_digest,
                    canonical_json(list(chunk.heading_path)),
                    canonical_json(list(chunk.kir_nodes)),
                    chunk.text,
                    chunk.tokens,
                    chunk.kind.value,
                    canonical_json(list(chunk.lines)),
                    chunk.namespace,
                ),
            )
            self._connection.execute(
                "INSERT INTO chunks_fts(anchor, text, title, heading_path) VALUES(?,?,?,?)",
                (chunk.anchor, chunk.text, title, " / ".join(chunk.heading_path)),
            )
            written += 1
        return written

    def delete_document(self, doc_id: str) -> None:
        """Remove a document and everything derived from it.

        Chunks and the document's ``doc_state`` row go with it (``ON DELETE
        CASCADE``); the lexical index is cleaned here because FTS5 tables know
        nothing of foreign keys.
        """
        anchors = self._connection.execute(
            "SELECT anchor FROM chunks WHERE doc_id = ?", (doc_id,)
        ).fetchall()
        for row in anchors:
            self._connection.execute("DELETE FROM chunks_fts WHERE anchor = ?", (row["anchor"],))
        self._connection.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))

    def put_doc_state(self, state: DocState) -> None:
        """Record what the index now holds for one document (roadmap 3.1).

        Call inside a :meth:`transaction`, after :meth:`put_document` (the row
        references the document) and after any conflicting old rows — same path
        under another id — were deleted; the orchestrator deletes before it
        inserts precisely so the two UNIQUE constraints here never fire.
        """
        self._connection.execute(
            """
            INSERT INTO doc_state(
                doc_id, path, source_digest, source_mtime, env_digest,
                document_digest, chunks_digest, warnings_json, graph_json)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(doc_id) DO UPDATE SET
                path = excluded.path, source_digest = excluded.source_digest,
                source_mtime = excluded.source_mtime, env_digest = excluded.env_digest,
                document_digest = excluded.document_digest,
                chunks_digest = excluded.chunks_digest,
                warnings_json = excluded.warnings_json,
                graph_json = excluded.graph_json
            """,
            (
                state.doc_id,
                state.path,
                state.source_digest,
                state.source_mtime,
                state.env_digest,
                state.document_digest,
                state.chunks_digest,
                canonical_json(list(state.warnings)),
                canonical_json(
                    {
                        "links": [dict(item) for item in state.links],
                        "aliases": list(state.aliases),
                        "headings": list(state.headings),
                    }
                ),
            ),
        )

    def put_edges(self, edges: Iterable[Edge]) -> int:
        """Insert edges, keyed by their content-derived id. In a transaction.

        The id is the digest of the assertion (spec 03 §2), so re-deriving the
        same edge is idempotent — which is what makes a rebuild converge rather
        than accumulate.
        """
        written = 0
        for edge in edges:
            provenance = edge.provenance.model_dump(mode="json")
            self._connection.execute(
                """
                INSERT INTO edges(
                    edge_id, from_id, to_id, type, status, weight, provenance_json, namespace)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(edge_id) DO UPDATE SET
                    weight = excluded.weight, status = excluded.status,
                    provenance_json = excluded.provenance_json,
                    namespace = excluded.namespace
                """,
                (
                    edge_id(edge.from_, edge.to, edge.type.value, digest_json(provenance)),
                    edge.from_,
                    edge.to,
                    edge.type.value,
                    edge.status.value,
                    edge.weight,
                    canonical_json(provenance),
                    edge.namespace,
                ),
            )
            written += 1
        return written

    def clear_edges(self) -> None:
        """Empty the graph. Call inside a :meth:`transaction`.

        Edges are republished wholesale rather than diffed: resolution is global
        (a new document can change what an untouched document's link means), so
        "which edges changed" is not a per-document question and pretending it is
        would leave stale assertions behind (ADR-0018).
        """
        self._connection.execute("DELETE FROM edges")

    def edges_of(
        self, ref: str, types: Sequence[EdgeType] | None = None
    ) -> tuple[tuple[Edge, str], ...]:
        """Every edge incident to `ref`, paired with its direction from `ref`.

        Ordered deterministically so a traversal of an unchanged graph always
        walks it in the same order — the edge indexes make both directions cheap.
        """
        clause = ""
        params: list[Any] = []
        if types:
            placeholders = ",".join("?" * len(types))
            clause = f" AND type IN ({placeholders})"
            params = [item.value for item in types]

        outgoing = self._connection.execute(
            f"SELECT * FROM edges WHERE from_id = ?{clause} ORDER BY to_id, type, edge_id",
            [ref, *params],
        ).fetchall()
        incoming = self._connection.execute(
            f"SELECT * FROM edges WHERE to_id = ?{clause} ORDER BY from_id, type, edge_id",
            [ref, *params],
        ).fetchall()
        return (
            *((_edge_from_row(row), "out") for row in outgoing),
            *((_edge_from_row(row), "in") for row in incoming),
        )

    def all_edges(self) -> tuple[Edge, ...]:
        """The whole graph, ordered deterministically — what `mycelium export` writes.

        Ordered by identity rather than by insertion, so a bundle's `edges.jsonl`
        is a function of the snapshot and not of the order the resolver happened
        to emit assertions in (ADR-0020).
        """
        rows = self._connection.execute("SELECT * FROM edges ORDER BY edge_id").fetchall()
        return tuple(_edge_from_row(row) for row in rows)

    def edge_count(self) -> int:
        row = self._connection.execute("SELECT count(*) AS n FROM edges").fetchone()
        return int(row["n"])

    def put_vectors(self, model_id: str, vectors: Iterable[tuple[str, Sequence[float]]]) -> int:
        """Store ``(chunk_digest, vector)`` pairs for one model. In a transaction.

        Keyed ``(chunk_digest, model_id)`` per D-013, which is what makes the
        embedding stage incremental *and* model-switching non-destructive:
        identical text under the same model is already present, and a different
        model adds rows beside the old ones instead of replacing them.

        Vectors are stored as little-endian float32 — fixed width, so a row's
        length is a checkable property rather than a hope, and readable by any
        implementation of the store protocol without a Python pickle in sight.
        """
        written = 0
        for chunk_digest, vector in vectors:
            blob = struct.pack(f"<{len(vector)}f", *vector)
            self._connection.execute(
                "INSERT INTO vectors(chunk_digest, model_id, dim, vec) VALUES(?,?,?,?) "
                "ON CONFLICT(chunk_digest, model_id) DO UPDATE SET "
                "dim = excluded.dim, vec = excluded.vec",
                (chunk_digest, model_id, len(vector), blob),
            )
            written += 1
        if written:
            self._bump_vectors_generation()
        return written

    def digests_without_vectors(self, model_id: str) -> tuple[str, ...]:
        """Chunk digests this model has not embedded yet — the stage's work list.

        DISTINCT because two documents may hold byte-identical chunks; they share
        one vector, and embedding it twice would be pure waste.
        """
        rows = self._connection.execute(
            """
            SELECT DISTINCT c.chunk_digest
            FROM chunks c
            LEFT JOIN vectors v ON v.chunk_digest = c.chunk_digest AND v.model_id = ?
            WHERE v.chunk_digest IS NULL
            ORDER BY c.chunk_digest
            """,
            (model_id,),
        ).fetchall()
        return tuple(str(row["chunk_digest"]) for row in rows)

    def delete_orphan_vectors(self) -> int:
        """Drop vectors whose chunk no longer exists in the published corpus.

        Called at publication: without it the table grows monotonically with
        every edit, since chunk digests change when text does.
        """
        cursor = self._connection.execute(
            "DELETE FROM vectors WHERE chunk_digest NOT IN (SELECT chunk_digest FROM chunks)"
        )
        deleted = int(cursor.rowcount)
        if deleted:
            self._bump_vectors_generation()
        return deleted

    def vector_counts(self) -> dict[str, int]:
        """Vectors per model id — what `doctor` and the manifest report."""
        rows = self._connection.execute(
            "SELECT model_id, count(*) AS n FROM vectors GROUP BY model_id ORDER BY model_id"
        ).fetchall()
        return {str(row["model_id"]): int(row["n"]) for row in rows}

    def clear_documents(self) -> None:
        """Remove every document, chunk, and index row. Call inside a :meth:`transaction`.

        The wholesale form of :meth:`delete_document`, for the one caller that
        genuinely replaces the entire corpus: restoring a snapshot (roadmap 3.2).
        ``doc_state`` cascades; the FTS index has no foreign keys of its own, so
        it is emptied explicitly.
        """
        self._connection.execute("DELETE FROM chunks_fts")
        self._connection.execute("DELETE FROM documents")

    def put_snapshot_state(self, state: SnapshotState) -> None:
        """Record where a published snapshot can be restored from (roadmap 3.2)."""
        self._connection.execute(
            "INSERT INTO snapshot_state(snapshot_id, state_blob, created_at) VALUES(?,?,?) "
            "ON CONFLICT(snapshot_id) DO UPDATE SET state_blob = excluded.state_blob, "
            "created_at = excluded.created_at",
            (state.snapshot_id, state.state_blob, state.created_at),
        )

    def delete_snapshot_state(self, snapshot_id: str) -> None:
        """Forget a snapshot's restore pointer — garbage collection (roadmap 3.2)."""
        self._connection.execute("DELETE FROM snapshot_state WHERE snapshot_id = ?", (snapshot_id,))

    def delete_cache_entries(self, build_keys: Iterable[str]) -> int:
        """Drop build-cache rows by key, returning how many went."""
        deleted = 0
        for key in build_keys:
            cursor = self._connection.execute("DELETE FROM build_cache WHERE build_key = ?", (key,))
            deleted += cursor.rowcount
        return deleted

    def cache_put(self, build_key: str, artifact_digest: str, created_at: str) -> None:
        """Index one cached stage artifact (build key → CAS digest, spec 02 §4.2).

        Call inside a :meth:`transaction`. `created_at` is wall-clock provenance
        for the retention window snapshot GC applies at roadmap 3.2 — it never
        participates in cache identity.
        """
        self._connection.execute(
            "INSERT INTO build_cache(build_key, artifact_digest, created_at) VALUES(?,?,?) "
            "ON CONFLICT(build_key) DO UPDATE SET artifact_digest = excluded.artifact_digest, "
            "created_at = excluded.created_at",
            (build_key, artifact_digest, created_at),
        )

    def _document_title(self, doc_id: str) -> str:
        row = self._connection.execute(
            "SELECT title FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        if row is None:
            msg = f"chunk references unknown document {doc_id!r}; write the document first"
            raise StoreError(msg)
        return str(row["title"])

    # -- reads -------------------------------------------------------------

    def document_ids(self) -> tuple[str, ...]:
        """Every document id in the store, in stable (sorted) order."""
        rows = self._connection.execute("SELECT doc_id FROM documents ORDER BY doc_id").fetchall()
        return tuple(str(row["doc_id"]) for row in rows)

    def get_document(self, doc_id: str) -> Document | None:
        row = self._connection.execute(
            "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        return None if row is None else _document_from_row(row)

    def get_document_by_path(self, path: str) -> Document | None:
        row = self._connection.execute("SELECT * FROM documents WHERE path = ?", (path,)).fetchone()
        return None if row is None else _document_from_row(row)

    def get_chunk(self, anchor: str) -> Chunk | None:
        row = self._connection.execute(
            "SELECT * FROM chunks WHERE anchor = ?", (anchor,)
        ).fetchone()
        return None if row is None else _chunk_from_row(row)

    def get_chunk_by_digest(self, chunk_digest: str) -> Chunk | None:
        """Any chunk with this content digest — they are interchangeable by definition.

        The embedding stage's lookup for text it did not recompile: identical
        content has one vector, so which row supplies the text cannot matter.
        """
        row = self._connection.execute(
            "SELECT * FROM chunks WHERE chunk_digest = ? ORDER BY anchor LIMIT 1",
            (chunk_digest,),
        ).fetchone()
        return None if row is None else _chunk_from_row(row)

    def chunks_of(self, doc_id: str) -> tuple[Chunk, ...]:
        rows = self._connection.execute(
            "SELECT * FROM chunks WHERE doc_id = ? ORDER BY anchor", (doc_id,)
        ).fetchall()
        return tuple(_chunk_from_row(row) for row in rows)

    def doc_states(self) -> tuple[DocState, ...]:
        """Every document's index state, ordered by path — the dirty detector's input."""
        rows = self._connection.execute("SELECT * FROM doc_state ORDER BY path").fetchall()
        return tuple(_doc_state_from_row(row) for row in rows)

    def cache_get(self, build_key: str) -> str | None:
        """The CAS digest cached under `build_key`, or ``None`` on a miss."""
        row = self._connection.execute(
            "SELECT artifact_digest FROM build_cache WHERE build_key = ?", (build_key,)
        ).fetchone()
        return None if row is None else str(row["artifact_digest"])

    def cache_entries(self) -> tuple[CacheEntry, ...]:
        """Every build-cache row — garbage collection's view of what is retained."""
        rows = self._connection.execute(
            "SELECT build_key, artifact_digest, created_at FROM build_cache ORDER BY build_key"
        ).fetchall()
        return tuple(
            CacheEntry(
                build_key=str(row["build_key"]),
                artifact_digest=str(row["artifact_digest"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        )

    def snapshot_states(self) -> tuple[SnapshotState, ...]:
        """Every snapshot restore pointer, oldest first (ULIDs sort by mint time)."""
        rows = self._connection.execute(
            "SELECT snapshot_id, state_blob, created_at FROM snapshot_state ORDER BY snapshot_id"
        ).fetchall()
        return tuple(_snapshot_state_from_row(row) for row in rows)

    def get_snapshot_state(self, snapshot_id: str) -> SnapshotState | None:
        row = self._connection.execute(
            "SELECT snapshot_id, state_blob, created_at FROM snapshot_state WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
        return None if row is None else _snapshot_state_from_row(row)

    def counts(self) -> dict[str, int]:
        """Row counts per artifact class, for the snapshot manifest (spec 03 §7)."""
        tables = ("documents", "chunks", "symbols", "edges", "vectors")
        return {
            table: int(
                self._connection.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            )
            for table in tables
        }

    def search_vectors(
        self,
        vector: Sequence[float],
        model_id: str,
        *,
        limit: int = 50,
        filters: SearchFilters | None = None,
    ) -> tuple[SearchHit, ...]:
        """Nearest chunks by cosine similarity, best first (spec 04 §3).

        A brute-force scan, and an honest one: it is exact, so there is no recall
        cliff to tune, and it is **linear**, so it does not meet spec 04 §1's
        60 ms candidate budget beyond a few thousand chunks — 94 ms over 10 000
        (`tests/bench/test_retrieval_bench.py`). That is a limit rather than a
        crisis today, because gate G2 left hybrid opt-in (ADR-0017), so nothing
        in the shipped configuration pays it; making the vector leg fast enough
        to be a default is roadmap 3.12.

        sqlite-vec, which the spec names, is the eventual answer but not this
        one: it is a *loadable* SQLite extension, and several stock Python builds
        ship without ``enable_load_extension`` (macOS's system interpreter among
        them), which would make the default retrieval path unavailable on a
        platform this project supports.

        Filters are applied in SQL, before scoring, because spec 04 §2 requires
        every generator to pre-filter: post-filtering a top-k list silently
        returns fewer results than asked for.
        """
        filters = filters or SearchFilters()
        clauses, params = self._filter_sql(filters)
        where = "".join(f" AND {clause}" for clause in clauses)

        packed = self._pack_for(model_id)
        if packed is not None:
            ranked = self._scan_packed(packed, vector, model_id, limit, clauses, params)
            if ranked is not None:
                return self._hydrate(ranked, "chunk_digest", limit)

        # Two phases, and the split is the whole performance story. Scoring needs
        # an anchor and 1 536 bytes of vector; a `SELECT c.*` would drag every
        # chunk's full text and JSON columns into Python to rank them and then
        # throw all but `limit` away — measured at 3.5x the cost of this at
        # 10 000 chunks (`tests/bench/test_retrieval_bench.py`).
        if clauses:
            key_column = "anchor"
            scored = self._connection.execute(
                f"""
                SELECT c.anchor AS key, v.vec AS vec, v.dim AS dim
                FROM vectors v
                JOIN chunks c ON c.chunk_digest = v.chunk_digest
                JOIN documents d ON d.doc_id = c.doc_id
                WHERE v.model_id = ?{where}
                """,
                [model_id, *params],
            ).fetchall()
        else:
            # Unfiltered — the common case — reads the vectors table alone. The
            # joins exist only to *filter*, and paying for them per candidate
            # cost 113 ms against 94 ms over 10 000 chunks.
            key_column = "chunk_digest"
            scored = self._connection.execute(
                "SELECT chunk_digest AS key, vec, dim FROM vectors WHERE model_id = ?",
                (model_id,),
            ).fetchall()
        if not scored:
            return ()

        scores = _cosine_scores(vector, scored)
        best = sorted(zip(scores, range(len(scored)), strict=True), key=lambda item: -item[0])[
            :limit
        ]
        ranked = {str(scored[index]["key"]): score for score, index in best}
        return self._hydrate(ranked, key_column, limit)

    def _scan_packed(
        self,
        packed: VectorPack,
        vector: Sequence[float],
        model_id: str,
        limit: int,
        clauses: list[str],
        params: list[Any],
    ) -> dict[str, float] | None:
        """Score `vector` against the packed matrix (ADR-0026).

        Returns ``None`` when the pack cannot answer this query — a dimension it
        does not hold, or a filter whose admissible digests it does not contain —
        and the caller falls back to the SQL scan, which is slower and exactly as
        correct.
        """
        import numpy as np

        if len(vector) != packed.dim:
            msg = f"query vector has dim {len(vector)}, but the store holds dim {packed.dim}"
            raise StoreError(msg)
        query = np.asarray(vector, dtype="<f4")
        norm = float(np.linalg.norm(query))
        if norm:
            query = query / norm

        if not clauses:
            return dict(packed.best(query, limit))

        # Pre-filter in SQL as spec 04 §2 requires, but read *digests* rather than
        # blobs: the filter decides which rows may be scored, and the pack holds
        # the rows.
        where = "".join(f" AND {clause}" for clause in clauses)
        admissible = [
            str(row["chunk_digest"])
            for row in self._connection.execute(
                f"""
                SELECT DISTINCT c.chunk_digest AS chunk_digest
                FROM chunks c
                JOIN documents d ON d.doc_id = c.doc_id
                JOIN vectors v ON v.chunk_digest = c.chunk_digest
                WHERE v.model_id = ?{where}
                """,
                [model_id, *params],
            ).fetchall()
        ]
        if not admissible:
            return {}
        rows = packed.rows_of(admissible)
        if len(rows) != len(admissible):
            return None  # the pack does not hold every admissible vector
        return dict(packed.best_of_rows(query, rows, limit))

    def _hydrate(
        self, ranked: dict[str, float], key_column: str, limit: int
    ) -> tuple[SearchHit, ...]:
        """Turn ``{key: score}`` into ranked hits with their document context."""
        if not ranked:
            return ()
        placeholders = ",".join("?" * len(ranked))
        rows = self._connection.execute(
            f"""
            SELECT c.*, d.path AS doc_path, d.title AS doc_title,
                   d.trust_class AS doc_trust, d.verification_status AS doc_status
            FROM chunks c
            JOIN documents d ON d.doc_id = c.doc_id
            WHERE c.{key_column} IN ({placeholders})
            """,
            list(ranked),
        ).fetchall()

        hits = [
            SearchHit(
                chunk=_chunk_from_row(row),
                score=ranked[str(row[key_column])],
                path=str(row["doc_path"]),
                title=str(row["doc_title"]),
                trust_class=TrustClass(row["doc_trust"]),
                verification_status=VerificationStatus(row["doc_status"]),
            )
            for row in rows
        ]
        # Re-impose the ranking the second query does not preserve; ties break on
        # anchor so an identical corpus always answers in an identical order.
        # The truncation matters on the unfiltered path: two chunks with the same
        # text share one vector, so a digest can expand into several candidates.
        hits.sort(key=lambda item: (-item.score, item.chunk.anchor))
        return tuple(hits[:limit])

    def _filter_sql(self, filters: SearchFilters) -> tuple[list[str], list[Any]]:
        """The WHERE fragments shared by every candidate generator."""
        clauses: list[str] = []
        params: list[Any] = []
        if filters.namespace is not None:
            clauses.append("c.namespace = ?")
            params.append(filters.namespace)
        if filters.collection is not None:
            clauses.append("d.collection = ?")
            params.append(filters.collection)
        for column, admissible in (
            ("d.trust_class", filters.trust_classes),
            ("d.verification_status", filters.verification_statuses),
        ):
            if admissible is None:
                continue
            # Sorted so the SQL text — and therefore SQLite's statement cache
            # entry — is a function of the set, not of iteration order.
            values = sorted(member.value for member in admissible)
            placeholders = ", ".join("?" for _ in values)
            clauses.append(f"{column} IN ({placeholders})")
            params.extend(values)
        if filters.path_prefix is not None:
            clauses.append("d.path LIKE ? ESCAPE '\\'")
            params.append(_like_prefix(filters.path_prefix))
        return clauses, params

    def search_chunks(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: SearchFilters | None = None,
        prefix: bool = False,
    ) -> tuple[SearchHit, ...]:
        """Field-weighted BM25 search over the lexical index (spec 04 §3).

        Scores are returned positive and descending — SQLite's ``bm25()`` is
        negated so that "better" is larger, which is what every consumer expects.
        """
        match = fts_query(query, prefix=prefix)
        if not match:
            return ()
        clauses, params = self._filter_sql(filters or SearchFilters())
        where = "".join(f" AND {clause}" for clause in clauses)

        rows = self._connection.execute(
            f"""
            SELECT c.*, d.path AS doc_path, d.title AS doc_title,
                   d.trust_class AS doc_trust, d.verification_status AS doc_status,
                   bm25(chunks_fts, ?, ?, ?, ?) AS score
            FROM chunks_fts
            JOIN chunks c ON c.anchor = chunks_fts.anchor
            JOIN documents d ON d.doc_id = c.doc_id
            WHERE chunks_fts MATCH ?{where}
            ORDER BY score
            LIMIT ?
            """,
            # Placeholder order follows the statement: weights, MATCH, filters, limit.
            [*_BM25_WEIGHTS, match, *params, limit],
        ).fetchall()

        return tuple(
            SearchHit(
                chunk=_chunk_from_row(row),
                score=-float(row["score"]),
                path=str(row["doc_path"]),
                title=str(row["doc_title"]),
                trust_class=TrustClass(row["doc_trust"]),
                verification_status=VerificationStatus(row["doc_status"]),
            )
            for row in rows
        )


# ---------------------------------------------------------------------------
# Row ↔ record mapping
# ---------------------------------------------------------------------------


def _cosine_scores(query: Sequence[float], rows: Sequence[sqlite3.Row]) -> list[float]:
    """Cosine similarity of `query` against each row's stored vector.

    Stored vectors are unit-length by the embedder's contract, so a dot product
    *is* the cosine — but the query is normalised here anyway, because a caller
    supplying a raw vector deserves a meaningful ranking rather than a silently
    scaled one.

    NumPy is required at this point and nowhere else in the query path: it
    arrives with the embeddings extra that produced the vectors in the first
    place, so the only way to reach the failure is to uninstall it while keeping
    the rows — which the message below names precisely.
    """
    try:
        import numpy as np
    except ImportError as error:  # pragma: no cover - requires a half-uninstalled env
        msg = (
            "this store holds vectors but numpy is not installed; reinstall "
            "`mycelium-os[embeddings]`, or set `[retrieval] hybrid = false` to search "
            "lexically only"
        )
        raise StoreError(msg) from error

    dim = int(rows[0]["dim"])
    if len(query) != dim:
        msg = f"query vector has dim {len(query)}, but the store holds dim {dim}"
        raise StoreError(msg)

    flat = np.frombuffer(b"".join(bytes(row["vec"]) for row in rows), dtype="<f4")
    matrix = flat.reshape(len(rows), dim)
    vector = np.asarray(query, dtype="<f4")
    norm = float(np.linalg.norm(vector))
    if norm:
        vector = vector / norm
    return [float(value) for value in matrix @ vector]


def _doc_state_from_row(row: sqlite3.Row) -> DocState:
    graph = json.loads(row["graph_json"])
    return DocState(
        doc_id=str(row["doc_id"]),
        path=str(row["path"]),
        source_digest=str(row["source_digest"]),
        source_mtime=str(row["source_mtime"]),
        env_digest=str(row["env_digest"]),
        document_digest=str(row["document_digest"]),
        chunks_digest=str(row["chunks_digest"]),
        warnings=tuple(json.loads(row["warnings_json"])),
        links=tuple(graph.get("links", ())),
        aliases=tuple(graph.get("aliases", ())),
        headings=tuple(graph.get("headings", ())),
    )


def _edge_from_row(row: sqlite3.Row) -> Edge:
    return Edge.model_validate(
        {
            "from": row["from_id"],
            "to": row["to_id"],
            "type": EdgeType(row["type"]),
            "status": EdgeStatus(row["status"]),
            "weight": float(row["weight"]),
            "provenance": json.loads(row["provenance_json"]),
            "namespace": row["namespace"],
        }
    )


def _snapshot_state_from_row(row: sqlite3.Row) -> SnapshotState:
    return SnapshotState(
        snapshot_id=str(row["snapshot_id"]),
        state_blob=str(row["state_blob"]),
        created_at=str(row["created_at"]),
    )


def _rfc3339(value: Any) -> str:
    return str(value.isoformat().replace("+00:00", "Z"))


def _like_prefix(prefix: str) -> str:
    """Escape LIKE wildcards so a path prefix is matched literally."""
    escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"


def _document_from_row(row: sqlite3.Row) -> Document:
    return Document(
        doc_id=row["doc_id"],
        path=row["path"],
        title=row["title"],
        namespace=row["namespace"],
        collection=row["collection"],
        tags=tuple(json.loads(row["tags_json"])),
        content_digest=row["content_digest"],
        trust_class=TrustClass(row["trust_class"]),
        curated=bool(row["curated"]),
        verification_status=VerificationStatus(row["verification_status"]),
        verification=(
            None if row["verification_json"] is None else json.loads(row["verification_json"])
        ),
        provenance=json.loads(row["provenance_json"]),
        fidelity_report=row["fidelity_report"],
        secret_flags=tuple(json.loads(row["secret_flags_json"])),
        stats=json.loads(row["stats_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _chunk_from_row(row: sqlite3.Row) -> Chunk:
    lines: Sequence[int] = json.loads(row["lines_json"])
    return Chunk(
        anchor=row["anchor"],
        doc_id=row["doc_id"],
        chunk_digest=row["chunk_digest"],
        heading_path=tuple(json.loads(row["heading_path_json"])),
        kir_nodes=tuple(json.loads(row["kir_nodes_json"])),
        text=row["text"],
        tokens=row["tokens"],
        lines=(lines[0], lines[1]),
        kind=ChunkKind(row["kind"]),
        namespace=row["namespace"],
    )
