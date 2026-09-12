# ADR-0090: Project a source's links as links, now that the compiler knows who asserted them

- **Status:** Accepted
- **Date:** 2026-09-12
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §5, spec 03 §§3, 6
- **Related:** [ADR-0079](0079-resolve-an-ingested-documents-links-through-its-source-tree-and-never-call-them-authored.md)
  (the rule that makes this safe, and the item that filed it), [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md)
  (the projector's contract, amended here), [ADR-0018](0018-build-the-graph-from-authored-links.md)
  (link extraction and resolution, reused unchanged), [ADR-0082](0082-open-the-frontmatter-contract-by-one-key-and-make-the-drift-unlandable.md)
  (what opening the field set costs — the alternative not taken), [ADR-0039](0039-measure-what-projection-costs.md)
  (the carried case set that must not move), [ADR-0045](0045-ask-the-documents-whether-two-runs-are-comparable.md)
  (the fingerprints that prove it did not), [ADR-0006](0006-adopt-markdown-it-adapter-and-kir-node-fields.md)
  (why a reference node has a label and no offset); spec 02 §§2, 5, spec 03 §§3, 3.1, 4, 6, spec 05 §3.3;
  D-004, D-014, D-017, D-020, D-021; threat model B11; roadmap 4.3, 5.7, 5.18

## Context

Roadmap 5.7 put an ingested corpus into the graph and measured what it had to work with:
the authored uv corpus carries 339 internal links, its ingested twin **30**. The gap was not
resolution. The projector rendered reference nodes *by nobody* — threat-model control B11 —
so an ingested document's real references lived only in its tier-1 KIR, and the thirty that
reached the compiler were link syntax that had survived as prose. 5.7 refused to derive the
edges from tier 1, correctly: `.mycelium/` is disposable and gitignored, a clone has the
projections and not the custody store, and a graph folded from custody would differ between
the machine that ingested and every machine that did not — an NFR-1 break in the manifest's
`edges` digest. It filed 5.18 as *a projection-format question with three parts*: where the
references go, that they stay `extracted` whatever shape they take, and what regenerating
every projected document costs. And it asked for the win to be measured before it was paid
for — 309 was the ceiling, not the yield.

Three measurements, taken before a line was written.

**What tier 1 holds.** Parsing the 81 vendored sources again: **509** reference nodes — 507
links and 2 images; 419 from HTML, 90 from DOCX, none from the PDFs' text layer. 199 point
outside the corpus, 276 inside it (207 distinct targets), 34 are in-page fragments. They sit
in paragraphs (433), list items (74) and two headings.

**Whether a reference can go back where it stood.** KIR gives a reference node its label and
its target and no offset — the locator is line-grained (spec 03 §4), and the adapters
flatten inline content on purpose (ADR-0006). So placing a link back means *finding* its
label in the block's text. Measured: **507 of 509** are found, from a cursor that advances
with each placement; the two that are not have no label at all — anchors around images in
`index.html`. And the compiler flattens a label back to its words, so a block whose link is
rendered as `[label](target)` re-parses to *exactly the text it had*: the chunk, its digest,
its anchor and its BM25 score cannot move.

**What a frontmatter key would cost.** The other home — a tool-owned `references:` list —
needs a change to the field set spec 03 §3 closes (ADR-0082 opened it by one key and wrote a
lint to hold the line), loses the chunk a link sits in (an edge's `provenance.anchor` would be
the document, or a section at best), and leaves a reader of the projection with no links at
all. It has one merit: the body does not change. The measurement above says the body does
not need to.

One defect surfaced by the first measurement and settled before anything else: on Windows,
159 of the 507 targets were spelled with backslashes. docling types a relative `href` as a
`Path`, the adapter called `str()` on it, and the string was the ingesting machine's. Noted
at 5.7 as changing no output; the moment a target is written into a committed projection it
changes output, and the reproduction check runs on Linux (BUG-0023).

## Decision

**A reference is syntax, and the projector regenerates it where it stood.** A link, wikilink
or embed the parser found is rendered back into the block that carries it — `[label](target)`,
`[[target|label]]`, `![[target]]` — around the very words the block's text already holds.
This is the projector's own contract applied to one more construct: *the text is verbatim;
only the syntax is regenerated* (ADR-0034). The label is located in the block's text from a
cursor that advances with each placement, because references are emitted in document order
and the same words may be linked twice. Images are not rendered — a picture's target is a
parser's internal reference and its alt text is already prose — and tags need nothing, their
`#` is already text.

**A reference that cannot be placed is dropped and counted, never appended.** Appending would
put the label into the block twice, and the block's text is the one thing this rendering must
not move. `Projection` reports `references` and `references_dropped`; `mycelium ingest`
prints them.

**The compiler is unchanged, and that is the design.** The rendered link is read by the same
extraction as an authored one (ADR-0018), resolved through the projection's source tree
(ADR-0079), and typed `extracted` because the document's `origin` is `ingested` (ADR-0079's
rule, which is what makes this safe). Its `provenance.anchor` is the chunk it sits in. Nothing
in spec 03 §3's field set changes; nothing in the store changes.

**Control B11 is restated, not weakened.** "The projector emits text, never assertions" was
the control until 5.7 found it covered reference *nodes* only and moved the guarantee to
where an assertion is made. With the guarantee there, rendering references back is not a hole
— it is the projector no longer paying a fidelity cost for a control that had already moved.
The threat model's B11 row and its forgery STRIDE row say so, and the property is asserted end
to end: a Markdown source containing `[[api]]` is ingested, projected with the wikilink intact,
built, and produces one `extracted` edge and no authored one.

**The adapter spells a relative hyperlink the way the source did** (`as_posix()` for a `Path`,
`str()` for a URL), so the same bytes project identically on every platform in the matrix.

**The vendored ingested corpus is regenerated in this change** — 67 of its 81 projections change,
the other fourteen carried no references — because the
reproduction check compares the committed tree against a fresh ingestion and either both move
or neither does. What regenerating cost was measured rather than feared, and the measurement
corrected the design's own prediction: the carried case set reproduces byte-for-byte, 584 of
the corpus's 585 chunks keep their text to the byte, and one does not — the consequences below
put the exception, its cause and what it moved on the record.

## Alternatives Considered

- **A tool-owned `references:` frontmatter key**, the home 5.18 assumed. Rejected on the
  measurement: it spends a spec change on a problem the body solves for free, it cannot say
  which chunk a link sits in, and it leaves the projection a document whose links a reader
  cannot follow. Kept in mind as the fallback if a corpus ever produced labels that could not
  be placed; this one produced two, both label-less.
- **Derive the edges from tier 1.** Rejected at 5.7 and still: it makes the graph a function
  of which machine ingested, which is an NFR-1 break in a committed digest.
- **Append unplaceable references at the end of their block**, so nothing is lost. Rejected:
  the label would appear twice in the chunk text, which moves the chunk, the carried anchors
  and the score — for two references in five hundred, both of which have no label to lose.
- **Render images too**, for symmetry. Rejected: docling's picture target is `#/pictures/0`,
  a reference into its own document model, and pandoc's is a path inside a container nobody
  has; a broken image in every projection helps no reader and no edge (`_LINK_KINDS` never
  included images).
- **Render a wikilink whose label needs a `|` inside a table cell**, escaping the pipe.
  Rejected: whether a wikilink parser reads an escaped pipe is a bet on someone else's parser,
  and losing it would put `[[target\|label]]` into a chunk as text. Such a reference is
  dropped and counted; plain links in cells are carried.
- **Keep the projector as it was and stop at 5.7's 54 edges.** The status quo. Rejected by the
  numbers below: the ingested twin was a corpus whose documents did not refer to each other,
  and the reason was a control that no longer controlled anything.

## Consequences

- **The win, measured after.** On `uv-docs-ingested`: links reaching the compiler **30 → 560**
  (the authored twin: 657, external links included); edges **54 → 366**, of which 293
  `links_to` — every one carrying the chunk it was found in — 61 `part_of`, 12 `defines`;
  305 of the 366 `extracted`. Unresolved-link warnings 12 → 42, all forty-two naming sources
  the corpus never vendored (`reference/settings.md`, `reference/cli.md`, `reference/environment.md`),
  the same family as the authored twin's 54. The twin holds 137 distinct link targets to the
  authored corpus's 149.
- **One chunk moved, and it found a defect older than this item.** 584 of 585 chunks re-parse
  to the text they had. The exception is `dependencies-docx-d90e9be4.md`, lines 741–768: an
  earlier paragraph *begins* with a literal ```` ```toml ```` — a code block flattened into
  prose upstream, smart quotes and all — so the compiler opens a fence there, finds no closing
  partner, and reads the heading and prose after it as code. Inside code a rendered
  `[label](target)` stays literal instead of flattening to its label, which is the only way
  this rendering can move a chunk's text. Four of the 81 projections carry such a region
  ([BUG-0024](../bugs/2026/09/BUG-0024-prose-that-opens-a-fence-swallows-the-rest-of-a-projection.md)); the repair is the escape the chats projector already applies to its
  own two shapes (ADR-0077), it moves those four documents' chunk boundaries, and it is
  roadmap 5.22 rather than a paragraph here.
- **What that one chunk moved.** Both fingerprints of `uv-docs-ingested`; on its release set
  one case, `u-1021` 0.3155 → 0.3333 (`exact` 0.8631 → 0.8667, overall 0.6370 → 0.6378), and
  nothing on its dev set. The incumbent moved more: grep ranks by term counts without length
  normalisation (ADR-0031), and a 28-line code chunk that now holds link targets outranks the
  judged passage for several queries — `exact` 0.549 → 0.586, `fact` 0.537 → 0.498,
  `relationship` 0.534 → 0.440, `symbol` 0.473 → 0.387, overall 0.5217 → 0.4865. The product's
  lead on that set widens from +0.115 to +0.151 **for a reason that is not a product
  improvement**, stated here so nobody reads it as one; 5.22 is where the chunk becomes what it
  should be and the numbers are measured again.
- **The ingested baseline is re-blessed, both retrievers, and gate G2's verdict re-recorded.** A
  bless rides with the change that occasions it (ADR-0056), and the change here is the corpus.
  In the re-recorded verdict `uv/dev`, `uv/release` and `uv-ingested/dev` reproduce
  byte-identically, `uv-ingested/release` moves by exactly that case on the lexical arm (hybrid
  0.6094 unchanged), and `ours` moves with its own corpus as it does on every pull request. The
  `lexical` default stands.
- **A tool that reads like a check is not one.** `stamp_baseline_fingerprints.py --check`
  verifies that fingerprints are *present*; it compares nothing that is already there, and this
  session read its *already carries every fingerprint* as *unmoved* until gate G2's currency
  test said otherwise. Comparison is G3's job at evaluation time. Noted rather than fixed, and
  the ADR's own first draft carried the misreading.
- **What did move is on the record.** 67 evidence documents under
  `eval/corpora/uv-docs-ingested/knowledge/evidence/`, links now inline; the manifest's
  `documents` and `chunks` artifact digests for that corpus (link nodes joined the chunks'
  `kir_nodes`; the chunk *digests*, which are over text, did not, bar the one above);
  `stats.links_out` on every ingested document; `eval/g2-verdict.json` and the ingested
  corpus's `eval/baselines/release.json`. Gate G6 is untouched: the fixture's evidence document
  is hand-written.
- **A reader of a projection sees the source's links.** Relative targets are the source tree's
  and will not open from `knowledge/evidence/` in a file browser; that is the coordinate
  system the compiler resolves them in (ADR-0079), and rewriting them would be interpretation
  rather than projection.
- **`mycelium ingest` reports references carried and dropped**, in the human summary and the
  JSON entry, so a corpus whose labels cannot be placed says so on the day it is ingested.
- **Known limits, on the record.** A destination with a space is percent-encoded on the way
  back through the compiler (`a b.md` → `a%20b.md`), a CommonMark normalisation this projector
  does not undo. An in-page `[text](#section)` link is carried and resolves as an authored one
  would. Docling's item-level and child-level hyperlinks can both name one target; they land in
  one chunk and fold to one edge.

## References

- Spec: `.draft-specs/02-architecture.md` §2 (the build never writes tier 2; `mycelium ingest`
  may), §5 (the evidence lane, "verbatim"); `.draft-specs/03-data-model.md` §3 (the closed
  field set, untouched), §3.1 (the profile's link syntax), §4 (the line-grained locator), §6
  (the status discipline).
- Threat model: B11 and its elevation-of-privilege row, restated.
- Bug ledger: [BUG-0023](../bugs/2026/09/BUG-0023-docling-hyperlinks-carry-the-ingesting-machines-separator.md).
- Re-runnable: `python tools/build_ingested_corpus.py --check`,
  `python tools/build_ingested_cases.py --check`, `python tools/stamp_baseline_fingerprints.py --check`,
  then `mycelium build --no-pin eval/corpora/uv-docs-ingested` and
  `mycelium neighbors knowledge/evidence/aws-html-ea633568.md`.
- Tests: `tests/test_ingest_projection.py` (placement, escaping, the per-engine target
  invariant, the wikilink and embed round trips), `tests/test_graph_ingested.py` (acquired HTML
  to a typed edge with its anchor), `tests/test_ingest_parsers.py` (BUG-0023).
