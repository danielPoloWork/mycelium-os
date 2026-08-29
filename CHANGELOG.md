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

### Changed

### Deprecated

### Removed

### Fixed

### Security

---

## Released versions

| Version | Date | Notes |
|---|---|---|
| [v0.1.0](docs/changelog/v0/v0.1.0.md) | 2026-08-29 | Milestone 1 — Project bootstrap & CI. Release notes: [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md). |
