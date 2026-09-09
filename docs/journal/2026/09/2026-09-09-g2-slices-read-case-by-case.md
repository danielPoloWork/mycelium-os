# 2026-09-09 — the bar was right and the item was wrong (roadmap 4.41)

- **Session scope:** roadmap 4.41 — G2's per-slice condition cannot discriminate at the set
  sizes it runs on (spec 04 §§7.3, 7.6; D-010; ADR-0044/0052/0064/0068).
- **PR:** #92 (`fix/g2-verdict-statement`). Follows #91 (4.40), merged as `6297b0b`.
- **Milestone 4:** 4.41 done; 4.42, 4.43 open. Filed here: 6.8.

## I set out to fix a bar and found it was doing its job

4.41's reading was that G2's failures are "one or two cases moving" — noise a four-case slice
cannot tell from a change — and that the remedy was G3's: arm the slices that have cases,
report the rest. Two measurements later, none of that survived.

**G3's rule does not transfer.** Every slice hybrid trips already has four or more cases, so
`MIN_ENFORCEABLE_SLICE_CASES` would change nothing. That is not a coincidence: G3 compares
one retriever *across time*, where a slice can move because the corpus was re-cut and not
because retrieval changed (ADR-0044 measured exactly that). G2 compares two retrievers on the
same cases, the same snapshot, the same instant. There is no confounder to arm against.

**And the trips are real.** Decomposed — ADR-0058's method, applied to G2 for the first time
— six of the seven are *one case*, and the item was right about that and wrong about what it
means:

```text
u-1016   0.635 -> 0.289    conceptual, uv/release
u-1022   0.885 -> 0.426    relationship, uv-ingested/release
u-1021   0.316 -> 0.000    exact, uv-ingested/release   <- the answer, gone
u-1019   0.396 -> 0.131    symbol, uv-ingested/release
```

That is not a slice wobbling. That is hybrid destroying four answers, and the condition
catching it.

## The arithmetic the item did not ask for

Having read the cases I measured the bar itself. A slice of `n` cases at lexical mean `m`
trips when one case loses more than `0.02·n·m`: across these thirty slice-rows that threshold
runs 0.007 to 0.089, median **0.053**. The median losing case gives up **0.126**.

So a *typical* losing case trips its slice on its own. At four to seven cases, "no slice worse
than −2 %" is a **per-case veto** wearing a percentage's clothes. And hybrid moves 55 % of the
119 answerable cases and worsens 15 % — over five or six slices, something trips on nearly any
set.

Both halves are true at once, which is the finding: **the condition is catching real harm and
is simultaneously unmeetable.** For it to require more than one case to move, at the losses
actually observed, a slice needs ~35 cases — five to nine times what it has.

## So the bar stays

Loosening a condition that is doing its job, inside a change whose premise was that it cannot
do its job, is the fitted parameter this project has refused thirteen times. What is wrong is
the denominator, and a denominator is not a bar to be edited — it is cases to be written.
Filed as **6.8**, with the number attached so nobody has to re-derive it.

The tempting middle — report the per-slice condition and enforce only the overall bar —
would not even have flipped the default today, because `uv-ingested/release` fails the
overall bar too. I rejected it precisely because of how close that is: the default would then
rest on one set's overall number with the harm check switched off, and `u-1021` going to zero
would be invisible.

## What did ship

Two things, and both are about the verdict rather than the bar.

**The cases are named.** `conceptual -13.1% (u-1016 0.6352->0.2894)` instead of `conceptual
-13.1%`, in the gate line, in the tool's table, and in the committed record. 4.41 could be
filed with the wrong premise *because it could be*: nothing in the output distinguished noise
from a destroyed answer. G3 got this at 4.20; G2 never had it.

**G2 stops calling a legitimate outcome a failure.** It reports now, in G6's vocabulary, for
two independent reasons: "ship lexical-only" is the shipped configuration, so the boolean was
red on every correct build (4.40's finding); and one set cannot decide a default that is
decided over every release set — `ours/release` clears both conditions while both `uv`
release sets fail. Enforcement stays where 4.40 put it, across corpora.

The standing consequence is now written down rather than left to be rediscovered: **G2 cannot
promote hybrid at these set sizes.** The lexical default rests on a burden that cannot
currently be discharged, not on a weighing that came out against hybrid.

## Small things

`tests/test_eval.py` gained the seven tests G2's semantics had never had — its boolean was
asserted *nowhere*, which is part of why its polarity survived three milestones unexamined.
And the consistency lint 4.27 built earned its keep: I numbered the new item 6.7 and it
refused, because 6.7 was already issued.
