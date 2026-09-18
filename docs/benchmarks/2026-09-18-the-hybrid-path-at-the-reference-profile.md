# Benchmark Report: the hybrid path at the reference profile

- **Date:** 2026-09-18
- **Version / commit:** v0.5.0 @ `767965c`
- **Environment:** see [`manifests/2026-09-18-the-hybrid-path-at-the-reference-profile.json`](manifests/2026-09-18-the-hybrid-path-at-the-reference-profile.json) — the machine of record, as in the [reference-profile report](2026-09-17-reference-profile.md)
- **Command:** `python tools/benchmark_reference_profile.py --scales "" --no-reference --query-scale 100000 --vectors`
- **Roadmap:** 6.21 · **Decision:** [ADR-0130](../adr/0130-measure-the-vector-path-and-retire-three-disagreeing-extrapolations.md)

## Scenario

The [reference profile](2026-09-17-reference-profile.md) measured the **shipped default**,
which is lexical (ADR-0017). It says nothing about what the hybrid path costs at the scale
NFR-2's budget is stated for, and said so in its own limitations.

What this measures, at 10⁵ chunks:

- **the vector leg alone**, on a fresh handle and on a warm one — the two patterns that
  exist, which is the distinction [ADR-0030](../adr/0030-correct-the-vector-scan-cost-model.md)
  had to establish once already;
- **the whole hybrid query** through `search` — plan, lexical leg, vector leg, fusion —
  which is what a caller waits for with `[retrieval] profile = "hybrid"`;
- **the same queries lexical-only**, on the same store, so the hybrid figure can be read as
  a cost *over* the default rather than in the abstract;
- **one `embed_query` against the shipped local model**, separately, because it belongs to
  the embedder rather than to retrieval.

### Why the vectors are synthetic, and where that is a limit

One synthetic unit vector per chunk, written through `put_vectors` and packed by the store's
own `repack_vectors`. Embedding 10⁵ real chunks with the 133 MB local model is hours of work
that would measure the *embedder*; the scan is exact and touches every vector whatever it
contains, so geometry cannot change how long the multiplication takes. It is the same choice
`tests/bench/test_retrieval_bench.py` has always made at 10 000 chunks and the same one
`tools/measure_vector_index.py` makes for its latency half.

It would be the wrong choice for a **quality** measurement, and none is claimed here: random
vectors have none of the structure real embeddings have (ADR-0025's cone), so nothing in this
report says anything about what hybrid *retrieves*. Gate G2 owns that question and cannot
answer it until 6.8 grows the judged sets.

### The store had to change to make this measurable

Every chunk the reference-profile generator wrote shared one `chunk_digest`. That was
harmless while the profile was lexical — `chunks_fts` does not carry the column, so BM25
cannot see it — and fatal to a vector measurement: vectors are keyed `(chunk_digest,
model_id)` (D-013) and `search_vectors` hydrates by that key, so the profile would have held
**one vector for a hundred thousand chunks**.

The digest is now derived from the chunk's anchor. It is taken outside the generator's
`random.Random` stream, so the prose the same seed produces is byte-identical and only that
column moves — which is what lets the 2026-09-17 figures and these be read as measurements of
one corpus.

## Results

100 000 chunks, 100 000 vectors at 384 dimensions — a 153.6 MB matrix, 154 MB packed with its
keys. 39 judged queries; the vector leg ran on 34 of them and was withheld on 5 for want of
lexical evidence (ADR-0025).

The manifest's `corpus.profile` describes the *compiled* corpus, which is built with the
embedder off because that is what the shipped default reads. The vectors are written into the
finished store afterwards and are documented in its `vector_profile` section, which is the
authority on what this report measures. (The run that produced the committed manifest wrote
that field before the distinction was spelled out; the tool states it explicitly from now on.)

### The vector leg, against spec 04 §1's 60 ms candidate budget

| Measurement | p50 | p95 | Budget | Verdict |
|---|---:|---:|---:|---|
| Vector leg, first query on a fresh handle (a CLI invocation) | 43.2 ms | 46.2 ms | 60 ms | ✓ **within** |
| Vector leg, warm handle (the MCP server) | 12.1 ms | 13.3 ms | 60 ms | ✓ **within** |

### The whole query, against NFR-2's 150 ms p95

| Measurement | p50 | p95 | Budget | Verdict |
|---|---:|---:|---:|---|
| `search`, hybrid, both legs ran | 1 288.3 ms | 2 020.3 ms | 150 ms | ✗ 13.5× over |
| `search`, lexical (the shipped default), same store | 1 004.9 ms | 1 862.7 ms | 150 ms | ✗ 12.4× over |
| `search`, hybrid configured, vector leg withheld | 1.9 ms | 2.0 ms | 150 ms | ✓ — abstains at once |
| **`vector_counts()`, the precondition `search` runs *per hybrid query*** | **129.9 ms** | **133.0 ms** | — | **3.0× the leg it guards** |
| `embed_query`, local ONNX model (excluded from the figures above) | 9.7 ms | 11.8 ms | — | a property of the model |

The lexical column is this run's own baseline, not a quotation: the
[2026-09-17 report](2026-09-17-reference-profile.md) measured 1 089 ms p50 / 1 816 ms p95 at
the same size, and this run reads 1 005 / 1 863. Same order, ordinary run-to-run variance on a
one-second measurement, and the conclusion in both is identical.

### What the three previous statements said

| Source | Fresh process | Warm handle |
|---|---:|---:|
| `tests/bench/test_retrieval_bench.py` (citing ADR-0026) | ~70 ms | ~1 ms |
| `src/mycelium/store/sqlite.py` (citing ADR-0030) | ~31 ms | ~1 ms |
| **Measured here, through `search_vectors`** | **43.2 ms** | **12.1 ms** |

## Interpretation

**1. The vector path was never the problem, and now that is measured rather than assumed.**
Both patterns that exist are inside spec 04 §1's 60 ms candidate-generation budget — 43.2 ms
for a CLI invocation, 12.1 ms for a server that keeps its handle. At the top of the v1 corpus
envelope (D-002), the exact brute-force scan ADR-0026 chose over a loadable extension still
holds. Nothing here argues for sqlite-vec or for an approximate index; ADR-0028's refusal
stands on its own recall evidence and this adds the latency half at the scale that matters.

**2. Both previous numbers were wrong, in opposite directions.** The benchmark's ~70 ms was
the *re-map-per-query* figure BUG-0015 identified as a pattern no code path has — ADR-0030
took that label away from it five milestones ago and the docstring never received the
correction. ADR-0030's own ~31 ms is closer and still low, because it timed a `numpy` memmap
and a matrix multiply: `search_vectors` also resolves the pack, applies the serving filters in
SQL, and hydrates fifty results back into records. The warm figure is the larger error — both
sources said ~1 ms and the method costs **12.1 ms**, twelve times that, for the same reason.
The arithmetic was never the cost, which is ADR-0026's own finding applied to its own
successor.

**3. The finding this run did not go looking for: the guard costs three times what it
guards.** `search` decides whether to run the vector leg by asking `store.vector_counts()`,
which is a `GROUP BY` over the whole `vectors` table, **once per hybrid query**. At 10⁵ rows
that is **129.9 ms** — three times the vector leg on a fresh handle, eleven times the warm
leg, and 87 % of NFR-2's entire 150 ms budget spent before any retrieval happens. It answers a
yes/no question — *does this snapshot hold vectors for this model* — with a full aggregate.
Filed as roadmap **6.27**; fixing it inside the item that measured it is how a measurement
stops being trustworthy.

**4. Hybrid costs +283 ms p50 over lexical, and half of that is the guard.** Of the difference
between 1 288.3 ms and 1 004.9 ms, 129.9 ms is the precondition and 12.1 ms is the leg itself;
the remaining ~141 ms is fusion plus the run-to-run variance two separately timed passes carry
on a one-second baseline. Do not read the residual as a mechanism — it is smaller than the
spread.

**5. None of this changes what the query path needs.** Every full-query figure here is an
order of magnitude over NFR-2, and the cause is the lexical leg at 10⁵ chunks, which roadmap
6.19 and 6.24 own. The vector leg is a rounding error against it. A reader deciding whether
hybrid is affordable should note that the honest answer at this scale is *"the question is
moot until the lexical path is fixed"*.

### Limits

- **The vectors are synthetic, so nothing here is about retrieval quality.** See the scenario
  above; gate G2 owns that and cannot answer until 6.8 grows the judged sets.
- **The page cache is warm for every figure**, including the "fresh handle" one: the pack had
  just been written. A genuinely cold filesystem read is a property of the machine, and this
  run does not measure it. The fresh/warm distinction here is the *mapping*, which is what
  ADR-0030 established as the one that matters.
- **The fresh-handle sample is twelve queries**, not thirty-nine, because each opens a store
  and maps 154 MB; the manifest records the count beside the number.
- **`embed_query` is excluded from the hybrid figures on purpose.** A real hybrid query adds
  it — 9.7 ms p50 here — and it is the embedder's cost rather than retrieval's. Add the two;
  do not assume either contains the other.
- **One machine, wall-clock, otherwise idle.** The manifest carries the hardware, without
  which none of these numbers is comparable.

## Reproduce

From a clean checkout, with `uv sync --all-extras --dev`, on an otherwise idle machine — a
contended benchmark is not a slow benchmark, it is a wrong one:

```bash
# This report, in one pass (~25 min on the machine of record).
python tools/benchmark_reference_profile.py \
    --out <scratch-dir> --scales "" --no-reference \
    --query-scale 100000 --vectors \
    --manifest docs/benchmarks/manifests/2026-09-18-the-hybrid-path-at-the-reference-profile.json

# The 10 000-chunk bench the extrapolation was taken from, for the comparison.
uv run pytest tests/bench/test_retrieval_bench.py --benchmark-only

# Validate every committed manifest (instant; the ladder runs this at every mode).
python tools/benchmark_reference_profile.py --check
```

The local embedding model is needed only for the `embed_query` line; without it that
measurement is reported as absent rather than invented, and every other number is unaffected.
