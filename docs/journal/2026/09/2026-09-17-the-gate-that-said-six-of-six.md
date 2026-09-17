# 2026-09-17 — the gate that said six of six (roadmap 6.8)

- **Session scope:** roadmap 6.8 — grow the judged sets until the per-slice conditions mean
  what they say. The instrument half.
- **PR:** #158 (`feat/derive-slice-enforceability`). Follows #157.
- **Milestone 6:** 6.8 **stays open** — the authoring is the larger half and is not here.
- **Decision it records:** [ADR-0123](../../../adr/0123-derive-the-count-a-slice-needs-instead-of-guessing-it.md).

## Measuring the premise before authoring a single case

6.8 budgets the fix at n ≥ 35 a slice and *"near 200 answerable cases per set"*. Two things
were worth checking first: whether 35 is still the number, and whether anything in the gate
knows what the number is.

Neither held. The requirement across all fourteen slices of the three committed baselines is
**50 to 97 cases, median 67** — roughly double. The difference is not drift: 35 came from the
median loss *observed* (0.126 at roadmap 4.41), and the bar has to survive the loss a single
case *can* inflict. The ordinary way a case fails is that it leaves the top ten, which costs
its slice the case's whole score, and a typical answered case in these sets is worth 0.43 to
1.00. The conservative reading is the one a gate needs.

It is also not one number. The count is `q / (0.02 · m)` for that slice's own mean and
per-case spread, and it ranges from 50 to 97 across rows measured on the same day. A single
figure for "how big a slice must be" was always the wrong specification.

## What the gate had been saying

`MIN_ENFORCEABLE_SLICE_CASES = 4`, guessed at roadmap 3.7, with its own docstring admitting
it: *"four is not a statistical threshold… what turns G3 into a regression gate rather than a
single-case alarm is set size, not a constant chosen at this milestone."*

Every slice in every committed baseline clears four. So G3 was reporting **"6 of 6 slice(s)
enforced"** while not one of those rows could distinguish a regression from a single case
moving. Four cases each worth 1.000 against a mean of 0.75 is a row one case moves by 25 % —
twelve times its own bar.

The constant was not merely imprecise. It was the reason nobody could see the problem the
item was filed about.

## The change, and the consequence it is honest about

A slice is enforced when it holds enough cases that no single case could trip it alone, and
the count is derived from the **blessed baseline** rather than from the run under test. That
direction matters: a regression lowers both the mean and the typical case, so a run scored
against its own numbers could raise its requirement above `n` and disarm the row exactly as it
fails.

The consequence, stated rather than buried: **G3 now enforces nothing on any set.** Not
because the gate was weakened — every row it stops enforcing is a row it could not have
enforced meaningfully — but because no set was ever large enough, and the constant was hiding
it. The failing information is not lost; the row still names the case that moved, and now also
names the count that would make the row a gate.

The gate arms itself. A slice that reaches its count starts being enforced on the next run,
with nothing to re-decide.

## What is not here

The authoring. Closing every shortfall is roughly 600 cases for the release sets alone and
past 1 000 with the dev sets, each a query and a verified anchor written from the documents
before anything is scored on them. That is not work this change could carry honestly: a judged
set is permanent infrastructure, and cases written quickly to reach a count would be the
benchmark measuring the judge's haste for the life of the project. 6.8 stays open, with a
target that is now checkable rather than remembered — `tools/measure_slice_power.py` prints
the shortfall per slice.

Gate G2 shares the problem and is deliberately untouched. Its verdict decides a shipped
default and is recorded and dated; moving its arming rule on the same day the instrument
appeared would re-open a shipped decision beside the evidence rather than on it.

## Lesson

A constant that documents itself as a guess is a finding waiting to be read. This one said so
for three milestones, and the thing it was guessing at — *is this row big enough to gate?* —
was computable from numbers the gate already had in front of it.
