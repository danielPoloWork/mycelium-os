# ADR-0042: Let an atomic block share its chunk, and ship it switched off

- **Status:** Accepted
- **Date:** 2026-09-02
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §5, spec 04 §7.1
- **Related:** [ADR-0007](0007-adopt-structure-first-chunking.md) (whose atomicity rule this
  reinterprets), [ADR-0023](0023-make-the-chunk-target-steer-size.md),
  [ADR-0029](0029-let-a-judgment-name-a-section.md) (whose durability argument this spends),
  [ADR-0031](0031-refuse-three-rerankings.md), [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md);
  D-008, D-010; roadmap 4.11

## Context

Ten re-rankings have been measured and refused across two ADRs, and ADR-0041 closed the
family with a bound: the section unit's ceiling, with per-case foresight no planner can have,
is 3 % above the grep incumbent. What both ADRs kept pointing at was the *unit*:

> BM25 normalises by document length, and our "documents" are chunks of wildly different
> sizes. A three-token code fence containing the query term has maximal term density, so it
> wins.

ADR-0031 named the fix and set it aside — "a chunking decision that cannot be smuggled in as
a ranking fix". This is that decision, taken on its own.

**The diagnosis was half right, and measuring the chunk population said which half.** On the
second corpus 47 % of chunks are under 25 tokens — but only 450 of those 1055 are code. **605
are prose.** They are fragments: 93 % of them sit *directly beside* a code or table chunk,
because an atomic block interrupts a prose run and closes the chunk on both sides. A section
reading "paragraph, command, paragraph" becomes three chunks, two of them offcuts.

And they did not need to be split at all: **97 % of the second corpus's multi-chunk sections
would fit entirely inside one 800-token chunk.** The chunker was not splitting oversize
sections; it was splitting ordinary ones, because a code fence ended the run.

## Decision

**Atomicity means indivisible, not solitary.** `[chunking] pack_atomic` lets a table or code
block share a chunk with the prose around it, subject to the same ceiling as everything else.
A block is still never *split* — that is what `atomic` protects — and packing never crosses a
heading, so ADR-0007's constraint holds exactly as written:

> Lifting any of them to the minimum means merging across a heading boundary, which is what
> heading-bounded chunking exists to prevent.

A section whose only content is a code block still yields one `code` chunk. A packed run's
`kind` is its own when homogeneous and `prose` when mixed, because a paragraph carrying the
command it introduces is prose that contains a code block, which is what a reader would call
it.

**There is no new parameter.** The change deletes a special case rather than adding a
threshold — which is why it is not the length prior ADR-0031 refused for needing a floor, and
not the "merge short fragments" phrasing roadmap 4.11 used, which would have needed one.

**And it ships switched off.** That is the load-bearing half of this decision; the reason is
below.

## What it measures

**Shape** — the thing the item is about:

| corpus | packing | chunks | median | p10 | p90 | < 25 tokens |
|---|---|---:|---:|---:|---:|---:|
| ours | atomic | 888 | 90 | 22 | 363 | 11.6 % |
| ours | packed | 702 | 117 | 34 | 431 | **7.4 %** |
| uv | atomic | 2244 | 27 | 6 | 102 | 47.0 % |
| uv | packed | **568** | 136 | 28 | 436 | **8.8 %** |

The `ours` rows are a snapshot and the `uv` rows are not. This repository is its own corpus,
so writing this ADR changed them — the argument therefore rests on the frozen second corpus,
and the same self-reference is why gate G3 cannot enforce on ours
([BUG-0014](../bugs/2026/08/BUG-0014-g3-compares-incomparable-corpora.md)).

**Retrieval** — dev sets are what tuning may read (spec 04 §7.1); the release view is beside
them because it is what would gate a flip:

| set | atomic | packed | |
|---|---:|---:|---|
| ours/dev | 0.536 | 0.491 | −8.4 %, and 4 of its 16 cases lost an anchor — see below |
| ours/release | 0.472 | 0.473 | +0.2 % |
| uv/dev | 0.403 | 0.561 | **+39 %** |
| uv/release | 0.280 | **0.451** | **+61 %**, against the incumbent's 0.471 |

Per slice on the release sets, against the committed baselines: **uv/release regresses
nothing** — `conceptual` +49 %, `exact` 0.000 → 0.500, `fact` +11 %, `relationship` +49 %,
`symbol` and `unanswerable` flat — and R@10 goes 0.500 → 0.679. On ours/release three slices
improve (`conceptual` +7.6 %, `fact` +1.3 %, `relationship` +58 %) and one regresses:
`exact`, −33.7 %.

That `exact` slice holds **one case**, and it is the same case ADR-0041 refused `section-open`
over. For the query `Conventional Commits` the top result becomes
`AGENTS.md#…conventional-commits/0` — this repository's *own contract*, which AGENTS.md §1
calls the source of truth — while the judged `docs/workflow/git-workflow.md#…/` drops to rank
two. Both judged anchors survive the change; nothing was invalidated. The judgment names two
of the three places this repository documents the rule and omits the authoritative one.

## Why it ships switched off

Because flipping it and justifying that one case are the same act, and they may not happen in
one change.

Chunk boundaries carry ordinals, so moving a boundary **deletes an anchor**: a judgment naming
`#section/2` in a section that now holds one chunk scores zero however good the retrieval is.
Measured per set — and this is where ADR-0029 pays for itself:

| set | judged anchors kept | cases needing re-anchoring |
|---|---|---|
| ours/release | **16 / 16** | none |
| uv/dev | **12 / 12** | none |
| uv/release | 17 / 18 | u-1016 |
| ours/dev | 29 / 33 | q-0002, q-0008, q-0013, q-0016 |

The release sets come through almost untouched, because 3.17 re-scoped to sections exactly
where a section was what the judgment meant. ADR-0029 argued that a judged set "survives a
chunking change to the extent it uses section anchors"; this is the first chunking change, and
it does.

Five cases still need re-anchoring, and `tools/check_frozen_release_sets.py` refuses a change
that edits a release set while touching `src/mycelium/chunking.py`. That rule is not an
obstacle here, it is the point: ADR-0031 rejected "re-judge the release cases so the change
passes" outright, and roadmap 4.11's own text says *re-judge nothing in the same change*. So
the mechanism lands measured and inert; roadmap **4.12** re-anchors the five cases from the
documents, and **4.15** flips the default afterwards. Those are two items rather than one for
the same reason: 4.12 edits a frozen release set and 4.15 edits the chunker.

**This is the shape ADR-0029 → 3.17 already used**: ship the mechanism, change no committed
number, re-judge deliberately in its own change. It worked then, and the reason it worked is
that the second change could be argued from documents instead of from a ranking.

## A gate that cannot see this change

Gate G3 **structurally cannot enforce on a chunking change.** It compares per-slice scores to
a committed baseline only when the corpus digest matches, and the corpus digest is folded from
chunk digests — so any change to chunk boundaries trips the "corpus has changed, reported not
enforced" branch that [BUG-0014](../bugs/2026/08/BUG-0014-g3-compares-incomparable-corpora.md)
introduced for a good reason.

The consequence is worth stating plainly: **the gate meant to catch a bad chunking change is
blind to chunking changes by construction.** Both release runs here reported rather than
enforced. That does not affect this ADR — nothing is flipped — but it does mean **4.15** has
no gate to clear, and it is filed as roadmap **4.13**.

The same guard had a smaller hole, which this change opened and closes: the shipped default
lives in `ChunkingConfig`, so `src/mycelium/config.py` can now move the retriever — and it was
**not** in the frozen-set guard's `TUNING_PATHS`. A single change could have flipped the
default *and* re-judged a release set without being refused. `config.py` is added to that
tuple here, so the 4.12 / 4.15 split is enforced by the machine rather than only by this
paragraph.

## Alternatives Considered

- **Flip the default now and accept five broken cases.** Rejected: five cases scoring zero for
  bookkeeping reasons is exactly the confound 3.17 existed to remove, and it would leave the
  benchmark quietly degraded while the numbers looked better.
- **Re-anchor the four `ours/dev` cases in this change** — dev sets are not frozen, and the
  machine would allow it. Rejected: the guard covers release sets because that is what a
  machine can check, not because dev judgments are fair game. One change moves the retriever
  or the judgments.
- **Merge only blocks below *n* tokens**, which is how roadmap 4.11 phrased it. Rejected: that
  is a threshold, and ADR-0031 refused the length prior for having one — `## License` plus a
  line is 24 tokens and answers completely. Deleting the special case needs no number.
- **Make `atomic` configurable to `[]`** instead of adding a key. Rejected: `atomic` protects
  against *splitting* a table mid-row, which is still right and which ADR-0007 argued; the two
  properties are independent and conflating them would remove a guarantee to gain a boundary.
- **Give a mixed chunk a new `ChunkKind`.** Rejected: `kind` is a stable record field (spec 03
  §5) and a fourth value would break every consumer to describe something a reader already has
  a word for.
- **Leave the unit alone and keep looking for a re-ranking.** Rejected on ADR-0041's bound: the
  family's ceiling is 3 % over the incumbent, and this change is worth 61 % on the same set.

## Consequences

- **Spec 03 §5 says "tables and code blocks are atomic chunks (`kind: "table" | "code"`)".**
  Under `pack_atomic` they are atomic *blocks* inside a chunk that may also hold prose. The
  default keeps the spec's wording literally true, and this ADR is the record of the deviation
  the setting introduces (AGENTS.md §7).
- **A citation gets larger.** On the second corpus the median chunk goes 27 → 136 tokens, so a
  reader handed a citation is handed ~5× more text. Whether that is better *as a citation* is
  the question roadmap 6.7 was filed to make measurable and cannot answer yet — recorded here
  as the cost side of the trade rather than discovered later.
- **The determinism golden is re-blessed with a one-line diff** — `config_digest` only. Every
  chunk of the fixture corpus is byte-identical, which is the proof that the default did not
  move. Flipping it at 4.12 will produce a large, deliberate golden diff.
- **The invariant is asserted under both settings.** No-content-loss is the chunker's one
  promise and a change that moves every boundary is what could break it, so the property test
  runs twice.
- **`tools/measure_chunking.py` is the instrument**: shape, retrieval, and judged-anchor
  survival in one command, the third axis being one no re-ranking ever needed.
- **Roadmap 4.11 closes; 4.8 does not.** The unit is now changeable and measured, which is what
  4.11 asked for. Whether it *beats grep* is 4.8, and that waits on 4.15's flip — at 0.451
  against 0.471 it is close, and closing it may still take the 3 % the section unit could not
  give.

## References

- Spec 03 §5 (chunking policy, `kind`), spec 04 §7.1 (dev/release split), §7.3 (gate G3); D-010
- [ADR-0007](0007-adopt-structure-first-chunking.md) — atomicity, and the heading-boundary
  constraint this change respects
- [ADR-0029](0029-let-a-judgment-name-a-section.md) — the durability argument, now spent
- [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md) — the bound that made the unit
  the only hypothesis left
- `python tools/measure_chunking.py` — the shape and survival tables, re-runnable
