# ADR-0075: Let the graph propose and the ranking dispose — and report that it lost the ablation

- **Status:** Accepted
- **Date:** 2026-09-10
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §5
- **Related:** [ADR-0018](0018-build-the-graph-from-authored-links.md) (the graph this walks,
  and the reason a chunk is not a node), [ADR-0074](0074-give-every-edge-type-a-derivation-or-a-reason-it-has-none.md)
  (the six edge types, and its deferral of weights to *this* ablation),
  [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) (RRF, and the first gate
  that decided a default by measurement), [ADR-0068](0068-give-gate-g2-a-runner-by-dating-its-verdict.md)
  (a gate needs a runner), [ADR-0064](0064-measure-the-gate-that-decides-the-default.md)
  (a verdict is about the configuration it was measured under),
  [ADR-0031](0031-refuse-three-rerankings.md) and [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md)
  (the refused re-rankings this joins), [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md)
  (evidence as a leg's precondition), [ADR-0024](0024-serve-what-the-configuration-admits.md)
  (the serving policy's one seam); spec 04 §§2–5, spec 05 §§2, 3.4; D-009, D-014; roadmap 5.3,
  5.7, 5.11

## Context

Spec 04 §5 has been waiting since Phase 3 was written:

> 1-hop expansion from top-k fused candidates over typed edges, budget-capped (≤ 10 nodes,
> ≤ 30 ms), edge types weighted (`defines`/`supersedes` high; `mentions` low). Expanded
> candidates enter fusion with a discount and are labeled `via_edge` in `explain`.
> **Gate:** graph expansion ships enabled-by-default only if ablation shows ≥ +3 % nDCG@10
> on the `relationship` slice with no overall regression; otherwise it remains an opt-in
> flag until it earns the default (F-8 discipline).

5.2 finished the graph it walks over. `[retrieval] graph_expansion` existed as a config key
that *refused* to be set. The milestone goal is careful about what success means here:
"graph expansion earns default-on or stays opt-in (**measured either way**)". The
deliverable is the measurement.

Four things were measured before any code was written, and each changed the design.

**Where the answers actually are.** Across the three corpora, every judgment a
`relationship` case misses at rank 10 is reachable by BM25 at *some* depth — ranks 11 to
189, never absent. So expansion never needs to add a passage the index cannot score; it
needs to surface one the ranking put too low. That makes the mechanism a *depth* problem,
not a *reach* problem, and it is why the leg resolves nodes back to chunks and ranks them
with the same BM25 as everything else.

**How wide one hop is.** From ten seeds on this repository's corpus, one hop reaches 530 of
982 chunks — more than half the corpus. "Expansion" over a densely cross-linked
documentation set is closer to "return everything" than to "return the neighbour", so the
budget is not a safety margin, it is the entire mechanism.

**Which edges carry a rescue.** `links_to`, almost exclusively. Across the nineteen
relationship cases, nine have at least one judgment a single hop can reach, and those nine
cases hold **eleven** such judgments: **ten** are reached by `links_to` and **one** by
`part_of`. Not one is reached by `defines`. So spec 04 §5's suggested weighting —
`defines`/`supersedes` high, `mentions` low — has nothing to act on: `supersedes` (roadmap
5.10) and `mentions` (5.4) are not emitted at all, and `defines` never appears on a rescue
path.

**What a rescuing node stands for.** Nine of those eleven are whole documents holding six
or more chunks. The graph names a document; which of its six chunks answers the query is a
question the graph cannot answer.

## Decision

**The graph proposes nodes; the ranking disposes of chunks.** Expansion walks one hop from
the fused seeds, resolves the surviving nodes back to the chunks behind them — a section to
its own chunks, a document to all of its chunks, a symbol to its `doc_refs` — and ranks
those with the same field-weighted BM25 the lexical leg uses (`SqliteStore.rank_anchors`). A
proposed node whose chunks contain none of the query's words contributes nothing. Adjacency
decides *membership*; relevance decides *order*.

**Expansion adds; it never promotes.** A passage another leg already returned is not carried
in this leg. This is the load-bearing rule and it was learned the expensive way: the first
implementation let both contributions sum, so a passage at lexical rank 40 that happened to
be adjacent to a seed scored `1/100 + 0.9/61` and leapfrogged the passage at lexical rank 1,
which scored `1/61`. Measured on six case sets it cost between **5 % and 56 %** overall —
cases that had been perfect fell to a third — because *being adjacent* was worth nearly as
much as *being the best match*. The consequence of the rule is worth stating plainly: since
the lexical leg is 50 candidates deep, expansion can only ever surface something the ranking
placed beyond 50. On a corpus smaller than that it does nothing at all.

**The budget is spent breadth-first across seeds, not depth-first through the best one.**
Ten seeds each contribute their first neighbour before any contributes a second. The
measurement that forced this: on `r-0018` the top hit is an ADR linking to a dozen others
and it filled all ten places by itself, so the seeds at ranks 3 and 4 — the two that reach
the answer — proposed nothing. Rescuing seeds were measured at ranks 1, 2, 3, 4, 5, 7 and 8,
so the seed budget is the served window of ten and not something tighter.

**One chunk per document leaves the leg**, which is spec 04 §4's diversity rule applied
where it is cheapest: without it one adjacent thirty-chunk document fills the whole leg.

**Every edge type weighs the same, and the reason is the measurement, not modesty.**
ADR-0074 deferred edge weights to this ablation. The ablation's own data says there is
nothing to weight: two of the eight types are not emitted, and of the six that are, only
`links_to` and `part_of` ever appear on a path to an answer. A weighting fitted to that
would be a constant tuned to two observations.

**The discount is 0.9, its admissible range is derived, and the difference between those
two facts is stated rather than blurred.** RRF at k=60 is deliberately flat: rank 1
contributes `1/61` and rank 50 `1/110`, less than a factor of two across a whole leg. For a
served window of ten, two bounds follow. A graph-only passage must not outrank the lexical
leg's best, so `d < 1`. And it must be able to displace the window's weakest, or the leg
cannot change an answer and the ablation measures nothing, so `d > 61/70 ≈ 0.871`. **The
mechanism spec 04 §5 prescribes therefore has an operating window of roughly `0.87 < d < 1`
and no more.** Anything at or below the coarse "half as good" reading of *discount* is
arithmetically inert. 0.9 is a round number inside the derived window, and the ablation was
run once at it.

**`via_edge` labels every proposed passage** with the edge type and the seed anchor that
reached it, in `mycelium search --explain`, in `--json`, and in `mycelium_explain`.

**And the verdict: expansion does not earn the default, so it stays opt-in.** Measured on
six case sets across three corpora, at the shipped constants:

| set | lexical | expanded | overall | `relationship` |
|---|---:|---:|---:|---:|
| ours/dev | 0.5400 | 0.5197 | −3.7 % | −1.2 % |
| ours/release | 0.5263 | 0.5049 | −4.1 % | −4.2 % |
| uv/dev | 0.6143 | 0.6043 | −1.6 % | −43.1 % |
| uv/release | 0.6109 | 0.6068 | −0.7 % | +0.0 % |
| uv-ingested/dev | 0.5505 | 0.5503 | −0.0 % | −0.8 % |
| uv-ingested/release | 0.6370 | 0.6212 | −2.5 % | −3.8 % |

Not one set clears +3 % on the slice, and every set regresses overall. **It does rescue the
case it was filed for** — `r-0018`, the query whose two documents hold the two halves of the
answer, goes **0.0000 → 0.2275** — and in the same set it loses `r-0011` 0.2761 → 0.0000. On
the relationship slice across all six sets the tally is **one case gained and six lost**.

`tools/measure_graph_expansion.py` is the runner, and `--check` fails when the shipped flag
disagrees with the measurement — never when the ablation is lost, because losing it is a
legitimate outcome that would otherwise turn CI red on every correct build (ADR-0068's
distinction). It runs from the `retrieval` rung in `tools/verify.py` and in CI, where —
unlike G2 — it can re-measure rather than merely re-date, because it needs no model.

> **Answered at roadmap 5.11 ([ADR-0083](0083-route-the-query-and-report-that-routing-cannot-save-a-lost-ablation.md)).**
> The follow-up this ADR filed — should the seed set be the query's own routing decision
> rather than every query's top ten — was measured, and routing does not change this
> verdict. It cannot: route by the judged slice itself, which no rule set can beat, and the
> `relationship` column above is reproduced **digit for digit on all six sets**, because the
> bar is stated on that slice and routing only withholds the leg from queries outside it. Of
> the thirteen cases expansion loses here, six are relationship cases — where a perfect
> router sends it on purpose. What routing does change is the collateral damage: with the
> shipped rules the overall cost falls from the 0.0–4.1 % below to **0.0 % on every set**.
> The leg is routed from 5.11 onward, so `tools/measure_graph_expansion.py --every-query`
> is what reproduces the table above.

## Alternatives Considered

- **Ship it on anyway, because the graph is the product's story.** Rejected on the numbers,
  and this is the whole point of having written the gate down before building the feature.
  Spec 04 §5 calls this F-8 discipline, and the milestone goal says either outcome is a pass
  so long as it is measured.
- **Tune the discount until a set passes.** The curve was measured and is reported below
  precisely so nobody has to guess — but choosing the peak is fitting, and this project has
  refused that move fourteen times (ADR-0031, ADR-0041). At `d = 0.5` and `d = 0.7` the
  results are **byte-identical to the baseline on all six sets** — the leg is inert, as the
  arithmetic predicts. At 0.9 the losses above; at 0.95 up to −6.4 % overall; at 1.0 between
  −6.8 % and −18.7 %. There is no value at which the leg both matters and helps.
- **Tune the node budget instead.** Also measured, also reported: at one node and `d = 0.9`,
  `uv/dev` *does* clear the gate (`relationship` +52.9 %, overall +2.0 %) — and the other
  five sets still lose. Taking that would be fitting to one four-case slice, and the same
  parameter at adjacent values swings that slice from **+52.9 % (1 node) to +6.2 % (3) to
  −43.1 % (5)**. A slice of four cases with a base mean of 0.115 moves by more than 100 %
  when one case moves; ADR-0058 and ADR-0069 both say to decompose a thin slice before
  believing it, and decomposed, this is one case, not a signal.
- **Let expansion promote as well as add** — the first implementation. Rejected by
  measurement: 5 % to 56 % worse overall, because RRF gives a leg authority proportional to
  its *length*, not its quality, so a second vote for adjacency outweighs the ranking's own
  first choice.
- **Weight edge types as spec 04 §5 suggests.** Rejected because the data has nothing to
  weight (above). Recorded rather than silently skipped, because the next reader will look
  for it in the code and find uniform weights.
- **Expand from the lexical list rather than the fused one.** Rejected: spec 04 §5 says
  "top-k fused candidates", and a seed the vector leg promoted is as good a door as one BM25
  found. It costs nothing to honour.
- **Emit warnings for nodes that proposed nothing.** Rejected for ADR-0074's reason about
  unresolvable uses: a proposal that does not match is the mechanism working, not a defect,
  and a warning per query would bury the ones that matter.
- **Refuse the feature and record the refusal**, as with the fourteen re-rankings. Genuinely
  arguable, and the closest call here. Rejected because spec 04 §5 defines the flag, the
  ablation is the deliverable rather than the feature, and the conditions that make
  expansion useless on these corpora are *named and open*: ingested corpora are barely in
  the graph at all (roadmap 5.7 — 29 edges against uv's 321), and the corpora we can measure
  on are documentation about a tool rather than about an API. Shipping the mechanism behind
  a measured-off flag keeps the ablation re-runnable on a corpus that has neither problem.

## Consequences

- **`[retrieval] graph_expansion` is real and defaults to `false`**, with the numbers in its
  docstring rather than a promise. The validator that refused the value is gone. An operator
  who turns it on gets a labelled, budgeted, explainable leg and a documented cost of
  0.0–4.1 % overall on the corpora measured.
- **A test asserts the default and the three constants**, so flipping either without
  re-running the ablation fails the suite as well as `--check`.
- **`retrieval_identity()` gains the graph constants** — they decide a ranking whenever the
  flag is on — so gate G2's verdict was re-recorded in this change (ADR-0064's rule). The
  shipped ranking is unchanged, so no baseline moved and no judged set was touched.
- **`src/mycelium/graph.py` joins `TUNING_PATHS`.** The edges were a read-only tool surface
  until now; with expansion available they are a candidate generator, and a change to them
  can change what a query returns. Leaving it out would be the gap `harness.py` was
  (ADR-0059).
- **Latency is inside budget.** Spec 04 §5 allows the expansion 30 ms; measured over 117–141
  queries per corpus after warm-up, the leg's p95 is **24 ms** on the densest corpus (max
  29), 15 ms on uv and 10 ms on the ingested twin. It costs one edge lookup per seed node,
  one grouped anchor query, and one BM25 query.
- **Two store methods join the protocol**: `rank_anchors` (score a named set of chunks) and
  `anchors_of_paths` (one round-trip for ten documents). Both are general, and the second is
  the difference between one query and ten inside the budget.
- **The G6 golden and every baseline are untouched**, because the shipped configuration is
  unchanged. This item moves no number the product reports by default.
- **A follow-up is filed rather than implied**: roadmap 5.11 asks whether the seed set
  should be *the query's own routing decision* rather than every query's top ten — spec 04
  §2 already routes relationship phrasing to "hybrid + graph expansion", and this item
  expands on every query alike, which is the cheapest possible reading of the spec and quite
  possibly the wrong one.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §2 (the planner's routing rules), §3
  (RRF, the leg contract), §4 (diversity), §5 (this gate);
  `.draft-specs/05-interfaces-and-plugins.md` §2 (`graph_expansion`), §3.4 (`explain`).
- Decision log: D-009 (hybrid + RRF), D-014 (typed edges, controlled vocabulary).
- Re-runnable: `python tools/measure_graph_expansion.py`, and
  `--discount` / `--nodes` for the curves above.
- Tests: `tests/test_expansion.py`.
