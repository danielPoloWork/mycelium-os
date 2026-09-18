# 2026-09-18 — the incumbent reads a window (roadmap 6.22)

- **Session scope:** roadmap 6.22 — decide what a grep loop does with a file larger than its
  context budget, and repair the agent-task comparison accordingly.
- **PR:** #166 (`fix/grep-reads-a-window`). Follows #165, merged as `899e0d8`.
- **Milestone 6:** 6.22 closed; 6.28 and 6.29 filed from it, and 6.23 gained a second question.
- **Decision it records:** [ADR-0131](../../../adr/0131-bound-the-incumbents-read-and-publish-the-band-it-buys-evidence-along.md).

## The item was a decision, and the decision goes against us

6.4 found the defect and refused to fix it in the same breath, which was right: *what does a
grep loop do with a file larger than its budget?* is not a bug report. The item also wrote the
constraint that decides the answer — *"whatever is chosen must be argued on what an agent
actually does and never on what makes our number better (D-010: fix the product, not the
benchmark — which cuts both ways)."*

An agent does not read an 88 000-token file. It reads a window around the hit, or it re-greps.
Only the first branch is modellable without a model in the loop, so: **one read costs at most
what one search may.** `budget_tokens` is what a caller will spend on one step of
context-gathering; Mycelium spends it once, on passages ranked across the whole corpus; a grep
loop spends it per file it opens, because it has no packing and no ranking across files. Five
files, as `MAX_GREP_FILES` has claimed since ADR-0022 and never delivered.

What that cost us, on the same 22 tasks and the same corpus:

| | before | after |
|---|---:|---:|
| grep, evidence found | 1 / 22 | **14 / 22** |
| grep, mean context | 52 529 | **15 268** |
| our lead | +15 tasks | **+2 tasks** |
| context ratio (means) | 19.2× | **5.6×** |

The incumbent gained thirteen tasks. That is the whole point of the exercise and the reason the
item existed.

## Three choices inside the decision, and why each went the way it did

**Sections, not lines.** A real read is line-addressed, and modelling it that way would have
charged grep for raw Markdown while charging us for rendered text — a better ratio for a reason
that has nothing to do with retrieval. It would also have been wrong on its own terms: line
count is no proxy for cost here, where `ROADMAP.md` averages **330 tokens a line** against
prose's thirteen. So the window is rounded to section boundaries, the loop stays in the store's
rendered view, and the rounding is stated rather than hidden.

**A section larger than the window carries no evidence.** The agent saw part of a passage,
which is not being handed it. Five sections in this corpus exceed a 4 000-token read and four
are in `ROADMAP.md`.

**No global cap on grep's total.** The tempting tidy answer was to give both sides the same
4 000 tokens and compare evidence at equal cost. It models a loop nobody runs: an agent with a
large context does not stop grepping at four thousand tokens, it reads a few files because it
does not know which one holds the answer — and that cost is precisely what compiling knowledge
removes. Capping both would have deleted the product's actual claim in order to tidy the table.

## The band, because one row is how the last two defects survived

Both constants of the loop are parameters now, and `tools/measure_agent_task_band.py` runs the
comparison across each. Every extra file the incumbent opens costs ~3 800 tokens and returns
~3 tasks — evidence spread evenly down its reading order, with no cheap point where it has what
it needs. So the honest claim is two-sided and neither half stands alone: *at equal cost* its
first read returns 1/22 against our 16/22; *at comparable evidence* it pays 5.7×.

## The consequence I did not get to choose

ADR-0120 quantified the verdict gate that arms at the v1.0.0 tag: the evidence lead must exceed
**two tasks**. On the repaired instrument it is exactly two. **Condition (a) fails.**

The rule stays as it is. It was calibrated in the same report that found the incumbent
degenerate, and it compares two evidence rates while the sides pay 5.7× different costs — both
are arguments for looking at it again, and neither is licence to move a bar in the act of
discovering you no longer clear it. That is the benchmark-fixing D-010 forbids and ADR-0120
itself refused for the performance budgets. The question travels to 6.23, to be settled before
the tag rather than in the act of failing it.

## What the repair made visible

Two tasks are now won by grep and lost by us, which the old instrument could not show because
grep won nothing. The mechanism turned out to be worth its own number: our ten hits span a mean
of **5.8 documents**, and on **10 of 22** tasks one document takes half the slots or more —
eight of ten on `t-0007`, where the crowding document is a bug record and the answer is in an
ADR grep reads whole. It is not obviously a defect: the concentrated document is usually the
right one. It is an unmeasured knob, and it is filed as 6.29 for the judged sets, where a
ranking change belongs.

And 6.28 for the mirror image: our own side asks for ten hits whatever the budget, so above
4 000 tokens it cannot spend what it is given and the comparison understates us. Left alone
deliberately — a change that lifts our own side needs its own argument in its own pull request,
which is the same rule this item was written under, pointed the other way.

## Lesson

A benchmark's scale must be a property of the instrument, not of the corpus. Before the bound,
the incumbent's cost was the size of whichever document matched first, so the comparison drifted
as one file grew and nobody noticed for two milestones. After it, grep's cost cannot exceed five
reads and a document growing moves the verdict by at most its share of one. Every instrument
defect this project has found — anchor rot, the degenerate read, and now two more filed — is the
same failure: a constant that was right when it was written and was never asked again.
