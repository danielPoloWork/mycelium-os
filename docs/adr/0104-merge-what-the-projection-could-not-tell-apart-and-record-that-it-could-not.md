# ADR-0104: Merge what the projection could not tell apart, and record that it could not

- **Status:** Accepted
- **Date:** 2026-09-13
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.1
- **Related:** [ADR-0039](0039-measure-what-projection-costs.md) (the carry this refines),
  [ADR-0029](0029-let-a-judgment-name-a-section.md) (the section judgement that collapses),
  [ADR-0097](0097-a-twin-case-that-outscores-its-source-is-the-defect-not-the-fall.md) (the
  above-source population this explains), [ADR-0102](0102-record-whether-the-passage-landed-whole-and-read-a-large-negative-with-it.md)
  (`whole`, the same argument for the other sign),
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md) (why nothing
  here is re-judged); D-010; spec 04 §7.1; roadmap 5.26, 5.33

## Context

`tools/build_ingested_cases.py` carries the second corpus's frozen judgements onto its
ingested twin by matching text: for each judged passage it picks the twin chunk with the
best coverage of that passage's distinct words. A headingless PDF projection is one
page-sized block where the Markdown had sections, so several judged passages can land on
**one** twin chunk. Two shapes follow, and until this item neither was recorded and neither
was noticed.

**Within one case, the carried file named an anchor twice.** `u-1001` and `u-1003` each
judge `docs/concepts/indexes.md#defining-an-index/` at grade 3 and the document preamble
`#/0` at grade 2; both carry onto `indexes-pdf-d37689d3.md#/0`, so the committed set listed
that anchor twice, at 3 and at 2. `_evaluate_case` builds `{relevant.anchor: relevant.grade}`
— so the repeat was never two judged units. It was one, at whichever grade came last in the
file, which was the **lower** one. Both cases had scored against a grade they were not given,
on both retrievers, since the twin existed. `validate_judged_set`'s three lints are
anchor-exists, unanswerable-is-unanswerable and grade-3-carries-the-answer; none of them
looks at an anchor twice.

**Across cases, nothing was malformed and the measurement quietly changed meaning.** Three
twin chunks receive more than one distinct judged unit. The starkest is
`python-versions-pdf-bae1444d.md#/0`: `u-1005`, `u-1006`, `u-1019` and `u-1024` all judge it
as their grade-3 answer, where their sources named three different passages of
`python-versions.md`. A retriever that returns that one block has answered all four
questions; on the Markdown it would have had to find three separate passages.

Roadmap 5.33 named the first shape and asked the second question before the fix: what does a
*correct* carry do when two judged units have one twin chunk — merge to the highest grade,
drop the case as uncarryable, or keep it and report that the twin cannot express the
judgement?

## Decision

**Within a case, merge onto one anchor at the highest grade that landed on the chunk.** The
merged chunk contains the passage that was graded highest; calling it a 2 understates what a
retriever returning it actually found, and writing it twice states something the harness
cannot represent.

**The grade is a claim about the chunk, not a choice about the score, and that is checkable.**
For a case left holding a single judged anchor the grade **cancels** in every metric this
harness computes: nDCG divides a gain by an ideal built from the same gain, recall counts
anchors, reciprocal rank reads only a position. So no grade could have been chosen here to
make a number look better, and the re-bless that carried the merge is the evidence — it moved
`cases_digest` and `blessed_from_snapshot` and **not one score**, on either retriever, overall
or per slice or per case. A test pins the property rather than leaving it as arithmetic in
prose.

**Across cases, merge nothing and drop nothing — record it.** The set is well formed; what
changed is what the number means. A twin chunk several judged units landed on is a
distinction the projection destroyed, and *that is the measurement this corpus exists to
take* (ADR-0039). So `eval/carry.json` gains a `collapsed` block (receipt `v2`) naming each
such chunk and every judged unit that reached it with its case and grade, and
`tools/measure_projection_cost.py` gains a `shared` column — the counterpart of ADR-0102's
`whole`, for the opposite sign of gap.

**And the malformed shape is refused from now on.** `validate_judged_set` gains a fourth
lint, an **error**: a case may not name the same anchor twice. It is an error rather than a
warning because the file is then claiming something `_evaluate_case` cannot express, and the
grade it scores against is an accident of line order.

## Alternatives Considered

- **Drop a collapsed case as uncarryable.** Rejected on roadmap 5.33's own reasoning, which
  survived contact with the data: a corpus that cannot represent a distinction is exactly
  what this twin exists to measure, and dropping the cases would delete the finding instead
  of reporting it. It would also take the three largest above-source cases out of the table
  that exists to show them.
- **Merge to the lowest grade.** This is what the harness was doing by accident, so it has
  the merit of changing nothing. Rejected because it is false about the chunk: the chunk
  holds the grade-3 passage. That it also happens to move no number is not an argument for
  it — the same is true of the highest grade, which is the one that is true.
- **Keep both anchors and teach the harness to hold two judgements for one anchor.** Rejected:
  two grades for one retrievable unit is not a judgement the metrics can express — nDCG asks
  what a chunk is worth, and "3 and also 2" has no answer. The projection merged the passages;
  pretending otherwise in the scoring would be inventing a distinction the corpus lost.
- **Re-anchor a collapsed case onto a narrower chunk.** Rejected: on a headingless PDF there
  is no narrower chunk, which is the whole point. Choosing a different one by a second metric
  is how a carry starts being fitted (ADR-0102 refused the same move for `whole`).
- **Floor or filter on `shared`, or exclude collapsed cases from the twin's mean.** Rejected
  for the reason every threshold here has been rejected: `shared` > 1 does not predict a gain
  — of the seven cases sharing a chunk, three gained and four did not move at all — so a
  cut-off would turn a reading aid into arithmetic nobody measured.
- **A warning rather than an error for the duplicate anchor.** Rejected: the three existing
  lints warn only where the rule is a proxy (a short grade-3 chunk may still answer the
  query). A repeated anchor is not a proxy for anything; the harness demonstrably cannot
  represent it.

## Consequences

- **Two carried cases change, and no number does.** `u-1001` and `u-1003` lose their
  duplicate anchor and keep grade 3. The uv-ingested release baseline is re-blessed on both
  arms and its diff is two digests per arm — `overall_ndcg_at_10`, every `per_slice` and every
  `per_case` entry are byte-identical (mycelium 0.618671, grep 0.575367). Gate G3 disarmed
  itself on the case-set digest between the change and the bless, exactly as roadmap 4.24
  built it to, and said so.
- **The above-source population now has a complete explanation.** All three cases that score
  higher on the twin than on the Markdown they were projected from — `u-1006` +0.569,
  `u-1001` +0.324, `u-1003` +0.075 — are collapsed ones, and nothing else in the table is.
  ADR-0097 opened that question with two mechanisms and could not close it; `shared` closes it.
- **Two corrections to the record.** Roadmap 5.26 attributed `u-1003` to the **size** effect
  — *"same single unit both sides"* — and named `u-1001` as the collapse. `u-1003` has the
  *same two source anchors* as `u-1001` and collapses identically; it is both. And roadmap
  5.33's own text said one carried case named an anchor twice; two did.
- **`shared` > 1 is a reading aid, not a predictor**, and the table now shows why: seven cases
  share a chunk, three gained, and `u-1005`, `u-1013` and `u-1024` moved 0.000 because they
  were already at the ceiling or the floor on both sides.
- **Receipt `v1` → `v2`.** The added block is additive; `tools/measure_projection_cost.py`
  reads it with `.get`, so an older receipt yields no marks rather than an error — the same
  tolerance ADR-0102 gave `whole`.
- **The lint is retrospective as well as prospective**: a test asserts that no committed set,
  judged or derived, names an anchor twice.
- **A partial collapse would make the grade matter**, and none exists today: both collapsed
  cases reduce to exactly one anchor. If a case ever keeps a distinct anchor *and* a merged
  one, the ideal DCG has two terms and the merge grade stops cancelling — the rule is still
  "the highest that landed", and it would then be a decision worth re-reading rather than a
  bookkeeping one. The test that pins the cancellation also pins where it stops.

## References

- Spec 04 §7.1 (frozen sets, the paired comparison), D-010 (fix the product, not the
  benchmark).
- `eval/corpora/uv-docs-ingested/eval/carry.json` — the receipt, `collapsed` block.
- Re-runnable: `python tools/build_ingested_cases.py --check`, then
  `python tools/measure_projection_cost.py` for the `shared` column.
- Tests: `tests/test_eval.py` (the fourth lint, and the grade-cancels property),
  `tests/test_eval_ingested_corpus.py` (the merge rule, and the receipt against the sets).
