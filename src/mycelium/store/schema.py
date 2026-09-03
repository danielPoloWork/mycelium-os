# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Store DDL and connection settings (spec 03 §8).

The schema is an *implementation detail* of the store component, deliberately
replaceable (spec 02 §10): nothing outside :mod:`mycelium.store` may depend on
these table shapes, and every record crossing the boundary is a
:mod:`mycelium.sdk.types` record instead.

Denormalized JSON columns (``provenance_json``, ``stats_json``,
``heading_path_json``, ``lines_json``) are deliberate: every row is a build
artifact rebuilt from source, so there is no update path along which an anomaly
could appear (RFC-0001, Data & schema). They are written in canonical form, so
two stores built from the same sources hold byte-identical column values.
"""

from typing import Final

SCHEMA_VERSION: Final = "mycelium/store/v4"
"""Bumped whenever the DDL below changes. v1 migration policy is rebuild (D-016):
a *writer* that meets a foreign version recreates the file (the store is derived
data, D-005 — ADR-0015); a *reader* refuses and points at `mycelium build`.
History: v0 → v1 added `doc_state` (roadmap 3.1, incremental builds);
v1 → v2 added `snapshot_state` (roadmap 3.2, restorable snapshots);
v2 → v3 added `doc_state.graph_json` (roadmap 3.4, the authored link graph);
v3 → v4 added the stem columns to `chunks_fts` (roadmap 4.19, ADR-0048) — a
tokenization change is not migratable, so this is exactly the case the rebuild
policy exists for."""

META_SCHEMA_VERSION: Final = "schema_version"
META_VECTORS_GENERATION: Final = "vectors_generation"
"""Bumped by every write to `vectors`; names the packed matrix (ADR-0026)."""
META_CURRENT_SNAPSHOT: Final = "current_snapshot"

PRAGMAS: Final = (
    # Concurrent readers during a build, which is the whole point (D-015).
    "PRAGMA journal_mode=WAL",
    # WAL already survives process crashes; FULL only guards OS crashes, at a
    # large write cost on a store that is disposable by design (D-005).
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=ON",
    # A writer that finds the lock taken waits rather than failing instantly;
    # the real single-writer discipline is the advisory lock (roadmap 2.7).
    "PRAGMA busy_timeout=5000",
)

DDL: Final = """
-- Spec 03 §8 lists this table in abbreviated form; every field of the Document
-- record has a column here, so a record round-trips through the store unchanged
-- (ADR-0008). `verification_status` in particular is not optional: retrieval is
-- contractually required to expose it on every result.
CREATE TABLE IF NOT EXISTS documents (
    doc_id              TEXT PRIMARY KEY,
    path                TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    namespace           TEXT NOT NULL DEFAULT 'default',
    collection          TEXT,
    tags_json           TEXT NOT NULL,
    trust_class         TEXT NOT NULL,
    curated             INTEGER NOT NULL DEFAULT 0,
    verification_status TEXT NOT NULL,
    verification_json   TEXT,
    content_digest      TEXT NOT NULL,
    provenance_json     TEXT NOT NULL,
    fidelity_report     TEXT,
    secret_flags_json   TEXT NOT NULL,
    stats_json          TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS documents_namespace ON documents(namespace);
CREATE INDEX IF NOT EXISTS documents_collection ON documents(collection);

CREATE TABLE IF NOT EXISTS chunks (
    anchor            TEXT PRIMARY KEY,
    doc_id            TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_digest      TEXT NOT NULL,
    heading_path_json TEXT NOT NULL,
    kir_nodes_json    TEXT NOT NULL,
    text              TEXT NOT NULL,
    tokens            INTEGER NOT NULL,
    kind              TEXT NOT NULL,
    lines_json        TEXT NOT NULL,
    namespace         TEXT NOT NULL DEFAULT 'default'
);
CREATE INDEX IF NOT EXISTS chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS chunks_digest ON chunks(chunk_digest);

-- Field-weighted lexical index (spec 04 §3). `anchor` is stored but not indexed,
-- so a hit maps back to its chunk without polluting the term statistics. The
-- prefix index serves identifier-like queries; unicode61 keeps CJK terms intact.
--
-- The three `_stem` columns hold the same text reduced to Porter stems, so a
-- query that inflects a word differently from the document still reaches it —
-- `signs` finds `signed` (roadmap 4.19). They are *additional* columns rather
-- than a `porter` tokenizer on the existing ones, because replacing the surface
-- form costs the literal match its edge: a document containing the query's exact
-- word matches both a surface column and a stem column, one containing only an
-- inflection matches a stem column alone, and the field weights do the rest
-- (ADR-0048). The stems live in this table rather than a second one so there is
-- one BM25 computation and no fusion stage to tune.
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    anchor UNINDEXED,
    text,
    title,
    heading_path,
    text_stem,
    title_stem,
    heading_path_stem,
    tokenize='unicode61',
    prefix='2 3 4'
);

-- sqlite-vec owns this table from roadmap 3.3; the DDL exists now so the schema
-- is whole and `(chunk_digest, model_id)` keying is fixed from the start (D-013):
-- unchanged text never re-embeds, and switching models adds rows instead of
-- destroying them.
CREATE TABLE IF NOT EXISTS vectors (
    chunk_digest TEXT NOT NULL,
    model_id     TEXT NOT NULL,
    dim          INTEGER NOT NULL,
    vec          BLOB NOT NULL,
    PRIMARY KEY (chunk_digest, model_id)
);

CREATE TABLE IF NOT EXISTS symbols (
    symbol        TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    defined_in    TEXT NOT NULL,
    doc_refs_json TEXT NOT NULL,
    namespace     TEXT NOT NULL DEFAULT 'default'
);

CREATE TABLE IF NOT EXISTS edges (
    edge_id         TEXT PRIMARY KEY,
    from_id         TEXT NOT NULL,
    to_id           TEXT NOT NULL,
    type            TEXT NOT NULL,
    status          TEXT NOT NULL,
    weight          REAL NOT NULL DEFAULT 1.0,
    provenance_json TEXT NOT NULL,
    namespace       TEXT NOT NULL DEFAULT 'default'
);
CREATE INDEX IF NOT EXISTS edges_from ON edges(from_id, type);
CREATE INDEX IF NOT EXISTS edges_to ON edges(to_id, type);

CREATE TABLE IF NOT EXISTS build_cache (
    build_key       TEXT PRIMARY KEY,
    artifact_digest TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

-- What the index currently holds per document, in build-key terms: the dirty
-- detector's ground truth (roadmap 3.1, ADR-0015). One row per *indexed*
-- document — quarantined documents have no row and are re-attempted every
-- build. Deleting the document cascades the row, so the two can never disagree.
CREATE TABLE IF NOT EXISTS doc_state (
    doc_id          TEXT PRIMARY KEY REFERENCES documents(doc_id) ON DELETE CASCADE,
    path            TEXT NOT NULL UNIQUE,
    source_digest   TEXT NOT NULL,
    source_mtime    TEXT NOT NULL,
    env_digest      TEXT NOT NULL,
    document_digest TEXT NOT NULL,
    chunks_digest   TEXT NOT NULL,
    warnings_json   TEXT NOT NULL,
    -- This document's contribution to the link graph: the references it makes,
    -- the aliases it answers to, and its heading slugs (roadmap 3.4). Edge
    -- *resolution* is global — a wikilink's meaning depends on every other
    -- document — so these are kept per document and re-resolved every build,
    -- which is what keeps extraction cached while the graph stays correct.
    graph_json      TEXT NOT NULL DEFAULT '{}'
);

-- What each published snapshot contained, as one CAS pointer per snapshot
-- (roadmap 3.2, ADR-0016). The blob is the snapshot's whole `doc_state` table in
-- canonical JSON, so a snapshot can be *restored* — not merely named — and
-- `mycelium gc` has a defined live set: a blob is garbage exactly when no
-- retained snapshot's state and no retained cache row points at it.
--
-- One row and one (deduplicated) blob per snapshot, deliberately not one row per
-- document per snapshot: publication stays O(changed) writes, and a rebuild that
-- changed nothing re-addresses the identical blob instead of writing anything.
CREATE TABLE IF NOT EXISTS snapshot_state (
    snapshot_id TEXT PRIMARY KEY,
    state_blob  TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""
