# ADR-0134: Own the decode, and stop asking whatever is importable

- **Status:** Accepted
- **Date:** 2026-09-19
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §5
- **Related:** [ADR-0117](0117-sign-and-inventory-the-artifact-and-reserve-the-rung-a-newcomer-stands-on.md)
  (where the incident was recorded and the reachability rule came from),
  [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md) (pinned resolution: a build is
  explainable from its manifest alone),
  [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md) (the fidelity report is a pure
  function of the KIR, and a parser's declared policies live in its warnings),
  [ADR-0039](0039-measure-what-projection-costs.md) (why the rendered corpus is vendored),
  [ADR-0095](0095-read-the-corpus-in-the-dialect-it-is-written-in.md) and
  [BUG-0025](../bugs/2026/09/BUG-0025-the-corpus-renderer-reads-a-dialect-the-corpus-is-not-written-in.md)
  (the sibling: a reader's assumption deciding what the documents said),
  [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md) (a signal that
  fires on everything selects for being ignored),
  [BUG-0008](../bugs/2026/08/BUG-0008-bom-hides-frontmatter.md) (a byte-order mark in a document
  this project *writes*), [BUG-0032](../bugs/2026/09/BUG-0032-an-importable-package-changes-what-html-ingestion-projects.md)
  (this defect); spec 02 §5, spec 03 §4; D-007, D-013, D-017; roadmap 6.6, 6.15

## Context

The HTML lane parses through docling's declarative backend, which builds a
`BeautifulSoup(raw, "html.parser")` over the document's raw bytes. BeautifulSoup has to
decide what encoding those bytes are in, and for a document that declares none it asks an
encoding detector that `bs4.dammit` **binds at import time** from the first of `cchardet`,
`chardet` and `charset-normalizer` it can import.

Roadmap 6.6 discovered what that means here. A dependency group added for the SBOM
generator pulled `chardet` into the environment, and `tools/build_ingested_corpus.py
--check` failed: documents of the vendored ingested corpus projected differently, with
nothing in `src/` changed. ADR-0117 fixed the instance — the generator now runs through
`uv tool run`, resolvable by nothing this project imports — and named the rule it came to:
*a tool that is not part of this product must not be resolvable alongside it; what is
importable is an input to the compiler, whether or not anything imports it on purpose.*

It did not fix the class, and filed 6.15 to. This decision is that item.

### What the measurement says

Two facts were established before anything was written, because the item asked for both.

**The committed corpus is a plain UTF-8 rendering.** All 62 HTML sources are valid UTF-8
and **not one of them declares a charset** — pandoc's html5 writer emits a bare fragment
without `--standalone`, so there is no `<head>` to carry a `<meta charset>`. The detector is
therefore consulted for every one of them, ahead of UTF-8, on every ingestion.

**The count is a property of the detector's version.** The incident was replayed without
installing anything: each detector's answers for the 62 sources were captured in a
throwaway environment, bound to `bs4.dammit.chardet_module` as a lookup table, and the
corpus check re-run in process.

| detector | sources read as windows-1252 | evidence documents that move |
|---|---|---|
| charset-normalizer 3.5.1 (what is installed today) | 0 | 0 |
| chardet 3.0.4 / 4.0.0 / 5.0.0 / 5.1.0 / 5.2.0 / 6.0.0 | 7 | 7 |
| chardet 7.6.0 | 0 | 0 |

The seven are the sources whose entire non-ASCII content is one character — an em dash, or
a single `✓`. That is too little signal for the detectors that guess wrong and enough for
the ones that do not, at 0.73 confidence either way.

Three things follow. The corpus as committed is not "a chardet rendering" or "a
charset-normalizer rendering" — it is what step 3 of the rule below produces, which three
of the four resolutions above happen to agree with. The figure 6.6 recorded, five, is not
what a replay produces; seven is, and the discrepancy is the finding restated rather than
something to reconcile. And **the defect is invisible on today's resolution**: anyone
re-running 6.6's experiment now would conclude there is nothing here.

## Decision

**The detector is removed from the path rather than pinned.** `mycelium.ingest.encoding`
decides what encoding a document's bytes are in, by a rule this repository owns:

1. a **byte-order mark** — the one encoding declaration carried in the byte stream itself;
2. an **encoding the document declares** — `<meta charset>`, `<meta http-equiv>`, or an XML
   declaration;
3. **UTF-8**, if the bytes are valid UTF-8;
4. **windows-1252**, the last-ditch fallback for legacy bytes;

first step that decodes the bytes wins, and if none does the document is a `ParseError`,
which the evidence lane quarantines. Every step is a function of the bytes alone.

It is deliberately **BeautifulSoup's own chain with the ambient step removed**, not a new
invention. That is what makes it reviewable — the behaviour it changes is exactly the
behaviour that was never ours — and it is why adopting it left the committed corpus
byte-identical. It departs from that chain in exactly one place, and in the author's
favour: step 2 scans the whole document, where HTML5 prescans 1024 bytes and bs4 looks at
2 KiB or 5 % of it. A browser stops early because it has a page to start painting; a
compiler has no such race, and a document that says what it is should be read as it says.

**The decoded text is handed on with a byte-order mark.** `Decoded.utf8_with_bom()`
re-encodes as UTF-8 and prefixes `EF BB BF`, and the docling adapter gives *that* to the
backend. A UTF-8 mark is the one encoding declaration that lives in the byte stream rather
than in the markup, so it changes no element, no attribute and no character — and
BeautifulSoup treats a sniffed mark as **definite**, ahead of everything else in its chain.
The detector is not agreed with; it is not asked. The mark is added only to bytes handed to
a parser: nothing stored carries one, which is BUG-0008's rule, still intact.

**What the bytes did not decide is recorded on the document, and nothing else is.** A
declaration that no codec answers to, a declaration that does not decode the bytes, a
fallback to windows-1252, and a UTF-8 decode that yields NUL characters — HTML cannot carry
one, so it is almost certainly UTF-16 with no mark — each add a warning to the KIR, which
the fidelity report carries verbatim. The ordinary case adds nothing.

Two reasons for that asymmetry, and they are the item's own third suggestion answered
rather than skipped. The item proposed recording *the detector's identity in the fidelity
report the way the parser's version already is* — a field. A field cannot go there:
ADR-0034 makes the report **a pure function of the KIR document**, so that anyone holding
the KIR blob can recompute it, and an encoding is not derivable from the KIR. The KIR's
`warnings` is where a parser's declared policies already live, and the report copies them
verbatim, so the fact reaches exactly where the item wanted it by the route the invariant
allows. And a note on *every* HTML document would say only what a reader holding the bytes
can recompute from a published, total rule — which is the shape of a signal that fires on
everything and is therefore read by nobody (ADR-0053).

**HTML only.** A DOCX is a zip whose parts carry their own encoding; decoding its bytes as
text would destroy it. The pandoc lane is untouched for a different reason: pandoc decodes
UTF-8 itself and refuses what is not, which is a fixed answer rather than an ambient one.

## Alternatives Considered

- **Declare a detector in the `ingest` extra** — the item's second suggestion, and
  BeautifulSoup even publishes `beautifulsoup4[charset-normalizer]` for it. Rejected on two
  measurements. It makes a detector *present*, not *chosen*: bs4 prefers `cchardet` and then
  `chardet` over it, so any environment holding one of those still overrides the
  declaration — including, exactly, the environment 6.6 created by accident. And the table
  above shows the answer moving **between versions of one detector**, so even a resolved,
  locked dependency would only narrow the ambiguity, not remove it. A pin that cannot pin
  the answer is worse than none, because it reads as a fix.
- **Pass an explicit encoding at the call site** — the item's first suggestion, in its
  literal form: hard-code UTF-8. Rejected: it is right for this corpus and wrong for the
  product. A document that declares windows-1252 and means it would be read as mojibake,
  and a BOM would land in the text. The rule keeps the document's own statements
  authoritative and only refuses to *guess* where it makes none.
- **Set `bs4.dammit.chardet_module = None` around the call.** The smallest possible change
  and it does close the path. Rejected: it mutates another package's module global, which is
  not thread-safe, is invisible to anyone reading our parser, and leaves the decode still
  defined by bs4's chain rather than by anything this repository states. The byte-order mark
  achieves the same through a documented, public property of the format.
- **Re-render the corpus with `--standalone` so every source declares `utf-8`.** It would
  close the corpus's exposure without touching the product. Rejected twice over: a full
  re-render is a deliberate provenance act with a cost table behind it (ADR-0039), and
  fixing the *instrument* to hide a defect in the *product* is backwards — a user's HTML is
  a user's HTML, and most of the web's undeclared documents look exactly like these.
- **Keep the detector as the last step before windows-1252**, so that only undeclared,
  non-UTF-8 documents depend on it. Rejected: it would have left the seven documents of this
  very corpus unaffected — they are valid UTF-8 — and therefore looks like a complete fix,
  while keeping an ambient input to the compiler on the one path where a wrong answer is
  hardest to notice.
- **Guess at UTF-16 when a UTF-8 decode yields NUL characters.** Rejected as a detector in
  miniature, which is the thing being removed. The case is reported instead, and the report
  says what it probably is.

## Consequences

- **An ingestion is reproducible from the bytes.** Two contributors with different packages
  installed project the same evidence. Proved rather than asserted: with `chardet` 5.2.0's
  answers bound, the corpus check now passes and the fake detector is consulted **0 times**,
  against 62 before.
- **The committed corpus did not move a byte** — `81 evidence documents match a fresh
  ingestion` — so no regeneration, no re-carry of judgements, no baseline touched.
- **`tools/build_ingested_corpus.py --check` now means what its docstring says.** *"A
  difference is always a change in ingestion: a parser, the projector, or the fidelity
  budget"* was not true while an unrelated package could cause one; it is now, and the
  docstring says why.
- **One case reads worse than before**, and it is named: an undeclared, non-UTF-8, non-
  windows-1252 document — undeclared Shift-JIS, say — was sometimes read correctly by a
  detector and is now read as windows-1252. It arrives with a warning on the document
  instead of in silence, and the remedy is the one the web already has. If a real corpus
  ever needs more, the trigger is a document that needs it, not a hypothesis.
- **A test that cannot pass vacuously.** `tests/test_ingest_encoding.py` binds a hostile
  detector, asserts that BeautifulSoup *does* misread the fixture under it, and only then
  asserts the KIR is unchanged — because a guard whose premise has quietly stopped holding
  is the defect BUG-0020 records. A second test pins the property that made this fix free:
  every committed HTML source is plain UTF-8, so a future re-render that changed that would
  say so out loud.
- **A limit, stated.** The rule covers the HTML lane, which is where the ambient decode
  was. It is not a general audit of what else an importable package can decide inside a
  dependency: ADR-0117's reachability rule remains the only thing standing between this
  project and the next instance, and it is a rule about *our* dependency list, not about
  docling's.

## References

- `src/mycelium/ingest/encoding.py`, `src/mycelium/ingest/parsers/docling.py`,
  `tests/test_ingest_encoding.py`.
- [BUG-0032](../bugs/2026/09/BUG-0032-an-importable-package-changes-what-html-ingestion-projects.md)
  — the defect, the per-version table, and the replay.
- Re-runnable: `python tools/build_ingested_corpus.py --check`, and
  `uv run pytest tests/test_ingest_encoding.py -q`.
- `bs4/dammit.py` — the import-time binding and `EncodingDetector.encodings`, the chain this
  rule is a copy of with one step taken out.
