# 2026-09-23 — a description of an intention (roadmap 6.38)

- **Session scope:** roadmap 6.38 — spec 04 §4 describes four ranking behaviours the
  product does not have, and one it measured and refused. Decide each, and never by
  deleting a sentence.
- **PR:** #PRNUM (`feat/decide-spec-04-s4s-unbuilt-behaviours`). Follows #187, merged as
  `6b6c6cf`.
- **Milestone 6:** 6.38 closed.
- **Decision it records:**
  [ADR-0153](../../../adr/0153-decide-spec-04-s4s-result-set-rules-on-evidence.md).

## The item's real constraint was the one about deletion

A spec paragraph naming work that does not exist is easy to fix badly: delete the sentence
and the divergence disappears. The item refused that in advance — each behaviour wants
either an implementation with an ablation that earns it, or a paragraph recording the
refusal the way diversity's does, because the spec is the record of what was *intended* as
much as of what shipped. That constraint is what made this an evidence exercise rather than
an editing one.

## Three of the four boosts never needed an arm

Spec 04 §4 makes boosts multiplicative on the fused rank score. A multiplicative factor
applied to every candidate alike is order-preserving *exactly*, so a boost over a field
holding one value in the corpus is not a weak effect to be measured — it is no effect, and
running it as an arm to report 0.00 % would dress a tautology as a result.

Every corpus here is single-valued in all three fields the trust boosts would read:
`trust_class`, `verification_status`, `curated`. Recency fails twice over — no judged query
asks for it, and there is no field to read, because `updated_at` is a build timestamp. uv's
81 documents span **0.7 seconds** of it. A recency boost on this data would rank by when a
build last touched a file, which is worse than not having one.

Checking the *data* before writing the arm was the cheapest useful thing in the session, and
I nearly skipped it.

## The one that varies got the full sweep, and the sweep is empty

Heading depth ranges 0–4, so that boost can move things. Eight weights, both directions
(shallow-favouring as the spec intends, deep-favouring as the opposite prior), each run
pool-wide as §4 describes and again confined to the served ten — because 6.37 had just
priced that window at 58–72 % of the reachable headroom, which makes "did the promotion or
the re-ordering cost it?" worth separating.

**None of the 96 arms gains on any set.** The best is −0.69 %, and the losses grow
monotonically with distance from 1.0 in both directions, so the family's optimum is the
shipped ranking approached from both sides. Inside the ten, weights 0.5, 0.7 and 0.8 score
*identically* — ADR-0144's inert-or-total finding turning up again in a narrower place,
because past a certain strength the boost simply sorts the ten by depth and every stronger
weight is the same policy.

## The control was the part that made the result mean something

"Every arm loses" has two readings that want opposite follow-ups: heading depth is the
wrong signal, or RRF's order is already near-optimal and any perturbation of this size costs
about this much. Dealing the same multipliers to the wrong candidates — depths shuffled
within each pool, seeded by case id — separates them, keeping the perturbation's magnitude
and destroying only the association.

Both things turned out to be true. **Any reordering of this size costs 8–25 %**, which is
the dominant effect and the real reason the sweep is empty. And heading depth genuinely
carries signal on the ingested twin (**+15.2 points** over the control, where projection
flattens headings) while being **worse than random** on the authored corpus — the spec's
prior that shallow sections answer better is backwards for prose written as documentation.
Signal that real, and it still never approaches breaking even.

## Dedupe never fires; stitching is the honest unknown

Dedupe finds **zero** same-digest pairs in the shipped ten across all six sets. I measured
the looser half of its own test too — token Jaccard ≥ 0.8 — precisely so the refusal would
not be of a narrower rule than the spec describes: 0.4 % to 5.2 % of cases. A rule whose
strict form never fires and whose loose form fires on one case in fifty is not paying for
its place in the query path.

Stitching is the opposite and is the one thing here **not** refused. It has occasions
everywhere (5.7–10.6 % authored, 29.6–32.1 % on the ingested twin), but nothing in this
project can judge it: collapsing a slot removes a judged anchor's chance to be credited, so
nDCG punishes it on principle regardless of whether an agent reads better, and its claim —
agents handle one coherent passage better than three overlapping ones — is about
comprehension, not ranking. It goes to the agent-task suite. Recording *"we cannot measure
this yet"* is a different act from *"we measured it and it lost"*, and collapsing the two
would have been exactly the dishonesty this item exists to prevent.

## One conflation worth separating

§4's boost sentence bundled the trust *weight* with the trust *filter*. The weight is
refused; the filter is not, and never was the same mechanism — `include_candidate` /
`served_statuses` exclude a class entirely, and every `candidate`/`evidence` result is
labeled so an agent knows what it is quoting. The amended text says which of the two ships.

## What shipped

`tools/measure_result_rules.py`, fourteen tests for the arithmetic that decides what its
verdict means, and three amended spec bullets. The runner joins `verify.py`'s `retrieval`
rung at ~52 s, guarding a refusal that rests on a property of the *corpora* rather than of
the ranking — so a corpus mixing trust classes should re-open it rather than have someone
rediscover it. Retrieval itself is untouched.
