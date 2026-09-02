---
id: BUG-0016
title: a DOCX footnote's body vanishes, and the fidelity report calls the document complete
status: fixed
severity: medium
reporter: internal
discovered: 2026-09-02
affected-versions: "0.3.0 (introduced by PR #51, roadmap 4.1)"
fixed-in: "0.4.0"
---

# BUG-0016: a DOCX footnote's body vanishes, and the fidelity report calls the document complete

## Summary

Word keeps footnote and endnote bodies in `word/footnotes.xml`, a package part docling's
DOCX backend does not read. A DOCX whose footnote says something arrives with that sentence
nowhere in the KIR — and because the fidelity report is computed *from* the KIR, the
document is reported as 100 % represented, 0 lost.

That is silent element loss, which is the one thing ingestion promises not to do
(spec 02 §5, ADR-0034) and the M4 exit gate's own words.

## Environment

- **Affected versions:** since PR #51 (roadmap 4.1), which introduced the docling adapter.
  Present in v0.3.0.
- **Configuration:** any configuration whose `[ingest] parsers` reaches `docling` for a
  DOCX. The `pandoc` route is unaffected — pandoc reads the notes part.

## Reproduction

`tests/fixtures/ingest/corpus/elements.docx` carries one footnote whose body reads
"Footnotes belong to pandoc's Markdown, not to CommonMark."

```text
kinds:        {"code_block": 1, "heading": 6, "image": 1, "list": 2, "list_item": 4, "paragraph": 6}
dispositions: {"represented": 19, "degraded": 0, "lost": 0}
```

The string is in `word/footnotes.xml`; it is in no KIR node.

## Expected vs. actual

- **Expected:** an element the pipeline cannot represent is *accounted for* — as an opaque
  node, degraded or lost — so the fidelity report counts it and the loss budget can act on
  it (ADR-0034).
- **Actual:** the element left no trace at all, and every downstream artifact agreed the
  document was complete.

## Root cause

Two things had to be true at once, and both were.

The adapter maps `DoclingDocument` items to KIR nodes and can only see what docling emits;
docling's DOCX backend walks `word/document.xml` and never opens the notes parts, so there
was no item to map. And the fidelity report — correctly, by design — is a pure function of
the KIR, so it cannot distinguish "this document has no footnotes" from "this document's
footnotes never arrived".

It went unnoticed because nothing checked a parse against a *declaration* of what the
source contains. Every existing check was computed from the parse itself, and a witness
cannot corroborate itself. The ingestion fixture corpus (roadmap 4.7) added the missing
half, and this was the first thing it found.

## Impact

Medium. Content leaves an ingested document with no warning, no opaque node, and no entry
in the report — so a citation into that document is silently incomplete and the loss budget
that exists to catch exactly this never fires. It is bounded by being one container part:
body text, tables, lists and code are unaffected.

## Fix / workaround

The engine's blind spot is not ours to fix; making it *visible* is. After the walk, the
docling adapter counts the foot- and endnotes the DOCX container declares — content notes
only, told from the `separator` furniture by their lack of a `w:type` attribute — and
records each one docling did not surface as an opaque `lost` node. The loss is then counted
by the fidelity report, charged to `[ingest] max_failed_elements`, and named in the
projection, which is the same treatment a PDF page with no text layer already got.

The count is taken with a regular expression over the part rather than an XML parse, because
the part is untrusted input and `xml.etree` expands internal entities — the billion-laughs
shape `hostile/laughs.docx` exists for (ADR-0033). Counting opening tags needs no parser, so
none is exposed.

Workaround before the fix: pin `parsers = ["pandoc", ...]` ahead of `docling` for DOCX;
pandoc reads the notes part and emits a real footnote.

## References

- Fixing PR: #57 (roadmap 4.7)
- Introduced by: #51 (roadmap 4.1)
- Related: [ADR-0032](../../../adr/0032-adapt-four-engines-and-pin-which-one-runs.md),
  [ADR-0034](../../../adr/0034-project-the-evidence-and-count-what-it-lost.md),
  [ADR-0038](../../../adr/0038-declare-the-corpus-then-compare-it.md)
