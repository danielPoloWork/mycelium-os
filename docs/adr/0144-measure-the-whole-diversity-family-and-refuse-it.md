# ADR-0144: Measure the whole diversity family, and refuse it — the spec asked for a rule the evidence will not carry

- **Status:** Accepted
- **Deciders:** tech-lead (EADOS delivery agent) with the maintainer, per RFC-0001 /
  spec 04 §§3-4
- **Date:** 2026-09-20
- **Related:**
  [ADR-0075](0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md)
  (the discount curve with no operating point, and the one-per-document rule that *is*
  built — inside the graph leg),
  [ADR-0094](0094-mint-a-command-the-corpus-demonstrates-and-names-and-report-what-promotion-can-and-cannot-reorder.md)
  (read the ceiling before tuning the heuristic),
  [ADR-0070](0070-take-the-leaf-heading-weight-on-the-third-asking.md) and
  [ADR-0080](0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md)
  (a ranking change earns its default on a held-out set, or ships as nothing),
  [ADR-0131](0131-bound-the-incumbents-read-and-publish-the-band-it-buys-evidence-along.md)
  (roadmap 6.22, which found the concentration),
  [ADR-0143](0143-take-the-result-count-from-the-contract-and-sweep-it-like-the-incumbents.md)
  (which moved the agent-task arm off the depth this was found at);
  D-010, D-011; spec 04 §§3-4, §7.3; roadmap 6.22, 6.29

## Context

Roadmap 6.22 measured the agent-task suite and reported that across twenty-two tasks the
top ten spanned a mean of **5.8 distinct documents**, and that on **10 of 22** one document
took half the slots or more. Roadmap 6.29 was filed to ask the question that observation
raises and cannot answer: *should it?*

The item's own framing was that "nothing has ever asked whether it should". That turned out
to be wrong in the way that matters.

### Something did ask. Spec 04 §4 asks, and it was never built

> **Diversity:** MMR across documents so one document cannot monopolize the result set
> unless it uniquely holds the answer.

That is a flat requirement of the pipeline — not a Phase-3 gate like graph expansion
(§5), not an ablatable boost (§4's first bullet). Nothing in `src/mycelium` implements it.
The only diversity rule in the codebase is **one chunk per document inside the graph leg**,
whose own docstring calls itself "the diversity guard spec 04 §4 asks of the result set,
applied where it is cheapest" (ADR-0075) — and that leg is **off by default**, because its
ablation refused it. So on the shipped configuration, the result set has no diversity guard
at all, and the sentence that says otherwise describes a leg nobody runs.

This is the third member of a family this project keeps finding: a requirement written
once, honoured nowhere, and invisible because nothing reads the specification back against
the code.

### The concentration is real, and larger on the judged sets than on the tasks

Measured by `tools/measure_document_diversity.py --concentration`, at depth 10:

| set | cases | mean distinct documents | largest share (mean / max) | one document takes half |
|---|---:|---:|---:|---:|
| `ours/dev` | 16 | 6.88 | 3.44 / 6 | 4 (25 %) |
| `ours/release` | 284 | 5.43 | 4.01 / **10** | **119 (42 %)** |
| `uv/dev` | 20 | 5.85 | 3.20 / 9 | 6 (30 %) |
| `uv/release` | 402 | 6.05 | 3.47 / 9 | 118 (29 %) |
| `uv-ingested/dev` | 20 | 6.05 | 3.10 / 10 | 3 (15 %) |
| `uv-ingested/release` | 402 | 6.14 | 3.29 / 9 | 100 (25 %) |

On this repository's release set **one document takes all ten slots** on at least one query,
and 42 % of queries give one document half of them — a harsher reading than the 10-of-22 the
agent tasks showed. The phenomenon is not an artefact of the task suite.

One correction to the item's premise while we are here: ADR-0143 moved the agent-task arm
from `limit=10` to the contract's maximum of 50, so *"4.3 of the ten slots"* no longer
describes the arm it was measured on. It still describes the **default caller** —
`mycelium_search` defaults `k` to 8 — which is why the judged sets at depth 10 remain the
right place to settle it.

## Decision

**Measure both families across their whole range, report the ceilings first, and ship
nothing. Amend spec 04 §4 to say that.**

### The two families are the family

A search serves `DEPTH` chunks from a fused pool `VECTOR_CANDIDATES` deep. Anything that
spends fewer slots on one document must either **refuse** them or **discount** them:

- **cap `n`** — at most `n` chunks per document, freed slots backfilled from the next
  document. A hard refusal.
- **decay `λ`** — greedy re-ranking where a document's j-th selected chunk scores
  `rrf · λʲ`. A soft discount, and the shape §5 already uses for the graph leg.

`cap 1` and `λ → 0` are the same policy (round robin); `cap ≥ DEPTH` and `λ = 1` are both
the shipped ranking. Everything else interpolates, so sweeping both families across their
range measures the family of policies rather than two guesses.

### RRF leaves no middle, and the arithmetic said so before the data did

With one leg a candidate at pool rank `r` scores `1/(60 + r)`, so the whole 50-deep pool
spans

```
(60 + 50) / (60 + 1) = 110 / 61 = 1.80x
```

between its best and worst candidate. A multiplicative discount is therefore **inert or
total**: below `61/110 = 0.55` a document's second chunk falls beneath *every* other
candidate in the pool — round robin — and near 1.0 it changes nothing. The measured curve
is exactly that shape, with `λ = 0.5` and `λ = 0.7` scoring **identically** on three of the
six sets because both are already saturated.

This is ADR-0075's finding reached a second time by a different mechanism. There, a graph
discount had no operating point under RRF; here, a diversity discount has none for the same
reason. It is worth stating as a general property rather than a coincidence: **RRF's score
range is too narrow to host a multiplicative preference.** Anything that needs to express
"this candidate is somewhat less wanted" cannot say it in RRF scores.

### What the sweep found

Every arm, every set, against the shipped fused order (`ours/release` and `uv/release` are
the held-out sets that decide a default):

| arm | `ours/dev` | `ours/release` | `uv/dev` | `uv/release` | `uv-i/dev` | `uv-i/release` |
|---|---:|---:|---:|---:|---:|---:|
| control | 0.4694 | 0.4812 | 0.6143 | 0.6903 | 0.6127 | 0.6477 |
| cap 1 | −21.9 % | −24.8 % | −11.1 % | −11.2 % | −13.5 % | −9.0 % |
| cap 2 | −3.7 % | −12.0 % | +0.2 % | −2.5 % | +1.6 % | −2.1 % |
| cap 3 | −2.7 % | −4.5 % | +0.8 % | −1.5 % | +0.8 % | −1.1 % |
| cap 4 | −1.3 % | −1.9 % | ±0.0 % | −0.6 % | ±0.0 % | −0.7 % |
| cap 5 | +0.2 % | −1.1 % | ±0.0 % | −0.1 % | ±0.0 % | −0.1 % |
| decay 0.5 | −18.2 % | −23.1 % | −10.5 % | −11.2 % | −13.0 % | −9.0 % |
| decay 0.7 | −18.2 % | −23.1 % | −10.5 % | −11.1 % | −13.0 % | −9.0 % |
| decay 0.8 | −16.5 % | −19.3 % | −6.6 % | −8.7 % | −6.7 % | −6.7 % |
| decay 0.9 | −10.8 % | −13.5 % | −3.7 % | −5.2 % | −3.1 % | −3.6 % |
| decay 0.95 | −5.7 % | −6.4 % | −3.4 % | −2.9 % | −1.7 % | −1.7 % |

**No arm gains on any release set.** Four arms gain on a dev set, by +0.2 % to +1.6 %,
moving one or two cases each — the textbook *proposable, not earned* that ADR-0070 exists to
refuse. Every arm strong enough to change more than a handful of cases costs a held-out set,
and most break gate G3's −2 % slice condition long before that: cap 2 costs `ours/release`'s
`conceptual` slice **−22.0 %**, and cap 2 on `ours/dev` costs `relationship` **−65.2 %**.

That last column is the mechanism in one number. The queries a cap hurts most are
`relationship` and `conceptual` ones — questions whose answer genuinely *is* spread across
several chunks of one document. Diversity takes slots from exactly the cases that need
concentration.

### The ceilings say the loss is not here at all

Read before any arm was tuned, per ADR-0094:

| set | control | best cap per case | best decay per case | pool re-ranked perfectly |
|---|---:|---:|---:|---:|
| `ours/dev` | 0.4694 | +4.1 % | +0.8 % | **+72.2 %** |
| `ours/release` | 0.4812 | +4.2 % | +3.0 % | **+86.3 %** |
| `uv/dev` | 0.6143 | +1.4 % | +0.6 % | **+35.9 %** |
| `uv/release` | 0.6903 | +1.6 % | +1.4 % | **+36.2 %** |
| `uv-ingested/dev` | 0.6127 | +1.8 % | +1.0 % | **+57.8 %** |
| `uv-ingested/release` | 0.6477 | +2.1 % | +2.1 % | **+46.0 %** |

The first two columns are the arm chosen **with hindsight, per query** — unreachable by any
fixed policy, and worth at most **+4.2 %**. The last is the same 50 candidates ordered by
their judged grade: **+36 % to +86 %**.

So the headroom at depth 10 is enormous and **document concentration is not where it is**.
The best conceivable diversity policy captures about a twentieth of what re-ordering the
pool correctly would. The ranking's problem is *which* chunks it puts first, not *how many
of them share a document* — and spending effort on the second is spending it in the wrong
place.

That column also prices spec 04 §4's own escape clause. *"Unless it uniquely holds the
answer"* requires knowing which document holds the answer, which is precisely the per-case
oracle: even granted that knowledge, the rule is worth 1.4–4.2 %.

## Consequences

**No mechanism ships, and no configuration knob is added.** D-011 is explicit that a knob
nobody has eval evidence for is a liability rather than a feature, and here the evidence
says something stronger than "unproven": the family has no operating point, by arithmetic
and by measurement. A `document_cap` setting would be a documented way to make retrieval
worse.

**Spec 04 §4's Diversity bullet is amended** to record what was measured and what ships.
The requirement is not quietly deleted: the bullet keeps the rule, states that it was
measured across both families on six judged sets, and says that the result set carries no
guard because every version of one lost. AGENTS.md §7 allows a divergence to be resolved by
updating the spec *or* by an ADR explaining it; this does both, because a reader of the spec
should not have to find this file to learn that the sentence above is not the product.

**The retrieval docstring that claimed otherwise is corrected.** `_expand`'s note now says
the one-per-document rule bounds *the leg*, and that the result set has no such rule by
measurement, rather than implying §4 is satisfied.

**`tools/measure_document_diversity.py` joins the `retrieval` rung of `verify.py`**, and it
guards the opposite of what its three siblings guard. The hybrid, graph, symbol and routing
runners watch a shipped default for a measurement that no longer supports it; this one
watches a **refusal** for a measurement that has started to. `--check` fails only when an arm
earns a release-set gain with no set regressing and no slice past −2 % — the day that
happens, this decision is stale and should be re-opened rather than rediscovered.

**What this does not settle.** The two agent tasks 6.22 saw the incumbent win are not
fixed by this and were never going to be: the judged sets say no re-ordering *within* the
current pool that is keyed on document identity will help. Where the +36–86 % of headroom
actually lives is a different question, and the pool ceiling is the number that says it is
worth asking — filed as a follow-up rather than guessed at here.

**Cost.** The runner takes about five minutes across six sets, one search per case and
arithmetic for all ten arms; it is cheaper than the symbol ablation it sits beside, which
searches twice per case.
