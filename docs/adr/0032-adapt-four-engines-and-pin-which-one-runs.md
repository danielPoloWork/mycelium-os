# ADR-0032: Adapt four engines behind two protocols, and pin which one runs

- **Status:** Accepted
- **Date:** 2026-09-01
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.1; RFC-0001; spec 02 §§5, 8; spec 03 §4; spec 05 §§2, 4; D-007,
  D-012, D-013, D-017, D-023, D-026; NFR-1, NFR-6; [ADR-0006](0006-adopt-markdown-it-adapter-and-kir-node-fields.md),
  [ADR-0014](0014-adopt-partial-strict-configuration.md), [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md)

## Context

Milestone 4 opens the ingestion lane: bytes from outside the repository — PDF, DOCX, HTML —
compiled into KIR and served with the same citations authored Markdown gets. Item 4.1 is
the plumbing for all of it: *"Connector/Parser protocols exercised for real: docling adapter
(PDF/DOCX/HTML), pandoc fallback (D-007)."*

Four forces shape the answer, and three of them pull against the roadmap line as written.

**D-007 says wrap, do not build.** Mycelium OS owns KIR and the custody guarantees, not the
parsing research. Architecture §5 names the engines: *"docling first; pandoc fallback"*.

**D-013 and NFR-6 say offline.** Zero network calls unless configured; the default profile
builds fully offline; no telemetry. ADR-0017 already spent the one exception the project
allows — the embedder — and made even that opt-in behind `allow_download`.

**NFR-1 and gate G6 say byte-identical, on three operating systems.** The parse stage feeds
chunk text, chunk text feeds digests, and digests feed the golden. A parse stage whose
output depends on float kernels is a determinism gate waiting to go red on one CI cell.

**Spec 05 §4.2 says pinned, never "best available".** A build must be explainable from its
manifest alone. No runtime capability negotiation, no "whichever engine happens to be
installed".

Measuring docling against those constraints changed the shape of the item. `pip install
docling` resolves to **sixty-odd packages including torch 2.13, torchvision, transformers,
opencv, scipy and pandas**, and it downgrades this project's own `typer` pin. Splitting it
apart, `docling-slim` with the `convert-core` and per-format extras is **24 packages, no
torch**, and it converts DOCX and HTML offline, in-process, with no model files —
measured, on this machine, this session. Its **PDF** path is the one that needs the rest:
`DocumentConverter.convert()` on a PDF fails with `ModuleNotFoundError: torch`, because
docling reads PDF through a layout model and a table model whose weights are fetched from
HuggingFace on first use.

So docling's PDF pipeline is not one dependency decision away. It is a network call at
first use (against NFR-6), a 2 GB closure on every developer machine (against D-013's
posture), and floating-point inference in a stage gate G6 compares byte-for-byte (against
NFR-1). Pandoc cannot cover for it: pandoc reads DOCX, HTML, ODT, EPUB, reStructuredText,
LaTeX and thirty more formats, and it does not read PDF at all.

## Decision

**Two Protocols, four adapters, one pinned list.**

`Connector` and `Parser` are declared in `mycelium.sdk.protocols` — acquisition with custody
is separated from parsing because the two fail differently and ingestion answers them
differently (refuse the first, quarantine the second). `Parser.parse` takes the document id
from its caller rather than minting one, because identity is the build's write (ADR-0009)
and a parser that minted its own would break incremental rebuilds.

Four parsers ship, each an adapter over an engine that already exists:

| id | engine | reads | runtime |
|---|---|---|---|
| `markdown` | markdown-it-py | Markdown | none — a runtime dependency already |
| `docling` | docling's declarative backends | DOCX, HTML | `mycelium-os[ingest]` |
| `pandoc` | the pandoc binary, `--sandbox` | DOCX, HTML, ODT, EPUB, RST, LaTeX | pandoc 3.x on `PATH` |
| `pdf` | PDFium via `pypdfium2` | PDF (text layer) | `mycelium-os[ingest]` |

**The `ingest` extra is `docling-slim` with named format extras plus `pypdfium2`** — no
torch, no weights, no network, deterministic on every platform in the matrix. **Docling's
ML PDF pipeline is out of scope for v1** and filed as roadmap 4.9 with the three
constraints above as its acceptance criteria. PDF is therefore read by its text layer only,
and every PDF document carries a warning saying exactly that.

**Which parser runs is `[ingest] parsers`, in order.** The first entry declaring a media
type wins, and an entry that cannot be resolved is an error naming what to install — never
a fall-through to the next one. `parsers = ["docling", "pandoc"]` *is* architecture §5's
"docling first, pandoc fallback", stated by the operator rather than inferred from what
happens to be installed. The default is `["markdown"]`: the only parser with no optional
runtime, so a fresh checkout resolves, and ingesting anything else is a deliberate edit.

**Two deviations from spec 05 §2 are taken deliberately**, both recorded here rather than
silently:

1. The spec's single `[ingest] connectors = ["markdown", "html", "pdf"]` names *parsers*,
   because §2 predates §4.1's split of the two Protocols. The keys split to match the
   Protocols: `parsers` pins how a source is compiled, `connectors` how it is acquired. The
   old shape is refused by name, with the replacement in the message.
2. `[ingest]` is honoured **by key**, not as a whole section — `parsers` and `connectors`
   steer ingestion now, `redact_secrets` (4.6) and `max_failed_elements` (4.3) do not.
   ADR-0014's section-level scheme gains a key-level companion, `unhonoured_keys`, so
   `doctor` can name the exact keys that do nothing yet.

**No element is lost silently.** Every adapter maps what KIR models and records what it
does not as an `opaque` node carrying the construct's name and a digest of its content
(spec 03 §4's escape hatch, F-3). This is why the pandoc adapter reads pandoc's **JSON AST**
rather than piping `pandoc --to gfm` into the Markdown adapter that already exists: the
Markdown writer flattens definition lists, line blocks and raw blocks with no trace, and
"zero silent element loss" is the milestone's exit gate.

## Alternatives Considered

- **Depend on full `docling` and use its ML PDF pipeline.** The roadmap line read this way,
  and it is the highest-fidelity PDF reading available. Rejected on three measured grounds:
  the closure (60+ packages, torch, and a downgrade of our own `typer` pin), the
  first-use model download (NFR-6 forbids an unconfigured network call), and cross-platform
  float reproducibility in a stage gate G6 compares byte-for-byte (NFR-1). Not rejected
  forever — filed as roadmap 4.9, where those three become the acceptance criteria instead
  of the objection.
- **Pipe `pandoc --to gfm` into the existing Markdown adapter.** Perhaps forty lines instead
  of four hundred, and it reuses a tested path. Rejected because pandoc's Markdown writer
  drops what GFM cannot express — the fixture's definition list is the case in point — and
  the loss is invisible: no warning, no opaque node, nothing for a fidelity report to count.
  An adapter that cannot see what it lost cannot report it.
- **Let resolution fall back to whatever is installed.** Friendlier: a machine without
  pandoc would still parse its DOCX with docling. Rejected because it makes a build
  unexplainable from its manifest (spec 05 §4.2) — two machines with the same config would
  produce different corpora, and nothing in either output would say why.
- **Ship a PDF adapter that infers headings from font size.** Rejected: that is layout
  analysis done badly, under a name that would imply structure the output does not have. The
  text layer, page-scoped, with a warning on every document, is what PDFium can honestly
  claim.
- **Keep spec 05 §2's single `connectors` key for parsers.** Rejected: a config key is a
  compatibility surface, the word would be wrong for what it configures forever, and a real
  connector (HTTP, at M7) would need a second key anyway. Pre-1.0, with an explicit
  migration error, is the cheapest moment to fix it.
- **Declare all six plugin Protocols now** (`Chunker`, `Embedder`, `Extractor`,
  `Synthesizer`, `Reranker` too). Rejected: a Protocol with no implementation and no
  resolver is a guess about a milestone that has not been designed. `Embedder` already
  exists in `mycelium.embedding.base` (ADR-0017); reconciling the import paths belongs to
  roadmap 6.1, which freezes the contracts.

## Consequences

- **A new public contract surface.** `mycelium.sdk.protocols` is contract number four of the
  five architecture §10 freezes at 1.0. `MYCELIUM_API_VERSION` is an integer generation, not
  the release version, and every plugin declares the range it supports so the registry can
  refuse an incompatible one precisely — without a PEP 440 parser in the runtime closure.
- **The claim is now testable, and tested.** One document, authored once and rendered by
  pandoc into DOCX, HTML and reStructuredText, reaches four different engines and comes back
  with the *same anchors* — `docs/retry.md#backoff/0` from all four. That is what the KIR
  boundary is for, and it was unproven while markdown-it was the only adapter.
- **Installing the `ingest` extra pins `typer` below 0.27** (docling-slim's own constraint).
  CI installs all extras, so this is the version the CLI is tested against. It is a
  co-installability constraint rather than a pin of ours, and it is recorded because the day
  it conflicts, this line is where the answer starts.
- **PDF ingestion is honest but thin.** Text layer, page locators, no structure — and a
  scanned PDF with no text layer yields an empty document plus a warning naming the page,
  not an error. The loss budget (4.3) is what will act on that.
- **Pandoc nodes carry no `src` locator.** Pandoc's JSON AST has no offsets, so an ingested
  DOCX cites by anchor and never by line. Docling's provenance is the answer where a backend
  provides it; the mapping is written and unit-tested, and the declarative backends do not
  fill it in today.
- **The config digest changed**, so the G6 golden is re-blessed — with a **one-line diff**
  (`config_digest` only). Every chunk of the corpus is byte-identical, which is the evidence
  that adding a config section did not touch the compiler.
- **CI grew a job and a step.** `ingest / parsers` names the adapters in the checks list, and
  pandoc is installed on all four build-matrix cells because subprocess behaviour is exactly
  what differs between Windows and the Unix runners.
- **Ruff no longer formats fixture Markdown.** `ruff format` rewrites Python inside Markdown
  code fences, which would have silently edited a committed fixture whose bytes tests assert.
- **What this does not do**: write blobs to the CAS (4.2), project evidence Markdown with
  provenance frontmatter (4.3), scan for secrets or quarantine (4.6), or add a `mycelium
  ingest` command — which has nothing to write until 4.3. A KIR document comes back from the
  registry; where it goes belongs to the items that own that question.

## References

- Spec 02 §5 (ingestion lanes), §8 (path safety, untrusted content); spec 03 §4 (KIR node
  kinds, `opaque`); spec 05 §2 (configuration), §4 (plugin API, pinned resolution), §5
  (compatibility policy).
- D-007 (KIR over ecosystem parsers), D-013 (offline default), D-017 (untrusted content,
  no unconfigured network), D-023 (extension points), D-026 (plugin naming).
- Measured this session: `docling` resolves 60+ packages including torch 2.13 and downgrades
  `typer`; `docling-slim[convert-core,format-docx,format-html,format-latex,format-pdf]`
  resolves 24 and converts DOCX and HTML offline; `DocumentConverter.convert()` on a PDF
  raises `ModuleNotFoundError: torch`; pandoc 3.10 reads 40 input formats and no PDF.
- [ADR-0006](0006-adopt-markdown-it-adapter-and-kir-node-fields.md) — the first adapter, and
  the KIR shape this one had to match.
- [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) — the optional-extra and
  `deterministic` precedents this ADR reuses.
