# 2026-09-21 — the gap that rested on two questions (roadmap 6.33)

- **Session scope:** roadmap 6.33 — the dev sets were still the size the release sets used
  to be, and they are the only signal that says whether tuning fitted the set it was
  allowed to read. Author them to the count that signal needs, and measure the signal
  before deciding what the count is.
- **PR:** #PRNUM (`feat/author-the-dev-sets-to-the-count-the-gap-needs`). Follows #182,
  merged as `c26b988`.
- **Milestone 6:** 6.33 closed. 6.34–6.37 remain open.
- **Decision it records:**
  [ADR-0148](../../../adr/0148-author-the-dev-sets-to-the-count-the-gap-needs.md).

## Measuring the instrument before enlarging it

The item asks for cases, and the temptation is to start writing them. What the number
needed first was a reading of itself. A dev set is reported and never gated (ADR-0027), so
the only thing it produces is the gap against the release set — and the question is not
"is the gap big" but "can the gap be read at all".

Scored on a clean checkout, the answer was no on most rows. Taking what
`enforceable_at` already calls a typical answered case, and dividing by the slice's size,
gives what one case is worth against the gap that row prints. **Nine of fourteen rows came
back above 1.0**: one case could erase or reverse the number a reviewer is invited to read.
`uv`'s `conceptual` row was the worst at **11.5×** — an overfitting signal one of its four
cases outweighed eleven times over. Our own `exact` row printed **+0.2295**, a
twenty-three-point overfitting claim, off two questions.

The second thing the measurement found was not in the item. **Every gap had gone negative**
— −0.0100, −0.0760, −0.0350 — where ADR-0027 measured +0.115 and +0.153. Nothing about
tuning explains a sign flip that size. 6.8 does: it re-authored the release sets from the
documents at ten to sixteen times their size, and left the dev sets as the cases frozen on
2026-08-31. The gap was no longer comparing a set tuning read against one it did not; it
was comparing two sets written years apart in project-time by different methods.

## The count came from the row the gap is subtracted from

A dev set has no baseline, because it gates nothing — so `enforceable_at`'s rule about
reading a *frozen* baseline seems to leave nothing to read. It does not: the gap is a
subtraction against the release row, and that row has a frozen baseline. Sizing the dev
slice to the count derived for the release slice makes both sides of the subtraction
equally precise, so the gap inherits the release row's resolution rather than the dev
row's much coarser one. No new constant, and nothing read from the run under test.

That gave 44/62/62/64 on our corpus and 74/67/72/66/50 across the two `uv` sets — 530 new
judgements, written from the documents with the anchor read rather than retrieved, and
validated mechanically against a real build before either set could be written.

## What measuring afterwards was allowed to claim, and what it was not

Holding the corpora fixed so that only the sets varied: fourteen of fourteen rows now
report a gap larger than one case can move, worst 0.92× and eleven at or below 0.3×. All
three gaps are positive again, ours at **+0.1271** against ADR-0027's +0.115.

The tempting sentence — "the overfitting signal is back" — is not available. These cases
have never been tuned against, so a positive gap today is the *baseline* the gap will be
read from, not a measured overfit. And there was an obvious alternative explanation worth
killing: several authoring agents reported steering away from answers buried deep inside
long sections, which would have biased the dev sets toward passages that are easy to find.
Checked rather than assumed, by comparing where each set's grade-3 anchors sit — 96.2 % vs
92.6 % first-chunk on ours, 95.8 % vs 97.3 % on `uv`, with the `uv` dev set marginally the
*deeper* anchored of the two while scoring higher. Anchor depth does not account for the
gap. That is a measured negative and it is recorded as one: some other difference between
two authoring passes may, and the thing to watch is the gap's movement rather than today's
value.

## Three things found on the way

**The twin drops whole cases now, not just anchors.** 6.8 reported 27 dropped anchors with
every case surviving; here four `uv` dev cases do not survive the projection, three of them
because their only grade-3 anchor is a section of uv's feature list, which the HTML lane
shatters into a heading per item. Three replacement `fact` cases were authored against
passages that project, so the twin clears its own floor on every slice, and the four are
left in the source set where they are honest questions about the Markdown corpus.

**Gate G2 digests the dev sets.** `SETS` is `("dev", "release")`, so growing them stales the
recorded verdict and `--check` fails until it is re-run — but `decision_of` filters to the
release rows, so no dev set can move the shipped default. The re-record refreshes digests;
`lexical` stands for the reasons ADR-0136 gave.

**Three queries were already in both a dev and a release set** — `q-0007`/`r-0001`,
`u-0016`/`u-1261`, `u-0017`/`u-1243` — all predating this item. Reported rather than
repaired: editing a standing judgement to tidy a number is the move the frozen-set guard
exists to make hard.

## What shipped

No baseline is re-blessed, because a dev set has none. Both release sets are rewritten
byte-for-byte by their generators, so the frozen-set conjunction is not engaged. The format
rotation still holds 66 entries and nothing is re-rendered — and the new cases judge all 66,
so the judged documents now cover the whole rotation instead of a part of it. Spec 04 §7.6's
≥ 1 000 target reads **1 995 cases across six sets**.
