# ADR-0093: Escape the prose that would open a block, and report what that costs

- **Status:** Accepted
- **Date:** 2026-09-12
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §5
- **Related:** [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md) (the projector,
  and its verbatim-text rule), [ADR-0077](0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-what-it-could-not-reach.md)
  (the chats projector's escape, which this generalises),
  [ADR-0090](0090-project-a-sources-links-as-links-now-that-the-compiler-knows-who-asserted-them.md)
  (the last thing the projector learned to render, and the item that found this),
  [ADR-0039](0039-measure-what-projection-costs.md) (the twin corpus, and what it is *for*),
  [ADR-0040](0040-refuse-the-pdf-layout-pipeline-on-its-merits.md) (why a PDF projection has
  almost no headings), [ADR-0072](0072-keep-our-own-restatements-out-of-our-own-benchmark.md)
  (a lead that narrows is the direction that says nobody fitted it);
  [BUG-0024](../bugs/2026/09/BUG-0024-prose-that-opens-a-fence-swallows-the-rest-of-a-projection.md);
  spec 02 §5, spec 03 §3.1; D-007, D-010, D-017; threat model B11; roadmap 5.18, 5.22, 5.24

## Context

The evidence projector writes a paragraph's text verbatim and does not ask what the compiler
will make of a line that *starts* with block syntax. When a source's upstream rendering has
flattened a fenced code block into prose — a DOCX whose smart quotes broke
```` ```toml title="pyproject.toml" ````, a PDF text layer that kept the backticks as
characters — the projected paragraph begins with a fence marker. CommonMark needs no closing
partner for an opener, so everything to the end of the document becomes one code block:
headings, prose, links (BUG-0024).

The chats projector met this class at roadmap 5.5 and escapes the two shapes that open block
structure inside its callouts (ADR-0077). The evidence projector, four items older, never
asked the question.

Three things were measured before choosing a rule.

**The escape is free.** Every shape that can open a block round-trips: CommonMark reads
`\##` as a literal `##`, so the indexed text keeps the original characters and only the
block-level meaning is gone. Counted across the corpus after the change, backslashes in node
text are **137 before and 137 after** — not one leaked into what BM25 reads. The one exception
is an indented line: four leading spaces are a code block whatever precedes them, and no
backslash reaches it. It occurs nowhere in the three corpora, and is recorded as a gap rather
than papered over.

**A literal block marker in projected prose is never a real structure.** A heading in a DOCX
is a heading *style*; in a PDF it is larger type; in HTML it is an `<h2>`. None of them reaches
KIR as the characters `## `. So a `## ` inside a projected *paragraph* is always content that
an upstream renderer flattened, and escaping it cannot suppress a structure the source had.

**Every shape interrupts a paragraph mid-block, not only at its start.** The item proposed a
rule for a paragraph's first line; measured, each shape breaks a paragraph from any line, and
`dependencies-docx` — one of the four — carries its marker in the middle. A first-line rule
would have left it exactly as broken.

## Decision

**Escape the line shapes that open block structure, on every line of a projected paragraph.**
A backslash before a fence (`` ``` ``, `~~~`), an ATX heading, a bullet, a quote marker, a
thematic break or a setext underline; an ordered marker is escaped on its *punctuation*
(`1\. `), because a backslash is only an escape before ASCII punctuation and `\1.` would leave
a literal backslash in the text. Left alone deliberately: an inline tag (`#tag`, no space —
its `#` is already in the text and the projector has always carried it), raw HTML (the Profile
disables it, so `<div>` is already prose), and an indented line.

**The shape list is the measured one, and the narrower variant was measured and refused.**
Escaping only the fence — the shape BUG-0024 was reported for, and the only one whose damage
is unbounded — fixes the four named documents too. It was built and scored:

| variant | ours | grep | lead |
|---|---:|---:|---:|
| before (the defect) | 0.6378 | 0.4865 | **+0.1513** |
| fence only | 0.5980 | 0.5310 | **+0.0670** |
| every shape (shipped) | 0.6018 | 0.5564 | **+0.0454** |

**Fence-only leaves us a larger apparent lead, and that is exactly why it is not the reason to
choose it.** Picking the shape list by which number flatters the product is fitting the
benchmark, which D-010 forbids in the direction it is usually tempting. The list is chosen on
the argument above — a literal marker in projected prose is never a real structure — and the
consequence is reported rather than optimised. The two variants differ by 0.004 on our own
arm; the visible difference is grep's, and grep is not the thing being tuned.

**What the repair costs is stated, not buried.** On the vendored ingested corpus:

- 125 lines escaped across 19 of 81 projections — 97 fences, 14 ATX headings, 12 bullets,
  2 ordered markers, 0 quote markers, 0 rules;
- **34,461 fewer characters trapped inside code blocks** (160,125 → 125,664, −21 %), code
  blocks 755 → 679, paragraphs 1,799 → 1,864;
- headings 553 → **573** overall: 48 gained in four documents, 28 lost in eight;
- `indexes-pdf` goes from **81 % of its text inside a code block to 0 %**;
- the release set: ours 0.6378 → **0.6018**, grep 0.4865 → **0.5564**, the lead **+0.1513 →
  +0.0454**. The dev set moves the other way, 0.5505 → **0.5620**.

**The 28 lost headings were fabricated, and that is the finding.** They existed because an
unescaped marker in prose mis-paired with a *real* fence the projector wrote, splitting a
genuine code block and letting its contents re-parse as document structure. `indexes-pdf`'s
four were the sentences *"Optional name for the index."*, *"Required URL for the index."*,
*"On the command line."* and *"Via an environment variable."* — a PDF text layer has no
headings at all (ADR-0040), so every one of them was an artifact. Our lead on this corpus was
resting on them. A change that removes fabricated structure and narrows the reported lead by
two thirds is the shape ADR-0072 described from the other side: nobody fits a benchmark in
that direction.

**The ingested baseline is re-blessed on both arms, and the carried set re-carried.** Three
judged anchors move, all of them off a fabricated heading and onto the section that now
contains the text; the carry still maps 62 anchors and drops the same 3 it dropped before.
`build_ingested_corpus.py --check` and `build_ingested_cases.py --check` both reproduce.

## Alternatives Considered

- **Escape only the fence.** Measured above. Rejected: it fixes the reported bug and leaves 28
  lines still fabricating structure, and the only argument for it is the number it produces.
- **Escape only a paragraph's first line**, as roadmap 5.22 proposed. Rejected on the
  measurement: every shape interrupts a paragraph from any line, and one of the four named
  documents carries its marker mid-paragraph.
- **Strip the marker instead of escaping it.** Rejected outright: it edits the source's text,
  which is the one thing spec 02 §5's *verbatim* forbids. The escape is invisible to the index;
  a deletion would not be.
- **Fix it in the parsers** — teach docling and PDFium not to flatten a fenced block. Rejected:
  parsing research is not this project's (D-007), and the projector must be safe against *any*
  engine's output, including one written by a third party tomorrow.
- **Re-judge the cases that moved**, so the release numbers hold. Rejected as the re-fit D-010
  forbids, and refused mechanically anyway: `check_frozen_release_sets.py` will not take a
  judgement change in a change that moves the corpus.
- **Keep the fabricated headings by leaving the bug in place**, on the grounds that they help
  retrieval. Rejected: a corpus whose structure comes from a parsing accident cannot measure
  what projection costs, which is the twin corpus's entire purpose (ADR-0039).

## Consequences

- **BUG-0024 is fixed.** The four projections it named recover their structure, and the
  reproduction it records reports no code block containing a heading in any of them.
- **The projection is now faithful to KIR, and that exposes a second defect.** Seven documents
  hold *more* text inside code blocks than before, because an unescaped marker used to split a
  code block the upstream engine had wrongly created — an admonition and the headings after it,
  read as one block by docling. That is an ingestion-fidelity question rather than a projector
  one, and it is filed as **roadmap 5.24** with the ten documents that show it.
- **Threat model B11 is unchanged but better served.** The boundary's rule is that the projector
  emits *text, never assertions*; a heading is an assertion about the document's structure, and
  an ingested source no longer gets to make one by accident.
- **The README's comparison table moves**, because it quotes the ingested row.
- **No authored corpus moves.** `uv-docs` and this repository are untouched — the projector runs
  only on ingested sources — so gate G3 on those sets, gate G2's verdict and every baseline
  outside the ingested corpus are byte-identical.

## References

- Spec: `.draft-specs/02-architecture.md` §5 (the evidence lane, verbatim projection);
  `.draft-specs/03-data-model.md` §3.1 (the Profile).
- Re-runnable: `python tools/build_ingested_corpus.py --check`,
  `python tools/build_ingested_cases.py --check`, then
  `mycelium eval eval/corpora/uv-docs-ingested --set eval/release.jsonl --against grep`.
- Tests: `tests/test_ingest_projection.py` — each shape escaped, each shape's text surviving
  the round-trip, each shape shown to open a block when it is *not* escaped, the shapes left
  alone, BUG-0024 as a test, and a real code block still rendering as one.
