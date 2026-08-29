# 2026-08-29 — Markdown→KIR adapter (roadmap 2.4)

- **Session scope:** roadmap item 2.4 — Markdown→KIR adapter (markdown-it), frontmatter
  contract, Mycelium Markdown Profile v1 (spec 03 §§3–4, D-022).
- **PR:** #17 (`feat/markdown-kir-adapter`), one item, one PR. Follows #16 (2.3), merged.

## What got done

- `src/mycelium/markdown/` — three modules mirroring the three concerns:
  - `frontmatter.py`: the closed eleven-field contract with its `FIELD_OWNERS` table
    (three tool writers plus the human; no `status` field, per D-021). Non-contract keys
    survive verbatim in `properties`.
  - `profile.py`: the syntax CommonMark lacks — wikilink/embed inline rules, an inline tag
    rule that leaves `C#` and `issue#3` alone, and callout recognition.
  - `adapter.py`: the token stream → KIR mapping, emitting an ordered node list where
    headings parent their content and `src.lines` points into the source file.
- **ADR-0006** settles ADR-0004's deferred question: `KirNode` stays a single record, but
  each kind now *declares* the optional fields it may carry, enforced on construction. Four
  fields added (`lang`, `variant`, `title`, `target`) plus `lines` on `SrcLocator` — the
  minimum a real producer needs, rather than a twenty-shape union frozen before the
  ingestion connectors (4.1) have shown what they carry.
- Two runtime dependencies: `markdown-it-py` and `PyYAML`.
- Patterns catalogue: **Adapter** → Implemented (it was seeded as Planned at intake).
- Tests: 194 passing. Every row of the profile table has a case; the tree shape is a
  hypothesis property (unique ids, contiguous `ord`, parents always earlier — so the list
  is a topological order and cannot contain a cycle); vault syntax that must be tolerated
  (Dataview, Templater, raw HTML, unclosed wikilinks) is asserted not to break a build.

## Decisions worth remembering

- **Frontmatter failure is deliberately lopsided.** A malformed *or present-but-empty*
  `mycelium_id` raises — minting a second ULID for a document that already claims one is
  unrecoverable — while every other bad value warns and is dropped, because a typo in
  `tags` must not stop a build.
- **A fence around non-mapping YAML is not frontmatter.** `---` / prose / `---` is two
  thematic breaks; CommonMark's reading wins. Found by the tree property test, which
  generated exactly that document.
- **PyYAML reads YAML 1.1**, so an unquoted `no`/`yes` in a text field arrives as a boolean
  with the author's spelling already lost. Rather than coerce it to `"False"`, the value is
  dropped with a warning that names the fix. Recorded as the known cost of the dependency.
- **Raw HTML is disabled**, so it lands as literal text (D-017).

## Where the project stands

- Milestone 2: 2.1 ✅ · 2.2 ✅ · 2.3 ✅ · **2.4 ✅ (this session)** · 2.5–2.13 open.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (194 passed), `python tools/consistency_lint.py`.

## How the next session resumes

- Wait for PR #17 to merge, then start **2.5** — the heading-bounded chunker with the
  no-content-loss property test, route standard/medium. Its inputs are all in place: the
  KIR heading tree gives the heading path, `src.lines` gives the line span, and
  `identity.anchor` builds the anchor. Sibling heading-slug collisions are the chunker's
  problem to solve (ADR-0005), and the invariant to prove is spec 03 §5's: ordered chunk
  texts ⊇ normalized document text.
- KIR kinds `footnote` and `equation` remain unused; no producer needs them yet.
