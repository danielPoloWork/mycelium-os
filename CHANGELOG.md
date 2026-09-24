# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

- **`tools/adoption_report.py` evaluates the three triggers that gate the server profile**
  (roadmap 7.5,
  [ADR-0155](docs/adr/0155-read-7-2s-three-triggers-and-say-which-one-cannot-be-read.md)).
  Spec 06 §3 defers roadmap 7.2's parts behind three sentences nothing could evaluate. Two get
  a reading and an instrument: an HTTP API's *consumer that cannot use MCP/CLI* appears by
  filing the new **I cannot use MCP or the CLI** issue form (recognised by its field headings,
  never by its `surface-request` label); a *third-party plugin with meaningful adoption* is a
  public repository outside this one — never a fork of it — declaring a `mycelium.plugins` or
  `mycelium.modules` entry point, found by GitHub code search, with one D-030 engaged actor who
  is not its owner. The third — *an organization commits to deploying the server profile* — is
  reported **unreadable** by decision: a commitment is a promise and the profile does not exist
  to deploy, so it is read as a condition inside 7.2's own RFC. A fired trigger is a decision
  owed to the owner, never one taken; today all three hold.

- **`tools/measure_cache_ceiling.py`, which prices a remote build cache before anybody builds
  one** (roadmap 7.4,
  [ADR-0154](docs/adr/0154-price-the-remote-cache-before-its-trigger-and-give-the-trigger-a-reading.md)).
  Roadmap 7.1's trigger — *≥ 1 team dogfooding with measured duplicate-build pain* — had no
  unit and no instrument, so it could only be asserted. The tool builds fresh checkouts of one
  corpus and varies only what `.mycelium/` holds: nothing, every stage artifact (a remote cache
  that answers instantly), another checkout's whole directory, and that directory with the
  cached checkout's mtimes kept. On the reference profile at 1 000 documents the ideal
  remote cache takes **35 %** off a 55 s cold build, of which **9 ms a document** is
  computation; one that keeps its hits pays **39 s** to write them, 20 s more than it saves on
  this machine; and the checkout given its cache's mtimes rebuilds **nothing**, in 1.6 s.
  Build keys are portable across paths, mtimes and line endings — a CRLF checkout hits every
  key an LF build minted. `--corpus` runs the same arms on a repository somebody already has
  and prints the report the trigger reads.

- **`tools/adoption_report.py` watches the remote-cache trigger** (roadmap 7.4, ADR-0154). It
  reads `measure_cache_ceiling.py` reports pasted into issues, fires on one from an external
  login on a corpus two or more people build with a saving outside the measurement's noise, and
  exits non-zero while a fired trigger's decision is owed. A report is a stranger's text, so only
  its numbers are kept; nothing it says is printed, and closing its issue as *not planned*
  withdraws it.

### Changed

### Deprecated

### Removed

### Fixed

- **A cache report whose saving is negative is a report, not a malformed block**
  ([BUG-0036](docs/bugs/2026/09/BUG-0036-a-report-of-no-saving-is-refused-as-malformed.md)).
  `tools/adoption_report.py` validated `ceiling_s` as a duration, so a report whose seeded
  build was no faster than its cold one — *this cache saved nothing* — was read as no report,
  and the test that round-trips a real four-document report failed on the one CI cell fast
  enough to produce that sign. A saving is a signed difference now; a non-positive one is shown
  as *saved nothing* and never counts as pain.

- **The release workflow can attest the SBOM it builds**
  ([BUG-0033](docs/bugs/2026/09/BUG-0033-the-release-sbom-is-refused-by-the-attestation-it-feeds.md)).
  `v0.6.0`'s first release run failed at the SBOM attestation, so no draft was created:
  `actions/attest` recognises CycloneDX only when `serialNumber` is present, the schema
  makes it optional, and `--output-reproducible` omits it on purpose. A workflow step now
  stamps a deterministic `urn:uuid` serial - a UUIDv5 over the wheel's digest, so two runs
  over one wheel still agree - between the generator and the attestation. It is a workflow
  step rather than a change to `tools/build_sbom.py` because re-drafting an existing tag
  runs the default branch's workflow against the tag's tree (BUG-0006).

### Security

## Released versions

| Version | Date | Notes |
|---|---|---|
| [v0.6.0](docs/changelog/v0/v0.6.0.md) | 2026-09-23 | Milestone 6 — Stable (spec Phase 4). Release notes: [docs/releases/v0.6.0.md](docs/releases/v0.6.0.md). |
| [v0.5.0](docs/changelog/v0/v0.5.0.md) | 2026-09-14 | Milestone 5 — Structure (spec Phase 3). Release notes: [docs/releases/v0.5.0.md](docs/releases/v0.5.0.md). |
| [v0.4.0](docs/changelog/v0/v0.4.0.md) | 2026-09-09 | Milestone 4 — Ingestion (spec Phase 2). Release notes: [docs/releases/v0.4.0.md](docs/releases/v0.4.0.md). |
| [v0.3.0](docs/changelog/v0/v0.3.0.md) | 2026-08-31 | Milestone 3 — The compiler (spec Phase 1). Release notes: [docs/releases/v0.3.0.md](docs/releases/v0.3.0.md). |
| [v0.2.0](docs/changelog/v0/v0.2.0.md) | 2026-08-30 | Milestone 2 — Walking skeleton (spec Phase 0). Release notes: [docs/releases/v0.2.0.md](docs/releases/v0.2.0.md). |
| [v0.1.0](docs/changelog/v0/v0.1.0.md) | 2026-08-29 | Milestone 1 — Project bootstrap & CI. Release notes: [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md). |
