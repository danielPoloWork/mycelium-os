# ADR-0043: Judge across the configurations a set is scored under

- **Status:** Accepted
- **Date:** 2026-09-02
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.1, §7.2
- **Related:** [ADR-0029](0029-let-a-judgment-name-a-section.md) (the section form, and the
  caution this ADR argues against in one case),
  [ADR-0042](0042-let-an-atomic-block-share-its-chunk.md) (the chunking change that forces
  the question), [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md);
  D-010; roadmap 4.12

## Context

Roadmap 4.11 shipped `[chunking] pack_atomic` **switched off**, because flipping it and
defending its consequences are two acts. One consequence is mechanical: moving a chunk
boundary deletes an anchor. Five judged cases name a chunk that ceases to exist when packing
is on — `q-0002`, `q-0008`, `q-0013`, `q-0016` on our dev set and `u-1016` on the second
corpus's release set — and a judgment naming a chunk that does not exist scores zero however
good the retrieval was. Those five measure nothing at 4.15.

`eval/README.md` states the judging rule: *name the section when a reader needs more than one
chunk, name the chunk when the answer is confined to it, and when unclear name the chunk —
the reading that cannot flatter us.* That rule was written for a **fixed** chunker. It has no
answer for a judgment that must be true under two chunkers at once, which is what a set
spanning a boundary change has to be.

## Decision

**A judgment names the smallest unit that contains the answer under every configuration the
set is scored under.** Where the chunk that holds the answer survives, that chunk is still
what the judgment names — nothing is section-scoped for tidiness. Where packing merges it
into its section, the section is the smallest such unit, and the judgment says so.

Applied, that re-anchors exactly the five cases and nothing else:

| case | set | before | after | why |
|---|---|---|---|---|
| `q-0002` | ours/dev | `0009#decision/1` | `0009#decision/` | 3 chunks → 1 |
| `q-0008` | ours/dev | `README.md#build-test-run/1` | `…/` | 2 chunks → 1 |
| `q-0013` | ours/dev | `0009#decision/2` | `0009#decision/` | 3 chunks → 1 |
| `q-0016` | ours/dev | `README.md#try-it/1` | `…/` | 2 chunks → 1 |
| `u-1016` | uv/release | `cli.md#logging-in-to-a-service/3` | `…/` | 6 chunks → 1 |

Every other anchor in all four sets is left exactly as it was. After the change every
judgment survives the flip: ours/dev 33/33, ours/release 17/17, uv/dev 12/12, uv/release
18/18.

**One judgment is also corrected for a different reason, and it is not anchor repair.**
`r-0003` (`Conventional Commits`, ours/release, the single `exact` case) named
`docs/workflow/git-workflow.md` and `CONTRIBUTING.md` — two of the three places this
repository documents the rule — and omitted **AGENTS.md §6.3**, the file this project calls
its own source of truth. Both its existing anchors survive packing, so nothing forced this;
it is a question about the documents, settled while no retrieval change is in flight.
AGENTS.md §6.3 and git-workflow.md §3 are both titled with the term and both state the
template, so both grade 3; CONTRIBUTING.md mentions it in passing among the branch and PR
steps, which is what grade 1 is for.

## The cost, measured rather than asserted

Controlled before/after — the same build, at the shipped default (`pack_atomic = false`),
old judgments against new:

| set | nDCG@10 | MRR | R@10 | moved slice |
|---|---|---|---|---|
| ours/dev | 0.536 → 0.536 (**+0.000**) | +0.000 | +0.000 | none |
| ours/release | 0.448 → 0.450 (**+0.002**) | +0.000 | +0.000 | `exact` 0.957 → 0.983 |
| uv/release | 0.280 → 0.306 (**+0.025**) | +0.008 | +0.036 | `conceptual` 0.377 → 0.495 |

**Our own dev set does not move at all.** Four of the five re-anchorings are free today: the
retriever was already returning the judged chunk, so widening the judgment to its section
credits nothing it did not already credit.

**The second corpus's release set moves, and the reason is not flattering.** `u-1016` asks
how to keep credentials out of shell history; the judged paragraph recommends stdin. Under
the section anchor the case is now satisfied at rank 5 by a *different* chunk of that
section — *"The credentials will not be validated, i.e., incorrect credentials will not
fail."* — which does not answer the question. That is +0.118 on a gated slice, bought by a
judgment that got easier rather than by retrieval that got better.

## Why that case is section-scoped anyway

ADR-0029 argues directly against this: *"Making section-scope the automatic unit would credit
'right neighbourhood' as 'right answer', and a reader who gets chunk 7 when the answer is in
chunk 4 did not get the answer."* `u-1016` is that shape — one paragraph of a six-chunk
section — and it is section-scoped regardless. Three reasons, in order of weight:

1. **There is no third form.** A judged anchor names a chunk or a section (ADR-0029); nothing
   else is expressible. The chunk form is false under one of the two configurations this set
   must be scored under, so it is not available.
2. **After the flip the objection dissolves.** Packing makes that section a single 204-token
   chunk, so post-flip the section anchor *is* chunk-exact: a reader who matches it gets the
   stdin recommendation. The generosity is confined to the configuration the project is
   leaving.
3. **The alternative measures nothing.** Left as it is, `u-1016` scores zero at 4.15 —
   contributing a false regression to the change it is supposed to help judge, which is worse
   than a judgment that is briefly too kind.

**And re-blessing now is what makes the trade safe.** Booking the +0.025 into the committed
baseline as a *judgment* change means 4.15 measures packing from the raised line, so packing
is credited with less than it would have been. Had the order been reversed — flip first,
re-anchor after — the same 0.025 would have been harvested as a retrieval gain. The ordering
is not bureaucracy; it decides who gets the credit.

## Alternatives Considered

- **Name the post-flip chunk anchor** (`…/0` under packing). Rejected: it does not exist
  today, so the set would be invalid against the configuration the project ships, and
  `build_eval_cases.py` validates every anchor against a real build for exactly this reason.
- **Leave the five broken and re-anchor at 4.15.** Rejected: that is the conjunction
  `tools/check_frozen_release_sets.py` refuses — a change that moves the chunker *and*
  rewrites the judgments it is measured by. Splitting them is the whole reason 4.11 shipped
  the flag switched off.
- **Section-scope every judgment, for durability.** Rejected: it is ADR-0029's rejected
  option and it would credit the neighbourhood as the answer across the whole set. Only the
  five cases packing actually breaks are touched.
- **Drop `u-1016` from the release set** rather than widen it. Rejected: a frozen set may
  grow, and it may be re-anchored from the documents; quietly shrinking it when a case
  becomes inconvenient is the failure mode the freeze exists to prevent.
- **Re-carry the ingested twin's judgments** to match the new source anchors. Rejected here,
  and the reason is [BUG-0018](../bugs/2026/09/BUG-0018-carried-ingested-cases-do-not-reproduce.md):
  the generator does not reproduce its own committed output on current `main`, dropping four
  unrelated cases. Regenerating would have smuggled that shrink into a re-judging PR. The
  derived set keeps the anchor it has, and the drift is on the books.

## Consequences

- **The judged sets survive 4.15.** Every anchor in all four sets still names something after
  the flip, so the change can be measured on the cases it is supposed to be measured on.
- **The release baselines are re-blessed**, and every comparison across this change is
  invalid — the same boundary 3.17 drew. `ours/release` also carries an unrelated
  `relationship` fall (0.304 → 0.106) that predates this change and is *not* caused by it:
  the controlled measurement shows 0.106 on both sides. It comes from corpus growth since the
  previous bless, gate G3 could not enforce across that boundary, and it is filed as roadmap
  4.17 rather than frozen in silence.
- **`eval/README.md` gains the rule**, because a rule applied once and left in an ADR is a
  rule the next contributor will not find.
- **No code changed**, so `tools/check_frozen_release_sets.py` passes on the conjunction it
  guards: release sets edited, nothing in `TUNING_PATHS` touched.
- **A limit worth naming:** this rule scales to *one* pending configuration change. A set
  that had to be true under three chunkers at once would have no anchor form left, and the
  answer then is not a wider anchor but a judgment that names text rather than a position —
  which is a bigger change than any milestone here needs.

## References

- Spec 04 §7.1 (dev/release split), §7.2 (metrics); D-010
- [ADR-0029](0029-let-a-judgment-name-a-section.md) — the section form, its "credited once"
  rule, and the caution this ADR overrides for one case with the cost measured
- [ADR-0042](0042-let-an-atomic-block-share-its-chunk.md) — the change that deletes the anchors
- [BUG-0018](../bugs/2026/09/BUG-0018-carried-ingested-cases-do-not-reproduce.md) — why the
  ingested twin was left alone
- `tools/measure_chunking.py` — the anchor-survival table, re-runnable
