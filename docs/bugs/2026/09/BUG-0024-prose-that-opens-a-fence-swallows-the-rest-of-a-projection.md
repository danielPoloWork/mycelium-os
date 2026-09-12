---
id: BUG-0024
title: a paragraph that begins with a fence marker opens a code block in the compiler and swallows the rest of the projected document
status: confirmed
severity: medium
reporter: internal
discovered: 2026-09-12
affected-versions: "0.4.0 (introduced by PR #53, roadmap 4.3)"
---

# BUG-0024: a paragraph that begins with a fence marker opens a code block in the compiler and swallows the rest of the projected document

## Summary

The evidence projector writes a paragraph's text verbatim. When a source's code block has
been flattened into prose upstream — a DOCX in which pandoc's smart quotes turned
```` ```toml title="pyproject.toml" ```` into ```` ```toml title=“pyproject.toml” ```` followed by
the code as ordinary text, or a PDF text layer that kept the backticks as characters — the
projected paragraph *begins with a fence marker*. The compiler reads that line as a fence
opener, finds no closing fence on a line of its own, and treats everything to the end of the
document as one code block: headings, prose, links, all of it.

Four of the 81 vendored ingested projections are affected, measured on 2026-09-12:

| projection | code block spans lines | headings swallowed |
|---|---:|---:|
| `config-pdf-4803c1e3.md` | 52–440 | 3 |
| `scripts-pdf-5dcfc70b.md` | 26–200 | 3 |
| `run-pdf-1537d99d.md` | 34–65 | 1 |
| `dependencies-docx-d90e9be4.md` | 741–768 | 1 |

`config-pdf` loses the structure of nearly its whole body: one chunk of kind `code` where
there should be sections, no anchors for the headings inside it, and BM25 field weights that
never see a heading term.

## Environment

- **Affected versions:** since PR #53 (roadmap 4.3), which introduced the projector. Present
  in v0.4.0.
- **Configuration:** any source whose upstream rendering flattened a fenced code block into
  prose that keeps the backticks — observed with DOCX via docling and with PDF text layers.

## Reproduction

```python
from pathlib import Path
from mycelium.markdown import parse_markdown
from mycelium.sdk.types import NodeKind

text = Path("eval/corpora/uv-docs-ingested/knowledge/evidence/config-pdf-4803c1e3.md").read_text("utf-8")
kir = parse_markdown(text, doc_id="01ARZ3NDEKTSV4RRFFQ69G5FAV").kir
print([(n.src.lines, n.text.count("\n## ")) for n in kir.nodes if n.kind is NodeKind.CODE_BLOCK and "\n## " in (n.text or "")])
# [((52, 440), 3)]
```

## Root cause

Two facts meet. The projector renders a paragraph as its text (ADR-0034: verbatim text,
regenerated syntax) and does not consider what the compiler will make of a line that
*starts* with block syntax. And CommonMark's fence opener needs no closing partner to be an
opener: an unmatched ```` ``` ```` at the start of a line runs to the end of the document.

The chats module's projector met the same class of problem at roadmap 5.5 and escapes the two
line shapes that open block structure inside its callouts — an ATX heading, a setext
underline (ADR-0077, threat model B15). The evidence projector has no such rule for any shape:
a paragraph beginning with ```` ``` ````, `~~~`, `# `, `- `, `> ` or `---` is projected as it
is and compiled as structure.

## Impact

Fidelity, not trust: the text survives (the no-content-loss invariant holds — it is all inside
the code block), but the *structure* does not, and structure is what anchors, headings and
field-weighted retrieval are made of. Found by roadmap 5.18, whose rendered links inside the
swallowed region of `dependencies-docx` were the one place in 81 documents where the chunk text
moved — link syntax that the compiler should have flattened to its label and could not, because
the region is code to it.

## Fix

Not fixed here. The repair is ADR-0077's rule applied to the evidence projector — escape the
line shapes that open block structure at the start of a projected paragraph, so the characters
survive as text and never as syntax — and it is its own change: it moves the chunk boundaries of
the four documents above, so the ingested corpus's carried case set and G3 baseline move with
it. Filed as roadmap 5.22.

## Verification

Pending the fix: the reproduction above must report no code block containing a heading in any
of the 81 projections, and `tools/build_ingested_cases.py --check` must reproduce the carried
set after the re-carry.

## Lesson

A verbatim projection is faithful to the source's *characters* and, without a rule for the
shapes that open structure, unfaithful to its *structure* wherever the two disagree. The chats
projector learned this at 5.5 for its own two shapes; the evidence projector, four items older,
never asked the question — and nothing measured the structure a projection lost, only the text.
