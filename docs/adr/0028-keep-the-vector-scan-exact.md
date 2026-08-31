# ADR-0028: Keep the vector scan exact, because every way of shortening it costs more than it saves

- **Status:** Accepted — the latency table's premise is corrected by [ADR-0030](0030-correct-the-vector-scan-cost-model.md) — the exact scan is ~31 ms, not 78; the refusal below is unchanged and stronger for it
- **Date:** 2026-08-31
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §1, §3
- **Related:** [ADR-0026](0026-pack-the-vectors-into-a-memory-mapped-matrix.md) (which filed
  this), [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md),
  [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md); D-002, D-013;
  roadmap 3.14

## Context

ADR-0026 packed the vectors into a memory-mapped matrix and took a query from 92.97 ms to
2.88 ms over 10 000 chunks. It left one gap and filed it as roadmap 3.14: at the top of the
v1 corpus envelope (10^5 chunks, D-002) the matrix is 154 MB, so the **first** query in a
fresh process costs about 78 ms against spec 04 §1's 60 ms budget, while every query after
it in the same process costs about 1 ms. A long-lived MCP server is far inside the budget at
every supported size; a one-shot CLI query at the largest supported corpus is not.

Closing it means not reading every vector. That trades away the exactness ADR-0017 chose
deliberately — "it is exact, so there is no recall cliff to tune" — which is why the item
was filed as a decision to argue on its own evidence rather than a speed-up to slip in.

Four mechanisms were measured. Recall was measured on **real embeddings** from a built
corpus, because random vectors are structureless and would flatter a partitioning index
exactly where real ones defeat it. Latency was measured at the reference profile on
synthetic vectors, because geometry does not change how long it takes to touch bytes. Both
halves re-run from `tools/measure_vector_index.py`.

**Recall against the exact top-50** — 2 090 real vectors, `bge-small-en-v1.5`:

| mechanism | work | recall@50 |
|---|---:|---:|
| IVF, nprobe=2 | 5.3 % of rows | 0.342 |
| IVF, nprobe=4 | 10.4 % | 0.530 |
| IVF, nprobe=8 | 20.2 % | 0.720 |
| IVF, nprobe=16 | 39.4 % | 0.894 |
| IVF, nprobe=24 | 57.3 % | 0.958 |
| PCA d'=64, exact rescore of 200 | 16.7 % of bytes | 0.508 |
| PCA d'=128, exact rescore of 200 | 33.3 % | 0.552 |
| **int8 first pass, exact rescore of 100** | 25 % on disk | **1.000** |

**Latency, cold process, 10^5 vectors:**

| mechanism | p50 | verdict |
|---|---:|---|
| exact scan, every vector (today) | 78.2 ms | over the 60 ms budget |
| partial scan, 6 % of rows (an IVF probe) | 13.3 ms | within |
| partial scan, 25 % of rows | 36.8 ms | within |
| partial scan, 58 % of rows (IVF at recall 0.958) | 68.2 ms | **over** |
| int8 first pass + exact rescore of 100 | 125.5 ms | **over** |

Read together, the two tables close the question. Everything fast enough loses between a
quarter and two thirds of the answer; at the recall anyone would accept, coarse quantisation
touches 57 % of the rows and is *still* over budget; and the one mechanism that loses nothing
is slower than the scan it replaces.

## Decision

**The vector scan stays exact, and no approximate index ships.** The gap ADR-0026 recorded
stays open, named, and measured rather than closed with an index that would answer a
different question than the one asked.

**The reason the fast options fail is geometry, and it is the same finding ADR-0025 made.**
`bge-small` embeddings of one corpus occupy a narrow cone: unrelated passages score
0.62–0.78 against each other, and the corpus mean direction alone carries 60 % of the squared
norm. A partitioning index needs neighbours to be *separated* to skip partitions safely, and
in a cone they are not — which is why IVF's recall climbs almost linearly with the fraction
of rows it reads, and why no low-rank projection preserves the ranking. The same shape that
made a similarity floor undetectable makes an approximate index unprofitable.

**The mechanism that works is known, and its blocker is a dependency rather than an idea.**
An int8 first pass with an exact rescore returns the exact top-50 — recall 1.000, not
approximately — and touches a quarter of the bytes. It is slower only because numpy cannot
multiply int8 without materialising a widened float32 copy of the whole matrix, which costs
more than the I/O it saves. Blocking the conversion to stay in cache does not help
(measured: 137–160 ms). A kernel that multiplies quantised integers in place would make this
mechanism win outright, and this project already ships one behind an optional extra —
`onnxruntime` — which is the thread to pull, and roadmap **3.16**.

## Alternatives Considered

- **Ship IVF at a recall the numbers justify.** Rejected twice over: at nprobe=24 recall is
  0.958 and the query still costs 68 ms, so it fails the budget it was adopted for; at a
  probe small enough to be fast it returns a third of the answer. There is no setting where
  it both works and pays.
- **Ship IVF anyway with a configurable `nprobe`.** Rejected: a knob whose correct value
  depends on a corpus's geometry, with no gate able to check it, is the "constant that
  silently rots" ADR-0025 refused. Worse here, because the failure is invisible — a query
  returns *results*, just not the right ones.
- **PCA or random projection as a first pass.** Rejected on the recall table: 0.51–0.75 at a
  third of the bytes. The discriminative variance lives in the tail dimensions, which is what
  a cone implies.
- **Parallelise the exact scan across threads.** Measured, not argued: 2 threads 77 ms, 4
  threads 77 ms, 8 threads 81 ms, against 75 ms serial. The scan is bound by neither
  arithmetic nor parallel page faults, so threads add scheduling and nothing else.
- **sqlite-vec**, which spec 04 §3 names. Still rejected for ADR-0017's reason, unchanged: a
  *loadable* SQLite extension is unavailable in stock Python builds on a supported platform,
  which would make the default retrieval path platform-dependent.
- **Declare the budget met because a long-lived server meets it.** Rejected: `mycelium
  search` is a real surface and a fresh process is what it is. Redefining the measurement to
  match the result is the failure D-010 exists to prevent.

## Consequences

- **No code changes to the query path**, and that is the outcome rather than an absence of
  one: the decision is that the current path is the best available one, taken against four
  measured alternatives instead of an assumption.
- **The limit is now stated where it will be read.** `search_vectors` documented "94 ms over
  10 000 chunks" and pointed at roadmap 3.12 long after 3.12 had made it 2.9 ms; the
  docstring now carries the real numbers and this decision.
- **The evidence is re-runnable.** `tools/measure_vector_index.py` reproduces both tables —
  recall against a built corpus, latency at 10^5 behind `--scale`. An ADR whose numbers
  cannot be re-derived ages into a belief.
- **Hybrid remains opt-in** (ADR-0017's G2, unchanged by this), so nothing in the shipped
  configuration pays the cost this ADR declines to remove. That is why an open gap here is a
  limit rather than a defect.
- **The gap is inherited, not resolved.** A deployment with 10^5 chunks that wants hybrid
  retrieval from a one-shot CLI pays ~78 ms for its first query. That is written into the
  roadmap as 3.16 with the mechanism already identified, not left as folklore.

## References

- Spec 04 §1 (60 ms candidate budget), §3 (candidate generation); D-002, D-013
- [ADR-0026](0026-pack-the-vectors-into-a-memory-mapped-matrix.md) — the packed matrix, and
  the gap it filed
- [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md) — the cone geometry,
  measured for a different question and decisive here
- `tools/measure_vector_index.py` — both tables, re-runnable
