# 2026-09-13 — one chunk, four questions (roadmap 5.33)

- **Session scope:** roadmap 5.33 — the carry collapses several judged units onto one twin
  chunk, and a carried case names the same anchor twice. Decide what a correct carry does
  before repairing anything (spec 04 §7.1).
- **PR:** #132 (`fix/merge-collapsed-carry-anchors`). Follows #131, merged as `a2a973a`.
- **Milestone 5:** 5.33 done.
- **ADR:** [ADR-0104](../../../adr/0104-merge-what-the-projection-could-not-tell-apart-and-record-that-it-could-not.md).

## Two shapes wearing one name

The item arrived describing a single defect and it is two, wanting opposite answers.

**Within a case**, the carried file named an anchor twice. `u-1001` and `u-1003` each judge
`indexes.md#defining-an-index/` at grade 3 and the document preamble at grade 2, and on a
headingless PDF both land on `indexes-pdf-*.md#/0`. The harness builds `{anchor: grade}`, so
the repeat was never two judged units — it was one, at whichever grade came last in the file,
which was the **lower**. Both cases had been scored against a grade nobody gave them, on both
retrievers, for as long as the twin has existed, and none of the three lints in
`validate_judged_set` looks at an anchor twice.

**Across cases** nothing was malformed and the measurement had quietly changed meaning.
`python-versions-pdf-*.md#/0` is the grade-3 answer of **four** cases whose sources named
three different passages. A retriever that returns that one block has answered all four; on
the Markdown it would have had to find three.

## The decision, and the reason it cannot be accused of fitting

The item offered three options — merge to the highest grade, drop the case, or keep it and
report that the twin cannot express the judgement — and guessed the third. That is right for
the cross-case shape and incomplete for the within-case one, which also has to stop writing a
file the harness cannot read. So: merge within a case at the highest grade, merge nothing
across cases, drop nothing, and record all of it.

The grade choice looked like the delicate part and turned out to be the safe one. With a case
left holding a single judged anchor the grade **cancels**: nDCG divides a gain by an ideal
built from the same gain, recall counts anchors, reciprocal rank reads a position. So no
grade here could have been picked to flatter a number, and the highest is simply the one
that is true of the chunk — it holds the passage that was graded 3.

Then the re-bless proved it rather than asserting it. Both arms of `uv-ingested/release` moved
`blessed_from_snapshot` and `cases_digest`, and **nothing else**: mycelium 0.618671, grep
0.575367, every per-slice and every per-case entry byte-identical. A baseline diff with no
numbers in it. In between, gate G3 disarmed itself on the case-set digest and said so — the
machinery roadmap 4.24 built, doing exactly its job on a change that moved no score.

Gate G2's verdict needed the same treatment for the same reason, and I had not expected it:
it records `cases_digest` per set, so editing two anchors staled it with no ranking input
touched, and two `test_g2_verdict.py` failures said so at the end of a twenty-minute verify
run. Re-recorded, it repeats the story — decision still `lexical`, all four `uv` and
`uv-ingested` set numbers byte-identical, and the only movement anywhere is `ours/*` growing
by the ADR and journal entry this very session is writing.

## What the new column closed

`measure_projection_cost.py` gains `shared` beside ADR-0102's `whole`: how many distinct
judged units landed on the chunk this case is judged on. It reads from the receipt, which now
carries a `collapsed` block (`v2`), for the same reason `whole` does — the table and the
receipt must not be able to disagree.

It answers the question ADR-0097 opened and could not close. **All three cases that outscore
their own source are collapsed ones, and nothing else in the table is**: `u-1006` +0.569,
`u-1001` +0.324, `u-1003` +0.075. That is not a retrieval finding, it is a distinction the
projection destroyed — which is the thing this corpus exists to detect, and the reason the
cases are kept and marked rather than dropped.

It is not a predictor, and the table says so itself: seven cases share a chunk and three
gained, because `u-1005`, `u-1013` and `u-1024` were already at the ceiling or the floor on
both sides. No floor, no filter — the same refusal `whole` got.

## Two corrections to the record

Roadmap 5.26 filed `u-1003` as the **size** effect, on the words *"same single unit both
sides"*. It has the same two source anchors as `u-1001` and collapses identically, so it is
both, and the sentence that separated them was wrong. And 5.33's own text said *one* carried
case named an anchor twice; two did. Neither correction changes what was decided at 5.26 —
the fall there was still the twin agreeing with its source — but a category written into an
ADR is worth being right about.

## Lesson

A judgement that names two passages and a corpus that holds them in one chunk disagree about
how many things there are to find, and the metric resolves that silently, in favour of
whatever the file happened to say last. The number never looked wrong. What was wrong was
that the file said something the harness had no way to represent — and the fix that made it
representable moved nothing, which is how you can tell it was a repair and not a tuning.
