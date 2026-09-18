# ADR-0130: Measure the vector path, and retire three disagreeing extrapolations

- **Status:** Accepted
- **Date:** 2026-09-18
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §1
- **Related:** [ADR-0120](0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md)
  (the reference profile this extends, and the limit it stated),
  [ADR-0026](0026-pack-the-vectors-into-a-memory-mapped-matrix.md) (the packed matrix, whose
  10⁵ figure this replaces), [ADR-0030](0030-correct-the-vector-scan-cost-model.md) (which
  corrected that figure once already, and was not carried everywhere),
  [ADR-0028](0028-keep-the-vector-scan-exact.md) (why the scan is exact, and why *its* recall
  half needs real embeddings where this needs none),
  [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) (the lexical default this
  measures the alternative to), [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md)
  (the precondition that splits the measurement in two),
  [BUG-0015](../bugs/2026/08/BUG-0015-benchmark-times-a-pattern-no-code-has.md) (the harness
  defect ADR-0030 recorded, and the ancestor of the two found here); spec 04 §§1, 3; D-002,
  D-013; roadmap 6.4, 6.21

## Context

The reference profile built at roadmap 6.4 measures the **shipped default**, which is lexical
(ADR-0017), and said so among its own limitations: *"Nothing here says what the hybrid path
costs at 10⁵ chunks; the only statement this project makes about that is an extrapolation
from 10 000 chunks, and roadmap 6.21 owns replacing it."*

That understated the problem. The project makes **three** statements about the vector path at
the reference scale, in three files, and they do not agree:

| where | what it says | status |
|---|---|---|
| `tests/bench/test_retrieval_bench.py` | *"the packed matrix at 100 000 chunks measures **~70 ms** for the first query in a fresh process and ~1 ms for every query after it, which is the honest limit **ADR-0026** records"* | the number ADR-0030 **corrected away**, carrying the label that ADR corrected, citing the ADR it superseded |
| `src/mycelium/store/sqlite.py` | *"a query costs 2.9 ms over 10 000 chunks, and about **31 ms** over 10^5 … from a fresh process"* | ADR-0030's number, correctly labelled — but measured over a bare `numpy` memmap, not through `search_vectors` |
| `tools/measure_vector_index.py` | `REFERENCE_N` is *"D-002's upper envelope, **where the exact scan misses the budget**"* | contradicts ADR-0030, which measured 31 ms against a 60 ms budget — inside it |

ADR-0030 is the one that already did this work, at roadmap 3.16, and its finding is precise:
the first query in a process costs ~31 ms, every later one that *re-maps the file* costs ~71,
and **no code path re-maps** — a store maps its pack once per handle, so a CLI invocation maps
once and exits and a server maps once and re-uses it. The 71 ms belongs to a pattern that
exists only in harnesses, which is what BUG-0015 records.

The benchmark docstring never received that correction. It still prints the harness number,
under the label ADR-0030 took away from it, sourced to the ADR ADR-0030 corrected. It has read
that way for five milestones.

**And even the correct statement is not a measurement of the product.** ADR-0030 timed a
`numpy` memmap and a matrix multiply. `search_vectors` also resolves the pack, applies the
serving filters in SQL, and **hydrates** its fifty results back into `SearchHit` records from
the `chunks` table. Nothing had measured that, and nothing at all had measured the thing a
user actually waits for: the whole hybrid query — plan, lexical leg, vector leg, fusion — at
10⁵ chunks.

### Why this could not simply be run

Two obstacles, and the first was invisible until the run was attempted.

**Every chunk in the reference profile shared one `chunk_digest`.** The generator wrote a
single placeholder, on the true observation that the lexical path never reads that column —
`chunks_fts` does not carry it, so BM25 cannot see it. The vector path can see nothing else:
vectors are keyed `(chunk_digest, model_id)` (D-013) and `search_vectors` hydrates by that
key. A vector profile over that store would have held **one vector for a hundred thousand
chunks**.

**Embedding 10⁵ real chunks is hours of work that measures the embedder.** The scan is exact
and touches every vector whatever it contains, so geometry cannot change how long the
multiplication takes — which is why synthetic vectors are honest for a *cost* measurement and
why `tests/bench/test_retrieval_bench.py` has always used them at 10 000. They would be
dishonest for a *quality* measurement, and none is made here.

## Decision

**The vector path is measured at 10⁵ chunks through the code that serves it, and the three
statements above are replaced by what the run says.** `tools/benchmark_reference_profile.py`
gains `--vectors`: it writes one synthetic unit vector per chunk through `put_vectors`, lets
the store's own `repack_vectors` build the memory-mapped matrix, and times five things — the
vector leg on a fresh handle and on a warm one, the whole hybrid query, the same queries
lexical-only on the same store, and the per-query precondition `search` runs to decide whether
the snapshot holds vectors at all. The report is
[`docs/benchmarks/2026-09-18-the-hybrid-path-at-the-reference-profile.md`](../benchmarks/2026-09-18-the-hybrid-path-at-the-reference-profile.md)
with its manifest committed beside it.

**The generated chunk digest is derived from the chunk's anchor**, outside the generator's
`random.Random` stream. The prose the same seed produces is byte-identical and only that
column moves, which is what lets 6.4's published figures and these be read as measurements of
one corpus rather than two.

**The hybrid measurement is split by whether the vector leg actually ran.** ADR-0025 withholds
it where the lexical leg found nothing, so a question this corpus cannot answer costs the
lexical price; folding those into one mean would report the cost of a leg that did not run.
Both buckets and their counts are in the manifest.

**What the run says**, at 100 000 chunks and 100 000 vectors (153.6 MB of matrix), against the
three statements it replaces:

| | fresh process / handle | warm handle |
|---|---:|---:|
| `tests/bench/test_retrieval_bench.py` claimed | ~70 ms | ~1 ms |
| `src/mycelium/store/sqlite.py` claimed | ~31 ms | ~1 ms |
| **measured through `search_vectors`** | **43.2 ms** | **12.1 ms** |
| spec 04 §1's candidate budget | 60 ms | 60 ms |

Both patterns are **inside** the budget, so ADR-0026's choice of an exact scan holds at the
top of the v1 envelope — and both previous numbers were wrong, in opposite directions. The
benchmark's was the harness pattern BUG-0015 named; ADR-0030's was low because a bare `numpy`
memmap skips the pack resolution, the SQL filters and the hydration of fifty results that
`search_vectors` performs. The warm figure is the larger error: twelve times, not one.

**The three statements are replaced by one.** The benchmark docstring and
`tools/measure_vector_index.py`'s stale *"where the exact scan misses the budget"* now point
at the report; `search_vectors`'s docstring carries the measured pair.

**And the run found what it was not looking for.** `search` decides whether to run the vector
leg by calling `store.vector_counts()` — a `GROUP BY` over the whole `vectors` table — **once
per hybrid query**. At 10⁵ rows that costs **129.9 ms**: three times the leg it guards on a
fresh handle, eleven times the warm leg, and 87 % of NFR-2's whole budget, to answer a yes/no
question. It is **filed as roadmap 6.27 and not fixed here**, for the reason this ADR applies
to itself elsewhere: an item that repairs what it measured cannot be read as a measurement.

## Alternatives Considered

- **Leave the extrapolation and correct only the stale docstring.** The cheapest fix, and it
  fails the test this item exists to apply: 6.4 was filed precisely because *"search p95 < 150
  ms on the 10⁵-chunk reference corpus"* had been a closed exit gate for three milestones on a
  measurement at 1/70th of its scale. Replacing one unmeasured sentence with another
  unmeasured sentence repeats that.
- **Embed 10⁵ real chunks with the local model.** The only way to make the vectors *mean*
  something, and it measures the wrong thing: hours of ONNX inference, whose cost is the
  embedder's, to produce a matrix whose contents the scan is indifferent to. It is what a
  quality measurement would need, and a quality measurement is gate G2's, which cannot run
  until 6.8 grows the judged sets.
- **Extend `tools/measure_vector_index.py` instead.** It already synthesises 10⁵ vectors and
  times a cold-process query, which is most of the machinery. Rejected because what it times
  is a bare `numpy` memmap — deliberately, since its subject is whether an *index* could beat
  the scan, and the answer must not depend on how the store hydrates. The question here is the
  opposite one: what the product costs, hydration and filters and fusion included.
- **Measure the vector leg only, not the whole query.** Half the finding. The leg's cost is
  the part that was already roughly known; what nothing knew is what a caller pays for a
  hybrid query at this scale, and that is the number a decision about the default would rest
  on.
- **Time the fresh-handle case in a subprocess**, as ADR-0030 did. Its reason was to defeat a
  harness that re-mapped per call inside one process; opening a fresh `SqliteStore` gives a
  fresh mapping without the process boundary, and the page cache is warm either way. The
  report states that limit rather than claiming a cold filesystem read.
- **Fix the per-query precondition here.** Measuring it found it; fixing it is a change to the
  query path with gates of its own, and folding it into the item that discovered it is how a
  measurement stops being trustworthy. Filed instead.

## Consequences

- **The one statement this project makes about the vector path at 10⁵ is now a measurement**,
  with a committed manifest and a command that reproduces it. Three files stop disagreeing.
- **ADR-0026's decision is confirmed at the scale that tests it**, and ADR-0028's refusal of an
  approximate index is untouched: its evidence is recall on real embeddings, which this run
  deliberately cannot speak to.
- **Roadmap 6.27 is filed** for the per-query precondition, which is the largest single
  avoidable cost anywhere on the hybrid path and was invisible until the path was timed.
- **`tools/benchmark_reference_profile.py` gains `--vectors`**, so the next person asking this
  question re-runs one command instead of building an instrument. The chunk digest it writes
  is now distinct per chunk; `chunks_fts` never carried that column, so no lexical figure it
  has published moves.
- **Two instrument defects were found and fixed before they reached a number**, which is worth
  recording because both are the family BUG-0015 belongs to — a harness measuring something
  the product does not do. The first read the legs that ran off the *last* query and reported
  `lexical` for a pass in which the leg had run on 34 of 39; the second drew 384 gaussians in
  Python inside the timed region, charging the instrument's cost to retrieval. Neither would
  have been visible in the published number.
- **A limit this does not remove.** Every figure is one machine's wall clock with a warm page
  cache, and the fresh-handle number is the *mapping* cost rather than a cold read. The report
  says so beside the number rather than in a footnote.
- **Nothing about the product's behaviour changes.** No gate, golden, baseline or corpus is
  touched; `retrieval_identity()` is unmoved, so the gate-G2 verdict stays current.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §1 (the latency budgets and the
  candidate-generation stage), §3 (the fusion these two legs feed).
- Report: `docs/benchmarks/2026-09-18-the-hybrid-path-at-the-reference-profile.md`; manifest
  `docs/benchmarks/manifests/2026-09-18-the-hybrid-path-at-the-reference-profile.json`.
- Re-runnable: the command in the report's *Reproduce* section, and
  `python tools/benchmark_reference_profile.py --check`.
