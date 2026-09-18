---
id: BUG-0031
title: writing a chunk scans the whole lexical index, so a build is quadratic in corpus size
status: fixed
severity: high
reporter: internal
discovered: 2026-09-17
affected-versions: ">=0.1.0"
fixed-in: "0.6.0"
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

**Fixed at roadmap 6.19 (ADR-0132), by the second candidate** — and one thing this record
said about it was wrong, which is worth keeping rather than editing away.

A `chunks_fts` row now carries the `rowid` of the `chunks` row it indexes. The upsert hands
that rowid back (`RETURNING rowid`), the index row is written at it, and `INSERT OR REPLACE`
does in one seek what a full scan and an insert did in two statements — so the delete is
**gone** rather than made cheap. `delete_document` became a single statement over a rowid
subquery instead of a per-anchor loop.

Measured on the machine of record: six batches of a thousand chunks cost 14.70 s by anchor
and **0.85 s** by rowid, and the second number is flat where the first grows with everything
already stored. Deleting a twenty-chunk document from a twenty-thousand-chunk store went
from 339 ms to **1 ms**. The 1 000-document cold build went from 193.5 s to **91.7 s**, and
its throughput stopped degrading: 93 ms per document at 250 and 92 at 1 000, against 134 and
194 before.

**The correction.** The candidate list above says the first two options move
`retrieval_identity()` and stale gate G2's verdict. That is true of the first and **not of
the second**: `retrieval_identity()` digests the `chunks_fts` *statement*, not the store's
schema version (ADR-0084 separated exactly these two), and aligning the rowids changes no
DDL at all. Verified rather than assumed — the digest is byte-identical across the fix,
`sha256:44bb6f6c…`. The store version still bumps, v6 → v7, because a store written earlier
holds rowids that mean nothing and has to be rebuilt; that is the first bump in this
project's history that changes no schema, and it is why the two versions are separate
questions.

The third candidate — ask `chunks` whether the anchor exists, and delete only then — would
have fixed the cold build and left `delete_document` quadratic, which is the path every
*rebuild* takes.

## References

- `src/mycelium/store/sqlite.py` — `put_chunks`; `src/mycelium/store/schema.py` — the
  `chunks_fts` DDL.
- `docs/benchmarks/2026-09-17-reference-profile.md` — where it was found, and what it costs.
- `docs/benchmarks/2026-09-19-the-quadratic-in-the-lexical-index.md` — the fix measured, and
  the profile of what the build spends its time on now that this is gone.
- [ADR-0120](../../../adr/0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md),
  [ADR-0132](../../../adr/0132-address-the-lexical-index-by-rowid-and-profile-what-is-left.md);
  roadmap 6.4, 6.19.
- Sibling in kind, not in cause: [BUG-0028](BUG-0028-the-private-key-secret-rule-scans-quadratically.md),
  the other quadratic this project has found.
