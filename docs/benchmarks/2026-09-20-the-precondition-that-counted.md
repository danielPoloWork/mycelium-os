# Benchmark Report: the precondition that counted

- **Date:** 2026-09-20
- **Version / commit:** v0.5.0 @ `7fa02e9` **plus the change this report is about** — the
  manifest records the base commit, and the working tree carried roadmap 6.27's probe
- **Environment:** see [`manifests/2026-09-20-the-precondition-that-counted.json`](manifests/2026-09-20-the-precondition-that-counted.json) — the machine of record, as in the [reference-profile report](2026-09-17-reference-profile.md)
- **Command:** `python tools/benchmark_reference_profile.py --query-scale 100000 --vectors --no-reference`
- **Roadmap:** 6.27 · **Decision:** [ADR-0142](../adr/0142-probe-for-the-vector-precondition-instead-of-counting.md)

## Scenario

Before running the vector leg, `search` asks whether this snapshot holds vectors for the
configured model — [ADR-0025](../adr/0025-make-lexical-evidence-the-vector-legs-precondition.md)'s
degradation path, so that a snapshot built before the embedder existed stays searchable and
*says* it is degraded rather than failing.

The question is a yes/no. The implementation was `vector_counts()`, a
`SELECT model_id, count(*) … GROUP BY model_id` over the whole table, **once per hybrid
query**. Roadmap 6.21 timed it at the reference profile and filed 6.27; this report is the
before-and-after, taken in one run so the two numbers share a machine, a store and a query
set.

Both are measured on the same 306 queries, against the same 10⁵-vector store, warm.

## Results

| Measurement | p50 | p95 | max |
|---|---:|---:|---:|
| `has_vectors()` — the precondition now | **0.013 ms** | **0.016 ms** | 0.063 ms |
| `vector_counts()` — what it used to cost | **91.008 ms** | **96.008 ms** | 100.108 ms |
| vector leg, warm handle (the leg it guards) | 11.124 ms | 12.797 ms | 13.609 ms |

**Seven thousand times**, and the shape is the point rather than the ratio: the aggregate
reads every row to produce a number nobody wanted, and the probe stops at the first row
that answers the question. Counted in SQLite VM instructions at the committed bench scale,
that is **120 033 against 20** — a figure that is the same on every machine, and the one
`tests/bench/test_retrieval_bench.py` guards.

The precondition was **8.2× the vector leg it guards** in this run, and 61 % of NFR-2's
entire 150 ms budget, spent before retrieval started.

### What did not change, and is not this report's subject

| Measurement | p50 | p95 |
|---|---:|---:|
| vector leg, fresh handle (a CLI invocation) | 46.501 ms | 57.818 ms |
| search, hybrid, both legs, warm | 761.278 ms | 1 483.015 ms |
| search, lexical, warm | 767.192 ms | 1 424.855 ms |

The query path at 10⁵ chunks misses NFR-2 by an order of magnitude, which
[the reference profile](2026-09-17-reference-profile.md) established at roadmap 6.4 and
which roadmap 6.19's and 6.24's successors own. Removing 91 ms from a 760 ms query does not
change that verdict and this report does not claim it does — the hybrid and lexical figures
are within noise of each other here, because what dominates them is the lexical leg both
share.

## Limits

- **The vectors are synthetic** — one unit vector per chunk, written through `put_vectors`
  and packed by the store's own `repack_vectors`, for the reason the
  [hybrid-path report](2026-09-18-the-hybrid-path-at-the-reference-profile.md) gives: real
  embeddings for 10⁵ chunks are hours of work and the scan does not read their meaning.
- **One machine, one run.** The 6.21 profile recorded 129.9 ms p50 for the same aggregate
  where this one reads 91.0. Both are this machine; the spread is load, and it is the
  reason the committed guard counts instructions rather than milliseconds.
- **The manifest carries the whole run**, including the build curve at 250 → 5 000
  documents that the same invocation produced. Those rows are real and are not this
  report's subject; the reference-profile reports own them.

## Reproduce

```bash
python tools/benchmark_reference_profile.py --query-scale 100000 --vectors --no-reference \
  --manifest docs/benchmarks/manifests/2026-09-20-the-precondition-that-counted.json
```

The mechanism guard, which needs no reference corpus and runs in CI:

```bash
pytest tests/bench/test_retrieval_bench.py -k precondition
```
