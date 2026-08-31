# 2026-08-31 — four ways not to read every vector, and why none of them ship (roadmap 3.14)

- **Session scope:** roadmap 3.14 — close the candidate-generation budget at the top of the
  v1 envelope, where ADR-0026 left a fresh-process query at ~78 ms against 60 ms.
- **PR:** #44 (`feat/vector-index-budget`). Follows #43 (3.13), merged as `19c4b87`.
- **Milestone 3:** 3.1–3.14 decided; 3.15 open, 3.16 filed by this item.

## The item was a decision, and the decision is no

The gap only closes by not reading every vector, which trades away the exactness ADR-0017
chose on purpose. So the work was measurement, and the measurements were unanimous in an
unusual way — every mechanism failed, but not all for the same reason.

| mechanism | work | recall@50 | cold p50 @ 10^5 |
|---|---:|---:|---:|
| exact scan (today) | 100 % | 1.000 | 78 ms |
| IVF, nprobe=4 | 10 % of rows | 0.530 | ~15 ms |
| IVF, nprobe=8 | 20 % | 0.720 | ~30 ms |
| IVF, nprobe=24 | 57 % | 0.958 | **68 ms** |
| PCA d'=128 + exact rescore | 33 % of bytes | 0.552 | — |
| int8 first pass + exact rescore | 25 % on disk | **1.000** | **125 ms** |

Everything fast enough returns between a third and three quarters of the answer. At the
recall anyone would accept, coarse quantisation touches 57 % of the rows and is *still* over
the budget it was adopted for. And the one mechanism that loses nothing is slower than the
scan it replaces.

## Two things I would have got wrong without measuring

**Random vectors would have sold me an index.** IVF's whole premise is that neighbours
cluster. Synthetic gaussian vectors have no structure, and measuring recall on them is
measuring nothing. Real embeddings had to be the substrate — and the second corpus from 3.13
is where 2 090 of them came from, which is a use for it nobody planned.

**The int8 result was a bug before it was a finding.** The first run reported recall 0.05 at
a rescore of 100 — implausible enough to check rather than write down. Accumulating 384 terms
of up to 127² in `int16` overflows; in `int32` the same code reports **1.000**. A number that
looks absurd usually is, and the five minutes spent doubting it turned the item's conclusion
around: the winning algorithm exists, and its blocker is that numpy cannot multiply int8
without materialising a widened copy of the matrix.

## The geometry is the same one, again

`bge-small` puts one corpus in a narrow cone: unrelated passages score 0.62–0.78 against each
other, and the corpus mean direction alone carries 60 % of the squared norm. A partitioning
index needs neighbours *separated* to skip partitions safely, and a cone does not separate
them — which is why IVF's recall climbs almost linearly with the rows it reads, and why no
low-rank projection preserves the ranking.

That is ADR-0025's finding, measured then for whether a similarity floor could detect
unanswerable queries, decisive now for whether an index can skip work. One property of the
model, two items apart, and I would not have recognised it if 3.11 had not written the
background band down.

## What ships

No change to the query path — and that *is* the deliverable, taken against four measured
alternatives rather than assumed. What ships beside it:

- `tools/measure_vector_index.py`, so the tables above re-run instead of ageing into belief.
- A corrected `search_vectors` docstring. It had been claiming "94 ms over 10 000 chunks" and
  pointing at roadmap 3.12 — for two items *after* 3.12 made it 2.9 ms. Code comments rot
  exactly where nobody re-reads them, which is next to the thing they describe.
- Roadmap **3.16**: an in-place quantised kernel. `onnxruntime` already ships one behind our
  optional extra, so the question is whether a per-query session costs less than the 47 ms it
  has to win back — a measurement, not an argument.

## On calling an item done when the gap is open

3.14 asked for the budget to be closed. It is not closed, and ticking it could read as if it
were. It is ticked because the item's own text said the trade "is a decision to argue on its
own evidence" — that argument is finished, and its answer is no. The roadmap line says so in
its first clause rather than burying it, because the next person to read it will be deciding
whether to try again.
