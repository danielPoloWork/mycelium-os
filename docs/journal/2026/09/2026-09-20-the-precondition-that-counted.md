# 2026-09-20 — the precondition that counted (roadmap 6.27)

- **Session scope:** roadmap 6.27 — the hybrid precondition costs three times the leg it
  guards, and the item leaves both the fix and its argument open.
- **PR:** #PRNUM (`perf/hybrid-precondition`). Follows #176, merged as `7fa02e9`.
- **Milestone 6:** 6.27 closed. Open: 6.28–6.36.
- **Decision it records:**
  [ADR-0142](../../../adr/0142-probe-for-the-vector-precondition-instead-of-counting.md).
  Report: [the precondition that counted](../../../benchmarks/2026-09-20-the-precondition-that-counted.md).

## One yes/no, answered by reading everything

`search` asks, before the vector leg: does this snapshot hold vectors for the configured
model? It is ADR-0025's degradation path — a snapshot built before the embedder existed
stays searchable and *says* it is degraded. The answer is a boolean; the implementation was
`SELECT model_id, count(*) … GROUP BY model_id`, over the whole table, once per query.

Measured at 10⁵ vectors on the machine of record, 306 queries, one run so the before and
the after share a machine, a store and a query set:

| | p50 | p95 |
|---|---:|---:|
| `vector_counts()`, what it cost | **91.0 ms** | 96.0 ms |
| `has_vectors()`, what it costs | **0.013 ms** | 0.016 ms |
| the warm vector leg it guards | 11.1 ms | 12.8 ms |

Seven thousand times, and the precondition was **8.2× the leg it was protecting**.

## Both of the item's options, and the second needed checking

The item offered an `EXISTS` probe *or* a per-handle cache, and asked what a cache would do
about vectors written under a handle that had already answered. The honest answer is that
both are needed, for different halves of the problem.

The probe fixes the hit path completely: `EXISTS` stops at the first matching row — **20
SQLite VM instructions against the aggregate's 120 033**, a count that is the same on every
machine and the one the committed guard asserts.

A *miss* still scans, because `vectors` is keyed `(chunk_digest, model_id)` and nothing
indexes `model_id` on its own: 9.5–10.6 ms, on exactly the degraded configuration ADR-0025
exists to serve, on every query, forever, for a fact that needs a rebuild to change. Hence
the cache — keyed `model@generation`, the key `_pack_for` already trusts (ADR-0026), which
answers the item's question three times over: every write path bumps the generation, the
generation lives in the meta *table* rather than in the object, and one generation is held
at a time.

## The number that argued against the cache, and why it lost

ADR-0128 refused a second cache at 6.18 on its own measurement, so the same test had to be
applied here rather than skipped: reading the generation costs **0.010 ms** against the
probe's **0.004 ms**. On the hit path the cache is *slower* — by six microseconds.

It is kept because the hybrid path reads that same generation one line later, when
`search_vectors` maps the pack, so on the path that runs both legs the key is free; and
because six microseconds against 10.6 milliseconds on the miss path is not a close call.
Writing that down mattered more than the decision: the next reader deserves to know the
cache was measured against its own alternative and not assumed.

An index on `model_id` would have fixed the miss too, at the cost of a schema bump and a
rebuild for every existing store, on a column whose cardinality is one. Refused.

## What it does not claim

It is not on the lexical path, so the shipped default never paid it. At 10⁵ chunks the
whole query is ~760 ms and the lexical leg both profiles share is what dominates — removing
91 ms does not change that verdict, and the report says so in its own words. What it
changes is the arithmetic of any future argument about whether hybrid is affordable, which
is what 6.21 filed it for.

## The guard counts instructions

6.18's lesson, applied: a timing bar on a shared runner is a flake. The committed test
asserts the probe stays under 100 VM instructions, that the aggregate is at least a hundred
times it, and — separately — that a miss scans, so the cache keeps a stated reason rather
than an inherited one. The reference profile now times the probe *and* the aggregate it
replaced, so the comparison stays visible in the next report rather than becoming a number
with nothing beside it.
