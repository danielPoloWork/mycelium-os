# ADR-0006: Adapt Markdown to KIR over markdown-it, and give KIR nodes declared per-kind fields

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §§3–4
- **Related:** [ADR-0004](0004-adopt-pydantic-v2-record-contracts.md) (whose deferred KIR
  question this settles), [ADR-0005](0005-adopt-in-repo-identity-library.md); spec 03 §3,
  §3.1, §4; D-007, D-017, D-021, D-022, D-028; roadmap 2.4

## Context

Roadmap 2.4 builds the authored lane: Mycelium Markdown Profile v1 → KIR. It is the first
*producer* of KIR, and ADR-0004 deferred one question to exactly this moment — whether
`KirNode` stays a single open record or becomes a per-kind discriminated union. Writing a
real producer answers it, because Markdown immediately needs somewhere to put a link's
destination, a fence's language, and a callout's type, and KIR v0 had no field for any of
them.

Three further questions have no derivable answer. Frontmatter is YAML, and YAML has no
stdlib parser — but it is also the surface where an author's typo meets a build that must
not stop. Callouts (`> [!note]`) are blockquotes wearing a marker, and CommonMark has no
notion of them. And a document that opens with `---` is ambiguous: Jekyll and Obsidian read
frontmatter, CommonMark reads a thematic break.

## Decision

**Adapt, do not own the parser (D-007).** markdown-it produces the token stream; this
project owns the mapping into KIR and the guarantees that mapping carries. The profile's
Obsidian constructs are added as markdown-it rules (wikilinks, embeds, tags) or recognised
after the fact (callouts), so unknown vault syntax — Dataview, Templater, anything — stays
plain text and can never break a build.

**`KirNode` stays a single open record, with declared per-kind fields.** A discriminated
union would freeze twenty per-kind shapes while only the Markdown subset has a real
producer; the ingestion connectors (4.1) will bring the rest, and a union written now would
be re-litigated then. What the union buys — no nonsense combinations — is bought instead by
`_KIND_FIELDS`: a table declaring which optional fields each kind may carry, enforced on
construction. A paragraph with a `level`, a code block with a `target`, or a heading with no
`level` are all rejected. Four optional fields are added (`lang`, `variant`, `title`,
`target`) plus `lines` on `SrcLocator`; `variant` carries kind-specific subtypes — callout
type, list ordering, table-row role — rather than growing one field per distinction.

**Frontmatter parsing is deliberately lopsided.** PyYAML `safe_load` reads the block, and
then: a malformed `mycelium_id` — or one present but empty — raises, because identity may
never be guessed and minting a second ULID for a document that already claims one is
unrecoverable; every other malformed value warns and is dropped, because a typo in `tags`
must not stop a build. Non-contract keys are preserved verbatim in `properties`, never
interpreted. A fence whose YAML is a scalar or sequence is *not* frontmatter: `---` / prose
/ `---` is two thematic breaks, and CommonMark's reading is the right one.

**Raw HTML is disabled**, so it reaches KIR as literal text. Authored content is untrusted
data (D-017); a representation whose purpose is to be typed and quotable has no business
carrying markup that renders.

## Alternatives Considered

- **A per-kind discriminated union for `KirNode`** — the enterprise-correct shape for tagged
  heterogeneous nodes, and the option ADR-0004 flagged. Rejected *for now*: it would fix
  field sets for sixteen kinds this milestone cannot exercise, and the freeze that matters
  is 1.0 (item 6.1), by which point the PDF/DOCX connectors will have shown what those kinds
  actually carry. The kind-field table is the same constraint with a cheaper reversal.
- **An open `attrs: dict` on `KirNode`** — one field, infinite flexibility. Rejected: it
  reintroduces exactly what `extra="forbid"` was adopted to prevent (ADR-0004), moves
  validation from the schema into every consumer, and makes the JSON Schema export useless
  as a contract for non-Python readers.
- **`mistune` or a hand-written Markdown parser** — fewer dependencies, full control.
  Rejected: CommonMark compliance is a large, well-tested surface that would be re-earned
  badly; markdown-it-py is the spec's own choice (D-007), is CommonMark-conformant, and
  exposes the rule pipeline the profile extensions need.
- **`ruamel.yaml` instead of PyYAML** — YAML 1.2, so `no` stays a string and the "Norway
  problem" disappears. Rejected on weight and ubiquity, but the cost is real and is paid
  explicitly: an unquoted YAML 1.1 boolean in a text field is *dropped with a warning that
  names the fix*, never silently coerced to `"False"`. Revisit if vaults hit it in practice.
- **Tokenizing callouts in the block parser** — a dedicated `callout` block rule.
  Rejected: a callout *is* a blockquote in every other Markdown tool, and keeping the block
  grammar untouched means an unrecognised `[!whatever]` degrades to a plain quote instead of
  a parse failure.
- **Transcluding embeds (`![[doc]]`) at build time** — Rejected by the profile itself
  (§3.1): embeds are links in v1. Transclusion would duplicate content into chunks and make
  a document's text depend on another document's mutable state.
- **Emitting `document` / `section` wrapper nodes** — a tidier tree. Rejected: the spec's own
  §4 example parents a paragraph directly to its heading, and synthetic wrappers add depth
  that neither the chunker nor a citation needs.

## Consequences

- Two runtime dependencies enter: `markdown-it-py` (CommonMark + the rule pipeline) and
  `PyYAML` (frontmatter). Both are pure-Python and offline; the zero-key posture is intact.
- Adding a field to a kind is now a two-line, reviewable change to `_KIND_FIELDS` plus a
  schema-version note — declared evolution, which is what KIR's "adds fields by minor
  version" clause asks for.
- The kind-field table can be *too* strict for a future connector (a paragraph that wants a
  title, say). That is the intended failure mode: it fails loudly at construction, in the
  connector's own tests, rather than silently entering a snapshot.
- Node text is normalized (ADR-0005) as it is stored, so chunk digests downstream are
  stable against line endings and Unicode composition without re-normalizing.
- `src.lines` is 1-based, inclusive, and offset past the frontmatter, so a citation points
  where an editor puts the cursor — but it means every producer must state which coordinate
  system it uses; the field's docstring is the contract.
- Emphasis, inline code, and list markup are flattened into node text and cannot be
  recovered from KIR. That is the "thin AST" bargain (spec 03 §4): KIR is for retrieval and
  citation, not for round-tripping Markdown. Rendering back to Markdown is not a v1 goal.
- Footnotes and math are recognised by neither CommonMark nor this adapter, so they remain
  literal text; the `footnote` and `equation` kinds stay unused until a producer needs them.

## References

- Spec: `.draft-specs/03-data-model.md` §3 (frontmatter contract), §3.1 (Profile v1), §4 (KIR)
- Decision log: D-007 (KIR over ecosystem parsers), D-017 (untrusted content), D-022
  (Obsidian-flavored profile), D-028 (multilingual corpus)
- [markdown-it-py](https://markdown-it-py.readthedocs.io/) — rule pipeline and token stream
- Patterns: Adapter (`docs/patterns/README.md`)
