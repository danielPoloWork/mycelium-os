# 2026-09-13 — the promise that was never kept (roadmap 5.29)

- **Session scope:** roadmap 5.29 — a DOCX loses its inline code inside docling, and only a
  report can say so.
- **PR:** #127 (`docs/report-what-a-lane-cannot-carry`). Follows #126, merged as `e81f107`.
- **Milestone 5:** 5.29 done. 5.36 filed.
- **ADR:** [ADR-0100](../../../adr/0100-declare-what-a-lane-cannot-carry.md).

## Three claims, all checked before anything was written

The item arrived with its measurements already taken at 5.25, and the habit this repository has
built is to re-read the artifacts rather than trust the summary. All three held.

The naming **is** in the DOCX container: `dependencies.docx` carries 224 `VerbatimChar`
character runs, `cache.docx` 74, `certificates.docx` 31. It **cannot** come out:
`docling_core.types.doc.document.Formatting` has exactly five fields — `bold`, `italic`,
`script`, `strikethrough`, `underline` — and no monospace among them. And the split across the
twin is larger than the item's sentence suggested:

| lane | documents | spans carried |
|---|---:|---:|
| html | 62 | 1 215 |
| docx | 10 | 0 |
| pdf | 9 | 0 |

So 5.25's *"the twin names commands again"* is a statement about 62 documents, presented as one
about 81.

## The design was already written down, in the module that needed it

I went looking for where a report like this belongs, and `fidelity.py`'s docstring answers it
in a paragraph that reads as though it were written for this item:

> A parser's *declared policies* — pandoc drops thematic breaks, docling drops running headers,
> the PDF reader claims no structure at all — are not per-element counts. They are properties
> of the parser, recorded once in the KIR document's warnings, and carried into the report
> verbatim. Emitting a node per dropped thematic break to make a counter tick would put noise
> in the projection to satisfy a metric.

That settles three things at once. Where it goes: the KIR warnings. What shape it takes: one
declaration per document, not a count. And what it must **not** be: an opaque node. The
contrast is one function away in `docling.py` — `_account_for_notes` turns a DOCX note body
into an opaque `lost` node because the *content* vanished, and here nothing vanishes.
`__token__` arrives with every character; only the fact that the source called it code is gone.
Charging the loss budget for content that is present would corrupt the one number the budget
exists to protect.

The HTML lane declares nothing, and that took a moment to see as a feature. A notice on every
lane would be uniform and useless. The split is the information.

## The part I nearly got wrong

The tempting version was to count: read `VerbatimChar` runs out of the container the way
`_count_notes` already reads `word/footnotes.xml`, and report *how many* namings each document
lost. It would have been exact on this corpus and meaningless anywhere else — `VerbatimChar` is
**pandoc's** style name, and every DOCX in the twin is pandoc-produced. A DOCX from Word spells
the same thing with a different style or a direct font run. A number that is right only for
documents we generated is a number fitted to the fixture, which is the thing this project
refuses in every other direction.

So the declaration says *what the lane cannot carry*, which is true of any DOCX, and says
nothing about how much.

## Nothing moved, and that was checked rather than argued

KIR warnings do not reach the projected text. I verified that before writing, and again after:
regenerating the ingested corpus produced **no change to any committed file**, the carried cases
are untouched, both baselines stand, gate G2's verdict is still current and G3 still enforces.
A report change that moved a number would not have been a report change.

## The inventory gate checked the argument for me

The element inventory failed on four fixtures, which is what it is built to do: it records each
parser's declared policies beside its element counts, and refuses a parser change nobody
reviewed. Re-blessing it produced a diff of **two policy lines and nothing else** — no `kinds`
count, no `dispositions` bucket.

That is a better proof of the design claim than the argument I had written for it. If this had
been a loss rather than a declaration, the counts would have moved and the loss budget with
them. The gate said so without being asked.

## The finding worth keeping

The adapter's own `_inline_spans` docstring has said since 5.25 that the span *"is reported as
absent from the other two"*. Nothing reported it. The sentence was written in the same commit
that made it false, and it read as a description of the system for four milestones.

That is the most ordinary way for a silence to survive: not by nobody noticing, but by someone
noticing, writing down what ought to happen, and the writing standing in for the doing.

## Found on the way

KIR models **no emphasis at all** (5.36). docling exposes bold, italic, underline,
strikethrough and script per run; this adapter reads none of them; and there is nowhere to put
them, because `KirNode.spans` carries code alone. So it is a vocabulary question about spec 03
§4's closed node kinds, not an adapter one, and it applies to every lane — `**bold**` indexes
as `bold` through authored Markdown exactly as it does through DOCX.

The prior is that this is correct and should stay: emphasis is not a naming, and the indexed
text is identical either way. What makes it worth an item is a measurable inconsistency —
`~~struck~~` survives as literal characters through markdown-it, which has no strikethrough
rule, and vanishes as formatting through docling, so the twin and its source disagree about a
document neither lane thinks it damaged. Measure that first; it may be zero occurrences, in
which case the answer is to record the refusal and close.

## Lesson

A docstring that says what *should* happen is indistinguishable, to a later reader, from one
that says what *does*. This project writes long docstrings on purpose and they are usually its
best asset; the failure mode they carry is that a promise and a description look the same on the
page. Worth asking of any sentence in the present tense: is there a test, or is this a plan
someone wrote in the wrong tense?
