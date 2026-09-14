# How to ingest an external document

Ingestion is for content you did not author in Mycelium Markdown — a PDF, a DOCX, an
HTML page, a wiki export. It runs a different lane from authored Markdown, with its own
guarantees: the original bytes are kept in custody, untouched, and a fidelity report
says exactly what did and did not survive the trip into KIR.

## 1. Install the ingest extra

The declarative parsers (docling's DOCX/HTML/LaTeX/PDF backends, plus PDFium) are
optional, because the authored lane needs none of them:

```bash
pip install "mycelium-os[ingest]"
```

A DOCX or HTML source needs nothing further. A PDF is read structurally by these
parsers; scanned pages with no text layer are outside v1's scope. For a format none of
the bundled parsers read, `pandoc` is a floor rather than a pin — install the binary
and pin `pandoc` last in `[ingest] parsers` as a fallback (see below).

## 2. Point `mycelium ingest` at the source

```bash
mycelium ingest path/to/handbook.pdf
```

This does four things, in order, and none of them can be skipped:

1. **Acquires** the bytes under custody — a connector takes them into
   content-addressed storage before anything tries to parse them, so a parser crash
   never loses the only copy of what it was reading.
2. **Parses** them into KIR, the thin versioned document AST every source compiles to.
3. **Projects** a verbatim Markdown copy under `knowledge/evidence/handbook.md` —
   `evidence` is a real verification-status folder, not `verified`, because nobody has
   looked at it yet.
4. **Writes a fidelity report** naming every source element and whether it was
   represented whole, degraded (structure simplified, content kept), or lost.

## 3. Read the fidelity report

`mycelium ingest` prints it immediately, for every source:

```text
handbook.pdf -> wrote knowledge/evidence/handbook.md (docling)
  41 represented, 2 degraded, 0 lost of 43 elements; 6 reference(s) carried
```

*Represented* survived whole. *Degraded* lost structure but kept its content — a table
flattened to plain text, say. *Lost* is the ratio a loss budget in `mycelium.toml`
(`[ingest] max_failed_elements`) bounds: a document that loses too much of itself is
refused rather than silently published with holes in it. If it refuses, the document
lands in quarantine (`.mycelium/quarantine/`) with the exact bytes that caused the
refusal kept alongside the reason — nothing is dropped and forgotten;
`mycelium doctor` lists what is waiting there, and `mycelium ingest --forget <source>`
clears a record for a source that is simply never coming back.

## 4. Pin more than one parser, in the order they should be tried

```toml title="mycelium.toml"
[ingest]
parsers = ["docling", "pandoc"]
```

Resolution is **pinned, not "best available"**: the first pinned parser that declares
the source's media type wins, and which one ran is recorded per document in the
manifest. Two machines with the same `mycelium.toml` compile the same corpus
regardless of what else happens to be installed on either of them.

## 5. Build, and the evidence joins the corpus

```bash
mycelium build
mycelium search "what the handbook says about timeouts"
```

The projected document is trust-classed `ingested` and answers queries like anything
else, with its `verification_status` visible in every result — an agent reading a
result can tell an ingested passage from one a human wrote and vetted.

## Next

- To turn ingested evidence into readable, cited prose rather than reading the
  verbatim projection yourself, see
  [Verify and promote a synthesized document](verify-and-promote.md).
- Untrusted content is never interpreted as an instruction at any stage of this
  pipeline (D-017) — see `docs/security/threat-model.md` in the repository for the
  full boundary-by-boundary account.
