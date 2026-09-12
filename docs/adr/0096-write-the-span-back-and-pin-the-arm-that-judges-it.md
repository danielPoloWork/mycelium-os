# ADR-0096: Write the code span back where the source named it, and pin the arm that judges the leg

- **Status:** Accepted
- **Date:** 2026-09-12
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §5, spec 04 §3
- **Related:** [ADR-0090](0090-project-a-sources-links-as-links-now-that-the-compiler-knows-who-asserted-them.md)
  (the reference write-back this copies), [ADR-0094](0094-mint-a-command-the-corpus-demonstrates-and-names-and-report-what-promotion-can-and-cannot-reorder.md)
  (`KirNode.spans`, and why a naming is what mints a command),
  [ADR-0080](0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md) (the leg's bar — amended here),
  [ADR-0070](0070-take-the-leaf-heading-weight-on-the-third-asking.md) (a default needs a held-out gain),
  [ADR-0093](0093-escape-the-prose-that-would-open-a-block-and-report-what-that-costs.md)
  (the projector's other syntax rule), [ADR-0095](0095-read-the-corpus-in-the-dialect-it-is-written-in.md)
  (the corpus this measures on), [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md)
  (adapt an engine, never patch it), [ADR-0079](0079-resolve-an-ingested-documents-links-through-its-source-tree-and-never-call-them-authored.md)
  (why a projected reference is safe); D-007, D-010; roadmap 5.23, 5.25, 5.28, 5.29

## Context

Roadmap 5.25 was filed at 5.23 with a measurement and a plan: the ingested twin mints 12
commands against its Markdown original's 69, because a command is minted only where the corpus
*names* it as code (ADR-0094) and the evidence projector emits flattened text. The plan was one
sentence — *"KIR now holds them (`KirNode.spans`, ADR-0094), so the projector can write a span
back as a span the way ADR-0090 wrote a link back as a link"*.

**The premise was false for this corpus.** `KirNode.spans` is populated by the markdown-it
adapter and the pandoc adapter. The twin is parsed by **docling** (72 documents) and the PDF
text-layer reader (9). Both emit zero spans, so there was nothing for the projector to write
back and the item could not be done by touching the projector at all.

What docling *does* carry, measured rather than assumed: an HTML `<code>` inside a paragraph
arrives as a `code`-labelled `CodeItem` **inside an `InlineGroup`**, and our adapter's inline
group branch joined the runs' text and discarded which of them were code. The naming was
reaching the adapter and being dropped there. The other two lanes lose it earlier and for
different reasons, and both were checked before being written down:

| lane | what carries the naming | what arrives |
|---|---|---|
| HTML | `<code>` in a `<p>` | a `code` run in an inline group — **recoverable** |
| DOCX | pandoc's `VerbatimChar` character style, 224 runs in the corpus's largest DOCX | docling's `formatting` exposes bold, italic, underline, strikethrough, script — **no monospace** |
| PDF | nothing | a text layer has no inline structure |

## Decision

**The docling adapter records an inline group's `code` runs as `KirNode.spans`.** The
discriminator is the label *and the position*: a block code fence is a `CodeItem` whose parent
is the section, an inline span is one whose parent is the inline group. Nothing else in
docling separates them — same label, same `code_language`, same `content_layer`, no
provenance — which is measured and which is why the check below exists.

**The projector writes a span back the way it writes a reference back** (ADR-0090): the span's
text is *found* in the block from a cursor that advances with each placement, because KIR's
locator is line-grained, and it is wrapped in a CommonMark code span whose fence is one
backtick longer than the longest run inside.

**A span that overlaps a reference is dropped in the reference's favour.** Both nestings are
legal Markdown and which one the source meant is not recoverable from flattened text; a link
carries an edge into the graph (ADR-0079) and a span carries emphasis. 66 spans in the corpus
sit inside a link label, and they lose.

**The invariant is enforced, not argued.** ADR-0090 and ADR-0093 both rest on *the block's
text does not move*, and both could keep it by inspection: a link label and a backslash escape
are inert to the reader that matters. A code span is not — it makes its content literal. So
the projector asks the compiler: it parses the block before and after, compares the text of the
block nodes, and keeps only the spans that read back identically. Six spans fail, and they are
the two shapes worth naming — a `<pre><code>` block docling nested inline (one of which holds a
Markdown link whose target would have entered the indexed text), and `__token__`, whose
underscores projected prose was reading as emphasis.

**Only HTML is repaired; DOCX and PDF are reported.** Recovering a DOCX naming would mean
inferring one from a heuristic — a token that looks like a flag, a word with a dot in it — and
that is the plausible-looking wrong answer this project refuses elsewhere. D-007 puts
repairing docling out of scope. Filed as roadmap 5.29 with the measurement above.

**The symbol leg's default flips on, because its own ablation now earns it.** That is not a
second decision made here; it is the rule ADR-0080 wrote and
`tools/measure_symbol_leg.py --check` enforces — *the default follows the ablation*. With the
namings carried, the leg fires on all four of the twin's judged `symbol` cases where it could
fire on **none**, and `uv-ingested/release` — a held-out set — gains **+5.6 % on the slice and
+0.9 % overall** with no set regressing, which is ADR-0070's criterion.

**And an ablation's control arm is pinned off, never inherited from the shipped product.**
Flipping the flag made `--check` report *"does not earn the default on any set"*, because
`MyceliumRetriever` runs `RetrievalConfig()` — the shipped config — so the control arm
acquired the leg under test. The guard could accept only one of the two answers it exists to
choose between. A `lexical` retriever now pins `symbol_lookup` and `graph_expansion` off and is
the control for both ablations. While every leg ships off it is byte-identical to `mycelium`,
which is why the defect stayed latent through roadmap 5.3, 5.9 and 5.23, and why no historical
ablation number moves.

## Alternatives Considered

- **A length bound on what counts as an inline span.** Built and measured against ground truth
  from the HTML itself: inline `<code>` in this corpus runs 1–55 characters with **no**
  newlines, while `<pre><code>` has a median of 95 and 62 % hold one. The populations do
  separate, so a bound would work — and it would be a constant fitted to this corpus, guarding
  a property (*the text does not move*) that can be tested exactly instead. Rejected for the
  round-trip check, which needs no number and catches `__token__` too, which no length bound
  would.
- **Re-parse the HTML in the adapter to recover the `<pre>` distinction.** Rejected: it is
  writing a second parser beside the one we adopted, which is exactly D-007.
- **Infer DOCX namings from shape.** Rejected above.
- **Carry the span and let the text move.** It would have "fixed" `__token__` — genuinely a
  repair, since projected prose was eating the underscores — at the cost of moving chunk text
  inside a change whose whole argument is that it does not. Filed as roadmap 5.28, where it can
  re-bless the baselines it moves.
- **Keep the leg off and file the flip.** Rejected because it is not available: with the
  namings carried, `--check` fails until the flag follows the measurement, and a PR cannot ship
  its own gate red. Arguing the bar away instead — "one set, one case" — is the fitting this
  project has refused in the other direction fourteen times; the caveat belongs in the record,
  not in the threshold.
- **Fix only the symbol ablation's control arm.** Rejected: the graph ablation has the same
  construction and the same latent defect. Pinning both costs one line each and is inert today.

## Consequences

- **The twin names what it demonstrates.** Commands minted: **11 → 59**, against the Markdown
  original's 69. Total symbols 32 → 80. `uv python pin` — the command roadmap 5.25 named,
  because `u-1019` could not be answered without it — is among them, with a definition site the
  judge marks relevant at lexical rank 1.
- **1 217 of 1 289 spans are written back**, across 46 of the 62 HTML documents. The 72 that are
  not: 66 inside a link label, 6 refused by the round-trip check.
- **Nothing moved that was not meant to.** Across the 46 changed projections: **0 chunks changed
  text, 0 documents changed anchors**, every judged anchor re-carried identically (62 mapped,
  the same 3 known drops), and gate G3 reports *"same corpus, same boundaries, same judgements"*.
  The corpus repair on its own moves the shipped retrieval by exactly **zero**, which is what
  makes the flip below separately attributable.
- **The shipped default changes, and this is the first optional leg ever to earn one.** Release
  sets, both retrievers re-blessed, G2 re-recorded. The gain is narrow and the record says so:
  `ours/*` and `uv/release` are byte-identical with the leg on, and the held-out gain is one
  set and one case (`u-1025` 0.5000 → 0.6309). What the leg demonstrably does is compensate for
  what ingestion costs — which is a real benefit, and a smaller claim than "the leg is good".
- **A latent defect in two guards is closed** before the second one could hit it. The lesson is
  general: an ablation arm that inherits a default cannot judge that default.
- **The `Projection` record gains `spans` and `spans_dropped`**, so a drop is counted rather
  than silent — the rule ADR-0090 set for references, applied to the syntax that joined them.
- **The projector now imports the Markdown reader.** That is a real coupling and it is the
  point: the claim *"the compiler reads this back unchanged"* is checked by the compiler's own
  reader rather than by a rule about Markdown. The direction is one `mycelium.ingest` already
  depends on.

## References

- Spec: `.draft-specs/02-architecture.md` §5 (the evidence lane), `.draft-specs/03-data-model.md`
  §4 (KIR), `.draft-specs/04-retrieval-and-evaluation.md` §§2–3 (the symbol leg and its routing).
- Decision log: D-007 (adapt engines, never patch them), D-010 (fix the product, not the
  benchmark).
- Re-runnable: `python tools/build_ingested_corpus.py` then `--check`;
  `python tools/build_ingested_cases.py --check`;
  `python tools/measure_symbol_leg.py --coverage eval/corpora/uv-docs-ingested`;
  `python tools/measure_symbol_leg.py --check`.
- Tests: `tests/test_projection.py`, `tests/test_ingest_parsers.py`, `tests/test_eval.py`.
