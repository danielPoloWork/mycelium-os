# ADR-0007: Chunk on document structure, with a dependency-free token estimate

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §5
- **Related:** [ADR-0005](0005-adopt-in-repo-identity-library.md) (which deferred sibling
  slug collisions to here), [ADR-0006](0006-adopt-markdown-it-adapter-and-kir-node-fields.md);
  spec 03 §2, §5; D-008, D-013, D-028; roadmap 2.5

## Context

Roadmap 2.5 turns a KIR document into chunks — the unit retrieval returns and citations
point at. Spec 03 §5 fixes the policy (heading-bounded, 200–800 tokens, atomic tables and
code blocks, no mid-sentence splits, no overlap) and one invariant: ordered chunk texts ⊇
normalized document text, property-tested.

Four things the spec does not settle have to be decided before a single chunk exists.
*Tokens* have no meaning without a tokenizer, and every real tokenizer is a model artifact.
The *invariant* needs an operational form, because KIR has already dropped Markdown syntax
(ADR-0006), so literal containment of the source file is not achievable by construction.
*Anchors* need to be unique, and ADR-0005 explicitly left sibling headings that slug alike
to this module. And the spec's own §5 example (`heading_path` of `["Architecture", "Event
Bus"]` producing anchor `architecture.md#event-bus/0`) shows the document's title absent
from the anchor without saying why.

## Decision

**Chunk boundaries are the document's structure**, never a window: a section's prose
accumulates until the next block would breach `target_max_tokens`, tables and code blocks
are chunks of their own, and the heading opens its section's first chunk — it is both the
best available retrieval context and document text that must not be lost.

**Tokens are estimated, not tokenized.** `estimate_tokens` counts words, standalone
punctuation, and one token per CJK glyph. It ships no model files, makes no network call,
and returns the same number on every platform and version — which matters more here than
matching any particular BPE vocabulary, because build keys and byte-identical rebuilds
(D-008, gate G6) depend on chunk boundaries being reproducible. `ChunkingPolicy` carries a
`count_tokens` callable (Strategy), so an embedder that needs exactness supplies its own.

**`target_min_tokens` is declared but not enforced.** The only chunks below it are a
section's remainder, a heading with no content of its own, and atomic tables and code
blocks. Lifting any of them to the minimum means merging across a heading boundary, which
is what heading-bounded chunking exists to prevent.

**The invariant's operational form**: the ordered chunk texts contain every KIR node's
text, in document order, each occurrence consumed once. Reference nodes are excluded —
their text is a substring of the block containing them — and what KIR never carried cannot
be asserted here.

**Anchors.** The document's title heading — a *single* level-1 heading — is omitted from
anchor slug paths, because the document is already identified by its path; several level-1
headings are sections and all count. Sibling headings that slug alike are numbered
(`overview`, `overview-2`), the convention every Markdown anchor generator uses. Ordinals
count within a *slug path*, not within a section: two distinct sections can share one path
— a preamble before the title heading is the case that occurs in practice — and the shared
counter is what keeps anchors unique.

## Alternatives Considered

- **A real tokenizer (`tiktoken`, HuggingFace)** — exact budgets against a named model.
  Rejected: both ship or download vocabulary files, which breaks the offline, zero-key
  default (D-013) and adds a heavyweight dependency; worse, a tokenizer version bump would
  silently move chunk boundaries and invalidate every cached artifact. The estimate is
  wrong by a predictable margin; the tokenizer would be wrong unpredictably across
  versions.
- **Fixed-size windows with overlap** — the RAG default. Rejected by the spec (§5) and on
  the merits: overlap pays storage and duplicate-hit costs to recover context that a
  heading path already provides, and window boundaries make anchors meaningless as
  citations.
- **Semantic or embedding-guided chunking** — better topical coherence. Rejected: it makes
  chunking depend on a model's output, so a rebuild is no longer byte-identical (G6) and a
  build key can no longer be computed from the inputs alone (D-008). It also cannot be
  explained to a reader of the manifest.
- **Splitting oversize paragraphs at sentence boundaries** — would keep chunks under the
  ceiling in all cases. Rejected for v1: the spec forbids mid-sentence splits, and reliable
  sentence segmentation is language-dependent (D-028 puts Japanese and Chinese in scope)
  and needs another dependency. A single oversize paragraph therefore stays whole and
  exceeds the ceiling; that is a visible, measurable outcome rather than a bad split.
- **Merging small sections to reach `target_min_tokens`** — fewer tiny chunks. Rejected: it
  crosses heading boundaries, so a chunk would answer to two heading paths and its anchor
  would lie about where the text lives.
- **Deepest-heading-only anchors** (`#event-bus/0` from the deepest heading alone) — the
  other reading of the spec's §5 example. Rejected: two sections with the same subheading
  name under different parents would collide, and §2 calls the component a heading-slug
  *path*.
- **Hash-suffixed slugs for collisions** — unique by construction. Rejected in ADR-0005 and
  again here: it destroys the readability that makes an anchor worth having.

## Consequences

- Chunk boundaries are a pure function of KIR plus the policy, so they are reproducible and
  participate honestly in build keys.
- Token counts are approximate. Anything that must not exceed a hard model limit (context
  packing in `mycelium_search`, roadmap 2.9) must measure with the model's own tokenizer
  rather than trusting `Chunk.tokens`.
- Small chunks exist by design: a heading with no prose of its own yields a chunk holding
  just its text. It keeps the invariant true and the heading citable, at the cost of some
  low-value hits that ranking will have to handle.
- Anchors are stable against edits that keep the heading path, and against added prose
  (ordinals shift only within their own scope). They are *not* stable against renaming a
  heading or inserting a sibling with a colliding slug — the spec accepts this: anchor
  survival is best-effort by construction, and `ANCHOR_GONE` is the designed outcome
  (spec 03 §2).
- Tables are rendered row-major with ` | ` separators, so a table chunk reads as a table.
  A table larger than the ceiling is still one chunk — atomicity outranks the budget.
- The chunker takes `doc_path` as an argument because KIR carries `doc_id`, not a path.
  The build orchestrator (2.7) owns that mapping.

## References

- Spec: `.draft-specs/03-data-model.md` §2 (identity rules), §5 (chunk record and policy)
- Decision log: D-008 (content-addressed incremental build), D-013 (offline default),
  D-028 (multilingual corpus)
- Patterns: Strategy, Dependency Injection (`docs/patterns/README.md`)
