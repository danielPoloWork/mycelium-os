# 2026-09-22 — near the top is the whole loss (roadmap 6.37)

- **Session scope:** roadmap 6.37 — a perfect re-ranking of the candidates we already have
  is worth +36 % to +86 %, and nothing knows which ones they are. Characterise the gap
  before proposing anything.
- **PR:** #187 (`feat/characterise-where-the-ranking-loss-lives`). Follows #186, merged
  as `1d25094`.
- **Milestone 6:** 6.37 closed. 6.38 remains open, and is now priced against this.
- **Decision it records:** [ADR-0152](../../../adr/0152-the-ranking-loss-is-ordering-not-recall.md).

## The item asked three questions and the third one settled it

Where do the judged passages sit when they are not in the top ten; is the loss concentrated
in a slice, a corpus or a document length; and — the one that decides what the next item is
about — does the pool contain the judged passage at all. A ranking failure and a
candidate-generation failure look identical in an nDCG average and want opposite fixes.

It is a ranking failure, and not narrowly. **Candidate generation finds 93.0 %–99.8 % of the
judged passages.** Probing four times deeper than anything ships adds +3.8 %–13.7 % of the
ceiling, and a judgment the served ten missed sits at a median rank of 18–31 — the middle of
the pool the product already builds, not past its edge. So the next item is not about BM25
and not about recall depth, and that is now a number rather than an intuition.

## The decomposition was the part worth building

The useful cut was not "found or not found" but **how wide a slice of the pool you need to
see in order to fix a case**. Re-ordering *perfectly* from progressively wider windows —
the ten already returned, the shipped fifty, a probe of two hundred — turns one ceiling into
three, and the differences between them are the answer.

Permuting only the ten chunks already served is worth **+23.8 % to +53.7 %** and carries
**58.4 %–72.1 % of the entire ceiling**. No new leg, no deeper pool, no additional
retrieval — the pipeline is already holding the right passages and showing them in the
wrong order. The position data says the same thing from the other side: a case's best-graded
judgment sits at median rank 1 on four of six sets, and is *first* on only 35.5 %–59.1 % of
the cases that serve it. The answer is usually in the ten and usually near the top, and
"near" is the whole loss.

## Two explanations measured and refused

The first hypothesis was that the ceiling is mostly the cost of failing to pack
*supporting* material — grade-2 judgments are served far less often than grade-3 ones, so
the gap would be real but much less interesting than it looks. Restricting the entire
measurement to the passages that answer outright moves the ceiling by **−1.7 to +4.4
points**, and moves it *up* on one set. The headroom is the same size when only the answers
count.

Document length was the item's own third candidate and shows nothing: median 7–12 chunks
when the ten serve a judgment, 7–12 when they do not, and the direction is not even
consistent between sets. Reporting a negative properly is cheaper than leaving the question
open for the next reader to re-ask.

The one real concentration is `relationship`, worst served on five of six sets — the same
slice a diversity cap cost −65.2 % at 6.29, and the same mechanism: those answers genuinely
are spread across several chunks of one document.

## A correction to the number this item was filed on

ADR-0144's oracle sorted candidates by `judged.get(anchor, 0)`. A judgment may name a whole
*section* (ADR-0029), which the metric satisfies with any chunk under it — but that lookup
scores such a chunk zero and sinks it below unjudged candidates. The oracle was understating
its own ceiling, by **+1.6 to +3.7 points** on the four sets carrying section judgments.
Small, and it only strengthens a refusal that was argued against a smaller number, but the
sort had to be fixed before anything was measured on top of it.

## What this deliberately does not conclude

A ceiling of +36–86 % looks like spec 06 §3's *"deterministic pipeline plateaus on frozen
sets"*, and reading it that way would be assuming the thing the item exists to establish.
What is measured is that the headroom is reachable by re-ordering — not that no
deterministic rule can reach it. Every ranking change this project has measured aimed at
*which candidates are selected* or *which legs compose*; none aimed at the order of the
served set. A family with no attempts in it has not plateaued; it has not been tried. The
trigger stays unmet, and 6.38's heading-proximity and trust-class boosts turn out to be
aimed at exactly the right window — now priced against the 58–72 % share rather than
against zero.

## What shipped

`tools/measure_ranking_gap.py` and eleven tests for the arithmetic that decides what its
verdict means. It joins `verify.py`'s `retrieval` rung at about a minute for six sets,
guarding the *shape* rather than a default, because everything filed on this conclusion is
filed on this number. Retrieval itself is untouched.
