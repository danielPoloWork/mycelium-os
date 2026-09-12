# 2026-09-12 — the invariant it did not ask of itself (roadmap 5.28)

- **Session scope:** roadmap 5.28 — projected prose was eating the underscores of
  `__token__`; repair it in the projector, measured over the corpora rather than listed.
- **PR:** #126 (`fix/escape-the-emphasis-the-source-did-not-author`). Follows #125, merged as
  `fc6e7e7`.
- **Milestone 5:** 5.28 done. 5.35 filed.
- **ADR:** [ADR-0099](../../../adr/0099-ask-the-compiler-whether-the-prose-survived.md).

## The tool for the job was already in the file

The item proposed a shape: *the projector escaping inline emphasis runs in text that came from
a source*. Before writing that I went looking for how to measure it, and the measurement was
already built. ADR-0096 had added `_reads_back` at 5.25 to decide whether a code span may be
written — parse the candidate with the reader the build actually uses, keep the span only if
the compiler extracts the same words — and it was applied to spans and to nothing else. The
prose those spans sit in was never asked.

So the first version of the measurement was wrong in an instructive way. I compared
`_extracted(emitted)` against `_extracted(plain)`, which is what `_spans_that_read_back` does,
and got six failures — all of them the ADR-0093 line escape *working*, changing a parse that
was wrong to begin with. The baseline was the bug. Comparing against the **literal source
characters** instead is the question that matters, because that is what the projector was
handed and what it owes back:

```
blocks rendered: 2699
blocks that do not read back: 42 in 15 documents
```

## Emphasis was half of it

The item named `__token__`, and the corpus has it — `cli.html`, where a service uses *a
`__token__` or arbitrary username*, indexed as `token`. It also has `__init__.py` indexed as
`init.py` in `build-backend`, which is worse: that is a Python filename the document is
naming, and the corpus lost the ability to answer a query about it.

The other half was not in the item. A PDF's text layer shows `[preview](../preview.md)`
literally, because the upstream rendering flattened a link into characters; the compiler reads
those characters as a link again and the target drops out of the indexed text. Same defect,
different construct, and a shape list built from the item's sentence would have missed it.

That is the argument for not writing a list. ADR-0093 chose block shapes and could defend each
one, because a block shape is recognisable at the start of a line. Whether `_` opens emphasis
depends on what follows it, what precedes it, and what else is in the paragraph. The compiler
knows; the projector should ask rather than predict. Nobody predicted `__init__.py`.

## Escape the gaps, not the placements

`_apply` already walks the stretches between the references and code spans the projector
deliberately wrote. Those renderings are syntax this module means. The gaps are still the
source's own characters, and only they are escaped — so a rendered link keeps its brackets
while the prose around it stops pretending to be one. Without that seam the repair would have
destroyed ADR-0090's work on the way past.

The check runs twice: render, ask, and if the answer is no, render again escaped and ask
again. 2 657 blocks of 2 699 answer yes the first time and pay nothing — not one backslash,
and the evidence document stays as readable as the source. 34 are repaired.

One wrinkle worth recording. The first implementation checked before `neutralise` ran, so it
counted 13 blocks unreadable that the line escape was about to fix. `_with_references` now
takes what will be done to its result and applies it inside the comparison. A read-back check
has to be asked of the *final* form or it is asking about something nobody will read.

## What it cost, and who it helped

Our own arm does not move. Every slice and every case on `uv-ingested/release` is identical to
six decimal places: 0.618671 before, 0.618671 after. The incumbent gains — grep 0.574590 →
0.575367, its `fact` slice on one case — so the reported lead **narrows**, +0.0441 → +0.0433.

Restoring words the corpus was losing turns out to help the term-matching baseline and do
nothing for a retriever with a stem index, which already reached `token` from what was left of
`__token__`. That is the honest direction, and it is the third time this repo has found a
repair pointing that way.

The carry says the same thing from the other side. Three anchors' coverage rose to exactly
**1.0000** — `cli.html` from 0.988, `python-versions` from 0.9821, `scripts.pdf` from 0.9697 —
because the words the coverage metric was missing are the words the compiler was eating.

## Two procedural things worth remembering

G3 disarmed itself on the corpus change before the bless — *"not comparable, reported, not
enforced"* — and I read it before re-blessing, which is the order that makes the gate mean
anything.

Gate G2's verdict is re-recorded in the same PR, because a corpus is a ranking input
(ADR-0068). The check that it was only the corpus: retrieval identity unchanged, decision still
`lexical`, every verdict unchanged, and `uv/dev` and `uv/release` byte-identical on both arms.
`uv-ingested` moves, which is the point; `ours/*` drifts down slightly on the lexical arm
because this PR adds a document to the corpus this repository is — reported, never gated.

And a re-bless is **two runs**. `write_baseline` writes `data[manifest.retriever]`, so
`--bless --against grep` refreshes the product's block and leaves the incumbent's untouched. I
blessed once, noticed the grep numbers had not moved when a fresh run said they should, spent a
while suspecting the harness, and found it in the history: the grep block changes only when
someone blesses with `--retriever grep`. Not a defect — a procedure I half-performed.

## Found on the way

Eight blocks in four documents still do not read back, and they are a different defect (5.35):
leading whitespace. A text layer renders a directory tree under one leading space and
CommonMark strips it. No backslash reaches that — the escape is defined only before ASCII
punctuation — and every candidate repair substitutes different characters, which is the
text-moving this lane refuses. ADR-0093 called the four-space case "a gap rather than a
decision" and measured it empty; it is not empty now.

## Lesson

The invariant a module enforces on one of its outputs is usually true of all of them, and the
gap between the two is where defects live for milestones. `_reads_back` was built at 5.25,
applied to code spans, and the prose around those spans went unchecked for three items — while
the same module's own docstring said the block's text must not move. Before writing a new rule,
look for the rule the file already has and ask what it is not being asked about.
