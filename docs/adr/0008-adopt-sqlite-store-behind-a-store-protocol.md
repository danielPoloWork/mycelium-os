# ADR-0008: Keep SQLite behind a store protocol, and index lexically in a standalone FTS5 table

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §8, spec 02 §10
- **Related:** [ADR-0004](0004-adopt-pydantic-v2-record-contracts.md),
  [ADR-0007](0007-adopt-structure-first-chunking.md); spec 02 §3 (on-disk layout), §7
  (concurrency), §10 (stable contracts); spec 03 §8; spec 04 §3; D-005, D-013, D-015,
  D-016, D-017, D-019; roadmap 2.6

## Context

Roadmap 2.6 is the first module that owns state on disk. Everything before it was a pure
function; from here on there is a file that outlives the process, and two claims in the
specification suddenly have to be made true rather than asserted. Spec 02 §10 calls SQLite
a *secondary store component*, "explicitly replaceable" — a claim worth nothing unless
something states what a replacement must do. And RFC-0001's migration policy says a
Mycelium meeting a store it does not understand "must say so and offer `mycelium build` —
never reinterpret silently", which needs a version to check.

Spec 03 §8 gives the DDL in abbreviated form, and spec 04 §3 fixes the lexical
configuration exactly: FTS5 BM25, field-weighted title 3.0 / heading_path 2.0 / body 1.0,
unicode61 with prefix support. The abbreviation is where the open questions live: the
`documents` table as listed cannot hold a `Document` record (it has no
`verification_status`, which retrieval is contractually required to expose), and the FTS
line — `FTS5(content=chunks.text, title, heading_path)` — describes an external-content
index over columns that live in two different tables.

## Decision

**SQL stays inside `mycelium.store`.** A `Store` protocol (`store/base.py`) states every
operation the compiler and serving layer need, in records rather than rows; `SqliteStore`
implements it, and row↔record mapping is confined to two functions. The platform-phase
store (D-019) implements the same protocol and nothing else changes.

**The store is `<root>/.mycelium/store.db`** (spec 02 §3), opened with WAL,
`synchronous=NORMAL`, `foreign_keys=ON`, and a 5 s busy timeout. WAL is what lets agents
query during a build (D-015). `NORMAL` is right because the store is derived and disposable
(D-005): it already survives process crashes, and only an OS crash could lose a
transaction — whose repair is `mycelium build`, which is also the repair for every other
corruption. `read_only=True` opens a reader that cannot write and never creates a file.

**The lexical index is a standalone FTS5 table**, not external-content: its indexed columns
come from two tables (`title` from `documents`, `heading_path` from a chunk's JSON), which
external content cannot express. It is written in the same call that writes chunks, so the
two cannot disagree about what exists. BM25 scores are negated on the way out, because
SQLite returns "better" as more negative and every consumer expects the opposite.

**Query text is data.** `fts_query` extracts word characters and quotes each term, so FTS5
operators, unbalanced quotes, and column filters inside a query are matched as words
instead of executed (D-017). Untrusted input is the rule for content; a query is no
different.

**The schema version lives in `meta` and is checked on open.** A store written by a
different version raises `StoreVersionError` naming `mycelium build` (D-016).

**The `documents` DDL is completed** past the spec's abbreviation so a `Document` record
round-trips without loss: `verification_status`, `verification_json`, `tags_json`,
`fidelity_report`, `secret_flags_json`. JSON columns are written in canonical form
(ADR-0005), so two stores built from the same sources hold byte-identical values.

## Alternatives Considered

- **External-content FTS5** (`content='chunks'`) — no duplicated text, the spec's apparent
  intent. Rejected: an external-content table's columns must be columns of the content
  table, and two of the three indexed fields are not. The cost is a second copy of chunk
  text in the index, which is bounded and rebuildable.
- **Storing whole records as JSON blobs with a few indexed projections** — trivially
  lossless round-trips. Rejected: it duplicates every field, lets the projections drift
  from the blob, and abandons the relational shape the spec describes. Explicit columns are
  the contract; the JSON columns that remain are the ones the spec itself denormalizes.
- **An ORM (SQLAlchemy)** — migrations, portability, less hand-written SQL. Rejected: a
  heavyweight dependency for a fixed schema of eight tables, and its migration machinery
  solves a problem v1 does not have (the migration policy is rebuild, D-016).
- **`synchronous=FULL`** — durability against OS crashes. Rejected: a large write cost to
  protect data whose recovery procedure is a rebuild that must work anyway.
- **A separate search engine (Tantivy, OpenSearch)** — better ranking features. Rejected
  for v1 by D-005: SQLite with FTS5 is the engine, and the store protocol is what keeps
  that decision reversible at the platform phase.
- **Tag filtering now**, via a `document_tags` join table. Deferred, not rejected: tags
  round-trip today but are not indexed for filtering. Adding the table when
  `mycelium_search` needs it (2.9) costs nothing, because a rebuild is how every schema
  change lands.

## Consequences

- Nothing outside `mycelium.store` may hold a cursor, a row, or a SQL string. The protocol
  is the boundary that makes "replaceable" testable — `isinstance(store, Store)` is
  asserted, so an implementation that drifts fails a test rather than a review.
- `Connection.executescript` commits any open transaction before it runs, so the DDL runs
  outside our transaction on purpose. Every statement is `IF NOT EXISTS` and the script is
  re-runnable; the comment in `_migrate` exists so nobody "fixes" it back.
- Chunks require their document to exist first — enforced by a foreign key *and* by an
  explicit error naming the missing document, because the FK message alone is unhelpful.
- `vectors` exists but is empty and unused: sqlite-vec owns it from roadmap 3.3. Its
  `(chunk_digest, model_id)` key is fixed now so unchanged text never re-embeds and
  switching models adds rows rather than destroying them (D-013).
- Snapshot publication, the `CURRENT` pointer, and the advisory single-writer lock are
  *not* here (roadmap 2.7). What the store provides toward them is `meta` and a transaction
  that takes the write lock at `BEGIN IMMEDIATE`.
- Benchmarks on 1 000 chunks: search ≈ 1.2 ms, point lookup ≈ 36 µs, a 100-chunk write
  ≈ 26 ms — inside the 60 ms lexical stage budget at this scale, with the real measurement
  due against the 10⁵-chunk reference profile (roadmap 3.7).

## References

- Spec: `.draft-specs/02-architecture.md` §3, §7, §10 · `.draft-specs/03-data-model.md` §8 ·
  `.draft-specs/04-retrieval-and-evaluation.md` §3
- Decision log: D-005 (SQLite as engine), D-013 (vector keying), D-015 (concurrency),
  D-016 (rebuild migration), D-017 (untrusted input), D-019 (platform phase)
- Patterns: Repository, Data Mapper (`docs/patterns/README.md`)
