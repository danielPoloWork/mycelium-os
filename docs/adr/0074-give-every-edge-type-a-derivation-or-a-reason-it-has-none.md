# ADR-0074: Give every edge type a derivation, or a reason it has none

- **Status:** Accepted
- **Date:** 2026-09-10
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §6
- **Related:** [ADR-0018](0018-build-the-graph-from-authored-links.md) (the authored graph and
  the two deferrals this closes), [ADR-0073](0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md)
  (the symbol table these edges are derived from),
  [ADR-0035](0035-let-an-llm-write-only-what-a-machine-can-check.md) (the synthesis lane
  `derived_from` describes), [ADR-0012](0012-adopt-the-g6-determinism-gate.md) (the golden
  this teaches to show edges), [ADR-0033](0033-keep-the-original-and-bound-the-hostile.md)
  (bound untrusted input before an engine reads it — and where that stops working);
  [BUG-0022](../bugs/2026/09/BUG-0022-tree-sitter-0-26-faults-on-a-projected-fence.md);
  spec 03 §§3.1, 6, spec 05 §3.3, spec 04 §5; D-014, D-017, D-020; roadmap 5.2, 5.3, 5.4, 5.7, 5.10

## Context

D-014 fixes a **controlled edge vocabulary** of eight types — `links_to`, `defines`,
`references`, `part_of`, `supersedes`, `derived_from`, `cites`, `mentions` — extensible only
by RFC, as the anti-ontology-sprawl valve (F-9). Roadmap 3.4 shipped two of them and
ADR-0018 was explicit that the rest were not being forgotten: `derived_from` was deferred
with a precise blocker, and mining anything out of prose or code was left to an extractor
that did not exist yet. Roadmap 5.1 built that extractor. This item is the vocabulary's
remaining derivations, and `mycelium_neighbors` over all of them.

Three things had to be measured or decided before writing any of it.

**A heading link is a dead end.** Spec 03 §3.1 makes `[[doc#Heading]]` resolve to a *section*
reference, `doc:<path>#<slug>` — a node coarser than a chunk and finer than a document
(ADR-0018). Nothing connected that node to the document it names, so a traversal that arrived
on a section stopped there, while one that arrived on a whole document carried on through its
links. Measured over the vendored uv corpus on 2026-09-10: **290 of its 657 authored links
carry a fragment, across 226 distinct section targets**, of which 76 resolve to a heading that
exists. Every one of the 76 was unreachable from its own document. Graph expansion (5.3) walks
this graph; expanding into a dead end finds nothing.

**A use is not a definition, and documentation is mostly uses.** The tags queries 5.1 already
runs capture `@reference.call`, `@reference.class`, `@reference.type` and
`@reference.implementation` beside the definitions, in eight of the ten grammars (C and C++
ship none). What they capture in a *documentation* corpus, measured: 84 captures across 49
distinct names on uv, and the top of that list is `print` (15), `get` (5), `json`, `items`,
`getLogger`, `FastAPI`, `read_parquet`. Documentation calls libraries; it defines almost
nothing. On our own corpus there are 4 captures and none of them names anything we define.

**`derived_from` had one missing input.** ADR-0018 refused the type for a stated reason: at
document granularity it would have been *"the deduplicated projection of the `cites` edges
already here — the same assertion at lower resolution"*, and the distinction spec 03 §6 wants
— a *synthesized* document versus an authored one citing the same evidence — was *"not
expressible until the graph's per-document state carries `origin`"*.

## Decision

**Six of the eight types are derived; two have a written reason for having no derivation.**

**`part_of` connects a section to its document, for sections the graph already names.** One
edge per *linked* section, not one per heading: the corpus has 909 headings and 3 linked
sections (ours) or 554 and 76 (uv), and emitting containment for every heading would add
thousands of edges nobody asked about and crowd out every neighbour query that has a limit.
The node set is therefore unchanged — the edge joins nodes that already existed — and a walk
that reaches a section now carries on through its document. It is `authored`: the author wrote
the heading and the link, and nothing was inferred.

**`defines` and `references` point at `sym:` nodes, and both are `extracted`.** `defines`
runs from a document to each symbol it declares, carrying the syntax that declared it in
`provenance.kind` (`code_fence`, `heading`, `definition_list`) and the chunk in
`provenance.anchor`. `references` runs from a document to each symbol its fences use. So the
two questions document 00 says agents ask constantly are one hop each, in opposite directions
on the same node, and a document-to-document path exists at depth two through the symbol —
the shape graph expansion can walk. Both are `extracted` because a grammar found them and
nobody wrote them down, which is the first time spec 03 §6's status discipline has had
anything to discipline: the graph carried nothing but `authored` edges until now.

**A use resolves against the corpus or produces nothing.** The captured name is unqualified
(`delay`, not `RetryPolicy.delay`), so it is matched as a whole symbol name first and then
against the last segment of every symbol *in the same language* — spec 03 §3.1's wikilink rule
applied to symbols, ambiguity included: two candidates yield no edge. A name the corpus does
not define yields no edge, which is what keeps the type honest rather than noisy, and is
ADR-0018's own reason for refusing edges to external URLs: a neighbour nothing can fetch. A
document that defines a symbol is not also recorded as using it. Unlike an unresolvable
wikilink, an unresolvable use is **not** a warning — a wikilink asserts that a document
exists, a call site asserts nothing, and warning on every library call would bury the manifest.

**`derived_from` is emitted for a synthesized document, at document granularity, from its
citations.** `origin` joins the per-document graph state, which is the input ADR-0018 named;
the type then says *this document was written from that one*, a fact about the document rather
than about any one of its claims, deduplicated from the `cites` edges to the evidence
documents behind them. It is `authored` — spec 03 §6 counts frontmatter as authored — and
orthogonal to whether the prose has been checked, which `verification_status` carries per
document.

**`mentions` and `supersedes` are not emitted, and the reasons differ.** `mentions` is the
entity-mention type: spec 03 §6 pairs it with the optional entity stage, which is roadmap 5.4,
and mining it out of prose before that stage exists would be inventing an extractor to avoid
writing one. `supersedes` needs an authored declaration — an ADR that supersedes another says
so in its own header — and the only machine-read metadata an authored document has is
frontmatter, whose field set spec 03 §3 closes deliberately. Adding a key is a spec change
with an anti-drift rule to re-argue, not a side effect of this item; filed as roadmap 5.10.

**Weights are all 1.0, and that is deliberate.** Spec 05 §3.3 promises weighted neighbours and
the field is served on every edge. What the values should be is a *ranking* question, and the
place that answers it is 5.3's ablation, which is where a weight can be measured instead of
guessed. Shipping a fitted-looking constant here would be the fourteen-times-refused move
(ADR-0031, ADR-0041) in a new costume.

**The determinism golden now records every edge.** It recorded a count and a folded digest, so
a change to the graph appeared as an unexplained digest move — the opposite of the reviewable
artifact ADR-0012 built the gate to produce. The 18 edges of the fixture corpus are in the
golden, ordered for a reader, and this ADR's own PR is the first to show them.

**The grammar binding is pinned below 0.26.** Measuring this item across the three corpora
crashed the build process with an access violation
([BUG-0022](../bugs/2026/09/BUG-0022-tree-sitter-0-26-faults-on-a-projected-fence.md)):
`tree-sitter==0.26.0` faults deterministically while reading one 20 KB fence of the ingested
corpus, and 0.25.2 reads the same bytes repeatedly with byte-identical results. A segfault is
not an exception, so ADR-0073's per-fence `try/except` cannot contain it and the 256 KiB
ceiling does not reach it. The pin is the control; the corpus that reproduces it is the
regression guard, and `tools/verify.py` builds that corpus from `retrieval` upward.

## Alternatives Considered

- **Emit `part_of` for every heading in every document.** Uniform, no resolution step.
  Rejected on the measurement: 909 headings against 3 linked sections here, 554 against 76 on
  uv. It would multiply the graph by an order of magnitude to connect nodes nobody references,
  and a `limit`-bounded neighbour query would return containment and nothing else.
- **Make `part_of` chunk-level** (chunk → section → document). Rejected: chunk boundaries are a
  packing decision (ADR-0018 refused chunk-level link targets for the same reason), so the
  graph would churn on every re-chunking while answering no question a section cannot.
- **Point `defines` at documents rather than at symbol nodes** — an edge from a document to
  the document that defines a symbol it uses. Rejected: it throws away the thing being asked
  about. "Where is `RetryPolicy` defined" is a question about `RetryPolicy`, and a graph whose
  nodes are only documents cannot answer it without a join the caller has to know to make.
- **Emit `references` to symbols the corpus does not define**, so `print` and `FastAPI` become
  nodes. Rejected: those are neighbours nothing can fetch, the exact failure ADR-0018 refused
  for external URLs, and on uv it would turn 1 useful edge into 84 mostly-useless ones.
- **Refuse `references` altogether**, given it yields 1 edge on uv and 0 on ours. Genuinely
  arguable, and the closest call in this ADR. Rejected because the mechanism is the same parse
  the definitions already pay for, the resolution rule bounds it to symbols the corpus holds,
  and the yield is a property of *these* corpora — both document a tool rather than an API.
  ADR-0073 already recorded that the symbol table earns its keep on a corpus that defines what
  it documents; the same sentence covers its edges. The number is published rather than
  implied, here and in the README.
- **Mine `mentions` from prose now** — a document naming another document's title without
  linking it. Rejected: it is the entity extractor's job (5.4), it is unmeasurable until the
  graph participates in retrieval (5.3), and D-014's valve exists to stop exactly this kind of
  speculative edge.
- **Add a `supersedes:` frontmatter key in this item.** Rejected as scope: spec 03 §3's field
  set is closed with a named owner per field, and opening it is a spec change that deserves
  its own argument (roadmap 5.10).
- **Give each type a default weight now** — `cites` above `links_to`, say. Rejected: no
  measurement supports any ordering, and 5.3 is where one can exist.
- **Work around BUG-0022 in-process** — a smaller byte ceiling, or a shape guard. Rejected:
  the faulting fence is 20 KB with a tree 14 levels deep, so neither guard fires, and no
  in-process guard can catch a fault that is not an exception. Parsing fences out of process
  would work and costs a subprocess per fence; it is not worth it against a fixed upstream
  defect on one release.

## Consequences

- **Measured, on the three corpora the gates run on.** The graph roughly holds its shape on
  ours and grows where the structure was being dropped:

  | corpus | edges before | edges now | `links_to` | `part_of` | `defines` | `references` | `cites` | `derived_from` |
  |---|---:|---:|---:|---:|---:|---:|---:|---:|
  | this repository | 611 | **614** | 611 | 0 | 3 | 0 | 0 | 0 |
  | uv-docs | 228 | **321** | 228 | 76 | 16 | 1 | 0 | 0 |
  | uv-docs-ingested | 10 | **29** | 10 | 7 | 12 | 0 | 0 | 0 |

  The 76 on uv are the dead ends this item closes. Our own corpus gains nothing structural
  because we link whole documents, not sections — worth stating rather than hiding, and it is
  the same corpus asymmetry ADR-0073 reported for symbols.
- **`cites` and `derived_from` are 0 on all three**, because none of them holds a synthesized
  document. The fixture corpus does, and it is where both types are exercised — which is also
  how a fixture flaw surfaced: its synthesized document cited an *authored* file, so the
  synthesis lane's own citation contract (D-020: candidates cite `knowledge/evidence/`) was
  not represented in the gate at all. It cites the evidence document now.
- **The status discipline is real.** The fixture publishes 7 `authored` edges and 11
  `extracted` ones; before this item every edge in every corpus was `authored`, so "extracted
  never becomes authored silently" was a rule with nothing to govern.
- **`mycelium_neighbors` accepts a symbol id** as its origin, in both the MCP tool and the
  CLI, and an id this snapshot does not hold is `NOT_FOUND` rather than an empty
  neighbourhood — an empty answer reads as "nothing defines it", which is a different and
  wrong statement. Spec 05 §3.3's own example input, `{"types": ["defines","links_to"]}`,
  returns `defines` edges for the first time.
- **Store schema unchanged.** `doc_state.graph_json` gains `symbol_uses` and `origin`, which
  older rows decode as empty and `authored`; `EXTRACT_STAGE_VERSION` goes to 2 because the
  stage's output grew, so the first build after upgrading recompiles through the parse and
  chunk caches.
- **The golden moves in a way a reviewer can read**: `counts.edges` 5 → 18, an `edges` section
  listing all of them with type, status and provenance, plus the two fixture edits (a worked
  example that calls what the API reference defines, and the synthesized document's
  citations).
- **`mycelium build` reports edges and symbols**, and the manifest's `edges` digest now covers
  six types instead of two, so a change to any derivation is visible in the snapshot.
- **Known limits, on the record.** `references` cannot see a qualified call whose receiver is
  a variable (`policy.delay` resolves by last segment, and would be ambiguous if two classes
  had a `delay`). C and C++ contribute no references at all, their tags queries having none. A
  section that is linked but whose heading does not exist produces a warning and no node, so no
  `part_of` either. And 5.7 stays open: an ingested corpus's *links* still mostly do not
  resolve, which is a resolution question this item did not touch.

## References

- Spec: `.draft-specs/03-data-model.md` §3.1 (wikilink resolution, the closed frontmatter
  contract), §6 (the vocabulary, the status discipline, `derived_from` beside `cites`);
  `.draft-specs/05-interfaces-and-plugins.md` §3.3 (typed, weighted neighbours with a status);
  `.draft-specs/04-retrieval-and-evaluation.md` §5 (graph expansion, 5.3's gate).
- Decision log: D-014 (typed edges, controlled vocabulary, no graph database), D-020
  (the synthesis lane `derived_from` describes), D-017 (all source content untrusted).
- Re-runnable: `mycelium build --no-pin` on `eval/corpora/uv-docs`, then
  `mycelium neighbors sym:python:main --json` and `mycelium neighbors docs/guides/tools.md`.
- Tests: `tests/test_typed_edges.py`; the golden's `edges` section in
  `tests/fixtures/determinism/golden.json`.
