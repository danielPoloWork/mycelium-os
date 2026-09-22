# ADR-0150: Report the stage budgets where they mean something, and keep gating the total

- **Status:** Accepted
- **Date:** 2026-09-22
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §§1, 7.3
- **Related:**
  [ADR-0120](0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md)
  (the precedent this applies one level down: publish what the instrument says, gate the
  instrument rather than the verdict),
  [ADR-0139](0139-time-the-tool-call-in-the-harness-and-keep-the-retriever-as-a-floor.md)
  (roadmap 6.24, which armed G5 on the call spec 04 §1 actually names),
  [ADR-0144](0144-measure-the-whole-diversity-family-and-refuse-it.md) (why one component
  of a stage budget is deliberately absent from the product),
  [ADR-0075](0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md) (why another ships off),
  [ADR-0050](0050-report-what-each-query-term-reached.md) (`terms`, the timed label
  that is not a pipeline stage); spec 04 §§1, 4, 7.3; roadmap 6.21, 6.24, 6.27, 6.35

## Context

Spec 04 §1 states five latency budgets: **plan + candidates 60 ms**, **fusion + boosts +
dedupe 20 ms**, **graph expansion 30 ms**, **stitch + pack 40 ms**, and the **150 ms**
end-to-end `mycelium_search` that is their sum plus slack. Roadmap 6.24 armed gate G5 on
the last one (ADR-0139). The four above it are gated by nothing and measured by nothing,
so the only thing anybody knows is the total — and 6.21 showed why that matters: at 10⁵
chunks the warm query alone is **1 816 ms p95**, and a total is a symptom while the stage
budgets are the diagnosis the spec already wrote down.

The item framed the decision as a choice between two costs: time the stages **inside**
`run_search` (a seam on the query path, paid on every call) or in a **bench that
reconstructs them** (no runtime cost, and it drifts from the path it claims to time).

**Reading the code first dissolved that choice.** The seam already exists and is already
paid. `search()` has timed itself since long before this item: `SearchOutcome.timings_ms`
carries `lexical`, `embed_query`, `vector`, `fusion`, `symbol`, `graph`, `terms` and
`total`, and it is a **published** field — `mycelium_explain` promises per-stage timings
(spec 05 §3.4) and `mcp/schemas.py` declares `timings_ms` as a map of counts. So there was
never a seam to add or a reconstruction to write. What was missing was the *mapping* from
those labels to the spec's stages, and a place to report them against their budgets.

**What reading the code found next is the reason four gates are the wrong answer.** Of the
four stages, two name work this product does not do:

- **`boosts` and `dedupe`.** Neither word appears anywhere under `src/`. Spec 04 §4
  describes heading-proximity, trust-class, verification and recency boosts and a
  near-duplicate collapse; `trust_class` exists only as a *filter*. The third component of
  that stage, diversity/MMR, was measured across its whole family and **refused**
  (ADR-0144). So "fusion + boosts + dedupe ≤ 20 ms" would, today, gate fusion alone.
- **`stitch`.** The word appears in spec 04 §§1 and 4 and nowhere in `src/`. So
  "stitch + pack ≤ 40 ms" would gate packing alone — and packing runs in `handle_search`,
  outside the seam.

A green gate on either row would assert the product does something it does not.

**And the third stage is off by default.** The graph leg ships disabled (ADR-0075) and is
additionally routed, so a 30 ms gate would be vacuous on every default run.

That leaves **plan + candidates** as the only stage whose named work wholly exists — and
its budget was already declared in the reference profile as `CANDIDATE_BUDGET_MS`.

**Measured, before deciding.** Reading the path's own timings across the judged query sets
on the three corpora this repository builds:

| corpus | chunks | warm p95 | `lexical` p95 / 60 ms | `fusion` p95 / 20 ms |
|---|---:|---:|---:|---:|
| this repository | 1 683 | 82.6 ms | **81 ms** | **0 ms** |
| `uv-docs` | 568 | 24.3 ms | 23 ms | **0 ms** |
| `uv-docs-ingested` | 526 | 21.1 ms | 20 ms | **0 ms** |

Two things fall straight out. **`fusion` reads 0 ms on every query of every corpus** — the
stage is smaller than the millisecond the path records it in, so a CI gate on a 20 ms
budget would be reading resolution rather than latency. And **the query path is its
lexical leg**: 81 of 82.6 ms on the corpus this repository compiles, with everything else
rounding to zero.

**And at the reference profile the stage breakdown answers the question the item was filed
to ask.** 10⁵ chunks written straight into a store (ADR-0120's method, and NFR-2's stated
condition is about what the retriever *reads*), warm, over the same 525 judged queries:

| measurement | p50 | p95 | budget |
|---|---:|---:|---:|
| `search`, warm store (in-process) | 1 374.6 ms | **2 349.7 ms** | 150 ms |
| — stage `lexical` (plan + candidates) | 1 374.0 ms | **2 348.0 ms** | 60 ms |
| — stage `fusion` (fusion + boosts + dedupe) | 0.0 ms | **0.0 ms** | 20 ms |
| `mycelium_search`, end to end (MCP handler) | 1 252.1 ms | 2 151.1 ms | 150 ms |

**The whole miss is candidate generation.** `lexical` is **2 348 of the 2 349.7 ms** — 99.9 %
of the warm query — and everything else the path times is zero. The total is 15.7× its
budget; the stage inside it is 39× its own. That is the diagnosis 6.21's 1 816 ms p95 could
not give (this run measures the same shape on a different day, and the magnitude agrees),
and it is what the stage budgets are *for*. It is also, precisely, an argument for
reporting rather than gating: nothing about a red CI row would have said "lexical", and the
number that does say it is now in the manifest.

## Decision

**The stage budgets are reported at the reference profile, read from the query path's own
timings, and CI keeps gating the total alone.**

This is [ADR-0120](0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md)'s
posture applied one level down. That ADR left G5 "enforcing the query budget on whatever
corpus ran, which is a floor worth having" and published what the budget does *at its own
stated conditions* rather than gating it there. The stage budgets are the same shape: spec
04 §1 states them for **10⁵ chunks, warm store**, and CI gates run on corpora three orders
of magnitude smaller, where the stages are below the resolution the path records them in.

**Concretely**, `tools/benchmark_reference_profile.py` gains:

- `SPEC_STAGES`, which maps each label `search` already times to the spec stage and budget
  it belongs to. `terms` is deliberately excluded: it is `explain`'s per-term report
  (ADR-0050), not a pipeline stage, and folding it in would price a budget against work
  the spec's pipeline does not contain.
- `_query_stage_notes`, which carries each stage's p50/p95 and its budget onto the warm
  search measurement — out of the *same call* the wall clock timed, so there is no second
  run and nothing to drift.
- `UNTIMED_STAGES`, which reports `stitch + pack` as having no number **and why**, rather
  than letting a stage vanish from a report. A stage absent from a report reads as a stage
  that cost nothing.
- Stages that did not run are reported with `samples: 0` and a note, for the same reason —
  the graph leg ships off rather than free.
- The four stage budgets declared in the manifest's `budgets` block, whose whole purpose
  is that "a changed budget is visible in a diff".

**No new gate, and `timings_ms` is untouched.** G5 continues to gate the 150 ms end-to-end
number on whatever corpus ran. The published `timings_ms` contract keeps its integer
milliseconds: widening it to floats would change an MCP wire schema to buy resolution that
only matters below the scale the budgets are stated for.

## Alternatives Considered

- **Add four gates, one per stage.** Rejected on the evidence above: two would gate
  unimplemented work, one would be vacuous under the shipped default, and all four would
  be compared against budgets stated for a corpus 60× larger than the one CI builds. A
  gate that cannot fail selects for being ignored (ADR-0053); a gate that asserts
  unimplemented work is worse, because it reads as a passing claim.
- **Gate the one honest stage — plan + candidates — and report the rest.** Tempting, and
  rejected on a number this work produced: `lexical` p95 is **81 ms against a 60 ms
  budget** on this repository's own 1 683-chunk corpus. Arming that gate would turn CI red
  on arrival for a budget whose stated condition (10⁵ chunks, warm) CI does not meet, and
  the honest response to a stage over budget is roadmap 6.37's re-ranking work and 6.36's
  import cost, not a red gate that blocks unrelated changes. It is *reported*, loudly, and
  filed — which is what makes it actionable rather than noisy.
- **Widen `timings_ms` to floats for sub-millisecond stages.** Rejected: it is a published
  MCP field declared as a map of counts, and the resolution only matters at scales below
  the one the budgets are stated for. At the reference profile the stages are tens of
  milliseconds and integers are ample.
- **Reconstruct the stages in the bench instead of reading the path's timings.** Rejected
  for the reason the item itself gave — it drifts from the path it claims to time — and
  made moot by the seam already existing.
- **Time `pack` by moving it inside the seam.** Rejected as out of scope and wrong-shaped:
  packing belongs to the tool handler, not to retrieval, and the honest fix for
  "stitch + pack" is to implement stitch or to correct the spec, not to half-measure the
  half that exists.

## Consequences

- **Every warm-search measurement now carries its stage breakdown**, on the generated
  curve, at the query-scale reference profile, and on the three real corpora — against the
  spec's own budgets, in the manifest and in the printed report.
- **A stage over budget is now visible.** `lexical` at 81 ms against 60 ms on this
  repository's corpus is the first thing this instrument found, and it is exactly the
  class of fact the end-to-end number hid: the total passed (102 ms against 150 ms) while
  the stage inside it did not.
- **The spec-versus-product divergence is now written down and filed** rather than
  implicit in a budget nobody could measure: boosts, dedupe and stitch are described by
  spec 04 §4 and implemented nowhere, and diversity is described there and deliberately
  refused (ADR-0144). Filed as roadmap **6.38** — reconciling the spec with the product is
  a decision about the spec, not a benchmark change.
- **`--check` is unaffected.** The new keys are notes on existing measurements, and the
  manifest check requires only that every measurement carries a `p95`.
- **Nothing on the query path changed**, so no baseline, golden or gate moves. The seam
  this reads was already there and already paid.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §1 (the five budgets and their stated
  conditions), §4 (boosts, dedupe, stitching, packing), §7.3 (the gates).
- `tools/benchmark_reference_profile.py` — `SPEC_STAGES`, `UNTIMED_STAGES`,
  `_query_stage_notes`, `_print_query_stages`.
- Re-runnable: `python tools/benchmark_reference_profile.py --scales "" --no-reference
  --real-corpora --out <dir>` for the cross-check above; add `--query-scale 100000` for
  the reference profile.
