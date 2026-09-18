# Benchmark Report: the quadratic in the lexical index, and what the build spends its time on now

- **Date:** 2026-09-19
- **Version / commit:** v0.5.0 @ `de02922`, with roadmap 6.19's fix
- **Environment:** see [`manifests/2026-09-19-the-quadratic-in-the-lexical-index.json`](manifests/2026-09-19-the-quadratic-in-the-lexical-index.json) — the machine of record, as in the [reference-profile report](2026-09-17-reference-profile.md)
- **Command:** `python tools/benchmark_reference_profile.py --out <dir> --scales 250,1000 --no-reference --profile 1000`
- **Roadmap:** 6.19 · **Decision:** [ADR-0132](../adr/0132-address-the-lexical-index-by-rowid-and-profile-what-is-left.md) · **Defect:** [BUG-0031](../bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md)

## Scenario

The [reference profile](2026-09-17-reference-profile.md) measured a 1 000-document cold build
at **193.5 s** against spec 01 §8's 60 s, and found that the cost per document *grew* with the
corpus — 134 ms at 250 documents, 194 at 998. Something was superlinear, and
[BUG-0031](../bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md) named
it: every chunk written deleted its own row from `chunks_fts` first, by an `UNINDEXED` column,
which SQLite answers with a full scan of the index.

Roadmap 6.19 asked for two things. Fix that. Then **profile what is left before touching any
of it** — because ADR-0026 is the precedent where the cost everyone assumed was the vector
arithmetic turned out to be reading the vectors row by row.

Both are here, and the second is the more interesting: the item's own guess about where the
remaining time went was wrong.

**Method.** Same generator, same seed, same machine as the 2026-09-17 report, so the before
and after are comparable. The profiled build is a *separate* invocation from the timed one, so
no published number carries the profiler's overhead. Everything was taken on an otherwise idle
machine — an earlier pass of this very measurement was contaminated by a type-check running
alongside it and reported 124.5 s where a quiet machine reports 91.7 s, which is the same
lesson the 2026-09-17 report recorded and promptly had to relearn.

## Results

### The quadratic, at the two scales the budget is stated near

| Corpus | Before (2026-09-17) | After | Per document, before → after |
|---|---:|---:|---:|
| 250 documents / 1 249 chunks | 33.5 s | **23.2 s** | 134 ms → **93 ms** |
| 1 000 documents / 4 929 chunks | 193.5 s | **91.7 s** | 194 ms → **92 ms** |

**The number to read is not the total, it is the last column.** Before, the cost per document
grew by 45 % between the two scales; now it is flat — 93 ms and 92 ms. That is the quadratic
gone, and it is the property that makes the total mean something at a size nobody has measured.

In isolation, the same change: six batches of a thousand chunks cost **14.70 s** written by
anchor and **0.85 s** written by rowid, with the second flat where the first grows. Deleting a
twenty-chunk document from a twenty-thousand-chunk store went from **339 ms to 1 ms**.

**The budget is still missed**, by 1.5× where it was missed by 3.2×. What follows is where the
remaining 91.7 s goes.

### Where the build spends its time now

The compiler's own stage timers, from the manifest each build writes:

| Stage | 250 documents | 1 000 documents |
|---|---:|---:|
| compile | 80 % | **82 %** |
| store | 13 % | 14 % |
| plan | 3 % | 3 % |
| discover | 3 % | 0 % |
| graph | 0 % | 0 % |
| symbols | 0 % | 0 % |

The item expected the remainder across *"parse, chunk, tree-sitter extraction and graph
resolution"*. Graph resolution and symbol extraction are **0 %** each.

### What `compile` is actually doing

Directly measured, not read off the profiler:

| Measurement | Cost |
|---|---:|
| `atomic_write_bytes`, 4 KiB (temp file + fsync + rename) | **26.4 ms** mean, 19.4 ms p50 |
| a plain `open`/`write`/`close` of the same bytes | **12.6 ms** mean |
| the atomic ceremony, over a plain write | **13.8 ms** (2.1×) |
| three `cas_put` per document × 1 000 documents, at that rate | **~79 s** |

A cold build of a thousand documents writes **2 995 content-addressed blobs** — a parse
artifact, a chunks artifact and a document artifact each — and on this machine each costs
about 26 ms. That is ~79 s of a 91.7 s build. The compiler's algorithms are not what is left;
writing three small files per document is.

Two halves, and only one is ours. A *plain* 4 KiB write costing 12.6 ms is a property of this
machine — a real-time scanner in the write path, the same constant the 2026-09-17 report
calibrated at ~1.3 ms for a warm *read*. The atomic ceremony doubling it is a property of the
compiler, because it touches two names per blob and the scanner charges for both.

### The stemmer, and why the profiler overstated it

The lexical index holds three stem columns beside the surface ones (ADR-0048), so
`put_chunks` stems four fields per chunk. Measured on the profiled corpus:

| | |
|---|---:|
| word occurrences stemmed | 620 293 |
| distinct words among them | **10 339** |
| calls a cache would serve from memory | **98.3 %** |
| stemming every occurrence | 7.44 s |
| the same, memoised | **0.31 s** (23.6×) |

**Read the profile as a hint, never as a measurement.** cProfile charges per call, so it
inflates code that makes many small ones and flattens code that makes few large ones. Taken at
face value its shares say stemming is 22 % of the build — 14.3 million inner calls will do
that — where measuring it alone puts it at 7.4 s of 91.7 s, about **8 %**. The file operations
go the other way: three thousand calls, and they are most of the build. Every number in this
report is a direct measurement; the profile is what said where to point one.

## Interpretation

**1. The fix is a shape change, not a speed-up.** Halving the total is the visible part; the
part that matters is that cost per document stopped growing. A build that is linear in the
corpus can be reasoned about at sizes nobody has run — at 92 ms per document the 10⁵-chunk
reference corpus is about half an hour to compile, against the nine hours the quadratic
implied, which is why that corpus had never been built.

**2. The store version moved and the ranking fingerprint did not, deliberately.**
`SCHEMA_VERSION` goes v6 → v7 because a store written earlier holds rowids that mean nothing
and must be rebuilt. But no DDL changed, so `retrieval_identity()` is byte-identical
(`sha256:44bb6f6c…`, checked before and after) and **gate G2's verdict is untouched** — no
re-record, and no need for the machine that holds the embedding model. ADR-0084 separated
those two questions for exactly this case, and this is the first time the separation has paid.

**3. What is left is not algorithmic, and that changes what to do about it.** Nothing in the
remaining 91.7 s is a stage doing too much work: it is 2 995 file writes on a machine that
charges 26 ms each. The actionable half is the ceremony rather than the writes — a temp file,
an fsync and a rename, for a store D-005 calls derived and disposable and whose recovery story
is `mycelium build`. That is a durability argument with two defensible sides, so it is filed
as **6.30** rather than settled in a pull request about a quadratic.

**4. The stemmer is the cheap one, and it is cheap to fix.** A pure function called 620 000
times over 10 339 distinct words. Filed as **6.31**.

**5. The incremental rebuild improved without being touched** — 3 945 ms p95 at 1 000
documents against 6 307 ms — and still misses NFR-3's 2 s budget. Its floor is a different
mechanism and roadmap 6.20 owns it.

## What these numbers do not say

- **One machine, and an unusually slow one at writing files.** 12.6 ms for a plain 4 KiB
  write is hundreds of times an unencumbered SSD. Since that is most of what remains, a
  faster machine would show a different balance — the stemmer would matter relatively more,
  and the build might well come in under its budget. The *shape* travels between machines;
  these absolute values do not.
- **The reference corpus still has not been compiled.** Half an hour is an extrapolation from
  a flat per-document cost, not a run. The query figures at 10⁵ chunks still come from a
  directly-populated store, as the 2026-09-17 report says.
- **The generated corpus has almost no link structure**, so the graph stage reading 0 % is
  partly the generator. On a real vault it would do more — though on this repository's own
  corpus it is also small.
- **Nothing here says the fix is faster on every corpus.** It removes a term that grows with
  corpus size; on a corpus of fifty documents there was never much of that term to remove.

## Reproduce

From a clean checkout, with `uv sync --all-extras --dev`, on an idle machine:

```bash
# The timed runs and the profile. ~10 minutes on the machine of record.
python tools/benchmark_reference_profile.py \
    --out <scratch-dir> --scales 250,1000 --no-reference --profile 1000 \
    --manifest docs/benchmarks/manifests/2026-09-19-the-quadratic-in-the-lexical-index.json

# The before numbers: check out 899e0d8 and run the same command without --profile.
```

The isolated write and stemmer measurements are in the decision record's references; the
store-level property — that a write does not get slower as the store fills — is a test,
`tests/test_store.py::test_writing_a_chunk_does_not_get_slower_as_the_store_fills`.
