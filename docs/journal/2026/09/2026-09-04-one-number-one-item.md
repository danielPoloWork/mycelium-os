# 2026-09-04 — the cheap half of a collision (roadmap 4.27)

- **Session scope:** roadmap 4.27 — the roadmap issued `4.23` twice; resolve the collision
  and stop the next one.
- **PR:** #76 (`chore/one-number-one-item`). Follows #75 (4.23), merged as `5ff2bcf`.
- **Milestone 4:** 4.27 done; 4.25, 4.26, 4.28, 4.29 open.

## I reversed the conclusion I filed this item with

At 4.22 I wrote: *"Renumber the **open** one — the later filing is the mistake."* That was
right about culpability and, by the time the work happened, wrong about everything else.

Between the filing and today, #75 closed the later `4.23` and grew its citations. Counted:

| which `4.23` | live references |
|---|---:|
| the later one — the foothold reach filed at 4.19, closed by #75 | **30**, across `store/sqlite.py`, `tests/test_store_expansion.py`, `tools/measure_ranking.py`, ADR-0048, ADR-0053, ADR-0054, `README.md`, `eval/README.md`, `CHANGELOG.md`, and two sibling roadmap items |
| the earlier one — the derived-set regeneration closed inside 4.15 | **1** |

Thirty pointers against one. Culpability is not a reason to move thirty of them: in a
regime whose first rule is *never renumber*, the tie-break has to be minimum disturbance,
because the number exists for a reader rather than for a ledger of who erred. So the
**earlier** item became **4.30** and its single CHANGELOG pointer moved with it.

Two details that make that honest rather than merely cheap. The renumbered item says where
its number came from, in its own line — so a reader arriving from the 2026-09-03 journal
entry that still says `4.23` lands somewhere that explains itself. And no dated record was
edited: a journal that said `4.23` on the day it was written was true then, and correcting
it would trade a small ambiguity for a rewritten history.

## The item was XS; the durable half is the lint

Fixing the collision fixes today. `ROADMAP.md` already stated the rule that prevents it —
*"a fresh `<milestone>.<task>` number; never renumber"* — and the rule was followed by
everyone right up until it wasn't. So the fix is not a better sentence, it is a check:

```text
[roadmap-numbering] item number 4.23 is used twice - 'Regenerate the derived ingested
sets after the chunker mov' and 'A query with no literal foothold still misses'; give
the newer one a fresh number and update every reference to it
```

That is `tools/consistency_lint.py` run against the tree *before* the fix — the check proved
to bite on the real defect rather than on a fixture, which is the only demonstration worth
having. It also refuses an item filed under a milestone it does not name.

What it deliberately does **not** refuse is a gap. An item folded into another leaves one,
and the hole is the truth; a lint that failed on it would teach people to fill holes, which
is renumbering with extra steps. `tests/test_consistency_lint.py` asserts that non-invariant
alongside the two real ones, because a deliberate omission that nothing records reads as an
oversight to the next person.

The preamble now says how the next number is chosen — one past the highest ever issued in
that milestone, closed items included, never the next gap — which is the sentence whose
absence let two people pick `4.23` in good faith.

## What this cost, for the next reader

Two files for the renumber, one for the preamble, one for the check, one for its tests. The
expensive version — the one I filed — would have touched ten, including an *Accepted* ADR
that says "ROADMAP 4.23 (this item)" and four comments in `store/sqlite.py` that have
nothing to do with numbering. The lesson is not about roadmaps: an identifier's cost is
where it is *referenced*, not where it is defined, and the cheapest thing to move is the
thing nothing points at.
