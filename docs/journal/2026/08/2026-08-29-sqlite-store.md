# 2026-08-29 — SQLite store (roadmap 2.6)

- **Session scope:** roadmap item 2.6 — SQLite store: DDL, WAL, field-weighted FTS5, meta
  table (spec 03 §8).
- **PR:** #19 (`feat/sqlite-store`), one item, one PR. Follows #18 (2.5), merged.

## What got done

- `src/mycelium/store/` — three modules: `base.py` (the `Store` protocol), `schema.py`
  (DDL + pragmas + schema version), `sqlite.py` (the implementation).
- WAL, `synchronous=NORMAL`, `foreign_keys=ON`, 5 s busy timeout; `read_only=True` opens a
  reader that cannot write, which is what an agent uses while a build is in flight.
- Field-weighted FTS5 exactly per spec 04 §3 (title 3.0, heading_path 2.0, body 1.0,
  unicode61, prefix index), with BM25 scores negated so higher means better.
- Meta-table schema versioning: a store written by another version raises and names
  `mycelium build` rather than being reinterpreted (D-016).
- **ADR-0008** records the decisions; patterns catalogue gains **Repository** and
  **Data Mapper**.
- Tests: 268 passing, 42 for this item. Benchmarks on 1 000 chunks: search ≈ 1.2 ms,
  point lookup ≈ 36 µs, 100-chunk write ≈ 26 ms.

## The two questions the spec left open

Both were flagged at the end of 2.5 and both turned out to be real:

- **"Replaceable" needed a definition.** Spec 02 §10 calls SQLite a secondary store
  component, explicitly replaceable — which is worth nothing unless something states what a
  replacement must do. `store/base.py` is that statement, and `isinstance(store, Store)` is
  asserted in the suite, so an implementation that drifts fails a test rather than a review.
- **The spec's DDL is abbreviated.** As listed, `documents` cannot hold a `Document`
  record: no `verification_status`, which retrieval is contractually required to expose on
  every result. Completed with the five columns a lossless round-trip needs, and the
  round-trip is now a test.

The FTS line (`FTS5(content=chunks.text, title, heading_path)`) describes an
external-content index over columns living in two tables, which SQLite cannot express. A
standalone FTS5 table is the honest reading; the cost is a second copy of chunk text in the
index, which is bounded and rebuildable.

## Worth remembering

`Connection.executescript` **commits any open transaction before it runs**, so wrapping the
DDL in a transaction leaves you committing one that is already closed — which is exactly
the error the first test run produced. The DDL now runs outside our transaction on purpose,
with a comment so nobody "fixes" it back.

## Where the project stands

- Milestone 2: 2.1–2.6 ✅ · 2.7–2.13 open. Source → KIR → chunks → store now works end to
  end; what is missing is the thing that makes it a *build*.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (268 passed), `python tools/consistency_lint.py`.

## How the next session resumes

- Wait for PR #19 to merge, then start **2.7** — the build orchestrator: sequential v0,
  snapshot manifest, atomic `CURRENT` swap, single-writer lock. Size L, route
  frontier-reasoning / high, and marked *sets-pattern* in the roadmap: the publication and
  crash-safety semantics chosen there bind every later phase, so it deserves more care than
  its line count suggests.
- What 2.6 leaves it: `meta` for the current-snapshot pointer, and a transaction that takes
  the write lock at `BEGIN IMMEDIATE`. What 2.7 must add: the `.mycelium/lock` advisory
  file (pid + host + heartbeat, stale takeover), `snapshots/<ulid>.json`, and the
  `CURRENT.tmp` → rename → fsync dance — which differs on Windows (`ReplaceFile`), and the
  CI matrix will hold us to it.
