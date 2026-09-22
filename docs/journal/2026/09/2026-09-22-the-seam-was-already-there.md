# 2026-09-22 — the seam was already there (roadmap 6.35)

- **Session scope:** roadmap 6.35 — four of spec 04 §1's five latency budgets have never
  been measured against. Decide whether to time the stages on the query path or in a bench,
  and whether four more gates is the right answer at all.
- **PR:** #185 (`feat/report-the-stage-budgets-where-they-mean-something`). Follows #184,
  merged as `15c59af`.
- **Milestone 6:** 6.35 closed. 6.36, 6.37 remain open; 6.38 filed by this item.
- **Decision it records:**
  [ADR-0150](../../../adr/0150-report-the-stage-budgets-where-they-mean-something-and-gate-the-total.md).

## The item posed a choice the code had already made

The framing was: time the stages *inside* `run_search`, and pay a seam on every call; or
reconstruct them in a bench, and watch it drift from the path it claims to time. Both costs
are real and the item was right to name them. Neither applies, because `search()` has timed
itself for milestones — `SearchOutcome.timings_ms` carries `lexical`, `embed_query`,
`vector`, `fusion`, `symbol`, `graph` and `terms`, and it is a *published* field that
`mycelium_explain` promises (spec 05 §3.4).

So there was no seam to add and no reconstruction to write. What was missing was smaller
and duller than either: the **mapping** from those labels to spec 04 §1's stages, and
somewhere to report them against their budgets. Reading the code before designing the
change is what turned an architectural decision into a naming one.

## Two of the four stages name work the product does not do

This is the part that settled the "is four more gates the right answer" half of the item,
and it settled it on a grep rather than on judgement. The word `boost` appears **nowhere**
under `src/`. Neither does `stitch`. There is no near-duplicate collapse. `trust_class`
exists only as a filter. So spec 04 §1's *"fusion + boosts + dedupe"* is, in the shipped
product, fusion; and *"stitch + pack"* is pack — which runs in `handle_search`, outside the
seam anyway.

A gate on either row would be green while asserting the product does something it does not,
which is worse than a gate that cannot fail. A third row, graph expansion, ships off by
default (ADR-0075), so it would be vacuous on every default run. That leaves one stage
whose named work wholly exists.

The honest precedent is right there in the same spec section: diversity/MMR was measured
across its whole family and **refused** (ADR-0144), and spec 04 §4 now records the refusal
in place of the behaviour. The other three have no such paragraph, so the spec reads as a
description and is an intention. Filed as **6.38** rather than absorbed — it is a decision
about the spec, and a benchmark change is not the place to make it.

## The measurement answered the question the item was filed to ask

`fusion` reads **0 ms on every query of all three committed corpora**: the stage is smaller
than the millisecond the path records it in, so a CI gate there would read resolution
rather than latency. That alone disposes of gating it.

Then the reference profile, which is what the budgets are actually stated for — 10⁵ chunks,
warm, 525 judged queries:

| | p50 | p95 | budget |
|---|---:|---:|---:|
| `search`, warm | 1 374.6 ms | **2 349.7 ms** | 150 ms |
| stage `lexical` | 1 374.0 ms | **2 348.0 ms** | 60 ms |
| stage `fusion` | 0.0 ms | 0.0 ms | 20 ms |

**`lexical` is 99.9 % of the warm query.** The total misses by 15.7×; the stage inside it
misses by 39×; everything else is zero. The whole miss is candidate generation. That is
precisely what 6.21's 1 816 ms p95 could not say, and it is the argument for reporting
rather than gating in one line: a red CI row would never have said the word *lexical*, and
the number that does say it is now in the manifest.

## What was left loud rather than gated

On this repository's own 1 683-chunk corpus, `lexical` is **81 ms against a 60 ms budget**
while the end-to-end total passes comfortably at 102 ms of 150. A stage over budget inside
a total that is not — exactly the class of fact the total hides, found on the first run of
the new instrument.

It is reported, not gated, and the reasoning is written down rather than assumed: the
budget's stated condition is a corpus sixty times larger than the one CI builds, so arming
it would turn CI red on arrival for a bar whose premise CI does not meet. The honest
response to candidate generation being the cost is 6.37's re-ranking ceiling (+36 % to
+86 % for ordering the same 50 candidates correctly), not a red row blocking unrelated work.

## What shipped

`SPEC_STAGES` maps label to stage and budget — with `terms` deliberately excluded, being
`explain`'s per-term report (ADR-0050) rather than a pipeline stage, so no budget gets
priced against work the pipeline does not contain. `_query_stage_notes` carries p50/p95
against each budget out of the *same call* the wall clock timed. `UNTIMED_STAGES` reports
stitch + pack as having no number **and why**, because a stage missing from a report reads
as a stage that cost nothing; stages that did not run are reported at `samples: 0` for the
same reason. The four budgets are declared in the manifest, whose `budgets` block exists so
that a changed budget is visible in a diff.

Nothing on the query path changed. `timings_ms` keeps its published integer contract —
widening it to floats would change an MCP wire schema to buy resolution that only matters
below the scale the budgets are stated for. G5 still gates the 150 ms call, alone.
