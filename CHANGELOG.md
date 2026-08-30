# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

- The release workflow built the wheel and sdist to verify the tag, then drafted the
  GitHub Release without attaching them, so v0.1.0 and v0.2.0 carried no downloadable
  artifacts while `docs/workflow/release.md` promised CI would attach them. The draft now
  carries `dist/*`, the artifact version is checked against the tag, and an existing tag
  can be re-drafted with `gh workflow run release.yml --ref main -f tag=v<X.Y.Z>`
  ([BUG-0006](docs/bugs/2026/08/BUG-0006-release-drafts-carry-no-artifacts.md), #30).

### Security

---

## Released versions

| Version | Date | Notes |
|---|---|---|
| [v0.2.0](docs/changelog/v0/v0.2.0.md) | 2026-08-30 | Milestone 2 — Walking skeleton (spec Phase 0). Release notes: [docs/releases/v0.2.0.md](docs/releases/v0.2.0.md). |
| [v0.1.0](docs/changelog/v0/v0.1.0.md) | 2026-08-29 | Milestone 1 — Project bootstrap & CI. Release notes: [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md). |
