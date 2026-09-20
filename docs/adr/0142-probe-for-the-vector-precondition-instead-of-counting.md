# ADR-0142: Probe for the vector precondition instead of counting, and key the answer to the generation

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §1
- **Related:**
  [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md) (the degradation
  path this question exists for),
  [ADR-0026](0026-pack-the-vectors-into-a-memory-mapped-matrix.md) (the packed matrix, and the
  generation key this reuses),
  [ADR-0130](0130-measure-the-vector-path-and-retire-three-disagreeing-extrapolations.md)
  (which measured the precondition and filed it),
  [ADR-0128](0128-cache-the-environment-not-the-repository-and-declare-the-names-instead-of-importing-them.md)
  (the same shape on the configuration path, and the precedent for refusing a cache on its
  own number),
  [ADR-0120](0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md)
  (the reference profile these numbers are taken on); spec 04 §1, NFR-2; roadmap 6.4, 6.21,
  6.27; report `docs/benchmarks/2026-09-20-the-precondition-that-counted.md`

## Context

`search` asks one yes/no before running the vector leg: does this snapshot hold vectors for
the configured model? ADR-0025's degradation path depends on it — a snapshot built before
the embedder existed stays searchable and *says* it is degraded rather than failing.

It asked by counting. `vector_counts()` is
`SELECT model_id, count(*) FROM vectors GROUP BY model_id`, which walks the whole table,
**once per hybrid query**. Measured at 10⁵ vectors on the machine of record:

| | p50 | p95 |
|---|---:|---:|
| `vector_counts()` | **91.0 ms** | 96.0 ms |
| the vector leg it guards, warm | 11.1 ms | 12.8 ms |

**8.2× the leg it guards**, and 61 % of NFR-2's entire 150 ms budget, spent before
retrieval starts. (Roadmap 6.21 read 129.9 ms p50 for the same statement on the same
machine; the spread between the two is load, which is itself an argument about what to
guard.)

It is the third instance of one shape: a per-call cost paying for a fact that does not
change between calls. Roadmap 6.18 removed it from the configuration path (ADR-0128) and
6.25 from the import path (ADR-0140).

## Decision

**`SqliteStore.has_vectors(model_id)` answers the question with an `EXISTS` probe, and
caches the answer under the vectors generation.** `vector_counts()` stays, unchanged, for
the two callers that want a *count*: `doctor` and the manifest.

### The probe

`SELECT EXISTS(SELECT 1 FROM vectors WHERE model_id = ?)` stops at the first matching row.
Counted in SQLite VM instructions at the committed bench scale — a figure that does not
move between machines, unlike a millisecond —

| | VM instructions |
|---|---:|
| `GROUP BY` over the table | **120 033** |
| `EXISTS`, model present | **20** |
| `EXISTS`, model absent | 30 014 |

The third row is the reason for the second half of this decision. `vectors` is keyed
`(chunk_digest, model_id)`, so **nothing indexes `model_id` on its own** and a *miss* still
walks the table: 9.5–10.6 ms at 10⁵ rows. That is the degraded path — precisely the
configuration ADR-0025 exists to serve — and it would pay the scan on every query, forever,
for a fact that cannot change without a rebuild.

### The cache, and the question the filing item asked of it

*"What happens when vectors are written under a handle that already answered."*

The key is `model@generation`, where the generation is `META_VECTORS_GENERATION` — the same
key the packed matrix already trusts (`_pack_for`, ADR-0026). That answers it three times
over: every write path calls `_bump_vectors_generation`; the generation lives in the meta
**table**, not in this object, so a write by another process invalidates this handle's
answer too; and the dict holds one generation at a time, so a stale answer is not merely
unused but absent.

### Why an index on `model_id` was not added instead

It would make the miss O(log n) as well, at the cost of a schema change — a
`SCHEMA_VERSION` bump and a rebuild for every existing store (D-016) — to speed up a path
that the cache removes entirely after one query. The column also has a cardinality of one
in every real store, which is the worst case for an index and the best case for a cache.

### Why the cache is not a pessimisation, which had to be checked

ADR-0128 refused a second cache on exactly this ground — *"reading `mycelium.toml` costs
2.1 ms, less than the store open beside it, so a cache would buy nothing"* — so the same
test applies here. Reading the generation costs **0.010 ms**, against **0.004 ms** for the
`EXISTS` hit: the cache is, on the hit path alone, six microseconds *slower*.

It is kept anyway, for two reasons that survive the arithmetic. The hybrid path reads that
same generation one line later, when `search_vectors` maps the pack, so on the path that
actually runs both legs the key is free. And six microseconds against 10.6 milliseconds on
the miss path is not a trade that needs a second opinion.

## Consequences

**Measured**, 10⁵ vectors, 306 queries, machine of record, one run so the two share
everything (`docs/benchmarks/2026-09-20-the-precondition-that-counted.md`):

| | p50 | p95 | max |
|---|---:|---:|---:|
| `has_vectors()` | **0.013 ms** | **0.016 ms** | 0.063 ms |
| `vector_counts()`, what it replaced | 91.008 ms | 96.008 ms | 100.108 ms |

Seven thousand times, and the 0.013 ms is almost entirely the generation read — the probe
itself is 0.004 ms.

**It is not on the lexical path**, so the shipped default pays none of it, and it is not
why NFR-2 is missed: at this scale the whole query is ~760 ms and the lexical leg both
profiles share is what dominates. Removing 91 ms from that does not change the verdict and
the report says so. What it changes is the arithmetic of any future argument about whether
hybrid is affordable, which is what 6.21 filed it for.

**The guard counts instructions, not milliseconds**, following roadmap 6.18's lesson that a
timing bar on a shared runner is a flake. `tests/bench/test_retrieval_bench.py` asserts the
probe stays under 100 VM instructions and that the aggregate is at least a hundred times
it — and, separately, that a *miss* scans, so the cache keeps a stated reason.

**The reference profile now times both**, the probe and the aggregate it replaced, so a
later reader of the report sees the comparison rather than a number with no scale beside
it.
