# ADR-0034: Project the evidence, and count what it lost

- **Status:** Accepted
- **Date:** 2026-09-01
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.3; RFC-0001; spec 02 §5; spec 03 §§3-4; spec 05 §§1-2; D-004,
  D-020, D-021; [ADR-0006](0006-adopt-markdown-it-adapter-and-kir-node-fields.md),
  [ADR-0007](0007-adopt-structure-first-chunking.md),
  [ADR-0014](0014-adopt-partial-strict-configuration.md),
  [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md),
  [ADR-0033](0033-keep-the-original-and-bound-the-hostile.md)

## Context

4.1 gave ingestion its contracts and engines; 4.2 kept the bytes. Neither produced anything
an operator could read, and neither made a claim about fidelity that could be checked. This
item closes both: a projected Markdown document under `knowledge/evidence/`, and an
accounting of what the projection lost.

Four things had to be decided, and three of them were not obvious.

**Spec 03 §3 leaves a gap in its own contract.** For an ingested document the document
record wants `provenance.source_digest`, `provenance.connector`,
`provenance.connector_version`, `provenance.ingested_at` and `fidelity_report` filled. The
frontmatter contract in the same section — the *only* machine-read metadata a document may
carry — stops at `source`. So a projected file has no way to tell the compiler any of it,
and today an ingested document compiles with an almost-empty `Provenance` and a
`fidelity_report` of `None`.

**"Zero silent element loss" needs a denominator.** The M4 exit gate is *"every element
represented / opaque / dropped-by-policy / failed-and-reported"*, and spec 02 §5 gives the
budget a name — `[ingest] max_failed_elements`. Neither says what an element is, nor which
bucket the budget bounds. Getting this wrong in the obvious direction — count every
imperfection — produces a budget that fires on documents that lost nothing, and an operator
whose first action is to raise it.

**The escape hatch has to end somewhere a person looks.** ADR-0033 made unrepresentable
elements `opaque` nodes. An opaque node in a KIR blob inside `.mycelium/` is not "visible
loss" to anyone who is not reading JSON.

**And the projection must not be a second parser.** KIR came *from* Markdown-adjacent
structures; rendering it back is regenerating syntax around text that must not change.

## Decision

**One frontmatter key carries the link; tier-1 custody carries the facts.**
`source_digest` joins the four fields spec 03 §3 gives to `mycelium ingest`, making the
contract twelve keys. From it the compiler finds the custody record, and from the record the
connector identity, the first-seen timestamp, and the fidelity report — four fields from one,
and they cannot drift from the evidence they describe because they *are* the evidence's own
record. A projected document compiled on a machine without the custody store keeps the
digest and loses the rest, which is the honest answer: there is no fidelity report to point
at where there is no evidence.

**The fidelity report is a pure function of the KIR**, stored in custody as
`mycelium/fidelity/v0`, with three buckets:

| bucket | meaning | counted by the budget |
|---|---|---|
| `represented` | a node carrying its content | — |
| `degraded` | an `opaque` node whose payload survived; *structure* lost, content not | no |
| `lost` | an `opaque` node whose content did not survive | **yes** |

`opaque` nodes therefore carry a `variant` — `degraded` or `lost` — added to
`_KIND_FIELDS[OPAQUE]` as the deliberate, reviewable schema event ADR-0006 anticipated.
Reference nodes (links, images, wikilinks, embeds, tags) are not elements: their text already
lives in the block that contains them, the same exclusion the chunker makes, and counting
them would inflate the denominator and quietly shrink every loss ratio. A parser's *declared
policies* — pandoc drops thematic breaks, the PDF reader claims no structure — are not
per-element counts; they are recorded once in the KIR's warnings and carried into the report
verbatim.

Because the report is derivable from the KIR alone, anyone holding the KIR blob can recompute
it and check it against the digest the document record carries. That is what makes it worth
storing rather than logging.

**`[ingest] max_failed_elements` bounds `lost / elements`, and a document with no elements at
all is refused whatever the budget says.** Zero over zero is not "no loss": an empty
projection from a non-empty source is precisely the silent failure this item exists to
prevent. At the default 5 %, a PDF of scans is refused and a document with one unreadable
page in thirty is not.

**The projector writes Markdown only** (D-020) and regenerates syntax around unchanged text.
Loss appears as a `[!missing]` callout — Profile v1 syntax, atomic in the chunker, legible in
Obsidian, impossible to mistake for the document's own prose. `mycelium ingest` acquires,
stores, guards, parses, stores, accounts, and projects; `mycelium build` then compiles the
projected file like any other authored document, which is how an ingested PDF acquires
`ingested` trust, `evidence` status, chunks, and citations without anything but the compiler
writing an index.

**Storing precedes refusing, twice.** The original is in custody before the parse (ADR-0033),
and the fidelity report is in custody before the budget is applied. A refusal with no
evidence behind it is not a diagnosis: an operator over budget needs to see *what* was lost
to decide whether to raise it or drop the source.

## Alternatives Considered

- **Extend the frontmatter contract with all four provenance fields** (`connector`,
  `connector_version`, `ingested_at`, `fidelity_report`). Direct, and it needs no custody
  read at build time. Rejected: four fields that a tool writes and nothing validates against
  their source will drift the first time someone edits one, and spec 03 §3's whole point
  about frontmatter is that its field set stays closed. One key that *locates* the facts is
  smaller and cannot disagree with them.
- **Count every imperfection against the loss budget** — degraded elements and declared
  policy drops included. Simpler to explain. Rejected because it makes the budget useless:
  a normal PDF drops running headers by policy and every DOCX with a raw block degrades one
  element, so the default would fire on healthy documents and the first thing every operator
  learns is to raise it. A budget nobody trusts is worse than no budget.
- **Emit a node per policy drop** so the report can count them. Rejected: it puts noise in
  the projection — a `[!missing]` callout for every thematic break — to make a counter tick.
  The policy is a property of the parser, and the KIR's warnings already say it once.
- **Encode the disposition in the opaque node's `note` string** instead of adding `variant`
  to the allowed field set. No schema event, no `_KIND_FIELDS` change. Rejected: the fidelity
  report would then be parsing English out of a free-text field, and the vocabulary would be
  unenforced. ADR-0006 declared the per-kind field table precisely so that adding one is a
  reviewable decision rather than a field appearing quietly.
- **Render loss as an HTML comment.** Invisible in a rendered document, which sounds tidy.
  Rejected: the profile disables raw HTML (ADR-0006), so the comment would survive as literal
  prose and be indexed as content — the worst of both.
- **Write the projection from inside `ingest_source`.** One function, one call. Rejected:
  everything else in that function writes only into `.mycelium/`, and putting a file into
  someone's Git working tree is a different kind of act. Splitting `write_projection` out
  makes `--dry-run` a real thing rather than a flag threaded through.
- **Reconstruct the source document rather than its content.** Rejected as out of scope and
  probably impossible: KIR is a *thin* AST by design (D-007) and never carried the source's
  formatting. What the projection promises is the text, and the tests assert exactly that.

## Consequences

- **Loss-free round-trip, proved per engine.** Every KIR node's text survives into the
  projected Markdown for all five fixture routes — Markdown, DOCX and HTML via docling,
  reStructuredText via pandoc, PDF via PDFium. It is the chunker's no-content-loss invariant
  (ADR-0007) transplanted, and it caught two real defects while being written: a blockquote's
  paragraph rendered twice (once inside the quote, once as prose), and a definition list's
  *definitions* rendered by nobody because they hang off a list item rather than a heading.
- **The document record for an ingested document is now complete**, verified end to end: a
  projected PDF compiles to `trust_class=ingested`, `verification_status=evidence`,
  `connector=file`, a real `ingested_at`, and both digests.
- **A new exported contract**, `mycelium/fidelity/v0`, joins `RECORD_MODELS`. Like the
  custody record, it is not a snapshot artifact class: it outlives every snapshot.
- **`[ingest]` is now honoured except for one key.** `parsers` and `connectors` landed at
  4.1, `max_failed_elements` here; only `redact_secrets` (4.6) is still accepted-and-inert,
  and `doctor` still names it. ADR-0014's promise, one key from complete.
- **A new leaf module, `mycelium.layout`.** Making the build read a custody record closed an
  import circle — custody needed the CAS layout and the durable-write primitives, both of
  which lived inside `mycelium.build`, whose package init imports the compiler, which imports
  the configuration, which asks the plugin registry which parsers exist, which reaches
  custody. The five names moved to a module that imports nothing from `mycelium`. They were
  never "build" concepts; they are what a content-addressed store on a filesystem is made of.
- **`MyceliumConfig.ingest` is a `default_factory`.** A section instantiated in the class body
  runs its validators while `mycelium.config` is still executing, which was the second half
  of the same circle.
- **`complete` and `loss == 0` are different questions**, and the report answers both: a
  document whose raw blocks became literal text lost no content and is still not a faithful
  round-trip. A reader deciding whether to trust the projection or open the original needs the
  stricter one.
- **The determinism golden is unchanged.** Nothing here alters what the compiler produces from
  an authored document, and the projected fixtures are not part of the golden corpus.
- **What this does not do**: author candidate documents with an LLM (roadmap 4.4), compute
  grounding or promote (4.5), or scan for secrets and quarantine (4.6). `mycelium ingest`
  reports a failure per source and exits 1 if any failed; deciding what to *do* with a failed
  document is 4.6's.

## References

- Spec 02 §5 (the evidence lane, the loss budget, "the projector writes Markdown documents
  only"); spec 03 §3 (document record, frontmatter contract and its ownership table), §4
  (KIR, the `opaque` escape hatch); spec 05 §1 (`mycelium ingest`), §2 (`[ingest]`).
- D-020 (the LLM never writes an index), D-021 (the folder is the verification status).
- Measured this session: the five-route projection round-trip is loss-free; a PDF with no
  text layer reports 1 of 1 elements lost (100 %) and is refused at the default 5 % budget,
  with the original *and* the report in custody afterwards.
- [ADR-0033](0033-keep-the-original-and-bound-the-hostile.md) — the custody this reads from,
  and the ordering rule ("store before you refuse") this one repeats for the report.
