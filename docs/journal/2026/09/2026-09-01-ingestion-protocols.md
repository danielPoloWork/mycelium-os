# 2026-09-01 — four engines, one boundary (roadmap 4.1)

- **Session scope:** roadmap 4.1 — Connector/Parser protocols exercised for real, docling
  adapter, pandoc fallback (D-007, spec 02 §5, spec 05 §4).
- **PR:** #50 (`feat/ingest-connector-parser-protocols`). Follows #49 (the v0.3.0 release
  cut), merged as `9adad70`.
- **Milestone 4:** 4.1 done; 4.2–4.8 open, plus 4.9 filed here.

## The item's own words did not survive contact with the dependency

"docling adapter (PDF/DOCX/HTML)" is one line of roadmap. Measuring it is what took the
session, and the measurements changed the shape of the delivery:

- `pip install docling` resolves **60-odd packages including `torch` 2.13, `torchvision`,
  `transformers`, `opencv` and `scipy`** — and downgrades this project's own `typer` pin.
- `docling-slim` with `convert-core` and the per-format extras is **24 packages, no torch**,
  and converts DOCX and HTML offline with no model files.
- `DocumentConverter.convert()` on a PDF, in that slim environment, raises
  `ModuleNotFoundError: torch`. Docling reads PDF through a layout model and a table model
  whose weights are fetched from HuggingFace **on first use**.

That last fact is not a packaging inconvenience, it is three contract violations at once:
NFR-6 forbids an unconfigured network call, D-013 makes the default profile offline, and
NFR-1 with gate G6 demands byte-identical artifacts across Linux, Windows and macOS — which
float kernels on three platforms do not promise, in a stage whose output feeds the digests
the golden compares.

So the milestone's named formats are all covered, and PDF is covered *honestly*: PDFium's
text layer, page locators, and a warning on every document saying there is no structure in
it. Docling's ML pipeline is filed as **roadmap 4.9** with those three constraints written
as its acceptance criteria rather than as objections — the shape ADR-0017 used for the
embedder.

## What "exercised for real" turned out to mean

The fixture is one authored Markdown document, rendered by pandoc into DOCX, HTML and
reStructuredText, plus a 964-byte PDF written by hand — small enough to read in a hex dump,
which is the right size for a fixture that feeds an untrusted-input parser. Four engines
read those five files, and the test that matters says they agree:

```text
source.md    via markdown   docs/retry.md#/0  docs/retry.md#backoff/0  #backoff/1  #backoff/2  #backoff/3
source.docx  via docling    docs/retry.md#/0  docs/retry.md#backoff/0  ...
source.html  via docling    docs/retry.md#/0  docs/retry.md#backoff/0  ...
source.rst   via pandoc     docs/retry.md#/0  docs/retry.md#backoff/0  ...
```

That is the whole point of KIR (D-007) and it had never been tested, because markdown-it was
the only adapter. It also did not work first time. Two real defects turned up on the way:

- **docling strips whitespace at a formatting-run boundary**, in `text` and `orig` alike, so
  a sentence containing a link came back as `...and thedelivery logrecords each attempt.`
  Concatenation is not the neutral choice it looks like — it corrupts every sentence with
  emphasis or a link in it. The runs are rejoined with a space, suppressed next to
  punctuation that binds to its neighbour.
- **docling numbers section headers from 1 whether or not the document also has a title**,
  so a DOCX whose first heading is "Heading 1" was landing at KIR level 2 — and the chunker
  reads level 1 as "this is the document's title" (ADR-0007). The same content would have
  cited differently depending on which format it arrived in.

## The decisions worth recording

**Pandoc is read through its JSON AST, not its Markdown writer.** The cheap adapter —
`pandoc --to gfm` into the Markdown adapter that already exists — would have been forty
lines instead of four hundred. It silently flattens definition lists, line blocks and raw
blocks, and the milestone's exit gate is *zero silent element loss*. Reading the AST means a
construct KIR cannot model becomes an `opaque` node carrying its name and a digest, which a
fidelity report can count and point at.

**Resolution refuses; it never falls back.** `[ingest] parsers` is pinned and ordered, the
first entry declaring a media type wins, and an unresolvable entry is an error naming what
to install. The friendlier behaviour — use whatever is installed — would let two machines
with identical configuration produce different corpora, with nothing in either output saying
why. `mycelium doctor` asks the same question first, so the refusal is met before a build
rather than during one.

**Two spec deviations, both deliberate.** Spec 05 §2's `[ingest] connectors = ["markdown",
"html", "pdf"]` names *parsers*; the key predates §4.1's split of the two Protocols. The
keys now match the Protocols, and the old shape is refused by name with the replacement in
the message — the useful behaviour for anyone copying the spec. And `[ingest]` is the first
section honoured **by key**: `parsers` works today, `redact_secrets` and
`max_failed_elements` do not, and pretending either way would have been a lie in one
direction or the other.

## What the golden proves

Adding `[ingest]` to the configuration moved `config_digest`, so gate G6's golden was
re-blessed. The diff is **one line**. Every chunk of the six-document corpus is
byte-identical — which is the evidence that a new config section reached the manifest and
nothing else.

## What this deliberately does not do

No CAS writes (4.2), no evidence projection with provenance frontmatter (4.3), no secret
scan or quarantine (4.6), and no `mycelium ingest` command — which would have nothing to
write until 4.3 exists. A KIR document comes back from the registry; where it is stored is
the next item's question.
