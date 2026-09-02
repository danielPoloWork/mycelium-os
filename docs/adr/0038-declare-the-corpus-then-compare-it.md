# ADR-0038: Declare what the corpus contains, then compare it — a report cannot corroborate itself

- **Status:** Accepted
- **Date:** 2026-09-02
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.7; RFC-0001; spec 02 §5; spec 03 §4; spec 06 Phase 2 exit gate;
  [ADR-0012](0012-adopt-the-g6-determinism-gate.md),
  [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md),
  [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md);
  [BUG-0016](../bugs/2026/09/BUG-0016-docx-footnotes-vanish-unreported.md)

## Context

Milestone 4's first exit gate is **zero silent element loss on the fixture corpus** — the
spec's words are "every element represented / opaque / dropped-by-policy /
failed-and-reported". Roadmap 4.3 built the accounting: `mycelium.ingest.fidelity` sorts
every KIR node into represented, degraded or lost, and the report is a pure function of the
KIR so anyone holding the blob can recompute it.

That report is honest about everything it can see, and it has a blind spot that no amount
of care inside it can remove. **It is computed from the KIR, so it can only account for
what became a node.** A parser that drops a table before emitting anything produces a report
saying 100 % represented, 0 lost. Asking the report to prove nothing was lost is asking a
witness to corroborate itself.

Nothing in the project closed that gap. Every check ingestion had — the fidelity report, the
projection round-trip, the loss budget, the per-parser tests — is computed from the parse.
A parse that lost an element and a source that never had one are indistinguishable to all of
them.

This is not hypothetical. The first corpus assembled under this ADR found, on its first run,
that docling's DOCX backend never reads `word/footnotes.xml`: a footnote's body reached no
KIR node, and every artifact downstream agreed the document was complete
([BUG-0016](../bugs/2026/09/BUG-0016-docx-footnotes-vanish-unreported.md)).

## Decision

**The corpus carries a declaration, written by a person against a source they can read, and
the gate compares it with what each engine produced. Every difference is either recorded
with a reason a reviewer approved, or it fails.**

The declaration is per **family** — one Markdown source and the DOCX, HTML and
reStructuredText pandoc renders from it are four fixtures and one declaration — stated in
KIR node kinds, because that is the only vocabulary the routes have in common. Its `note`
says how the numbers were arrived at, so checking the claim means reading the source rather
than trusting a generator.

`tests/fixtures/ingest/inventory.json` is half human and half machine, and the split is
load-bearing:

| Field | Written by | Meaning |
|---|---|---|
| `families[*].declared` | a person | what the source contains |
| `families[*].note` | a person | how it was counted |
| `fixtures[*].deviations` | a person | which route differences are approved, and why |
| `fixtures[*].parser` | the tool | which parser actually ran |
| `fixtures[*].inventory` | the tool | what it produced |

`tools/update_ingest_inventories.py` regenerates the machine half and **never touches the
human half**. A tool that could rewrite a declaration would let a regression re-bless
itself: the parser drops a table, the tool records that it drops a table, and the gate
agrees with the defect.

Three checks run against that file, and they fail for different reasons:

1. **Unexplained difference** — an element the declaration has and the parse does not (or
   the reverse), with no recorded reason. This is the exit gate.
2. **Stale reason** — a deviation still recorded for a kind that now agrees. An approval
   left standing over changed behaviour is how a gate's exception list grows until the gate
   means nothing.
3. **Changed observation** — any other difference from the committed inventory, the golden
   discipline ADR-0012 established for G6: a behaviour change is *reviewed*, not absorbed.

The inventory counts **reference nodes** (links, images, wikilinks, embeds, tags), which the
fidelity report excludes from its denominator. A vanished link is a vanished edge even
though its text survives inside its parent block, and a loss *ratio* is the wrong instrument
for noticing it. They stay out of the disposition totals, so the two artifacts still agree
on how many elements a parse had.

**BUG-0016 is fixed in the same change**, not recorded as an approved deviation. Shipping the
corpus with a live silent loss written down as approved would enshrine exactly what the gate
exists to forbid. The engine's blind spot is not ours to fix; making it visible is, so the
adapter counts the notes the container declares and records each one docling did not surface
as an opaque `lost` element.

## Alternatives Considered

- **Trust the fidelity report; add more fixtures.** The cheapest option, and it was the
  status quo. Rejected because more fixtures measured by the same instrument do not add
  information about what the instrument cannot see: BUG-0016 was already reachable through
  the existing suite and no number anywhere was wrong.
- **Make the Markdown route the reference and compare the others to it.** No hand-authoring
  at all, and every deviation still visible. Rejected as circular: markdown-it dropping
  something would move the reference, and the corpus would ratify the loss. It also happens
  to be wrong here — markdown-it is the route that *cannot* see footnotes.
- **Declare per fixture rather than per family.** More precise, and it would have avoided
  deviations for format differences. Rejected because it multiplies the hand-authored
  numbers by four and turns the reviewer's job into checking a generator instead of reading
  a document — the four routes' differences are then invisible again, which is the
  information the corpus exists to surface.
- **Assert the loss ratio instead of the counts.** One number per fixture, easy to review.
  Rejected: a ratio cannot express "the table is gone", which is the failure mode. It is
  also the exact instrument that reported BUG-0016 as perfect.
- **Record BUG-0016 as an approved deviation and file the fix.** Smaller change, and
  defensible as scope discipline. Rejected: an approved deviation is a statement that the
  difference is acceptable, and silent loss is not — the corpus's first act would have been
  to bless the thing it was built to catch.
- **Parse `word/footnotes.xml` with `xml.etree` to count notes.** The obvious way. Rejected
  because the part is untrusted input and ElementTree expands internal entities — the
  billion-laughs shape `hostile/laughs.docx` exists for (ADR-0033). Counting opening tags
  needs no parser, so none is exposed.

## Consequences

- **The exit gate is mechanical.** "Zero silent element loss on the fixture corpus" is now
  a test that names the kind and the fixture when it fails, rather than a claim in a
  roadmap line.
- **Route differences became documentation.** Twenty-one deviations are recorded across the
  corpus, each a true sentence about a format — pandoc's DOCX writer flattens a definition
  list to styled paragraphs; its HTML writer renders a footnote as a trailing `<ol>` with
  two anchors; docling emits an image's alternative text as a paragraph of its own. That
  knowledge existed nowhere before and was rediscovered by hand every time someone looked.
- **A defect the whole existing suite could not see** was found on the corpus's first run,
  and is fixed with its own ledger record.
- **Adding a parser or a format now has a cost**: a declaration, and a reason for every
  route difference. That is the intended cost. The gate's value is exactly the effort of
  writing down what you believe before measuring it.
- **A fixture nobody declared is caught too** — the corpus directory and the inventory are
  asserted to agree, so forgetting to declare a new file cannot leave it silently untested.
- **The corpus grew** by an `elements` family (the kinds `source.md` never reached), a
  `profile` family for the Markdown-only vocabulary, and a two-page PDF whose second page
  has no text layer — one parse producing both a page locator and an opaque `lost` node.
- **The fixture generator no longer passes `--sandbox`**, which is the opposite of the rule
  the pandoc *parser* follows. The sandbox fences an engine reading untrusted bytes at build
  time; the generator reads a source in this repository, by hand, and the sandbox stopped it
  embedding the image it is supposed to embed — which would have recorded a generator
  restriction as a parser difference.
- **What this does not do:** it says nothing about *retrieval* over ingested documents. The
  M4 exit gate's third clause — an ingestion-heavy corpus joining the eval set — needs
  judged cases, which is a different kind of work, and is filed as roadmap 4.10 rather than
  folded in here.

## References

- Spec 02 §5 (ingestion lanes, quarantine-not-abort); spec 03 §4 (KIR kinds, `opaque`);
  spec 06 Phase 2 exit gates.
- [ADR-0012](0012-adopt-the-g6-determinism-gate.md) — the reviewable-golden discipline this
  reuses, and the rule that the gate and the re-bless tool share one module.
- [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md) — the fidelity report, its
  three buckets, and the reference-node exclusion this inventory deliberately does not make.
- [BUG-0016](../bugs/2026/09/BUG-0016-docx-footnotes-vanish-unreported.md) — what the corpus
  found first.
