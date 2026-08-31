# ADR-0026: Pack the vectors into a memory-mapped matrix, and keep the SQL scan as the definition

- **Status:** Accepted — the 10^5 figures are corrected by [ADR-0030](0030-correct-the-vector-scan-cost-model.md): the gap this ADR filed as 3.14 was a benchmark artifact and does not exist
- **Date:** 2026-08-31
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §1, §3
- **Related:** [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) (whose
  measurement filed this), [ADR-0008](0008-adopt-sqlite-store-behind-a-store-protocol.md),
  [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md); D-002, D-013;
  roadmap 3.12

## Context

ADR-0017 shipped an exact brute-force cosine scan and recorded that it missed spec 04 §1's
60 ms candidate-generation budget: 94 ms over 10 000 chunks, and linear. Two rounds of query
shaping had already taken it from 168 ms, and the ADR named the remaining suspect — SQLite
row iteration over blob columns — and filed the fix as roadmap 3.12, a prerequisite for
hybrid ever earning its default.

Before changing anything, the scan was profiled phase by phase at 10 000 chunks, dim 384:

| phase | p50 |
|-------|----:|
| **full `search_vectors` (before)** | **92.97 ms** |
| SQL `fetchall` of 10 000 rows | 67.56 ms |
| `b"".join(bytes(row["vec"]) ...)` | 11.20 ms |
| ranking the scores with Python's `sorted` | 10.60 ms |
| numpy reshape + matrix multiply | **0.41 ms** |

The suspicion was right and incomplete. Reading the rows is 68 ms and joining their blobs
another 11, as ADR-0017 guessed — but a *second* cost it never named, ranking 10 000 scores
through Python's `sorted`, is 10.6 ms against 0.5 ms for `numpy.argpartition`. The
arithmetic everyone assumes is the expensive part is 0.4 % of the total.

**Representations, measured rather than argued** (per query, top-50, 10 000 vectors):

| representation | p50 |
|----------------|----:|
| row-by-row fetch + join + Python sort (before) | 91.95 ms |
| one BLOB row in SQLite, read per query | 38.64 ms |
| `np.memmap` of a packed file, mapped per query | 11.09 ms |
| `np.memmap` held open by a long-lived process | 0.59 ms |

float16 storage was measured and dropped: the upcast costs more than the halved bytes save
(22.8 ms against 13.5 ms at 10 000), so precision never became the question.

## Decision

**The vectors are packed into one memory-mapped file per model, and the `vectors` table
stays exactly as it is.** The pack holds a header, the chunk digests at fixed width in
sorted order, and the matrix as contiguous little-endian float32. A query maps it, multiplies,
and takes the top *k* with `argpartition`; a filtered query pre-filters in SQL as spec 04 §2
requires, but reads *digests* rather than blobs and turns them into row indices with a binary
search over the sorted keys.

**It is a cache, not a source of truth, and that is the load-bearing part.** Every failure —
no file, foreign format, truncation, a filter naming a vector the pack does not hold, numpy
absent — returns to the SQL scan, which is slower and *exactly as correct*. A test asserts
the two paths return identical anchors and identical scores, because that equivalence is what
makes the pack safe to be absent.

**Staleness is made impossible rather than detected.** The generation counter in `meta` names
the file, so a pack whose vectors have since changed is a file nobody opens. Exactly three
code paths write vectors — `put_vectors`, `delete_orphan_vectors`, and the recreate that
drops the schema — and each bumps the counter. The pack is written after the commit of the
transaction that touched vectors, by the process that already holds the write lock and has
just paid for the rows.

## Alternatives Considered

- **Store the packed matrix as one BLOB row inside SQLite.** Rejected on the table above:
  38.6 ms at 10 000 chunks, because every query copies the whole matrix into a Python
  `bytes` before numpy can look at it. At the top of the v1 envelope that copy is 154 MB
  per query. The file exists to be *mapped*, not read.
- **Only swap `sorted` for `argpartition`.** Rejected as insufficient, kept as part of the
  fix: it is worth 10 ms of 92, and leaves the scan four times over budget. It is included
  because it costs one line and the profile says it is 20x.
- **float16 storage.** Rejected: measured slower, since the upcast to float32 for the
  matrix multiply costs more than halving the bytes saves.
- **sqlite-vec, which spec 04 §3 names.** Still rejected, and for ADR-0017's reason rather
  than a performance one: it is a *loadable* extension, and stock Python builds on a
  supported platform ship without `enable_load_extension`, which would make the default
  retrieval path unavailable on macOS's system interpreter.
- **An approximate index (HNSW/IVF) in-process.** Rejected for this item: it trades the
  exactness ADR-0017 chose deliberately — no recall cliff to tune — for headroom the
  measurements say is not needed inside the envelope this milestone targets. It is the
  answer for the one gap below, and it is filed rather than smuggled in here.
- **Rebuild the pack lazily on the read path.** Rejected: a search command would write into
  `.mycelium/`, two concurrent readers would race to produce the same file, and a read-only
  handle would stop being read-only. Writing it where the write lock already is costs
  nothing extra and keeps the invariant simple.

## Consequences

- **The budget is met at 10 000 chunks, with margin**, and the improvement holds
  end-to-end rather than only in a micro-benchmark:

  | | before | after |
  |---|---:|---:|
  | `search_vectors`, warm process | 92.97 ms | **2.88 ms** |
  | fresh process: open store + one query | 108.05 ms | **23.42 ms** |

- **One honest gap remains, and it is filed rather than papered over.** At the top of the
  v1 envelope (10^5 chunks, D-002) the packed matrix is 154 MB: the first query in a *fresh*
  process measures ~70 ms — still 17 % over the 60 ms budget, against ~930 ms for the old
  scan — while every query after it in the same process is ~1 ms. So an MCP server, which is
  what an agent actually talks to, is two orders of magnitude inside the budget at every
  corpus size; a one-shot CLI query at the largest supported corpus is not. Closing that
  needs an index that does not read every vector, which is roadmap **3.14**.
- **`.mycelium/` gains a file per model**, `vectors-<model>-<generation>.pack`, sized
  `count × dim × 4` bytes plus 80 bytes per key. It is derived state: `mycelium build`
  rewrites it, deleting it costs only speed, and it is not part of a snapshot, an export
  bundle, or the CAS the collector sweeps.
- **Windows keeps a mapped file alive.** A long-lived reader holding a pack mapped prevents
  the writer from unlinking that generation, so old packs can survive a rebuild until a
  later prune finds them unmapped. Pruning tolerates the refusal rather than failing a
  build, and closing a store releases its maps.
- **Gate G6 is untouched**: no config key changed and no build artifact moved — the pack is
  written beside the store, not into a snapshot, and the golden re-blesses to nothing.
- The scan stays **exact**, so ADR-0017's "no recall cliff to tune" survives this change
  intact — which is the property that makes the equivalence test meaningful rather than
  approximate.

## References

- Spec 04 §1 (60 ms candidate budget), §3 (candidate generation); D-002 (corpus envelope),
  D-013 (vectors keyed by `(chunk_digest, model_id)`)
- [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) — the measurement that
  filed this item
- `tests/bench/test_retrieval_bench.py` — the committed 10 000-chunk measurement and the
  budget assertion
