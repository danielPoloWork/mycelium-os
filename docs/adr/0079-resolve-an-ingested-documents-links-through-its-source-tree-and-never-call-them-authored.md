# ADR-0079: Resolve an ingested document's links through its source tree, and never call them authored

- **Status:** Accepted
- **Date:** 2026-09-11
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §6, D-014, D-017
- **Related:** [ADR-0018](0018-build-the-graph-from-authored-links.md) (the extraction /
  resolution seam this extends), [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md)
  (the projector whose control this restates), [ADR-0074](0074-give-every-edge-type-a-derivation-or-a-reason-it-has-none.md)
  (the typed-edge vocabulary), [ADR-0076](0076-let-the-corpus-declare-its-entities-and-refuse-to-guess-the-rest.md)
  (the entity stage this applies the same rule to), [ADR-0015](0015-adopt-content-addressed-incremental-builds.md)
  (the stage-version discipline the bump follows), [ADR-0073](0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md)
  (the first `extracted` edges); spec 02 §5, spec 03 §§3.1, 6, spec 05 §3.3; D-014, D-017,
  D-020, D-021; threat model B4, B11; roadmap 4.10, 5.7, 5.18

## Context

Roadmap 5.7 was filed at 4.10 with a measurement and a diagnosis. The measurement: the
Markdown corpus compiles many edges and its ingested twin almost none, so `mycelium_neighbors`
returns nothing for an ingested document and graph expansion has nothing to walk. The
diagnosis: *"the parser reads a link whose target is a path, the projector writes it into a
flat `knowledge/evidence/` tree, and the resolver meets a path that names nothing"*, and
therefore *"the fix is a resolution question rather than a parsing one"*.

Re-measured today on the two vendored corpora, the numbers have moved (5.2 added edge types)
and the diagnosis turns out to be half right and half wrong.

| | authored corpus | ingested twin |
|---|---:|---:|
| documents | 81 | 81 |
| internal links reaching the compiler | 339 | 30 |
| edges | 321 | 29 |
| unresolved-link warnings | 54 | 30 |

**The resolution half is real.** Of the 30 internal links an ingested document actually
carries, 18 name a document in the corpus and resolve against nothing, because they are
written in the *source* tree's coordinates — `../../concepts/resolution.md`, relative to
`sources/guides/`— while the projection of that document landed in a flat
`knowledge/evidence/` tree under a slugified, digest-suffixed name. The other 12 are correct
misses: `reference/settings.md` is not vendored in either corpus.

**The parsing half is not what the item assumed, and the difference matters.** 339 internal
links become 30 not because they fail to resolve but because they never reach the compiler:
the projector renders reference nodes *by nobody*, deliberately, and that is threat-model
control **B11**. An ingested document's links are absent from the graph **by design**.

So the 30 that survive are not projected links at all. They are link *syntax that arrived as
text* — `[the settings](../../reference/settings.md)` and `[[tool.uv.index]]`, the latter a
TOML array-of-tables header from a DOCX whose code fence did not survive — projected verbatim
and then re-parsed by the compiler as genuine Markdown.

Which exposes the real defect. The threat model carries two STRIDE rows saying this cannot
happen, one of them marked *"Asserted by test"*:

> Ingested content forging an *authored* assertion — a wikilink, an embed, a tag — by being
> projected into the authored tree … The projector renders only section-level, non-reference
> nodes, so wikilink and embed syntax cannot survive into a projected document.

The test that asserts it ingests **Markdown**, whose parser turns `[[secrets]]` into a
reference node the projector then drops. Every format ingestion exists for — HTML, DOCX, PDF —
has no wikilink syntax for a parser to recognise, so those characters are ordinary prose. A
one-paragraph fixture proves the hole: an ingested document containing `See [[api]]` produced

```
authored  links_to  doc:knowledge/evidence/hostile-html-….md -> doc:knowledge/verified/api.md
```

The entity stage had the same hole from the same cause: an inline `#production` in a projected
PDF's prose minted an **authored** entity, against a STRIDE row claiming *"a projected
document has none of them"*.

## Decision

**An ingested document's references become edges — and every one of them is `extracted`.**
Two changes, one rule.

**Resolution learns the source tree.** Each document's `provenance.source_uri` rides in its
per-document graph state, and `CorpusIndex` gains an index from *source stem path* to the
document projected from it. A link in a document that has a source URI is joined to that
source's own directory, `.` and `..` applied textually, the extension dropped, and looked up
there. It sits **below** the corpus's own paths — a link that already names a document in this
corpus means what it says — and **above** basename and alias, because it is a path match and
those are heuristics. The extension is dropped because the two ends rarely agree on one: a
page rendered to HTML keeps the `.md` hrefs it was written with, and the source beside it is
`.html`. The stem is what identifies the document in both trees.

**Status follows the document's origin, not the syntax.** An edge derived from a document
whose `provenance.origin` is `ingested` is `extracted`; everything else stays `authored`. The
same rule applies to the entity stage: an entity only an ingested document declares is
`extracted`, and one a human also declared stays `authored` with the ingested document
contributing a `doc_ref`. Synthesized documents stay `authored` on purpose — the synthesis
lane refuses to write a document at all unless its citations resolve (D-020), so those are a
deliberate assertion, not a finding.

This is spec 03 §6's own sentence — *"extracted edges never gain authored status silently"* —
enforced where the assertion is **made** rather than where the text is written. It is also why
the fix is not "escape reference syntax in the projection": that would break the projector's
verbatim-text guarantee (ADR-0034) to solve a problem that is not the projector's. The
projector's job is to emit the source's content faithfully. Deciding what an assertion in that
content is *worth* is the compiler's.

**`EXTRACT_STAGE_VERSION` 3 → 4**, because the per-document state now carries a field it did
not. Without the bump a store built before this would keep resolving ingested links against an
empty source URI on every document the build had no other reason to touch — the silent
staleness ADR-0015's version discipline exists to prevent.

**`part_of` stays `authored`**, deliberately and narrowly. It says a section belongs to its
document, which this compiler derives from that document's own headings and verifies against
them; it is a fact about our tree, not a claim made by a source. Re-typing it would be churn
without an argument.

## Alternatives Considered

- **Escape reference syntax in the projection**, so `[[api]]` becomes `\[\[api\]\]` and never
  compiles to anything. Rejected on two grounds. It breaks the projector's contract — *the
  text is verbatim; only the syntax is regenerated* (ADR-0034) — and the fidelity property
  that every node's text survives into the projection. And it fixes the symptom at the wrong
  layer: the question is not what the characters look like, it is who asserted them, which is
  exactly what `status` is for.
- **Refuse to resolve an ingested document's links at all**, leaving the graph as it was.
  Maximally safe, and it is roughly what the product did by accident. Rejected: it makes an
  ingested corpus a set of isolated documents forever, which is the product gap 5.7 was filed
  about, and it throws away a true fact — the source really does refer to that document —
  because we lacked a word for it. We have the word.
- **Emit `references` rather than `links_to` for an ingested document's links.** Rejected: the
  assertion is a link, and its trust is carried by `status`. Encoding the same distinction in
  two fields lets them disagree, and D-014's vocabulary is an anti-sprawl valve.
- **Derive the edges from the tier-1 KIR instead**, which holds the links the projector
  dropped and would recover all 339 rather than 30. Rejected here for a reason worth writing
  down: `.mycelium/` is disposable and gitignored, so a clone has the projections and not the
  custody store, and a graph folded from it would differ between the machine that ingested and
  every machine that did not — a determinism break (NFR-1) in the manifest's `edges` digest.
  Recovering those links needs them carried in tier 2, which is a projection-format change
  with its own compatibility and trust questions. Filed as roadmap 5.18.
- **Resolve a directory-style link (`../concepts/projects/`) to `…/index`.** Plausible for
  web-rendered corpora and implemented by nobody here, because the vendored corpus contains
  none and an unmeasured branch is a guess. It joins when a corpus produces one.
- **Key the source index on the full filename rather than the stem.** Rejected on the
  measurement: it resolves none of the 18, because every link in the vendored corpus names
  `.md` while the sources beside them are `.html`, `.docx` and `.pdf`.

## Consequences

- **The ingested corpus joins the graph.** On `uv-docs-ingested`: **29 → 54 edges** and
  **30 → 12 unresolved-link warnings**, the 12 being links to sources the corpus never
  vendored, which are unresolved in the authored twin too. 28 of the 54 are `links_to`, all
  `extracted`. `mycelium_neighbors` now answers on an ingested document, and graph expansion
  (5.3) has something to walk if it is ever switched on.
- **The authored corpora do not move.** `uv-docs` stays at 321 edges and 54 warnings; this
  repository stays at 669, all `authored` apart from the symbol stage's `defines`. A document
  with no source URI cannot reach the new branch, which is what keeps this invisible to a
  corpus that never ingested anything.
- **A live forgery is closed**, and the threat model now describes the control it actually
  has. Both STRIDE rows are restated rather than quietly amended: the projector's rule covers
  reference *nodes*, the compiler's rule covers everything, and the second is where the
  guarantee lives.
- **A consumer can tell the difference, and must.** `mycelium_neighbors` has always returned
  `status` per edge (spec 05 §3.3); until now every edge on every corpus was `authored` except
  the symbol stage's, so nothing exercised it. An agent that treats `extracted` as "the corpus
  claims this" is reading an ingested source's assertion as a human's.
- **The first build after upgrading recompiles every document** (the stage bump), through the
  parse and chunk caches, which is seconds on these corpora.
- **Gate G6 is untouched** — the fixture corpus has no ingested documents, so the golden does
  not move, and no judged case, baseline or eval corpus is affected.
- **Two things found and named, not fixed.** The docling HTML backend hands back link targets
  with Windows path separators on Windows (`..\..\guides\integration\bazel.md`); it changes no
  output today because those links are not projected, and `source_stem` normalises separators
  anyway. And a DOCX's TOML fragment `[[tool.uv.index]]`, stripped of its code fence, is read
  as a wikilink — nine of them in the vendored corpus, now correctly `extracted` and correctly
  unresolved.

## References

- Spec: `.draft-specs/03-data-model.md` §3.1 (wikilink resolution), §6 (the edge record, the
  status discipline); `.draft-specs/02-architecture.md` §5 (the evidence lane);
  `.draft-specs/05-interfaces-and-plugins.md` §3.3 (`status` on every neighbour).
- Decision log: D-014 (typed edges, controlled vocabulary), D-017 (all source content
  untrusted), D-020/D-021 (the two lanes, folder-encoded status).
- Threat model: B4 (ingested source content), B11 (evidence projection) and its two
  elevation-of-privilege rows, restated here.
- Tests: `tests/test_graph_ingested.py`; the narrowed claim in
  `tests/test_ingest_projection.py::test_a_projection_cannot_forge_an_authored_wikilink`.
- Re-runnable: `mycelium build --no-pin eval/corpora/uv-docs-ingested`, then
  `mycelium neighbors knowledge/evidence/projects-docx-e41d7476.md`.
