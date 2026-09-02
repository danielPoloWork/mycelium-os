# 2026-09-02 — a report cannot corroborate itself (roadmap 4.7)

- **Session scope:** roadmap 4.7 — the ingestion fixture corpus with element inventories,
  which is the M4 exit gate's first clause (spec 06 Phase 2).
- **PR:** #57 (`test/ingest-fixture-inventories`). Follows #56 (4.6), merged as `570c6fb`.
- **Milestone 4:** 4.1–4.7 done; 4.8, 4.9 open, plus 4.10 filed here.

## The item was one sentence and the problem was one sentence

"Ingestion fixture corpus with element inventories." The exit gate it serves is *zero
silent element loss*, and 4.3 had already built the accounting for it — the fidelity report
sorts every KIR node into represented, degraded or lost. So the obvious reading of 4.7 was
"add more fixtures and check the report on them".

That reading is wrong, and the reason is worth writing down: **the report is computed from
the KIR, so it can only account for what became a node.** A parser that drops a table before
emitting anything produces a report saying 100 % represented. Every check ingestion had —
the report, the projection round-trip, the loss budget, each parser's own tests — is
computed from the parse. A parse that lost an element and a source that never had one are
indistinguishable to all of them.

The missing half is not another measurement. It is a **declaration**: a statement, written
by a person against a source they can read, of what that source contains. Then the gate is a
comparison, and a difference is either approved with a reason or it is a defect.

## It found something on the first run

Within minutes of the first comparison, the DOCX route came back one code block short, one
blockquote short, and with the footnote's body **nowhere**. Two of those turned out to be
pandoc's writer flattening structure into styles — real, explainable, and now recorded as
deviations with their reasons.

The third was not. Word keeps footnote bodies in `word/footnotes.xml`, a package part
docling's DOCX backend never opens. The sentence was in the file; it was in no node; and
every artifact downstream agreed the document was complete. That is
[BUG-0016](../../../bugs/2026/09/BUG-0016-docx-footnotes-vanish-unreported.md), and it was
reachable through the existing suite the whole time — no number anywhere was wrong, because
nothing was asking the question.

I fixed it rather than recording it as an approved deviation. Recording it would have been
defensible on scope grounds and wrong on every other: an approved deviation *says the
difference is acceptable*, and the corpus's first act would have been to bless the thing it
was built to catch. The engine's blind spot is not ours to fix; making it visible is, so the
adapter counts the notes the container declares and records each one docling did not
surface as an opaque `lost` element — the same treatment a PDF page with no text layer
already got.

The count is taken with a regular expression rather than an XML parse, because that part is
untrusted input and `xml.etree` expands internal entities — the shape `hostile/laughs.docx`
exists for. And the first pattern I wrote reported *three* footnotes for a document with
none: `<w:footnoteRef/>` and the `separator` furniture both matched. That mistake is now a
test.

## The design decision worth keeping

The inventory file is half human and half machine, and the re-bless tool may only write its
own half. Without that rule the tool would let a regression bless itself: the parser drops a
table, the tool records that it drops a table, the gate agrees with the defect. It is the
same asymmetry the G6 golden has — a tool that regenerates the observation, never the claim
— and it is the only thing that makes a re-bless button safe to have.

The three checks fail for three different reasons, and the third one surprised me by being
worth writing: a **stale** deviation, still recording a reason for a kind that now agrees,
fails too. An approval left standing over behaviour that has changed is how an exception
list quietly eats a gate.

## The by-product turned out to be the documentation

Twenty-one deviations are recorded across five families, and each is a true sentence about a
format that previously had to be rediscovered by hand: pandoc's DOCX writer flattens a
definition list into styled paragraphs; its HTML writer renders a footnote as a trailing
`<ol>` with a reference anchor and a back-link; docling emits an image's alternative text as
a paragraph of its own; docling joins a run of consecutive `SourceCode` paragraphs into one
code item. None of that was written down anywhere. It is now, next to the numbers that
prove it.

One fixture-generation trap is worth the warning: the generator no longer passes
`--sandbox` to pandoc. The sandbox is right for the *parser*, which reads untrusted bytes at
build time; in the generator it stopped pandoc opening the image it was supposed to embed,
and the corpus would have recorded a generator restriction as a parser difference. A fixture
must never make a tool look worse than it is.

## What is left of the milestone's exit gate

Three clauses, and only two had owners. Zero silent element loss is this item; the
hostile-file suite was 4.2. **An ingestion-heavy corpus joining the eval set** had nobody,
so it is filed as 4.10 rather than quietly absorbed here — it needs judged cases, which is a
different kind of work, and ADR-0027's warning about judging a corpus we produced ourselves
applies to it with full force.
