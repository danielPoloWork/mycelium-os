# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

- `mycelium.sdk.types` — frozen pydantic v2 record contracts v0: document, KIR, chunk,
  symbol, edge, entity, and snapshot manifest (spec 03 §§3–7), with validated identity
  formats (ULID, `sha256:` digests, anchors) and RFC 3339 UTC timestamps (#14, ADR-0004).
- `mycelium.sdk.schema` — byte-deterministic JSON Schema 2020-12 export of every record
  contract (`export_json_schemas`) for non-Python consumers (#14).
- First runtime dependency: `pydantic >= 2.11` (#14, ADR-0004).
- `mycelium.sdk.identity` — the identity library (spec 03 §§1–2): text normalization and
  canonical-JSON hashing, in-repo monotonic ULIDs, heading slugs, chunk anchors, citation
  URIs, and the symbol/entity/edge reference forms (#16, ADR-0005).

- `mycelium.markdown` — the authored lane (spec 03 §§3–4, D-022): the frontmatter contract
  with its named field owners, Mycelium Markdown Profile v1 (wikilinks, embeds, inline
  tags, callouts, GFM tables), and the markdown-it → KIR adapter (#17, ADR-0006).
- Runtime dependencies `markdown-it-py >= 3.0` and `PyYAML >= 6.0` (#17, ADR-0006).
- `mycelium.mcp` — the MCP server over stdio (spec 05 §3): `mycelium_search` and
  `mycelium_fetch`, the closed error taxonomy, and the data-not-instructions notice on
  every response. Started with `mycelium serve` or `python -m mycelium.mcp`; no new
  runtime dependency (#22, ADR-0011).
- `mycelium` command line (spec 05 §1): `init`, `build`, `search`, `show`, `doctor`, `serve`, with
  `--json` on every read command, exit codes 0/1/2, `NO_COLOR` support, and no interactive
  prompts. Installed as the `mycelium` console script; new runtime dependency `typer`
  (#21, ADR-0010).
- `mycelium.build` — build orchestrator v0 (RFC-0001 pseudocode): sequential full
  rebuild, the `.mycelium/lock` single-writer lock (heartbeat + stale takeover),
  immutable snapshot manifests, the atomic `CURRENT` pointer swap, per-document
  quarantine, and the diagnostic `journal.jsonl`. First builds pin `mycelium_id`
  into frontmatter — the build's only tier-2 write (#20, ADR-0009).
- `mycelium.store` — the derived store (spec 03 §8): SQLite DDL, WAL, a field-weighted
  FTS5 lexical index, meta-table schema versioning, read-only connections for concurrent
  agents, and a `Store` protocol that keeps the engine replaceable (#19, ADR-0008).
- `mycelium.chunking` — the heading-bounded chunker (spec 03 §5): sections become chunks,
  tables and code blocks are atomic, oversize sections split at paragraph boundaries, and
  anchors are unique by construction. Token budgets use a dependency-free estimate behind
  a pluggable `ChunkingPolicy.count_tokens` (#18, ADR-0007).

### Changed

- `mycelium.sdk.types.Ulid` now requires a leading `0`–`7`: 26 Crockford characters carry
  130 bits, so the previous pattern admitted strings that overflow a 128-bit ULID (#16).
- `KirNode` gains `lang`, `variant`, `title`, and `target`, and `SrcLocator` gains `lines`;
  each kind now declares which optional fields it may carry, and illegal combinations are
  rejected on construction (#17, ADR-0006).

### Deprecated

### Removed

### Fixed

- The `Ulid` record contract accepted 26-character strings that overflow 128 bits and have
  no valid decoding; it now refuses exactly what `identity.decode_ulid` refuses
  ([BUG-0004](docs/bugs/2026/08/BUG-0004-ulid-pattern-admits-overflow.md), #16).

### Security

---

## Released versions

| Version | Date | Notes |
|---|---|---|
| [v0.1.0](docs/changelog/v0/v0.1.0.md) | 2026-08-29 | Milestone 1 — Project bootstrap & CI. Release notes: [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md). |
