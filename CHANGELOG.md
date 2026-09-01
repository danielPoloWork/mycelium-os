# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

- **Ingestion contracts and four parsers** (roadmap 4.1). `mycelium.sdk.protocols` declares
  the `Connector` and `Parser` Protocols, `Blob` and `PluginMeta` — the fourth of the five
  contracts that freeze at 1.0. Four adapters ship behind them: `markdown` (markdown-it,
  no optional runtime), `docling` (DOCX and HTML), `pandoc` (DOCX, HTML, ODT, EPUB,
  reStructuredText, LaTeX, through one `--sandbox`ed binary), and `pdf` (PDFium's text
  layer). One document rendered into DOCX, HTML and reStructuredText produces the same
  citable anchors as its Markdown original. See
  [ADR-0032](docs/adr/0032-adapt-four-engines-and-pin-which-one-runs.md).
- **`[ingest] parsers` and `[ingest] connectors`** — the pinned, ordered plugin lists.
  The first parser declaring a media type wins; a name that cannot be resolved is an error
  naming what to install, never a fall-back to whatever is installed (spec 05 §4.2). The
  default is `parsers = ["markdown"]`, which needs no optional runtime.
- **A new optional install, `mycelium-os[ingest]`** — `docling-slim` with its declarative
  format extras plus `pypdfium2`: no `torch`, no model weights, no network. The `pandoc`
  parser additionally needs pandoc 3.x on `PATH`.
- **`mycelium doctor` now reports the pinned parsers** and whether each one can run on this
  machine, with the remedy in the message — so an unavailable plugin is met before a build
  rather than during one.
- **Roadmap 4.9** — read PDF *structure*, or record why v1 does not — filed with the three
  measured constraints (dependency closure, first-use model download vs NFR-6,
  cross-platform float reproducibility vs gate G6) as its acceptance criteria.

### Changed

- **`[ingest]` is honoured by key rather than as a whole section.** `parsers` and
  `connectors` steer ingestion now; `redact_secrets` (roadmap 4.6) and
  `max_failed_elements` (4.3) are still accepted and digested but do nothing, and
  `mycelium doctor` names them individually. This extends
  [ADR-0014](docs/adr/0014-adopt-partial-strict-configuration.md) one level finer.
- **`[ingest] connectors` no longer names parsers.** Spec 05 §2's example
  (`connectors = ["markdown", "html", "pdf"]`) predates the Connector/Parser split in §4.1;
  the keys now match the Protocols, and the old shape is refused with the replacement in
  the message.
- The snapshot manifest's `config_digest` now covers the `[ingest]` section. The
  determinism golden is re-blessed with a one-line diff — every chunk is byte-identical.

### Deprecated

### Removed

### Fixed

### Security

## Released versions

| Version | Date | Notes |
|---|---|---|
| [v0.3.0](docs/changelog/v0/v0.3.0.md) | 2026-08-31 | Milestone 3 — The compiler (spec Phase 1). Release notes: [docs/releases/v0.3.0.md](docs/releases/v0.3.0.md). |
| [v0.2.0](docs/changelog/v0/v0.2.0.md) | 2026-08-30 | Milestone 2 — Walking skeleton (spec Phase 0). Release notes: [docs/releases/v0.2.0.md](docs/releases/v0.2.0.md). |
| [v0.1.0](docs/changelog/v0/v0.1.0.md) | 2026-08-29 | Milestone 1 — Project bootstrap & CI. Release notes: [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md). |
