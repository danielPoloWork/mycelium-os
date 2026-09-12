# 2026-09-12 — the twin was easier than its source (roadmap 5.26)

- **Session scope:** roadmap 5.26 — read the one `exact` case that moved when the ingested
  twin was re-rendered (ADR-0095), and decide whether its carried anchor is right.
- **PR:** #124 (`test/read-the-case-the-repair-moved`). Follows #123, merged as `69a433a`.
- **Milestone 5:** 5.26 done. 5.30, 5.31, 5.32 and 5.33 filed.
- **ADR:** [ADR-0097](../../../adr/0097-a-twin-case-that-outscores-its-source-is-the-defect-not-the-fall.md).

## The item offered two answers and the premise of both was false

5.26 asked whether the new anchor was the right one, *or* whether the carry had picked a
worse chunk among several good ones. Both assume the carry moved the anchor. It did not, and
the check took one query: `knowledge/evidence/indexes-pdf-*.md#/0` is lines 8–51 of the
projection before and after, 535 tokens before and after, and covers the judged passage at
**1.0000** — the maximum the coverage rule admits — before and after. There is no "several
good ones": the next-best chunk in the document covers 0.7097.

The two texts are not byte-identical, and the difference is the whole of it: `“default”`
became `"default"`. pandoc's `markdown` dialect applies smart quotes and `gfm` does not, so
the repair straightened them. The store's `unicode61` tokenizer indexes neither character, so
the chunk's alphanumeric tokens are *identical*. Its BM25 score against `tool.uv.index`
cannot have changed, and did not.

So the judged chunk did not fall. Something rose past it.

## What rose was a document that had been broken

`dependencies-docx-*.md#dependency-sources/index/0` went from rank 6 to rank 2 — and it did
not exist before. `docs/concepts/projects/dependencies.md` is one of the nine documents 5.24
named: its `### Index` heading was inside a code block, and the section's text sat in a
626-token `#dependency-sources/0` block together with four of its siblings. The repaired twin
cuts that document into 28 chunks where it cut 23, and its `dependency-sources` subsections
are now the same nine, with the same names and token counts within four, as the Markdown
corpus it was projected from.

The check that settles it is the source corpus, where the same frozen judgement is applied to
the documents a human actually wrote:

| | judged passage | the rival |
|---|---:|---:|
| `uv/release` — Markdown | rank 6 | rank 3 |
| twin, before the repair | rank 2 | rank 6 |
| twin, after the repair | rank 3 | rank 2 |

The broken twin ranked them in the opposite order from its own source. The repaired twin
ranks them in the source's order. Nothing to adjust: 0.7602 is the slice's correct reading,
and the number it replaced was produced by a corpus defect. Tuning to recover it would have
been fitting the ranker to a rendering bug, which is D-010 pointed at the instrument.

## The number that should have been asked about was never the fall

`u-1003` scores **0.3562** on `uv/release` and scored **0.6309** on the twin. A copy of a
document cannot be easier to retrieve than the document it was copied from; where it is,
something upstream of the measurement is wrong. That gap stood for three milestones and
nothing said so, because `measure_projection_cost.py` reported per format and never printed a
case — so a standing +0.27 was invisible and the −0.13 that partly corrected it arrived
looking like a regression, which is how it came to be filed as one.

The tool now prints every shared case, widest gap first, and names the ones above their
source. No threshold: which way a gap points depends on the case, and a cut-off would turn
that reading into arithmetic. Its first run makes `u-1003` look minor:

```
u-1006  pdf  0.431 -> 1.000  +0.569
u-1001  pdf  0.676 -> 1.000  +0.324
u-1003  pdf  0.356 -> 0.500  +0.144
```

Three cases, all PDFs, and together they *are* the `pdf` row's +0.093. Reading them split the
one mechanism I had into two.

`u-1003` is the mild one and it is the size effect: the same single chunk on both sides, 535
tokens against 64. That was already printed one line above it — a PDF has no headings, so its
chunks are packed to the token budget and the carried target averages 602 tokens against the
Markdown chunk's 128, **4.7×** — and nobody had joined the two tables.

The two large ones are **collapse**, which is worse. A headingless PDF hands the carry one
chunk where the judgement named several units, so a case that asked for more than one thing
becomes a case that asks for one. `u-1006`'s source judgement is section-scoped precisely
because the answer is spread across the section (ADR-0029); on the twin the section is a
single block at rank 1 and the case is complete. `u-1001` is the same thing made literal: its
two distinct source anchors — a section at grade 3 and a chunk at grade 2 — both carry onto
`#/0`, so the twin's set **lists that anchor twice**. `run_evaluation` builds
`{anchor: grade}`, the duplicate dedupes to grade 2, and a case that needed a section and a
chunk in the right order needs one chunk at rank 1. Nothing reports it: the validator's three
lints are anchor-exists, unanswerable-is-unanswerable and grade-3-carries-the-answer.

The `pdf` row has never been a gain.

The dev set, judged and frozen separately, says it from the other side: the twin is worse
overall there (−0.032), `docx` −0.037, `html` −0.108, and `pdf` is again the only row that
rises (+0.111) on the strength of its one above-source case. Every apparent ingestion gain
this project has reported is a PDF case whose judged target the projection enlarged or
collapsed; every format whose structure survives loses a little. That is what the twin was built to measure, and it is now legible.

## Two corrections to the item's own arithmetic

The slice moved on **two** cases, not one. `u-1021` went 0.315465 → 0.30103, rank 8 to 9 —
10 % of the slice's 0.0291, and it is judged inside the *same* repaired `dependencies`
document, pushed down by its own newly separate siblings. The same mechanism, on the other
side of the ledger.

And the anchor is not an ordinal because the source is a PDF: the Markdown original's anchor
is `#/0` too. It is a document preamble, before the first heading, on both sides.

## Found on the way, filed rather than absorbed

`u-1004` (5.31) is the `pdf` row's other half and the only large negative the per-case block
prints: 0.387 on its source, **0.000** on the twin, anchored in the same projected PDF that
carries `u-1003` at `#/0`. One document holding the format's largest gain and its largest
loss is not explained by target size, so it wants its own reading.

The collapse itself (5.33) is not fixed here, and deliberately: repairing the carry edits the
carried set and re-blesses the twin's baselines, which is the one thing an item reading a
corpus repair must not do in the same change. Making it visible on every run is what this PR
does instead.

Whether `u-1003`'s *source* judgement is right is a real question (5.30) and was deliberately
not touched here: the preamble names `[[tool.uv.index]]` once while the document gives the key
three sections of its own, all of which outrank it. That is ADR-0062's rule, and whether it
reaches the `exact` slice is a decision about a frozen held-out set, not a paragraph inside
another item's change.

And `docs/journal/README.md` (5.32) has not been written to since 2026-09-10: 69 rows against
98 files, 24 entries unindexed, starting with 5.1's. The congruence lint asserts *ADR index ↔
files* and has no counterpart for the journal, which is how twenty-three consecutive PRs each
omitted a line with every tick green.

## Lesson

A measurement that only ever reports averages can hide a defect *and* make its correction
look like damage — the same blindness twice, in opposite directions. The fix was not a better
threshold; it was printing the rows the average was made of, which is what ADR-0044 concluded
about slices four milestones ago and what ADR-0052 had to build again for cases. This is the
third time. The rule is worth stating plainly: when a number moves and the explanation is not
immediately obvious, the first question is not *why did it move* but *what is it the mean
of*.
