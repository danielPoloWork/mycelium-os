# 2026-09-10 — the ablation the graph lost (roadmap 5.3)

- **Session scope:** roadmap 5.3 — graph expansion behind spec 04 §5's ablation gate. The
  third Milestone 5 feature, and the first whose deliverable was the measurement rather
  than the mechanism.
- **PR:** #102 (`feat/graph-expansion-ablation`). Follows #101, merged as `15db406`.
- **Milestone 5:** 5.3 done; 5.11 filed (expansion runs on every query, and spec 04 §2 says
  it should not).
- **ADR:** [ADR-0075](../../../adr/0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md).

## Four measurements before a line of code

Spec 04 §5 has waited since Phase 3 was written, and it is unusually specific: one hop, ten
nodes, thirty milliseconds, a discount, a `via_edge` label, and a gate — +3 % nDCG@10 on the
`relationship` slice with no overall regression, or the flag stays opt-in. The milestone
goal is careful in the same way: *measured either way*. So the honest order of work was to
measure the thing the spec assumes before building the thing the spec describes.

**Where the answers are.** Every judgment a relationship case misses at rank 10 is
reachable by BM25 at some depth — ranks 11 to 189, never absent. Expansion is a depth
problem, not a reach problem.

**How wide one hop is.** Ten seeds reach 530 of this repository's 982 chunks. Over a
densely cross-linked documentation set, "expansion" is closer to "return everything".

**Which edges carry a rescue.** Nine of the nineteen relationship cases have a judgment one
hop can reach, eleven judgments between them: ten by `links_to`, one by `part_of`, none by
`defines`. Spec 04 §5 suggests weighting `defines` and `supersedes` high and `mentions`
low; two of those are not emitted at all and the third never appears on a path to an
answer. ADR-0074 deferred edge weights to this ablation, and the ablation's answer is that
there is nothing to weight.

**What a rescuing node stands for.** Nine of those eleven are whole documents with six or
more chunks. The graph names a document; which chunk answers the query is not a question
an edge can answer. Hence the design: the graph proposes nodes, the ranking disposes of
chunks, and a proposed node whose chunks match nothing contributes nothing.

## The defect that cost 56 %

The first implementation let a passage appear in both the lexical leg and the graph leg.
RRF sums contributions, so a passage at lexical rank 40 that happened to be adjacent to a
seed scored `1/100 + 0.9/61` and leapfrogged the passage at lexical rank 1, which scored
`1/61`. On six case sets it cost between 5 % and 56 % overall — `q-0007` and `q-0010`, both
perfect, fell to a third.

The rule that fixes it is one sentence: **expansion adds, and never promotes.** What the
ranking already found keeps the rank the ranking gave it. The consequence is worth stating
because it bounds the whole feature: the lexical leg is fifty candidates deep, so expansion
can only surface something placed beyond fifty. On a corpus smaller than that it does
nothing, which is why this item's test fixture carries seventy filler documents.

The second defect was quieter. The budget was spent in seed order, and on `r-0018` the top
hit is an ADR linking to a dozen others — it filled all ten places by itself, so the seeds
at ranks 3 and 4, the two that actually reach the answer, proposed nothing. Round-robin
across seeds fixed it, and it is the same principle `neighbours` already applies across
depth: spend a bounded budget on breadth.

## The discount has no operating point

RRF at k=60 is deliberately flat — rank 1 contributes `1/61`, rank 50 contributes `1/110`.
Two bounds follow for a ten-deep window. A graph-only passage must not outrank the lexical
leg's best (`d < 1`), and it must be able to displace the window's weakest or the leg
cannot change an answer at all (`d > 61/70 ≈ 0.871`). The mechanism the spec prescribes has
an operating window of about `0.87 < d < 1`, and the sweep confirms it exactly:

| discount | result |
|---|---|
| 0.5, 0.7 | identical to the baseline on all six sets — inert |
| 0.9 | −0.0 % to −4.1 % overall |
| 0.95 | up to −6.4 % |
| 1.0 | −6.8 % to −18.7 % |

Below the window it is invisible; inside it, it loses. That is a fact about Reciprocal Rank
Fusion worth knowing before anyone reaches for a fourth leg: **RRF gives a leg authority
proportional to its length, not its quality.**

## The verdict, and the temptation

Not one of six sets clears +3 % on the slice, and every one regresses overall. It does
rescue the case this item was filed for — `r-0018`, 0.0000 → 0.2275 — and loses `r-0011`
0.2761 → 0.0000 in the same set. Across all six sets: one relationship case gained, six
lost.

The temptation was real and is on the record. At a **one-node** budget, `uv/dev` clears the
gate: relationship +52.9 %, overall +2.0 %. Shipping that would have been a pass. It is
also one four-case slice with a base mean of 0.115, where a single case moving changes the
mean by more than 100 % — and the same knob at three and five nodes reads +6.2 % and
−43.1 % on that same slice while five other sets lose throughout. ADR-0058 and ADR-0069
both say to decompose a thin slice before believing it. Decomposed, it is one case.

So the flag ships off, with the numbers in its own docstring, and
`tools/measure_graph_expansion.py` is the runner. Its `--check` fails when the shipped
default disagrees with the measurement and never when the ablation is lost — the
distinction ADR-0068 had to make for G2, for the same reason: a gate that is red on the
correct configuration is a gate everyone learns to ignore.

## What shipped anyway, and why

A feature that lost its gate is still a feature: `via_edge` labels every proposed passage
in `--explain`, the leg's p95 is 24 ms against a 30 ms budget, the serving policy filters
it at the same seam as everything else, and `src/mycelium/graph.py` joins `TUNING_PATHS`
now that an edge can change what a query returns. Refusing the feature outright was
argued and rejected for one reason: the conditions that make expansion useless here are
*named and open*. Ingested corpora are barely in the graph at all (5.7 — 29 edges against
uv's 321), and both corpora we can measure on document a tool rather than an API. The
mechanism sits behind a measured-off flag so the ablation can be re-run on a corpus that
has neither problem.

And one thing the work found rather than planned, filed as 5.11: expansion runs on *every*
query, while spec 04 §2's routing table already reserves it for relationship phrasing. That
matters because of how the ablation lost — the cost is paid on all cases, the benefit is
available on few, and four of the six losses are in slices expansion should never have
touched. The v1 planner arrives with the symbol leg at 5.9, so routing is one decision to
take once with both legs in hand.

## Lesson

A gate written before the feature is worth more than a feature written before the gate: it
turns "the graph should help" into a number, and the number was no. The cheaper lesson
inside it is arithmetic — in a rank-fusion scheme a discount that makes a leg polite also
makes it invisible, so "add a leg and discount it" is not a design, it is two settings that
cannot both be satisfied.
