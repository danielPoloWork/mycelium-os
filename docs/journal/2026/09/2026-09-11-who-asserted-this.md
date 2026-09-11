# 2026-09-11 — who asserted this (roadmap 5.7)

- **Session scope:** roadmap 5.7 — ingested documents are not in the graph; make them so
  (spec 03 §§3.1, 6; D-014, D-017; threat model B11).
- **PR:** #106 (`fix/resolve-links-in-ingested-documents`). Follows #105, merged as `e447831`.
- **Milestone 5:** 5.7 done; 5.18 filed. Remaining open: 5.9–5.18.
- **ADR:** [ADR-0079](../../../adr/0079-resolve-an-ingested-documents-links-through-its-source-tree-and-never-call-them-authored.md).

## The item's diagnosis was half right, and the other half was the finding

5.7 was filed at 4.10 with a number and an explanation. The number: the Markdown corpus
compiles many more edges than its ingested twin. The explanation: relative links do not survive
re-projection into a flat `knowledge/evidence/` tree, so *"the fix is a resolution question
rather than a parsing one"*.

Re-measured before touching anything, because the numbers in the item predate 5.2:

| | authored | ingested twin |
|---|---:|---:|
| internal links reaching the compiler | 339 | 30 |
| edges | 321 | 29 |
| unresolved-link warnings | 54 | 30 |

**The resolution half is real.** Eighteen of the thirty name a document in the corpus and
resolve against nothing, because they are written in the *source* tree's coordinates while the
projection sits in a flat evidence tree under a slugified name. Fixing that is the feature:
each projection carries its source URI, so a link inside it is joined to the source's own
directory and looked up among the corpus's sources. Extension-insensitively — a page rendered
to HTML keeps the `.md` hrefs it was written with, and the source beside it is `.html`, so the
stem is the part that identifies it in both trees. That is 29 → 54 edges and 30 → 12 warnings,
the twelve being links to sources this corpus never vendored, unresolved in the authored twin
too.

**The parsing half is not a bug at all.** 339 becomes 30 because the projector renders
reference nodes *by nobody* — deliberately, as threat-model control B11. Ingested links are
absent from the graph by design, and no amount of resolution work changes that. So what are the
thirty?

## They were forgeries

They are not projected links. They are link *syntax that arrived as text*: an HTML page whose
docling output flattened an anchor into prose, a DOCX's `[[tool.uv.index]]` — a TOML
array-of-tables header that lost its code fence — projected verbatim and then re-parsed by the
compiler as a genuine Markdown link or wikilink.

The threat model has two STRIDE rows saying this cannot happen, one of them marked *"Asserted
by test"*. The test ingests **Markdown**, whose parser recognises `[[secrets]]` and hands back
a reference node for the projector to drop. HTML, DOCX and PDF have no wikilink syntax for a
parser to recognise, so those characters are ordinary prose. One fixture paragraph:

```
authored  links_to  doc:knowledge/evidence/hostile-html-….md -> doc:knowledge/verified/api.md
```

An acquired document, asserting an `authored` edge into the knowledge graph. And the entity
stage had it too, from the same cause: an inline `#production` in a projected PDF minted an
`authored` entity, against a row claiming *"a projected document has none of them"*.

## The fix is one rule, not an escape hatch

The obvious repair is to escape reference syntax in the projection. I did not, for two reasons.
It breaks the projector's contract — *the text is verbatim; only the syntax is regenerated* —
and the fidelity property that every node's text survives. And it answers the wrong question.
The issue is not what the characters look like. It is **who asserted them**, and the record has
a field for that.

So: an edge or entity derived from a document whose `origin` is `ingested` resolves
`extracted`, never `authored`. That is spec 03 §6's own sentence, enforced where the assertion
is *made* rather than where the text is written. An entity a human also declared stays
`authored` and the ingested document contributes a `doc_ref`, which is exactly what it
evidences. Synthesized documents stay authored on purpose: the lane refuses to write one at all
unless its citations resolve, so those are deliberate.

The pleasing part is that the security fix and the feature are the same change. Ingested
references can now enter the graph precisely *because* there is a word for what they are.

## What I refused to do, and why it is 5.18

Recovering the other 309 links is tempting and I did not attempt it. Those references exist
only in the tier-1 KIR, and `.mycelium/` is disposable and gitignored — a clone has the
projections and not the custody store, so a graph folded from it would differ between the
machine that ingested and every machine that did not. That is an NFR-1 determinism break in the
manifest's `edges` digest, not a detail. Carrying them properly means putting them in **tier 2**,
which is a projection-format change: a new frontmatter key against a field set spec 03 §3
closes, a regeneration of the whole vendored corpus with its carried case set and G3 baseline,
and the reproduction check moving with it. Filed with the argument and the ceiling — 309 is
what could be recovered, not what would resolve.

## Noted, not fixed

The docling HTML backend hands back link targets with Windows separators on Windows
(`..\\..\\guides\\integration\\bazel.md`). It changes no output today, because those links are
not projected, and the new stem comparison normalises separators anyway. Worth knowing before
anyone builds on parser link targets.

## Lesson

A control is only as strong as the format it was tested on. B11's rule — the projector drops
reference nodes — is true, tested, and was verified against the one input format that produces
reference nodes to drop. Ingestion exists for the other three. The test passed for four
milestones while the property it claimed was false everywhere it mattered, and the fixture that
broke it is one paragraph long.
