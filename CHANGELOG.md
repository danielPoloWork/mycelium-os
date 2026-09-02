# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

- **The ingestion fixture corpus and its element inventories** (roadmap 4.7) — the M4 exit
  gate, *zero silent element loss*, is now a test. `tests/fixtures/ingest/inventory.json`
  carries a hand-authored **declaration** of what each source document contains, in KIR node
  kinds, and the gate compares it with what every engine produced: a difference is either
  recorded with a reason a reviewer approved, or it fails. This is the half the fidelity
  report cannot supply — the report is computed from the KIR, so it cannot see an element
  that never became a node. See
  [ADR-0038](docs/adr/0038-declare-the-corpus-then-compare-it.md).
- **`tools/update_ingest_inventories.py`** — re-bless the corpus after an intended parser
  change. It regenerates only the machine half of the file and never the declarations or
  the approved deviations, so a regression cannot bless itself.
- **A new CI job, `inventory / zero silent element loss`**, and a matching `inventory`
  pytest marker.
- **New corpus fixtures**: an `elements` family covering the node kinds the original fixture
  never reached (deeper headings, an ordered list with a nested one, two code blocks, an
  image, a footnote, a thematic break), a `profile` family for the Markdown-only vocabulary
  (wikilinks, an embed, tags, a callout), and a two-page PDF whose second page has no text
  layer — one parse producing both a page locator and an opaque `lost` node.
- **Roadmap 4.10** — an ingestion-heavy corpus joining the eval set, the third clause of the
  M4 exit gate, filed with the judging trap ADR-0027 warns about written into it.
- **Ingestion quarantine** (roadmap 4.6) — a source the evidence lane refuses now leaves a
  `mycelium/quarantine/v0` record under `.mycelium/quarantine/` naming the stage that
  refused it (`acquire`, `dispatch`, `guard`, `parse`, `budget`), the reason, and the
  **custody digest of the bytes that caused it** — so a quarantined file can be opened
  again rather than only counted. Ingesting it successfully clears the record; `mycelium gc`
  never sweeps it. See
  [ADR-0037](docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md).
- **`mycelium ingest --forget <source>…`** — drop a quarantine record without ingesting, for
  a source that is never coming back.
- **Secret scanning at ingestion**, and `[ingest] redact_secrets` is honoured. Eleven
  structural rules — vendor key prefixes, PEM armour, credentials in a URL's authority —
  and deliberately **no entropy heuristic**, because a scanner that fires on base64 images,
  digests and UUIDs is one an operator switches off. A match is redacted **before the KIR
  is stored**, so the credential survives in exactly one artifact — the tier-1 original,
  which is what a citation is checked against — while the compiled document, its
  projection, its chunks and the index carry `[redacted: <rule-id>]`.
- **`Document.secret_flags` is populated**, through the ingested document's custody record
  (ADR-0034's mechanism), and **whether or not redaction acted**: flagging is the
  observation, redaction is the action, and switching redaction off should not silently
  also remove the record that a credential is there.
- **`mycelium doctor` reports two new conditions** — what is quarantined (as a warning: a
  recorded refusal is the system working), and, when `redact_secrets = false`, that
  credentials found in an ingested source are being written to the authored tree verbatim.
- **`GuardError` and `LossBudgetError`** join `mycelium.ingest.errors` as subclasses of
  `ParseError`, so a quarantine record can name its stage from the exception's type instead
  of parsing its message. Every existing handler is unaffected.
- **Verification: `mycelium verify`, `promote`, `demote`** (roadmap 4.5) — gate G7 as a
  per-document decision (D-021). `verify` recomputes citation coverage against the corpus
  *as it is*, which is what catches a candidate whose evidence has been edited,
  re-projected or deleted since it was written, and measures **sampled entailment** through
  an LLM judge when one is configured. `promote` moves a candidate into
  `knowledge/verified/`, refusing below the gate; `demote` moves it back and strips its
  verification block. See
  [ADR-0036](docs/adr/0036-measure-what-can-be-measured-and-let-a-human-outrank-the-gate.md).
- **`entailment` is `None` when it was not measured**, never a number. There is deliberately
  no offline approximation: term overlap between a claim and its citation would look like a
  grounding score and would not be one. The recorded `grounding` is
  `min(coverage, entailment)`, so a perfect citation record cannot hide a failed entailment.
- **`verify --gate`** is the CI form and fails on a *measured* shortfall; an unmeasured
  entailment is reported and does not fail it. `promote` is stricter — there the unmeasured
  half is a blocker, and `--force` is the human override, recorded in the document as
  `verified_by: <name> (forced: <code>)` so it survives in Git.
- **`[verification]`** is honoured — `cites_coverage_min` (0.95), `entailment_min` (0.90),
  `auto_promote` (off: promotion is a human act), plus `sample_size` and `model_id`, which
  points the judge at a different model than the one that wrote. Unset, the writer grades its
  own work, and the report, the document and the CLI all say `self-judged`.
- **`[sources]`** is honoured — trust per origin, stamped at acquisition and carried by the
  document. `verify` reports the weakest trust among a candidate's cited evidence, and never
  gates on it.
- **`mycelium doctor` reports gate G7** — the floors, the judge, the sample size, and whether
  promotion is automatic — once a provider is configured.
- **`mycelium.markdown.frontmatter.upsert`** — one textual frontmatter writer, shared by
  identity pinning and by verification. It never re-serializes a human's block, and it never
  folds a value across lines.

- **The synthesis lane** (roadmap 4.4) — the LLM half of dual-lane ingestion (D-020).
  `mycelium ingest` now additionally authors a *candidate* document under
  `knowledge/candidate/` in which every claim-bearing block cites the evidence layer with a
  wikilink. The lane runs only when `[synthesis]` names a provider, so a default install
  still ingests entirely offline. See
  [ADR-0035](docs/adr/0035-let-an-llm-write-only-what-a-machine-can-check.md).
- **`Synthesizer`** joins `Connector` and `Parser` in `mycelium.sdk.protocols`, with
  `SynthesisContext`, `EvidenceDocument` and `Synthesis` — the first plugin contract whose
  output is not a function of its input, so it declares itself non-deterministic and returns
  the identity of what produced the text.
- **The `wiki` plugin** (D-026): a closed citable vocabulary in the prompt, one repair
  round-trip when a draft breaks the contract, and a refusal when the second one does too.
  An ungrounded document is never written.
- **`[synthesis]`** is honoured — `enabled`, `plugin`, `provider`, `model_id`, `effort`,
  `max_output_tokens`, `instructions`, and `min_citation_coverage`, which defaults to **1.0**:
  every claim-bearing block cites, or nothing is written.
- **A new optional install, `mycelium-os[synthesis]`** — the official `anthropic` SDK, four
  packages. Nothing imports it unless a provider is configured.
- **`mycelium/synthesis/v0`** run records in tier-1 custody (`CustodyKind.SYNTHESIS`):
  provider, model, prompt digest, parameters, the evidence set, and the citations the
  document was accepted on. The compiler recovers them into `provenance.synthesizer`.
- **`mycelium ingest --no-synthesize`** skips the lane even when a provider is configured,
  and `mycelium doctor` reports the lane's state once one is.

### Changed

- **`[verification]` and `[sources]` are honoured**, leaving `eval` as the only section
  `mycelium.toml` accepts and nothing reads — and it may stay that way, since the harness
  takes its case set on the command line.
- **All three verification frontmatter fields are written by the verify machinery.** Spec 05
  §2's table assigns `verified_at` to `promote`; the compiler treats the three as a unit and
  warns about a partial block, so splitting their owners would warn on every candidate in the
  corpus. `promote` runs the measurement rather than writing the field itself (ADR-0036).
- **`verified_at` records when the grounding last *moved*.** The block is rewritten only when
  the score or the checker changed, so a nightly `verify` over an unchanged corpus produces no
  diff and no rebuild.
- Identity pinning now goes through the shared frontmatter writer rather than its own textual
  insert. Byte-compatible: the determinism golden did not move.
- The snapshot manifest's `config_digest` covers the two new sections. The golden is
  re-blessed with a one-line diff — every chunk byte-identical.

- **A wikilink into `knowledge/evidence/` is now a `cites` edge**, not `links_to` (spec 03
  §6). Folder-derived, so no store migration: `mycelium neighbors --type cites` answers what
  a document rests on.
- The snapshot manifest's `config_digest` now covers `[synthesis]`. The determinism golden is
  re-blessed with a one-line diff — every chunk is byte-identical.

- **Ingestion contracts and four parsers** (roadmap 4.1). `mycelium.sdk.protocols` declares
  the `Connector` and `Parser` Protocols, `Blob` and `PluginMeta` — the fourth of the five
  contracts that freeze at 1.0. Four adapters ship behind them: `markdown` (markdown-it,
  no optional runtime), `docling` (DOCX and HTML), `pandoc` (DOCX, HTML, ODT, EPUB,
  reStructuredText, LaTeX, through one `--sandbox`ed binary), and `pdf` (PDFium's text
  layer). One document rendered into DOCX, HTML and reStructuredText produces the same
  citable anchors as its Markdown original. See
  [ADR-0032](docs/adr/0032-adapt-four-engines-and-pin-which-one-runs.md).
- **`[ingest] parsers` and `[ingest] connectors`** — the pinned, ordered plugin lists.
  The first parser declaring a media type wins; a name that cannot be resolved is an error
  naming what to install, never a fall-back to whatever is installed (spec 05 §4.2). The
  default is `parsers = ["markdown"]`, which needs no optional runtime.
- **A new optional install, `mycelium-os[ingest]`** — `docling-slim` with its declarative
  format extras plus `pypdfium2`: no `torch`, no model weights, no network. The `pandoc`
  parser additionally needs pandoc 3.x on `PATH`.
- **`mycelium doctor` now reports the pinned parsers** and whether each one can run on this
  machine, with the remedy in the message — so an unavailable plugin is met before a build
  rather than during one.
- **Roadmap 4.9** — read PDF *structure*, or record why v1 does not — filed with the three
  measured constraints (dependency closure, first-use model download vs NFR-6,
  cross-platform float reproducibility vs gate G6) as its acceptance criteria.

- **Tier-1 custody** (roadmap 4.2). An ingested source is stored verbatim under its own
  digest in `.mycelium/cas/originals/`, with the KIR compiled from it and a
  `mycelium/custody/v0` record of where it came from — written beside the blob, not into
  the store, because the store is disposable and evidence is not.
  `mycelium gc` never sweeps that subtree and now reports how much it kept;
  `mycelium doctor` re-hashes it and reports corruption instead of healing it.
  See [ADR-0033](docs/adr/0033-keep-the-original-and-bound-the-hostile.md).
- **`mycelium.ingest.ingest_source`** — the evidence lane end to end: acquire, store, guard,
  parse, store. The original reaches custody *before* the parse, so a file that is refused
  can still be examined afterwards.
- **Shape-based guards on untrusted input** (`mycelium.ingest.safety`). A ZIP container is
  refused from its own header when it declares a decompression bomb; markup nested or
  populated past a ceiling is refused from a single linear scan; and the shared KIR builder
  caps node count and text size, so a new adapter inherits the last line of defence. Every
  ceiling is set two orders of magnitude clear of anything measured on a real document.
- **A committed hostile fixture suite** under `tests/fixtures/ingest/hostile/`, each file
  generated by `make_fixtures.py` so what makes it hostile is reviewable, and each asserted
  to produce one typed failure inside a per-file time budget.

- **`mycelium ingest <path>...`** (roadmap 4.3) — the evidence lane end to end: acquire,
  keep, guard, compile, account, project. Each source is handled on its own, so one that
  cannot be read is reported and the rest continue; `--dry-run` takes custody and reports
  fidelity without writing a document. See
  [ADR-0034](docs/adr/0034-project-the-evidence-and-count-what-it-lost.md).
- **Evidence projection.** An ingested source becomes a Markdown document under
  `knowledge/evidence/` with provenance frontmatter, which `mycelium build` compiles like any
  authored file — so it arrives in the store with `ingested` trust, `evidence` status, chunks
  and citations, without anything but the compiler writing an index (D-020). Every KIR node's
  text survives the round-trip, proved per engine.
- **Fidelity reports** (`mycelium/fidelity/v0`), stored in tier-1 custody and linked from the
  document record. Three buckets — represented, degraded (structure simplified, content kept),
  lost — and the report is a pure function of the KIR, so anyone holding the KIR blob can
  recompute it and check the digest.
- **`[ingest] max_failed_elements` is honoured**: a projection whose *lost* fraction exceeds
  the budget is refused, with the counts and the setting's name in the message. A document
  with no elements at all is refused whatever the budget says. Both leave the original and the
  report in custody.
- **`source_digest` joins the frontmatter contract** as a fifth `mycelium ingest`-owned key.
  It is the link from a projected document to its tier-1 evidence, and the compiler reads the
  connector identity, the acquisition time and the fidelity report from the custody record
  rather than from four more frontmatter fields that could drift.
- **`mycelium.layout`** — a leaf module for the CAS layout and the durable-write primitives,
  which the build, snapshot publication and custody all need and none should have to import
  the compiler to get.
- **A hostile document can no longer take a build down.** Measured before the fix: HTML
  nested 5 000 deep took docling **45 s** (at 50 000, it never returned), and the same input
  made the pandoc adapter raise an uncaught `RecursionError` out of `json.loads`. Both are
  now refused in under 0.1 s as a typed `ParseError`.
- **An `opaque` node no longer names a CAS blob that was never written.** Where pandoc's
  payload is literal source text it is kept as the node's `text` — the treatment ADR-0006
  already gives raw HTML in authored Markdown — and `blob` is reserved for a payload that is
  actually in custody.
- **`[ingest]` is honoured by key rather than as a whole section.** `parsers` and
  `connectors` steer ingestion now; `redact_secrets` (roadmap 4.6) and
  `max_failed_elements` (4.3) are still accepted and digested but do nothing, and
  `mycelium doctor` names them individually. This extends
  [ADR-0014](docs/adr/0014-adopt-partial-strict-configuration.md) one level finer.
- **`[ingest] connectors` no longer names parsers.** Spec 05 §2's example
  (`connectors = ["markdown", "html", "pdf"]`) predates the Connector/Parser split in §4.1;
  the keys now match the Protocols, and the old shape is refused with the replacement in
  the message.
- The snapshot manifest's `config_digest` now covers the `[ingest]` section. The
  determinism golden is re-blessed with a one-line diff — every chunk is byte-identical.

### Deprecated

### Removed

### Fixed

- **[BUG-0016](docs/bugs/2026/09/BUG-0016-docx-footnotes-vanish-unreported.md)** — a DOCX
  footnote's body vanished and the fidelity report called the document complete. Word keeps
  note bodies in `word/footnotes.xml`, a package part docling's DOCX backend does not read,
  so the text reached no KIR node and — the report being a pure function of the KIR — nothing
  downstream could tell that from a document with no footnotes. The adapter now counts the
  notes the container declares and records each one docling did not surface as an opaque
  `lost` element, so the loss is counted, charged to `[ingest] max_failed_elements`, and
  named in the projection. Found by the corpus above, on its first run.

### Security

## Released versions

| Version | Date | Notes |
|---|---|---|
| [v0.3.0](docs/changelog/v0/v0.3.0.md) | 2026-08-31 | Milestone 3 — The compiler (spec Phase 1). Release notes: [docs/releases/v0.3.0.md](docs/releases/v0.3.0.md). |
| [v0.2.0](docs/changelog/v0/v0.2.0.md) | 2026-08-30 | Milestone 2 — Walking skeleton (spec Phase 0). Release notes: [docs/releases/v0.2.0.md](docs/releases/v0.2.0.md). |
| [v0.1.0](docs/changelog/v0/v0.1.0.md) | 2026-08-29 | Milestone 1 — Project bootstrap & CI. Release notes: [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md). |
