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
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Final, Self

from mycelium.sdk.identity import canonical_json
from mycelium.sdk.types import Chunk, ChunkKind, Document, TrustClass, VerificationStatus
from mycelium.store.schema import (
    DDL,
    META_SCHEMA_VERSION,
    PRAGMAS,
    SCHEMA_VERSION,
)

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

    v1's migration policy is rebuild (D-016): a Mycelium that meets a store it does
    not understand says so and points at ``mycelium build`` rather than
    reinterpreting the bytes.
    """


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Restrictions applied before ranking (spec 05 §4 `filters`)."""

    namespace: str | None = None
    collection: str | None = None
    trust_class: TrustClass | None = None
    verification_status: VerificationStatus | None = None
    path_prefix: str | None = None


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One ranked chunk, with the document context a citation needs."""

    chunk: Chunk
    score: float
    path: str
    title: str
    trust_class: TrustClass
    verification_status: VerificationStatus


def fts_query(text: str, *, prefix: bool = False) -> str:
    """Turn user text into a safe FTS5 MATCH expression.

    Query text is untrusted (D-017): every term is extracted and quoted rather
    than passed through, so FTS5 operators, unbalanced quotes, and column filters
    in a query are matched as words instead of executed as syntax. Returns an
    empty string when nothing searchable remains, which callers read as "no hits".
    """
    terms = _FTS_TERM.findall(text)
    if not terms:
        return ""
    suffix = "*" if prefix else ""
    return " ".join(f'"{term}"{suffix}' for term in terms)


class SqliteStore:
    """A SQLite-backed catalog and lexical index."""

    def __init__(self, connection: sqlite3.Connection, *, read_only: bool = False) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._read_only = read_only

    # -- lifecycle ---------------------------------------------------------

    @classmethod
    def open(cls, root: Path, *, read_only: bool = False, create: bool = True) -> Self:
        """Open the store under `root`, i.e. ``<root>/.mycelium/store.db``.

        `read_only` opens a reader that cannot write and never creates the file —
        what an agent's query path uses while a build is in flight (spec 02 §7).
        """
        path = root / STORE_DIRNAME / STORE_FILENAME
        if read_only:
            if not path.exists():
                msg = f"no store at {path}; run `mycelium build` first"
                raise StoreError(msg)
            uri = f"file:{path.as_posix()}?mode=ro"
            connection = sqlite3.connect(uri, uri=True, isolation_level=None)
        else:
            if not path.exists() and not create:
                msg = f"no store at {path}; run `mycelium build` first"
                raise StoreError(msg)
            path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(path, isolation_level=None)

        store = cls(connection, read_only=read_only)
        store._configure()
        if not read_only:
            store._migrate()
        store._check_version()
        return store

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
        self._connection.close()

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
            raise
        self._connection.execute("COMMIT")

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
        """Remove a document and everything derived from it."""
        anchors = self._connection.execute(
            "SELECT anchor FROM chunks WHERE doc_id = ?", (doc_id,)
        ).fetchall()
        for row in anchors:
            self._connection.execute("DELETE FROM chunks_fts WHERE anchor = ?", (row["anchor"],))
        self._connection.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))

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

    def chunks_of(self, doc_id: str) -> tuple[Chunk, ...]:
        rows = self._connection.execute(
            "SELECT * FROM chunks WHERE doc_id = ? ORDER BY anchor", (doc_id,)
        ).fetchall()
        return tuple(_chunk_from_row(row) for row in rows)

    def counts(self) -> dict[str, int]:
        """Row counts per artifact class, for the snapshot manifest (spec 03 §7)."""
        tables = ("documents", "chunks", "symbols", "edges", "vectors")
        return {
            table: int(
                self._connection.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            )
            for table in tables
        }

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
        filters = filters or SearchFilters()
        clauses: list[str] = []
        params: list[Any] = []
        if filters.namespace is not None:
            clauses.append("c.namespace = ?")
            params.append(filters.namespace)
        if filters.collection is not None:
            clauses.append("d.collection = ?")
            params.append(filters.collection)
        if filters.trust_class is not None:
            clauses.append("d.trust_class = ?")
            params.append(filters.trust_class.value)
        if filters.verification_status is not None:
            clauses.append("d.verification_status = ?")
            params.append(filters.verification_status.value)
        if filters.path_prefix is not None:
            clauses.append("d.path LIKE ? ESCAPE '\\'")
            params.append(_like_prefix(filters.path_prefix))
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
