# ADR-0100: Declare what a lane cannot carry, per document, and report the split it creates

- **Status:** Accepted
- **Date:** 2026-09-13
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §5
- **Related:** [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md) (the fidelity
  report, and its doctrine on declared policies),
  [ADR-0096](0096-write-the-span-back-and-pin-the-arm-that-judges-it.md) (the HTML repair whose
  result this qualifies), [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md) (adapt
  an engine, never patch it), [ADR-0039](0039-measure-what-projection-costs.md) (the twin whose
  three lanes this splits), [ADR-0040](0040-refuse-the-pdf-layout-pipeline-on-its-merits.md)
  (what the PDF lane already declares);
  [BUG-0016](../bugs/2026/09/BUG-0016-a-docx-note-body-never-reaches-the-kir.md) (the contrast:
  a loss that *is* an opaque node); D-007; roadmap 5.25, 5.29

## Context

Roadmap 5.25 taught the evidence projector to write an inline code span back where the source
named one, and reported that the ingested twin now names commands. Roadmap 5.29 was filed
against the honesty of that sentence: it is an **HTML result presented as a corpus result**,
because the other two lanes lose the naming before the projector can carry it, and nothing
says which documents are which.

Every claim in the item was checked against the artifacts before anything was written.

**The naming is in the DOCX container.** pandoc writes inline code as a `VerbatimChar`
character run: 224 in `dependencies.docx`, 74 in `cache.docx`, 31 in `certificates.docx`.

**And it cannot come out.** `docling_core.types.doc.document.Formatting` carries exactly five
fields — `bold`, `italic`, `script`, `strikethrough`, `underline`. There is no monospace among
them, so the distinction is destroyed inside docling, before this project's adapter is called.

**The split across the twin is large and was invisible:**

| lane | documents | code spans carried | documents carrying one |
|---|---:|---:|---:|
| html | 62 | **1 215** | 46 |
| docx | 10 | **0** | 0 |
| pdf | 9 | **0** | 0 |

D-007 puts patching docling out of scope, and asking upstream is not a change this repository
can land. What is left is to report it — and the fidelity report's own doctrine already says
exactly how.

One more fact, and it is the one that makes this an item rather than an observation: the
adapter's own `_inline_spans` docstring has said since 5.25 that the span *"is reported as
absent from the other two"*. Nothing reported it. The promise was written and never kept, which
is the most ordinary way for a silence to survive four milestones.

## Decision

**A lane declares what it cannot carry, once per document, in the KIR warnings.** ADR-0034
draws the line this sits on: *"A parser's declared policies — pandoc drops thematic breaks,
docling drops running headers, the PDF reader claims no structure at all — are not per-element
counts. They are properties of the parser, recorded once in the KIR document's warnings, and
carried into the report verbatim."* The DOCX lane's blindness to monospace is that kind of
fact, so it is recorded that way: `docling.py` warns on every DOCX it reads, and `pdf.py` adds
a second notice beside the structure one it has carried since ADR-0032.

**The HTML lane declares nothing, and that is the point.** A notice on every lane would say
nothing about which documents lost a naming. The split is the information, and it is only
legible because two lanes speak and one does not.

**It is a policy and never an opaque node.** The contrast is one function away in the same
file: `_account_for_notes` turns a DOCX note body docling never surfaces into an opaque `lost`
node, because the *content* vanished (BUG-0016). Here nothing vanishes — `__token__` arrives
with every character intact, and only the fact that the source called it code is gone. A node
per lost naming would put noise in the projection to make a counter tick and would charge the
loss budget for content that is present, which is precisely what ADR-0034 refuses.

**The two notices are two sentences, because the causes differ.** A PDF has no headings
because the format records none, and no inline code because a text layer is glyphs and
positions — the fact never existed to be lost. A DOCX loses one its own container is still
holding. Collapsing them into a single "this lane is lossy" would hide the more interesting
half.

**And the corpus-level split is stated where the numbers are read** — `eval/README.md`, beside
the twin's description, with the table above. A per-document declaration answers *which
document*; it does not stop someone quoting 1 215 spans as a property of ingestion.

## Alternatives Considered

- **Count the lost namings and report a number per document** — read `VerbatimChar` runs out
  of the container the way `_count_notes` reads `word/footnotes.xml`. Rejected, and this was
  the tempting one: `VerbatimChar` is *pandoc's* style name, and the twin's DOCX files are all
  pandoc-produced, so the count would be exact on this corpus and meaningless on a DOCX from
  Word, which spells the same thing with a different style or a direct `rFonts`. A number that
  is right only for documents we generated is a number fitted to the fixture.
- **Emit an opaque node per lost naming.** Rejected above: it inflates the loss budget with
  content that is present, and ADR-0034 wrote the rule against exactly this.
- **Put the notice in the projected document**, as a `[!missing]` callout. Rejected: it moves
  the chunk text of every DOCX and PDF projection, which would re-carry the judged cases and
  re-bless the baselines for a change that loses nothing — and the evidence documents are read
  by people, who do not need a banner on all nineteen.
- **Say it once in the documentation and not in the parsers.** Rejected as the whole answer,
  kept as half: prose in `eval/README.md` cannot tell a reader which of the 81 documents is
  affected, and it drifts the moment a lane changes. The parser is where the fact lives.
- **Teach the DOCX lane to read the container itself** and recover the runs docling drops.
  Rejected: that is writing a DOCX backend, which is the research D-007 keeps out of this
  project, and it would put our adapter and docling in disagreement about what the document
  says.
- **Ask upstream** — the move 5.29 named second. Not rejected and not a substitute: it is not
  a change this repository can land, and the report is what makes the corpus honest in the
  meantime. Worth doing separately by whoever wants it.

## Consequences

- **Nineteen of the twin's 81 documents now say what they could not carry**, in their fidelity
  reports, and 62 do not. The split that made 5.25's result an HTML result is legible from the
  corpus rather than from a person's memory.
- **Nothing moves.** KIR warnings do not reach the projected text, so the committed evidence
  documents are byte-identical, the carried cases are untouched, both baselines stand, gate G2's
  verdict stays current and G3 still enforces. Verified by regenerating the corpus and reading
  the gates rather than by argument — a report change that moved a number would not be one.
- **The element inventory proves it is a declaration and not a loss.** The gate failed on four
  fixtures — which is the gate working, since it records each parser's declared policies and
  refuses an unreviewed change — and re-blessing produced a diff of *only* the two policy
  lines. No `kinds` count and no `dispositions` bucket moved. Had this been an opaque node,
  both would have.
- **The loss budget is unaffected**, because no element was lost. That is the distinction this
  ADR exists to keep: the budget counts content, and this is about a naming.
- **5.25's claim is now qualified where it was made.** The twin names commands *in the lane
  that can carry a naming*; `eval/README.md` carries the table.
- **Filed rather than absorbed:** roadmap 5.36 — the same question asked of the *other* inline
  constructs, and the answer is not the same shape. docling does expose bold, italic,
  underline, strikethrough and script per run, and this adapter reads none of them — but there
  is nowhere to put them: KIR models no emphasis at all, and `spans` carries code alone
  (roadmap 5.25). So this is a vocabulary question rather than an adapter one, it applies to
  *every* lane including authored Markdown (`**bold**` indexes as `bold` there too), and the
  measurable half is an inconsistency it creates — `~~struck~~` survives as literal characters
  through markdown-it, which has no strikethrough rule, and vanishes as formatting through
  docling, so two renderings of one source disagree.

## References

- Spec: `.draft-specs/02-architecture.md` §5 (the evidence lane and its fidelity claim).
- Decision log: D-007 (adapt engines, never patch them).
- Measured this session: 224 / 74 / 31 `VerbatimChar` runs in three of the corpus's DOCX files;
  `Formatting` fields `bold, italic, script, strikethrough, underline`; 1 215 spans across 46
  of 62 HTML documents, 0 across 19 DOCX and PDF.
- Re-runnable: `python tools/build_ingested_corpus.py`, then read any DOCX projection's
  fidelity report.
- [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md) §declared policies,
  [ADR-0096](0096-write-the-span-back-and-pin-the-arm-that-judges-it.md).
