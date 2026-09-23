# ADR-0153: Decide spec 04 §4's result-set rules on evidence, and record each one

- **Status:** Accepted
- **Deciders:** tech-lead (EADOS delivery agent) with the maintainer, per RFC-0001 /
  spec 03 §6
- **Date:** 2026-09-23
- **Related:**
  [ADR-0144](0144-measure-the-whole-diversity-family-and-refuse-it.md) (roadmap 6.29 —
  §4's fourth rule, measured across its family and refused; the precedent this file
  follows for the other three),
  [ADR-0152](0152-the-ranking-loss-is-ordering-not-recall.md) (roadmap 6.37 — the ceiling
  a boost is competing for, and the window it lives in),
  [ADR-0150](0150-report-the-stage-budgets-where-they-mean-something-and-gate-the-total.md)
  (roadmap 6.35, which found the gap while mapping §1's budgets and reported rather than
  gated it),
  [ADR-0070](0070-take-the-leaf-heading-weight-on-the-third-asking.md) (the BM25 *column*
  weight, which is not this and is easy to mistake for it),
  [ADR-0080](0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md)
  (a bar adopted by analogy and stated rather than implied; sweeping in both directions),
  [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) (the lexical default
  these pools are built under); D-021 (trust classes and verification status);
  spec 04 §§1, 4, 7.4; roadmap 6.35, 6.37, 6.38

## Context

Spec 04 §4 describes five behaviours for the result set: boosts, dedupe, diversity,
stitching and packing. Roadmap 6.35 was mapping §1's stage budgets onto the labels the query
path already times when it noticed that the word `boost` appears nowhere under `src/`, nor
does `stitch`, and that there is no near-duplicate collapse — so *"fusion + boosts +
dedupe"* is fusion, and *"stitch + pack"* is pack. It reported this rather than gating it,
correctly: a stage budget naming work that does not exist cannot be gated.

Diversity is the honest case and the precedent. It was measured across its whole family and
**refused** (roadmap 6.29, ADR-0144), and §4 now carries a paragraph saying so. The other
three had no such paragraph, which left the spec reading as a description of the product
while being a description of an intention.

The item's requirement was explicit and is the reason this file exists: each behaviour wants
**either an implementation with an ablation that earns it, or a spec paragraph recording the
refusal** — never a silent deletion, because the spec is the record of what was intended as
much as of what shipped.

An audit confirms the absence before anything is decided. There is no score multiplication
anywhere in the ranking path: `reciprocal_rank_fusion` computes `scores[anchor] += weight /
(k + position)` and nothing after it touches `FusedHit.score` except to attach labels. The
`weights` parameter there is a **per-leg** scale (the graph and symbol discounts), not a
per-hit boost. ADR-0070's "leaf-heading weight" is *not* this either — it is a BM25 **column**
weight over `(anchor, text, title, heading, ancestors)` inside the lexical leg, about which
field a term matched in, and it never sees heading depth. `trust_class` and
`verification_status` reach filtering and display only. No timestamp reaches the ranker.

## Decision

**Refuse three of §4's four unbuilt rules on measurement, defer the fourth to the only
instrument that could judge it, and write each outcome into the spec.**
`tools/measure_result_rules.py` is the measurement and joins `verify.py`'s `retrieval` rung.

### Three boosts are refused by arithmetic, not by an arm

§4 makes boosts **multiplicative on the fused rank score**. A multiplicative factor applied
to every candidate alike is order-preserving *exactly* — `b · s` sorts as `s` does for any
`b > 0`. So a boost over a field that holds one value in the corpus is not a weak effect
waiting to be measured; it is no effect at all, and reporting it as a 0.00 % arm would
dress up a tautology as a result.

Every corpus in this repository is single-valued in all three fields §4's trust boosts
would read. Recency is refused on two grounds at once: no judged query asks for it, and
there is no field to read — `updated_at` is a build timestamp, and uv's 81 documents span
**0.7 seconds** of it. A recency boost here would rank by when files were last touched by a
build, which is worse than not having one.

### Heading proximity is the one that varies, and it was swept

Chunk heading depth ranges 0–4 across the corpora, so this boost can move things and had to
be measured rather than argued about. The arm is `score · w ** (depth − 1)`, swept over
eight weights **in both directions** (ADR-0080's discipline: below 1.0 is the spec's stated
prior that H1/H2 sections beat deep fragments, above 1.0 the opposite prior that deep
fragments are more specific), each run **pool-wide** as §4 describes and again **confined to
the served ten**, because ADR-0152 established that 58–72 % of the reachable headroom lives
in that window and "did the promotion or the re-ordering cost it?" is therefore a real
question.

**The bar** is the one this project applies to every ranking change (ADR-0070, ADR-0080,
ADR-0144): a gain on a **release** set, no overall regression on any set, and no slice worse
than gate G3's −2 %.

**Where the usable range is, stated before the arms ran.** With one leg a candidate at pool
rank `r` scores `1 / (RRF_K + r)`, so neighbours differ by about 1.6 % at the top of the
pool and a factor `w` crosses roughly `|w − 1| · (RRF_K + r)` of them: at `r = 10`, 1.05 is
~4 ranks, 0.9 is ~8, 0.7 is ~21, 0.5 clears the pool. That is a genuinely tunable band, and
it is worth saying why it differs from ADR-0144's finding that RRF *"leaves no room in the
middle"*. There the discount applied to a document's own second and third chunk, competing
against neighbours at nearly equal score, so it was inert or total. A boost over a **class**
of candidates moves that class against the pool's whole 1.80x spread. The family had room to
win in. It did not use it.

### A permutation control, because "every arm loses" has two readings

Without one, the result is ambiguous between *heading depth is the wrong signal* and *RRF's
order is already near-optimal and any perturbation of this size costs about this much* —
which want opposite follow-ups. The control deals the same multipliers to the wrong
candidates (the depths shuffled within each pool, seeded by case id), keeping the
perturbation's magnitude exactly and destroying only the signal.

## Measured

From a clean worktree, all three corpora rebuilt. The frozen external corpora reproduce
their controls exactly (`uv/release` 0.6903, `uv-ingested/release` 0.6477); `ours` differs
from earlier records because that corpus is this repository.

### The fields the trust boosts would read

| corpus | `trust_class` | `verification_status` | `curated` |
|---|---|---|---|
| `ours` | `authored` ×242 | `verified` ×242 | `False` ×242 |
| `uv` | `authored` ×81 | `verified` ×81 | `False` ×81 |
| `uv-ingested` | `ingested` ×81 | `evidence` ×81 | `False` ×81 |

One value each, in every corpus. **Three of §4's four boosts are inert by construction** on
every set this project can measure on.

### The heading-proximity family: 96 arms, none of them positive

Best arm per set, out of eight weights × two scopes:

| set | shipped | best arm | |
|---|---:|---|---:|
| `ours/dev` | 0.6042 | `depth^1.05` | **−6.23 %** |
| `ours/release` | 0.4765 | `depth^1.05` | **−0.69 %** |
| `uv/dev` | 0.7395 | `^0.95` within ten | **−9.43 %** |
| `uv/release` | 0.6903 | `^1.05` within ten | **−8.92 %** |
| `uv-ingested/dev` | 0.7189 | `^0.95` within ten | **−10.02 %** |
| `uv-ingested/release` | 0.6477 | `depth^0.95` | **−3.70 %** |

**Not one arm gains on any set**, and the losses grow monotonically with distance from 1.0
in both directions — so the family's optimum *is* the shipped ranking, approached from both
sides. Confining the boost to the served ten does not rescue it. Inside that window the
weights 0.5, 0.7 and 0.8 produce **identical** scores, which is ADR-0144's inert-or-total
result appearing again in a narrower place: a strong enough weight simply sorts the ten by
depth, and everything beyond that strength is the same policy.

### The control says the cost is the perturbation, not the field

| set | `depth^0.9` | shuffled control | signal |
|---|---:|---:|---:|
| `ours/dev` | −19.04 % | −12.90 % | **−6.1 pt** |
| `ours/release` | −13.41 % | −7.95 % | **−5.5 pt** |
| `uv/dev` | −16.40 % | −19.47 % | +3.1 pt |
| `uv/release` | −18.95 % | −17.47 % | −1.5 pt |
| `uv-ingested/dev` | −18.51 % | −22.67 % | +4.2 pt |
| `uv-ingested/release` | −9.86 % | −25.06 % | **+15.2 pt** |

Two things at once, and both matter. **Any reordering of this size costs 8–25 %** — RRF's
local order is already better than a reweighting of this family, which is the dominant
effect and the real reason the sweep is empty. And heading depth **does** carry signal on
the ingested twin (+15.2 points over a random permutation of the same multipliers), where
projection flattens headings, while being **worse than random** on the authored corpus — the
spec's prior that shallow sections answer better is, if anything, backwards for prose
written as documentation. Signal that real still never approaches breaking even.

### What dedupe and stitching would collapse

Neither can be scored by nDCG — collapsing a slot removes a judged anchor's chance to be
credited, so the metric punishes both on principle — so what is measured is the
**opportunity**, in the shipped ten:

| set | same digest | Jaccard ≥ 0.8 | adjacent chunks |
|---|---:|---:|---:|
| `ours/dev` | 0 (0.0 %) | 1 (0.4 %) | 23 (9.4 %) |
| `ours/release` | 0 (0.0 %) | 3 (1.1 %) | 25 (8.8 %) |
| `uv/dev` | 0 (0.0 %) | 24 (4.5 %) | 50 (10.6 %) |
| `uv/release` | 0 (0.0 %) | 33 (3.5 %) | 31 (5.7 %) |
| `uv-ingested/dev` | 0 (0.0 %) | 30 (5.2 %) | 215 (32.1 %) |
| `uv-ingested/release` | 0 (0.0 %) | 39 (4.7 %) | 219 (29.6 %) |

**Dedupe never fires in its strict form and fires on one case in fifty in its loose one.**
The looser half of its own test was measured deliberately: refusing it on exact-digest
equality alone would be refusing a narrower rule than the spec describes.

**Stitching is the opposite case** — it has occasions everywhere and three times as many on
the ingested twin, where projection splits sections further.

## Consequences

**Spec 04 §4 is amended, not trimmed.** Each of the three bullets keeps its rule and gains a
paragraph recording what was measured and what ships, exactly as the diversity bullet does.
A reader of the spec learns that the sentence above it is not the product without having to
find this file. AGENTS.md §7 allows a divergence to be resolved by updating the spec or by
an ADR; this does both.

**Trust and verification stay contracts rather than weights.** The boost is refused; the
*filter* is not, and is not the same mechanism. `RetrievalConfig.include_candidate` /
`served_statuses` exclude a class entirely, and every `candidate`/`evidence` result is
labeled so an agent knows what it is quoting. §4's own sentence conflated the two, and the
amended text separates them.

**Stitching is deferred, not refused, and the distinction is the point.** It is the one §4
rule with occasions and no way to judge it here: its claim is about an agent reading one
coherent passage better than three overlapping ones, which is comprehension, not ranking.
The agent-task suite (§7.4) measures evidence-found and tokens-spent and is the only
instrument in this project that could settle it. Recording "we cannot measure this yet" is a
different act from recording "we measured it and it lost", and collapsing them would be the
dishonesty this item exists to prevent.

**`tools/measure_result_rules.py` joins the `retrieval` rung** (~52 s for six sets, the same
cost as ADR-0152's runner). Like the diversity runner it guards a **refusal**, and it has a
specific reason to exist beyond the sweep: three of the four boosts are inert only because
every corpus here is single-valued in the field they read. A corpus that mixes trust classes
makes that decision worth re-opening rather than assuming, and `--check` is what notices.

**What this does not settle.** ADR-0152 found that 58–72 % of the depth-10 headroom is
reachable by re-ordering the served ten. This file shows that *one* family of re-orderings —
multiplicative boosts over a document- or heading-level field — does not reach it, in either
direction, pool-wide or narrow. That is a real constraint on what the next attempt should
look like and not a reason to stop looking: the headroom is still there, and the control
says the thing standing in the way is that RRF's local order is already good, not that
re-ordering is the wrong idea.
