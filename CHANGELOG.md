# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

- **The compatibility suite for the five stable contracts** (roadmap 6.1, ADR-0114).
  `tests/test_contracts.py` holds the identity rules, the KIR schema, the snapshot manifest
  schema, the MCP tool contracts and the plugin protocols to committed goldens of their
  *shape* under `tests/fixtures/contracts/` — every schema keyword that constrains, no
  description — and loads the manifest and KIR document a v0.5.0 build wrote with today's
  readers. `python tools/update_contract_goldens.py` re-blesses a golden, as part of the RFC
  and the migration note a contract change now requires. The promise the goldens back —
  what is stable, from which version, and how a change to it is made — is published as
  [`docs/compatibility.md`](docs/compatibility.md); it binds at the v1.0.0 tag.
- **Every MCP tool declares an `outputSchema`** in `tools/list`, beside the `inputSchema` it
  always had (MCP 2025-06-18 and later; older clients ignore the key), so the shape an
  agent depends on is a declared contract rather than a habit of four handlers. The fields
  an error result may carry are declared per code (`mycelium.mcp.errors.ERROR_FIELDS`), and
  a code cannot carry one it does not declare.

### Changed

### Deprecated

### Removed

### Fixed

### Security

## Released versions

| Version | Date | Notes |
|---|---|---|
| [v0.5.0](docs/changelog/v0/v0.5.0.md) | 2026-09-14 | Milestone 5 — Structure (spec Phase 3). Release notes: [docs/releases/v0.5.0.md](docs/releases/v0.5.0.md). |
| [v0.4.0](docs/changelog/v0/v0.4.0.md) | 2026-09-09 | Milestone 4 — Ingestion (spec Phase 2). Release notes: [docs/releases/v0.4.0.md](docs/releases/v0.4.0.md). |
| [v0.3.0](docs/changelog/v0/v0.3.0.md) | 2026-08-31 | Milestone 3 — The compiler (spec Phase 1). Release notes: [docs/releases/v0.3.0.md](docs/releases/v0.3.0.md). |
| [v0.2.0](docs/changelog/v0/v0.2.0.md) | 2026-08-30 | Milestone 2 — Walking skeleton (spec Phase 0). Release notes: [docs/releases/v0.2.0.md](docs/releases/v0.2.0.md). |
| [v0.1.0](docs/changelog/v0/v0.1.0.md) | 2026-08-29 | Milestone 1 — Project bootstrap & CI. Release notes: [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md). |
