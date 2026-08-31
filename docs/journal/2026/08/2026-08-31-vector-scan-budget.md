# 2026-08-31 — profiling before optimising, and finding half the cost nobody had named (roadmap 3.12)

- **Session scope:** roadmap 3.12 — make the vector leg meet spec 04 §1's 60 ms
  candidate-generation budget. Filed at 3.3 by ADR-0017, which measured the miss.
- **PR:** #42 (`feat/vector-scan-budget`). Follows #41 (3.11), merged as `c909f8d`.
- **Milestone 3:** 3.1–3.12 done; 3.13 open, and 3.14 filed by this item.

## The diagnosis was right and incomplete

ADR-0017 left a suspect in writing: "the rest is SQLite row iteration over blob columns".
Profiling the scan phase by phase before touching it confirmed that and found something
else:

| phase | p50 |
|-------|----:|
| full `search_vectors` | 92.97 ms |
| SQL `fetchall` of 10 000 rows | 67.56 ms |
| joining the row blobs | 11.20 ms |
| **ranking the scores with Python's `sorted`** | **10.60 ms** |
| numpy reshape + matrix multiply | 0.41 ms |

Nobody had named that fourth line. It is 11 % of the scan, it has nothing to do with
storage, and `numpy.argpartition` does the same job in 0.5 ms — because sorting 10 000
scores to keep 50 is 10 000 comparisons in the interpreter, and partitioning is one pass in
C. Had I gone straight to the representation, that 10 ms would have survived the rewrite and
nobody would have looked again.

The other half of the lesson is the last line. The matrix multiply — the thing that *sounds*
like the cost of "scanning 10 000 vectors" — is 0.4 % of the total. The scan was never
compute-bound; it was bound by turning rows into Python objects.

## Choosing the representation with a table instead of an opinion

| representation | p50 |
|----------------|----:|
| row-by-row fetch + join + Python sort | 91.95 ms |
| one BLOB row in SQLite, read per query | 38.64 ms |
| `np.memmap` of a packed file, mapped per query | 11.09 ms |
| `np.memmap` held open | 0.59 ms |

The BLOB-in-SQLite option is the one I would have guessed at — it keeps everything in one
file and needs no new artifact. It loses because every query copies the whole matrix into a
Python `bytes` before numpy sees it: 15 MB at 10 000 chunks, 154 MB at the top of the
envelope. The file exists to be *mapped*, not read. float16 was measured too and dropped
for a reason I did not expect: the upcast costs more than the halved bytes save, so
precision never became the question.

End-to-end: `search_vectors` 92.97 → **2.88 ms**, and a fresh process (open the store, ask
one question — a CLI invocation) 108.05 → **23.42 ms**.

## The part I spent the most care on

The pack is a **cache**, and the `vectors` table stays the source of truth. Every failure
path returns to the SQL scan: no file, foreign format, truncation, numpy missing, or a
filter naming a vector the pack does not hold. A test asserts the two paths return identical
anchors *and* identical scores, because that equivalence is the whole licence to keep a
second copy of the data.

Staleness is **made impossible rather than detected**: the generation counter names the
file, so a pack whose vectors have moved is a file nobody opens. Exactly three code paths
write vectors, and I checked that by grep rather than by memory — `put_vectors`,
`delete_orphan_vectors`, and the recreate that drops the schema.

## Two things the platform taught me

**Windows will not unlink a mapped file.** The first run of the equivalence test failed with
`WinError 32` because I unlinked the pack before releasing the map. My test had the order
wrong — but the failure is also real in production, where a long-lived reader pins a
generation the writer wants to prune. Pruning tolerates the refusal, closing a store
releases its maps, and the ADR says so.

**A benchmark that silently falls back measures the wrong thing.** A store built by the
previous version has no pack, and the query path is *designed* to fall back quietly. That is
correct behaviour and a terrible property for a benchmark, so there is now a test asserting
the pack is the thing being measured — otherwise a broken pack would show up as a slow
machine.

## What I did not do

At 10^5 chunks the matrix is 154 MB and the first query in a fresh process is ~70 ms — still
17 % over budget, against ~930 ms before. Every query after it is ~1 ms, so an MCP server is
far inside the budget at every supported size and a one-shot CLI query at the largest corpus
is not. Closing that needs an index that does not read every vector, which trades away the
exactness ADR-0017 chose on purpose. That is a decision with its own evidence to gather, so
it is roadmap **3.14** rather than a paragraph smuggled into a speed-up.
