# ADR-0018: Build the graph from authored links, and resolve it globally on every build

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §§3.1, 6
- **Related:** [ADR-0015](0015-adopt-content-addressed-incremental-builds.md) (the
  per-document cache this splits against), [ADR-0016](0016-make-snapshots-restorable.md)
  (the restore state the graph joins), [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md)
  (the fusion a graph leg will one day enter), [ADR-0011](0011-implement-mcp-stdio-in-repo.md)
  (the tool surface these two tools complete); spec 03 §§2, 3.1, 6, spec 04 §5, spec 05 §§1,
  3.3–3.4; D-011, D-014; roadmap 3.4, 5.1–5.3

## Context

Roadmap 3.4 asks for `mycelium_neighbors` "on authored links" and `mycelium_explain`.
ADR-0011 deferred both when the MCP server shipped, for reasons that have now expired:
neighbours needed edges, and explain needed a retrieval plan worth explaining. 3.3 built
the plan; this item builds the edges.

"Authored links" is the narrow half of the graph on purpose. D-014 fixes a **controlled edge
vocabulary** and no graph database; spec 03 §6 adds an assertion discipline — `authored`
(an explicit link) versus `extracted` (mined by an extractor), where *extracted edges never
gain authored status silently*. Roadmap 5.1/5.2 own extraction. This item owns only what a
human wrote: wikilinks, embeds, and Markdown links between documents.

The design problem is not extraction — it is **where resolution belongs**. Spec 03 §3.1
resolves a wikilink by "basename if unique, else path, aliases honored", which means
`[[api]]` in one document is a question about *every other document in the corpus*. That
collides directly with ADR-0015: the compiler recompiles only dirty documents, so an
untouched document's links would never be reconsidered — and adding `api.md` would leave
every dangling `[[api]]` dangling until each referring file happened to change. A graph that
is stale in a way nobody can predict is worse than no graph.

## Decision

**Extraction is per-document and cached; resolution is global and runs every build.**
`extract_links` reads one document's KIR and yields `LinkRef`s — kind, target, heading
fragment, and the chunk anchor the reference sits in — knowing nothing about the corpus.
`resolve_edges` takes the whole corpus's references plus an index of paths, aliases, and
heading slugs, and produces edges. Spec 02 §4.2 anticipated exactly this split:
*"rebuild global artifacts whose inputs changed — graph closure, stats"*.

**The references live in `doc_state`, so resolution never re-parses.** A reused document
contributes its stored `links`, `aliases`, and `headings` (store schema v3) to every build's
resolution pass. Extraction stays O(changed); resolution is dictionary lookups over the
corpus's references, measured in microseconds at v1 scale. That is what makes "add a
document and every dangling link to it resolves" true *without* giving up incrementality —
the property is tested directly, on a build that recompiles one document and fixes another's
link.

**The graph is republished whole, not diffed.** Resolution is global, so "which edges
changed" is not a per-document question; keeping only some would leave stale assertions
behind. Edge identity makes this safe rather than wasteful: an edge id is the digest of
`(from, to, type, provenance_digest)` (spec 03 §2), so re-deriving the same assertion
produces the same row and a rebuild converges instead of accumulating.

**A heading link targets a section, not a chunk.** `[[doc#Heading]]` resolves to
`doc:<path>#<slug>` — coarser than a chunk anchor, finer than a document. A chunk anchor
would be the wrong target: the author named a section, and which chunk the packer cut first
is an implementation detail that re-chunking may change (ADR-0007).

**Unresolvable is a warning, never an error** (spec 03 §3.1), and **ambiguous is also a
warning** — an ambiguous basename names its candidates and produces no edge, because
silently picking one of two documents is how a knowledge graph starts lying. External
targets (`http`, `mailto`, …) are neither: they are references to the world, and warning on
every cited URL would train operators to ignore warnings.

**Rollback re-resolves rather than restoring edges.** The snapshot state (ADR-0016) gained
the three per-document graph fields, and `rollback` rebuilds the graph from them. The
manifest's `edges` digest is then folded from the *re-resolved* edges and compared with the
digest the snapshot published — so a successful restore proves the graph is the one that
snapshot described, not merely a graph. Storing the edges instead would have made the state
blob larger and the verification weaker.

**`mycelium_explain` returns no passage text.** It answers "how would you answer this, and
why": the plan, which legs ran, each candidate's rank in each leg, per-stage timings, and
the configuration behind them. Keeping evidence in `mycelium_search` and reasoning here is
what makes explain cheap enough to call whenever an answer looks wrong (spec 05 §3.4, "the
debugging and trust surface"), and stops it becoming a second, unbudgeted way to read the
corpus.

**Traversal is bounded twice and answers both directions.** `MAX_DEPTH = 3` caps the walk
and `limit` caps the results, breadth-first so the budget is spent on the closest
neighbours. Every result says whether the origin asserts it or something asserts the origin:
"what does this cite" and "what cites this" are different questions, and a graph tool that
answers only the first is half a tool.

## Alternatives Considered

- **Resolve per document, at extraction time.** Simplest, and cacheable end to end.
  Rejected: it makes the graph silently stale — adding a document cannot fix an untouched
  document's dangling link, and nothing in the build would ever notice.
- **Mark referring documents dirty when a link's target appears.** Precise invalidation,
  keeping resolution per-document. Rejected: it needs a persistent index of unresolved
  targets and a second dirty-detection path, to buy back work that measures in microseconds.
  Complexity should be spent where the time goes.
- **Diff edges instead of republishing them.** Rejected for the same reason: the inputs to
  an edge include the whole corpus, so a per-document diff cannot be computed without doing
  the global resolution anyway.
- **Store the edges in the snapshot state and restore them literally.** Rejected: it grows
  the state blob with data that is a pure function of what is already in it, and it weakens
  the check — re-resolving and *reproducing the published digest* proves the restore, where
  copying edges back would only prove the copy worked.
- **Resolve `[[doc#Heading]]` to a chunk anchor.** Rejected: chunk boundaries are a packing
  decision, so the link would break when the target is re-chunked without being edited.
- **Emit edges for external URLs.** Rejected: `to` would not be a node in this graph, and
  `mycelium_neighbors` would return things nothing can be fetched from.
- **Resolve an ambiguous basename by picking the shortest path (or the first).** Rejected:
  a plausible-looking wrong edge is worse than a warning naming both candidates.
- **Let `mycelium_explain` return passages too.** Rejected: it duplicates
  `mycelium_search`'s contract with different budgeting, and D-011 counts every tool surface
  as a permanent liability.

## Consequences

- **The MCP surface is now the four tools spec 05 §3 defines**, and ADR-0011's two deferrals
  are closed. The v1 tool surface is complete; anything further is a new compatibility
  liability and needs its own argument.
- **Store schema v3** adds `doc_state.graph_json`. Existing stores are recreated and
  recompiled on the first build (D-016, automated since ADR-0015) — no operator action.
- **The G6 golden gains edges**: `counts.edges` 0 → 5 and the `edges` artifact digest becomes
  real. Verified field by field before re-blessing — documents, chunks, warnings and every
  other field are byte-identical, and no fixture link failed to resolve.
- **`mycelium neighbors` accepts a path, a `mycelium://` URI, a chunk anchor, or a `doc:`
  reference.** The graph keys on `doc:<path>`; making a caller learn that would be a leak,
  not a contract.
- **The graph does not yet participate in retrieval.** Spec 04 §5's expansion is gated on an
  ablation (≥ +3 % nDCG@10 on the `relationship` slice) and belongs to 5.3. `mycelium.retrieval`
  was built so that a graph leg is one more rank list into the same fusion when it earns one.
- **Found and fixed on the way:**
  [BUG-0009](../bugs/2026/08/BUG-0009-mcp-stdio-uses-the-console-code-page.md) — the MCP
  server's second entry point never configured its stdout, so on Windows the protocol stream
  used the console code page. Two em dashes in these tools' descriptions were enough to
  corrupt a frame and hang the client; a multilingual passage (D-028) would have done the
  same to any user. It is the same failure ADR-0010 fixed for the CLI, on the entry point
  that was left out — and it was the reference-client conformance test (ADR-0011) that
  surfaced it.

## References

- Spec: `.draft-specs/03-data-model.md` §2 (edge identity), §3.1 (wikilink resolution),
  §6 (the edge record, the vocabulary, the status discipline);
  `.draft-specs/04-retrieval-and-evaluation.md` §5 (graph expansion, gated);
  `.draft-specs/05-interfaces-and-plugins.md` §1, §§3.3–3.4
- Decision log: D-011 (two surfaces, minimal), D-014 (typed edges in SQLite, controlled
  vocabulary, no graph database)
- Tests: `tests/test_graph.py`, and the tool contracts in `tests/test_mcp.py`
