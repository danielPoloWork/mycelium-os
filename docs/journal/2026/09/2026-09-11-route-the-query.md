# 2026-09-11 — the router that cannot save it (roadmap 5.11)

- **Session scope:** roadmap 5.11 — build spec 04 §2's planner, and re-run the two lost
  ablations under it (spec 04 §§2, 5; ADR-0075, ADR-0080).
- **PR:** #110 (`feat/route-the-query-not-every-leg`). Follows #109, merged as `83dfe03`.
- **Milestone 5:** 5.11 done. 5.12–5.21 open.
- **ADR:** [ADR-0083](../../../adr/0083-route-the-query-and-report-that-routing-cannot-save-a-lost-ablation.md),
  narrowing [ADR-0075](../../../adr/0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md)
  and completing [ADR-0080](../../../adr/0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md).

## The item's hypothesis, and the half of it that was wrong

5.11 was filed twice, by both ablations, with the same reasoning: expansion pays its cost on
every query and offers its benefit on few, so *"a router that spent the budget only where the
shape of the question predicts a relationship would change the arithmetic the gate is decided
on — six losses spread across `fact`, `conceptual` and `symbol` are cases expansion should
never have touched."*

The first half is true. Of the thirteen cases expansion loses unrouted, seven are outside the
relationship slice and routing removes every one of them: with the shipped rules the overall
cost of enabling the leg falls from 0.0–4.1 % to **0.0 %** on all six judged sets.

The second half is where the item's hypothesis breaks, and the number that breaks it is the
oracle. Route by the judged `relationship` slice itself — no deterministic rule set can beat a
router that reads the answers — and the slice's column comes back **identical to the unrouted
arm, digit for digit, on all six sets**. The bar is stated on that slice; routing only decides
whether the leg runs on queries *outside* it; the leg already ran on the slice's cases in the
unrouted arm. **Six of the thirteen losses are relationship cases** — exactly where a perfect
router sends expansion on purpose. So routing cannot move the gate's number, not with better
rules and not with a model, and the verdict stands for a reason stronger than a measurement.

That was worth building the oracle arm for. Without it this session would have shipped a
router, measured +0.0 %, and left open the question of whether a better one would have won.

## A phrase list cannot find a relationship question

Measured as a classifier against all 133 judged case-instances:

| rule set | fires | precision | recall |
|---|---:|---:|---:|
| the spec's two phrasings, literally | 1 | 100 % | 5 % |
| those two, generalised to their verb family (shipped) | 3 | 100 % | 14 % |
| a list written by reading the queries it had to catch | 18 | 72 % | 59 % |

The judged slice is judged by *where the answer lives* — two documents holding two halves —
and not by wording. `can an agent keep querying while a build is running` is the case
expansion exists to rescue, and there is no relationship phrase in it. Nor in
`why does a single lockfile cover every package in a workspace`, nor in sixteen others.

The wide list was the interesting temptation: on ours/release it clears the gate outright
(`relationship` +19.7 %, overall +2.6 %). It also loses 43.1 % on uv/dev — and it was written
by reading the queries. It helps on exactly the corpus whose questions I read and nowhere
else, which is what fitting looks like from the inside. Refused and reported, as the fifteen
re-rankings before it were.

So the shipped list is the spec's two phrasings generalised to their verb family and no
further, its 14 % recall is printed in the module that holds it, and `--related` is the signal
that actually works: the caller knows what kind of question they are asking.

## The rule the planner needed before it could exist

Three of this project's defaults were set by measurement — the vector leg by gate G2, the two
derived legs by their ablations. A router that could switch a leg *on* would overturn all
three with a regex, and the first symptom would be a benchmark moving for a reason no manifest
could record. So: **the plan narrows; the configuration decides.** A plan may withhold a
generator the configuration enabled and may never enable one it disabled. It is the direction
`_serve_only` already narrows in, and the direction `--mode` already widens in: the safe one.

`--related` therefore does what `--hybrid` does — it edits the configuration for one
invocation and then satisfies the routing rule. The planner still enables nothing.

## Two smaller findings, both refusals

**"Vector as backfill" is the wrong way round.** Spec 04 §2's first row ends with it, and it
is tempting because hybrid's one losing slice at gate G2 was `exact`, which is where the
identifier queries are. Measured: withholding the vector leg from identifier queries costs
uv/dev 5.2 points of hybrid's gain and turns its `exact` slice from +9.7 % to −0.5 %, and
uv/release's from −1.6 % to −9.0 %. The vector leg helps identifier queries here. Refused,
and written down where the next reader will look for it.

**The symbol leg was already routed.** It has always tested each query token before touching
the store — the routing existed, inside the leg, where a plan could not report it. Moving that
test into the planner is a refactor with identical behaviour by construction, and all three
arms score +0.0 % on all six sets, which is the check rather than the claim.

## What did not move

The shipped ranking. Both derived legs are off by default, so a default search plans exactly
the legs it always ran — asserted directly rather than assumed. No baseline was re-blessed, no
judged set touched, gate G3 had nothing to re-run and the frozen-set guard had no conjunction
to refuse. Gate G2's verdict was re-recorded, because `retrieval_identity()` gained the
routing rules and a verdict is about the configuration it was measured under (ADR-0064).

## Lesson

When a feature loses an ablation and the obvious next move is "we measured it wrong", build
the arm that reads the answers before building the one that guesses them. The oracle took
twenty minutes and turned an open question into a closed one: it is not that this router is
too weak, it is that the bar sits on the slice routing cannot reach. A cheap upper bound is
worth more than a clever heuristic, and it is the only way to tell a lost measurement from a
lost mechanism.
