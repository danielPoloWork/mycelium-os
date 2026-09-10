# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

- **Six of the eight edge types are now derived** (roadmap 5.2, [ADR-0074](docs/adr/0074-give-every-edge-type-a-derivation-or-a-reason-it-has-none.md)). A linked
  section is joined to its document by `part_of`, so a traversal that reaches a heading link carries
  on instead of stopping — 76 such dead ends on the vendored uv corpus. A document `defines` the
  symbols its fences and headings declare and `references` the ones they use, both pointing at
  `sym:` nodes, so *where is this defined* and *what uses it* are one hop each in opposite
  directions; a use becomes an edge only when the corpus defines what it names. A synthesized
  document is `derived_from` the evidence it cites, the type ADR-0018 deferred for want of a
  per-document `origin`. `defines` and `references` are the first `extracted` edges this graph has
  carried, so spec 03 §6's status discipline now governs real data. `mycelium_neighbors` and
  `mycelium neighbors` accept a symbol id as the origin and report `NOT_FOUND` for one this
  snapshot does not hold. `mentions` waits for the entity stage (5.4) and `supersedes` for a
  frontmatter field the closed contract does not have (5.10); every weight stays 1.0, because what
  the values should be is 5.3's ablation to measure.

- **Code fences and headings now define symbols** (roadmap 5.1, [ADR-0073](docs/adr/0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md)). A new
  `extract` stage reads every code fence through its grammar's own tree-sitter tags query — Python,
  JavaScript, TypeScript/TSX, Rust, Go, Java, C, C++, Ruby — and qualifies each definition by its
  nesting (`sym:python:RetryPolicy.delay`); it also reads the documentation's own definition syntax:
  definition lists, and headings whose text is an identifier (`## uv.lock` defines
  `sym:doc:uv.lock`). The `symbols` table, `counts.symbols`, `artifact_digests.symbols`,
  `schema_versions.symbol` and the export bundle's `symbols.jsonl` — empty since Milestone 2 — are
  filled; each record says where the thing is defined (`path#L<line>`) and which chunks define it.
  The grammars are the new optional extra **`mycelium-os[symbols]`**: without it a build compiles and
  publishes a snapshot marked `degraded: symbols` that names the extra, `mycelium doctor` gains a
  `symbols` check listing each grammar it can load, and installing or upgrading a grammar is a build
  input the next build recompiles for. `mycelium build` reports edges and symbols beside documents
  and chunks; gate G6's fixture gains a document and its golden a `symbols` section. Nothing reads
  the table at query time yet — the retrieval leg is roadmap 5.9.

### Changed

- **The determinism golden records every edge** (roadmap 5.2). It carried a count and a folded
  digest, so a change to the graph showed up as an unexplained digest move; the fixture's 18 edges
  are now listed with their type, status and provenance, which is the reviewable artifact gate G6
  exists to produce ([ADR-0012](docs/adr/0012-adopt-the-g6-determinism-gate.md)).

- **`AGENTS.md` now says what a clone contains** (roadmap 5.8). §4 draws the tree that exists —
  flat `src/mycelium/`, `eval/`, `tools/`, `.draft-specs/`, the vendored `.eados-core/` bundle and
  the Claude Code adapters — and names what is deliberately untracked and how each is regenerated;
  §13 states the owner's deviation from the EADOS default (bundle and Claude Code tree tracked,
  PR #1) instead of contradicting it three times. `.benchmarks/` is ignored, so a benchmark
  autosave no longer surfaces as untracked noise.

### Deprecated

### Removed

### Fixed

- **The grammar binding is pinned below 0.26.0** ([BUG-0022](docs/bugs/2026/09/BUG-0022-tree-sitter-0-26-faults-on-a-projected-fence.md), roadmap 5.2).
  `tree-sitter==0.26.0` faults with an access violation while reading one 20 KB fence of the
  vendored ingested corpus and takes the whole build process with it — not an exception, so no
  per-fence guard can catch it and the byte ceiling does not reach it. 0.25.2 reads the same bytes
  repeatedly and produces byte-identical definitions for every grammar. Anyone installing the
  `symbols` extra gets the working binding.

### Security

## Released versions

| Version | Date | Notes |
|---|---|---|
| [v0.4.0](docs/changelog/v0/v0.4.0.md) | 2026-09-09 | Milestone 4 — Ingestion (spec Phase 2). Release notes: [docs/releases/v0.4.0.md](docs/releases/v0.4.0.md). |
| [v0.3.0](docs/changelog/v0/v0.3.0.md) | 2026-08-31 | Milestone 3 — The compiler (spec Phase 1). Release notes: [docs/releases/v0.3.0.md](docs/releases/v0.3.0.md). |
| [v0.2.0](docs/changelog/v0/v0.2.0.md) | 2026-08-30 | Milestone 2 — Walking skeleton (spec Phase 0). Release notes: [docs/releases/v0.2.0.md](docs/releases/v0.2.0.md). |
| [v0.1.0](docs/changelog/v0/v0.1.0.md) | 2026-08-29 | Milestone 1 — Project bootstrap & CI. Release notes: [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md). |
