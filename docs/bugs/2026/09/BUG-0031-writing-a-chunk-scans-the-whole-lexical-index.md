---
id: BUG-0031
title: writing a chunk scans the whole lexical index, so a build is quadratic in corpus size
status: confirmed
severity: high
reporter: internal
discovered: 2026-09-17
affected-versions: ">=0.1.0"
---

# BUG-0031: writing a chunk scans the whole lexical index, so a build is quadratic in corpus size

## Summary

`SqliteStore.put_chunks` deletes the chunk's row from `chunks_fts` before inserting it.
`anchor` is declared `UNINDEXED` in that FTS5 table, so SQLite answers
`DELETE FROM chunks_fts WHERE anchor = ?` with a **full scan of the index**. The delete
runs once per chunk, so writing a corpus of *N* chunks costs O(*N*²) — and the compiler
writes every chunk of every changed document through this path on every build.

Measured: writing a thousand chunks into an empty store takes 2.7 s, and writing the
thousand after nine thousand others takes **68 s**. Extrapolated to the 10⁵-chunk
reference profile spec 04 §1 states its budgets against, loading it once is about **nine
hours**, which is why that corpus had never been built.

## Environment

- **Affected versions:** every release. `chunks_fts` has had an `UNINDEXED` anchor column
  and `put_chunks` its delete since the store was adopted (roadmap 2.6, ADR-0008).
- **Toolchain / platform:** any; nothing here is platform-specific.
- **Configuration:** unconditional — the lexical index is the shipped default (ADR-0017).

## Reproduction

Found by roadmap 6.4 while building the reference profile. Write chunks into a store in
batches of a thousand and time each batch:

```text
after   1000 chunks: 1000 chunks written in   2.67 s  =  2.67 ms/chunk
after   2000 chunks: 1000 chunks written in  10.10 s  = 10.10 ms/chunk
after   5000 chunks: 1000 chunks written in  35.82 s  = 35.82 ms/chunk
after  10000 chunks: 1000 chunks written in  68.14 s  = 68.14 ms/chunk
```

The per-chunk cost is linear in what is already there — ~0.0068 ms per resident chunk —
which is the signature of a scan per write. The query planner says so directly:

```text
sqlite> EXPLAIN QUERY PLAN DELETE FROM chunks_fts WHERE anchor = 'x';
SCAN chunks_fts VIRTUAL TABLE INDEX 0:
```

## Expected vs. actual

- **Expected:** writing a chunk costs the same whether the store holds a hundred chunks or
  a hundred thousand.
- **Actual:** it costs time proportional to the number of chunks already stored.

## Root cause

An FTS5 table has no ordinary indexes, and a column declared `UNINDEXED` is not searchable
through the full-text index either — it is stored and nothing more. So the only way to find
the row for an anchor is to read every row. `put_chunks` issues that delete for **every**
chunk, including the overwhelmingly common case of a chunk that is not in the index yet,
where it has nothing to remove.

The delete itself is not wrong: `chunks` upserts on its anchor, and without the delete a
rewritten chunk would leave its old text in the lexical index, so `chunks` and `chunks_fts`
would disagree about what exists — which the method's own docstring says it exists to
prevent.

## Impact

- The cold build is superlinear in corpus size. At 998 documents / 4 939 chunks this term
  alone is ~83 s of a 193.5 s build (roadmap 6.19) against a 60 s budget.
- The 10⁵-chunk reference profile cannot be compiled in practice, so the one condition
  NFR-2 states its budget against was unreachable until this is fixed. Roadmap 6.4
  measured the query path on a store loaded by plain SQL instead, and says so.
- Nothing is *incorrect*: the index it produces is right. This is cost, not corruption.

## Fix

Not fixed here — roadmap 6.19 owns it, and the choice wants an argument rather than a
patch. The candidates, cheapest first: make `chunks_fts` an **external-content** table over
`chunks` so deletion is by `rowid`; or keep the content table and give the FTS row the same
`rowid` as its `chunks` row, deleting by `rowid` (indexed) instead of by `anchor`; or ask
`chunks` — an indexed lookup — whether the anchor exists and issue the delete only then,
which fixes the common case and leaves the rewrite case as it is. The first two change the
lexical schema, which bumps the store version *and* moves `retrieval_identity()`, so gate
G2's verdict has to be re-recorded with them (ADR-0068, ADR-0084); the third does not touch
the schema at all.

## References

- `src/mycelium/store/sqlite.py` — `put_chunks`; `src/mycelium/store/schema.py` — the
  `chunks_fts` DDL.
- `docs/benchmarks/2026-09-17-reference-profile.md` — where it was found, and what it costs.
- [ADR-0120](../../../adr/0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md);
  roadmap 6.4, 6.19.
- Sibling in kind, not in cause: [BUG-0028](BUG-0028-the-private-key-secret-rule-scans-quadratically.md),
  the other quadratic this project has found.
