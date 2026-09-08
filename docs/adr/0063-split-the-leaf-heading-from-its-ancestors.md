# ADR-0063: Split the leaf heading from its ancestors, and take only the weight dev can see

- **Status:** Accepted
- **Date:** 2026-09-08
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.36 (this item), 4.25 (where it was filed), 4.22, 4.39; RFC-0001;
  spec 04 §§3, 7.1; D-010; D-016;
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0031](0031-refuse-three-rerankings.md),
  [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md),
  [ADR-0048](0048-index-the-stem-beside-the-surface-form.md),
  [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md),
  [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md),
  [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md)

## Context

`chunks_fts` had one field for a chunk's heading: `heading_path`, the whole ancestor chain
joined with `/`. So a subsection's heading field was a strict **superset** of its parent's.
Every word that made a query match the parent matched the child too, at the same weight of
2.0, and the child added its own words on top — which means the leaf heading, the one that
names what *this* chunk is about, never got to distinguish it from everything nested under
it.

The defect is reproducible in four rows of SQL, and the reproduction is now a test. Two
chunks with identical bodies, one under `Retries` and one under `Retries / Retries
schedule`, query `retries`: with the fields joined the **subsection wins** (−1.636e-6
against −1.457e-6), because a superset can carry the query term more often than the set it
contains. Split, the section the query is about wins. It is the shape ADR-0058 found on
`u-1006`, where *"Requesting a version / Python version files"* outranked *"Requesting a
version"*.

ADR-0058 measured the split as the twelfth family in `tools/measure_ranking.py` and
**refused it**, correctly and for a reason that had nothing to do with the mechanism. The
candidate it measured was `heading 3.0/0.5` — leaf raised to 3.0, ancestors dropped to 0.5
— and that pair wins on both release sets while scoring **exactly the baseline on uv/dev**.
Two free parameters, no dev signal, and a value chosen by reading the held-out sets: the
thing spec 04 §7.1's split exists to refuse. Roadmap 4.36 recorded the lead and named the
condition for proposing it — *"a dev set on which the effect is visible"*.

The corpus growth 4.26 began did not produce one: it grew **uv/release** from 14 to 25
cases, and uv/dev is still the 12 cases it was, with one `exact` case and one `symbol` case
in it. A set that thin cannot see a field-weight change, and this item could have waited on
another growth item indefinitely.

## Decision

**Ask a smaller question, and answer it where dev can see it.**

The split has two parameters and only one of them has dev evidence. Measured across the
whole ancestor range at the shipped leaf weight — `heading 2.0/1.0`, `2.0/0.75`, `2.0/0.5`,
`2.0/0.25`, `2.0/0.0`, two of those rows added here — ours/dev is a **plateau**:

| ancestors (leaf 2.0) | ours/dev nDCG@10 | MRR | R@10 | uv/dev nDCG@10 | MRR |
|---|---:|---:|---:|---:|---:|
| 2.0 *(unsplit)* | 0.537 | 0.572 | 0.719 | 0.673 | 0.663 |
| 1.0 | 0.540 | 0.577 | 0.719 | 0.673 | 0.664 |
| **0.75** | 0.540 | 0.581 | 0.719 | 0.673 | 0.664 |
| **0.5** | 0.540 | 0.581 | 0.719 | 0.673 | 0.664 |
| **0.25** | 0.540 | 0.581 | 0.719 | 0.673 | 0.664 |
| 0.0 | 0.523 | 0.577 | **0.688** | 0.673 | 0.664 |

Three readings, all from sets tuning is allowed to see. Splitting at all helps. Anything
between 0.25 and 0.75 is **indistinguishable**, so the dev sets cannot choose within that
band. And **zero is refused**: dropping the ancestors entirely costs 0.017 nDCG@10 and three
points of R@10, so where a chunk sits is real evidence — just weaker evidence than what it
is about.

So: **`heading_path` splits into `heading` and `ancestors`; the leaf keeps spec 04 §3's
2.0 and the ancestors take 0.5, the middle of the flat part.** One parameter moved, its
value taken from the interior of a plateau rather than from a maximum, and the parameter
with no dev signal — the leaf weight — left exactly where the spec put it.

**The leaf increase stays refused, and this is the second time.** `heading 3.0/0.5` and
`4.0/0.5` gain three to four times as much on the release sets (uv/release 0.611 and 0.616
against the shipped 0.604) and score *identically to the shipped setting* on both dev sets —
0.673 on uv/dev, 0.540 on ours/dev, where they are in fact a hair **worse** on ours/dev MRR
(0.578 against 0.581). A change whose entire benefit is invisible on dev and visible on the
held-out set is indistinguishable from a change fitted to it, whatever the mechanism story.
Roadmap 4.39 is filed for what would settle it: a uv/dev set thick enough to answer a
field-weight question.

**The claim made for this change is that it costs nothing, not that it gains something.**
The reason to adopt it is that the field was wrong. The measurements below are there to show
the correction is free, and they are small: on 25 judged cases per vendored corpus it moves
**one case each**.

## Verification, read before anything was re-blessed

Gate G3 was read against the **committed** baselines first — the order that makes a gate
mean something (the discipline PR #67 recorded) — and only then were the two enforceable
baselines re-blessed.

| set | before | after | the slice that moved | G3 |
|---|---:|---:|---|---|
| uv/release | 0.6021 | **0.6035** | `exact` 0.7269 → 0.7333 (+0.9 %) | *enforced*: same corpus, same boundaries, same judgements, no enforced slice regressed — **pass** |
| uv-ingested/release | 0.6300 | **0.6306** | `fact` 0.5180 → 0.5200 (+0.4 %) | *enforced*, same verdict — **pass** |
| ours/release | 0.504 | 0.505 | `fact` 0.4585 → 0.4602 | *reported, never enforceable* (4.22, ADR-0053) |
| ours/dev | 0.537 | 0.540 | — | dev, not gated |
| uv/dev | 0.673 | 0.673 | — | dev, not gated |

Per case, on the two sets G3 enforces, **exactly one case moves on each and both move up**:
`u-1003` (`exact`, the literal key `tool.uv.index`) from 0.30103 to 0.33333 — rank 10 to
rank 8, its subsection competitors demoted to inheriting "index" at 0.5 instead of owning
it at 2.0 — and `u-1008` (`fact`) from 0.30103 to 0.31547 on the ingested projection. Every
other judged case on both sets is unchanged to six decimal places. `fact` on uv/release
stays conceded at 0.431 against grep's 0.497, and `u-1006` does not move at all, exactly as
ADR-0058 said it would not: that gap is in `text` length normalisation, and this was never
its lever.

The dev/release gap moved by 0.002 in both directions — it *shrank* on uv (0.071 → 0.069)
and grew on ours (0.033 → 0.035), which is what a change with no fitted parameter looks
like. The agent-task loop is unchanged: evidence found 68 % before and after, at 2564 and
2551 mean tokens.

Two controls hold, in both directions. `baseline (ships)` and `heading 2.0/0.5` now score
identically on all four sets, so the family is measuring the field split and nothing else;
and `heading 2.0/2.0` reproduces the pre-change numbers exactly (0.537 / 0.673 / 0.504 /
0.602), so reverting is priced — it reads `exact −0.9 %` against the new baseline.

## Alternatives Considered

- **`heading 3.0/0.5` — the pair 4.36 proposed.** Refused, again, and the refusal is the
  main decision in this ADR rather than an aside. Its release gains are three to four times
  larger and its dev evidence is nil; adopting it because the mechanism sounds right is how
  a project acquires a parameter nobody can later justify. Available the day roadmap 4.39
  gives it a dev set.
- **`heading 4.0/0.5`.** The best row in the file on uv/release (0.616). Refused for the
  same reason, more so.
- **`ancestors = 0.0`** — drop the chain entirely, the simplest possible split. Refused
  *by dev*: 0.523 against 0.540 nDCG and 0.688 against 0.719 R@10 on ours/dev. This is the
  refusal worth noting, because it is the one dev could make on its own.
- **Grow uv/dev first, then decide the whole family at once.** The instruction 4.36 wrote
  for itself, and rejected here on sequencing rather than on merit. Growing a judged set is
  a *judgements* change and this is a *retrieval* change; the project's standing rule is
  that one change moves one of the two (spec 04 §7.1,
  `tools/check_frozen_release_sets.py`), and while that script guards only the release sets,
  writing dev cases and choosing a parameter on them in one commit is exactly the coupling
  the rule is about. Filed as 4.39, where the leaf weight is its first customer.
- **Leave 4.36 refused.** Defensible, and it was the answer for one milestone. Rejected
  because the question changed: a two-parameter pair with no dev signal and a one-parameter
  move with a dev plateau are different propositions, and refusing the second leaves a
  known modelling defect in the index for no benefit. The refusal count stays at fourteen
  *ranking* candidates — this is an **indexing** change, the family that produced the two
  others that shipped (roadmap 4.15, 4.19).
- **Keep `heading_path` and add `heading` beside it.** Rejected: the superset would still be
  there, still scoring, and the two fields would double-count every leaf word. The point is
  to stop one field meaning two things.
- **Re-bless this repository's own baseline while re-blessing the other two.** Rejected. Our
  corpus grows with every PR, so its committed baseline is stale by construction and G3
  reports rather than enforces on it (4.22, ADR-0053); re-blessing it here would fold a
  milestone of corpus growth into a baseline as though this change had caused it. The
  isolated number for ours is in `measure_ranking.py`, which scores both arms on one build.

## Consequences

- **Store schema v4 → v5.** FTS5 columns cannot be altered, so the split is a rebuild — the
  case the v1 migration policy exists for (D-016), and the same shape as v3 → v4's stem
  columns (ADR-0048). A writer meeting a v4 store recreates it; a reader refuses and says
  `mycelium build`. Verified by accident and worth recording: running the pre-change code
  against a v5 store produced exactly that refusal rather than silently reinterpreting it.
- **Spec 04 §3 is amended in this PR**, not deviated from. The line now states the four
  surface weights and the stem columns that ADR-0048 added without touching it; the three
  original weights are unchanged. A spec line accumulating undocumented amendments is how
  the spec stops being the reference.
- **`mycelium_explain` reports one more field weight.** `field_weights` gains `ancestors`;
  an additive key in a debugging payload, and the MCP tool contract's shape is otherwise
  untouched (architecture §10 freezes it at 1.0, which is roadmap 6.1's business).
- **The leaf weight is now a knob that can be turned.** Before the split it could not be:
  `heading 3.0/3.0` and `4.0/4.0` fail G3 on `exact` (−10.6 %, −14.1 %), so 2.0 was stuck
  wherever it was. Split, both `3.0/0.5` and `4.0/0.5` pass G3 on both release sets. That is
  the durable value here, and it is why 4.39 has something to buy.
- **The refused families in `tools/measure_ranking.py` keep their own weights.** The section
  and tokenizer indexes are recorded refusals over a four-column index, and a refusal whose
  numbers move when an unrelated field is split is not re-runnable — so `_LEGACY_WEIGHTS` is
  pinned in the tool rather than imported from a store that has moved on. Found by the tool
  crashing on an arity mismatch, which is the better way to find it.
- **What is still open is unchanged.** `fact` on uv/release stays conceded (ADR-0058's
  reasons, unaltered), `u-1006` still sits at 0.431, and roadmap 4.37 and 4.38 still name the
  two cases no shipped profile serves.

## References

- Spec 04 §3 (field weights, amended here), §7.1 (the dev/release split).
- Measured this session, reproducible with `python tools/measure_ranking.py --release`
  (the `heading` rows) and, for the verdicts,
  `mycelium eval <corpus> --set eval/release.jsonl --gate --against grep`:
  the ancestor-weight plateau on ours/dev; both dev sets flat in the leaf weight; the two
  per-case movements; the two G3 verdicts; both controls.
- [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md) — measured the family
  and refused it for where the parameters were found; this ADR keeps that refusal for the
  leaf and lifts it for the split.
- [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md) — the split
  the leaf refusal is an application of.
- [ADR-0048](0048-index-the-stem-beside-the-surface-form.md) — the other indexing change
  that shipped, and the schema-bump precedent.
