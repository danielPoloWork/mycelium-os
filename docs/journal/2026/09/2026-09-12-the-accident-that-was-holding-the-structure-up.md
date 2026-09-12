# 2026-09-12 — the accident that was holding the structure up (roadmap 5.22)

- **Session scope:** roadmap 5.22 / BUG-0024 — the evidence projector writes a paragraph
  verbatim, so prose that begins with a fence marker opens a code block that swallows the rest
  of the document (spec 02 §5; ADR-0034, ADR-0077).
- **PR:** #120 (`fix/projector-escapes-block-openers`). Follows #119 (5.21), merged as `a949b7f`.
- **Milestone 5:** 5.22 done; 5.24 filed. 5.23 remains open.
- **ADR:** [ADR-0093](../../../adr/0093-escape-the-prose-that-would-open-a-block-and-report-what-that-costs.md).

## The repair was the easy half

ADR-0077 already had the rule — the chats projector escapes the shapes that open block
structure inside its callouts — and this is that rule, generalised and applied where the
projector is four items older. Two things the item proposed needed correcting, both by
measurement rather than argument.

It asked for a rule on *a paragraph's first line*. Every shape interrupts a paragraph from any
line, and `dependencies-docx` — one of the four documents the bug named — carries its marker
mid-paragraph. A first-line rule would have left it exactly as broken.

And the escape had to be shown to be free before anything else was worth doing. It is:
CommonMark reads `\##` as a literal `##`, so the indexed text keeps the characters and loses
only the block-level meaning. Counted across the corpus, backslashes in node text are **137
before and 137 after**. Not one reached BM25.

## Choosing the shape list, and refusing the flattering answer

The item said the list should be chosen by measurement. The measurement that mattered was not
how often each shape occurs — it was what a narrower list would score. So I built the
fence-only variant, the one that fixes the reported bug and nothing else, and ran it end to
end:

| variant | ours | grep | lead |
|---|---:|---:|---:|
| before (the defect) | 0.6378 | 0.4865 | **+0.1513** |
| fence only | 0.5980 | 0.5310 | +0.0670 |
| every shape (shipped) | 0.6018 | 0.5564 | +0.0454 |

Fence-only leaves us a bigger lead. That is the whole reason it cannot be the reason to choose
it: picking the rule by the number is fitting the benchmark, in the direction that is always
tempting. The shape list is chosen on an argument instead — a heading in a DOCX is a *style*, in
a PDF it is larger type, in HTML it is an `<h2>`, and none of them reaches KIR as the characters
`## `. So a literal marker inside a projected paragraph is always content an upstream renderer
flattened, and escaping it cannot suppress a structure the source had.

## What the fix cost, which is the part worth reading

125 lines escaped across 19 of 81 projections — 97 fences, 14 ATX headings, 12 bullets, 2
ordered markers, and zero of the two shapes that never occur. **34,461 characters came out of
code blocks**, a fifth of the corpus's code; `indexes-pdf` went from 81 % of its text inside a
code block to none. Headings 553 → 573 overall.

And then: ours **0.6378 → 0.6018**, grep **0.4865 → 0.5564**, the lead **+0.1513 → +0.0454**.
Two thirds of our reported advantage on this corpus, gone.

The reason is the finding. Net +20 headings hides 48 gained and **28 lost**, and the lost ones
were fabricated. An unescaped marker in flattened prose was mis-pairing with a *real* fence the
projector had written, splitting a genuine code block and letting its contents re-parse as
document structure. `indexes-pdf`'s four "headings" were the sentences *"Optional name for the
index."*, *"Required URL for the index."*, *"On the command line."* and *"Via an environment
variable."* — and a PDF text layer has no headings at all (ADR-0040), so every one was an
artifact of the bug.

Our field-weighted retrieval was leaning on them. The incumbent, which reads no fields, was
not. So the gap we had been reporting on the ingested corpus was partly the measure of a
parsing accident. 4.44 found the same shape from the other side and ADR-0072 named the test: a
change that *narrows* the lead is the direction nobody fits a benchmark in. The dev set moved
the other way over the same change, 0.5505 → 0.5620, which is the second half of that check.

## What the honesty exposed

Making the projection faithful to KIR revealed a second defect underneath. Seven documents now
hold *more* text inside code blocks than before, because the accident had been splitting blocks
that were wrong in the first place: docling reads an admonition and the headings after it as one
code block, and the projector faithfully fences all of it. Ten such blocks across nine
documents. That is upstream of the projector and D-007 puts parser repair out of scope, so it is
filed as 5.24 with the nine named — and with the observation that a code block swallowing a
heading is a structural loss the fidelity report does not currently count.

## Lesson

When a bug is repaired and a benchmark falls, the first question is whether the repair is wrong
and the second is what the benchmark had been measuring. Here the repair was right and the
benchmark had been measuring, in part, the bug — which is only discoverable because the corpus
scores an incumbent beside us on the same documents. A single-arm number would have shown a
regression and told me nothing about its cause.
