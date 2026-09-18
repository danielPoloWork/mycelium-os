# 2026-09-19 — the quadratic, and what was under it (roadmap 6.19)

- **Session scope:** roadmap 6.19 — fix BUG-0031, then profile what is left before touching it.
- **PR:** #167 (`perf/quadratic-chunk-writes`). Follows #166, merged as `de02922`.
- **Milestone 6:** 6.19 closed; 6.30 and 6.31 filed from its profile.
- **Decision it records:** [ADR-0132](../../../adr/0132-address-the-lexical-index-by-rowid-and-profile-what-is-left.md).

## The bug record was wrong about the fix I chose, and checking was the first task

BUG-0031 listed three candidates and said the first two *"change the lexical schema, which
bumps the store version **and** moves `retrieval_identity()`, so gate G2's verdict has to be
re-recorded"*. That is a heavy price: re-recording G2 needs the 133 MB embedding model, so it
is a task only one machine can finish.

It is true of the first candidate and false of the second. `retrieval_identity()` digests the
`chunks_fts` **statement** — ADR-0084 changed it from the store's schema version for exactly
this reason — and aligning the FTS rowids with the chunks rowids changes no DDL at all. I
checked rather than inferred: `sha256:44bb6f6c…` before the change and after it.

So the expensive-looking candidate was the cheap one, and the record now carries the
correction beside the sentence that was wrong, rather than a tidied list.

## The fix

A `chunks_fts` row carries the `rowid` of the `chunks` row it indexes. The upsert returns it,
`INSERT OR REPLACE` writes at it, and the per-chunk `DELETE` is **gone** rather than made
cheap — a chunk's index row *is* the row at its rowid, which is the guarantee the delete
existed for. `delete_document` became one statement over a rowid subquery instead of a loop,
which matters because that is the path every rebuild takes.

| | before | after |
|---|---:|---:|
| cold build, 1 000 documents | 193.5 s | **91.7 s** |
| per document at 250 / 1 000 | 134 / 194 ms | **93 / 92 ms** |
| six batches of 1 000 chunks | 14.70 s | **0.85 s** |
| delete a 20-chunk document from 20 000 | 339 ms | **1 ms** |

The total halving is the visible part. The part that matters is the second row: the cost per
document stopped growing, so the build is linear in the corpus and a number at a size nobody
has run can be reasoned about. The 60 s budget is still missed, by 1.5× where it was 3.2×.

The store version bumps v6 → v7 and it is the first bump here that changes no schema: what
moved is an invariant *between* two tables, and a store written earlier holds rowids that mean
nothing.

## The profile said the item's own guess was wrong

6.19 predicted the remainder would be across *"parse, chunk, tree-sitter extraction and graph
resolution"*. Graph resolution: **0 %**. Tree-sitter extraction: **0 %**.

What is actually left, measured directly rather than read off the profiler:

- **~79 s of the 91.7 s is writing files.** 2 995 content-addressed blobs — three per document
  — at 26.4 ms each. A plain 4 KiB write costs 12.6 ms on this machine, which is the scanner;
  the atomic ceremony (temp file, fsync, rename) doubles it, which is ours.
- **~7.4 s is the Porter stemmer**, 620 293 word occurrences over 10 339 distinct words.

## The methodological finding, which I nearly published as a number

The profiler said stemming was 22 % of the build. I almost wrote that down. Measured on its
own it is 8 %.

cProfile charges per call, so it inflates whatever makes many small ones — the stemmer makes
14.3 million inner calls — and flattens whatever makes few large ones, like three thousand
file operations that turn out to be most of the build. The shares are a *hint about where to
point a measurement*, and this project has been here before: ADR-0026 is the precedent where
the cost everyone assumed was the vector arithmetic turned out to be reading the vectors row
by row, which is why the item said to profile before touching anything.

Every number in the report is now a direct measurement. The profile is in the manifest,
labelled as what it is.

## Two things I did not do

Neither finding is fixed here, which is the item's own instruction and the discipline 6.4 used
when it filed six items rather than six patches. 6.30 is the atomic ceremony and it has a real
question inside it — what durability does a *derived* store owe, when its recovery story is
`mycelium build`? 6.31 is the stemmer cache, which is small and safe and worth ~7 s.

## The benchmark I had to throw away

The first pass reported 124.5 s where a quiet machine reports 91.7. I had run `mypy --strict`
and `ruff` alongside it, in the same minutes it was timing a build. The 2026-09-17 report
records this exact lesson — *"a contended benchmark is not a slow benchmark, it is a wrong
one"* — and I relearned it within a day of reading it. The run was killed and redone with the
machine idle.

## Lesson

A profiler tells you where to look, and a measurement tells you what is there. The two
disagreed by a factor of three on the first thing I looked at, and the one that was wrong was
the one that came with percentages already attached.
