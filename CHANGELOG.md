# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

- **`mycelium eval --tasks --verdict`, and the agent-task verdict armed in CI** (roadmap 7.3,
  D-031,
  [ADR-0156](docs/adr/0156-read-the-agent-task-verdict-where-we-did-not-write-and-ask-it-for-significance.md)).
  Spec 04 §7.4's 1.0 comparison — does Mycelium beat the agent's own grep loop? — is now a
  gate, not a paragraph: the suite must be sound, Mycelium must find the evidence on **more
  than two** tasks beyond grep *and* the tasks only one strategy found must split with a
  one-sided exact **sign test p < 0.05**, and its **median** context must be at most **half**
  grep's. It is gated on the corpora this project did not write — `uv-docs` and its ingested
  twin, where it reads +6 (7 to 1, p = 0.035) and +7 (8 to 1, p = 0.020) at 3.8× less
  context — and printed, never gated, on this repository's own, where it reads +2 (6 to 4,
  p = 0.38). With `--gate` a verdict that does not hold exits 1.

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

- **A touch is not an edit, and a fresh clone with a restored `.mycelium/` is incremental**
  (roadmap 7.7, D-032,
  [ADR-0157](docs/adr/0157-take-the-timestamps-out-of-the-document-record.md)). Dirty
  detection compares the source digest and the environment digest; the file's mtime is kept
  only as the stat memo that decides whether the digest must be recomputed, and a file with
  the same bytes under a new mtime is reused. Roadmap 7.4 had measured the mtime as what
  kept every clone cold — a restored checkout re-assembled every document, 40 s against
  1.6 s at 1 000 documents. Measured after the change
  (`docs/benchmarks/2026-09-25-a-restored-checkout-rebuilds-nothing.md`): **5.4 s, with 0
  documents rebuilt**, the rest being the memo reading every file once. Watch mode no
  longer builds for a touch, and gate G6 no longer pins mtimes before building — a test
  touches every file and asserts the golden holds.
- **The store schema is `mycelium/store/v9`** (roadmap 7.7). `documents.created_at`,
  `documents.updated_at` and `doc_state.source_mtime` are gone; an existing store is
  recreated on its next build (D-016).

### Deprecated

### Removed

- **`created_at` and `updated_at` from the Document record** (roadmap 7.7, D-032,
  [ADR-0157](docs/adr/0157-take-the-timestamps-out-of-the-document-record.md)). Both were
  the source file's mtime — process metadata of one checkout, set from the same stat on
  every build, so the two never differed and reached no surface: not `mycelium show`, not
  `mycelium_fetch`, not retrieval. They are gone from the record, the store, the export
  bundle's `documents.jsonl` and the G6 golden. The tag stays `mycelium/document/v0`: the
  record is not one of the five frozen contracts and changes at a MINOR with this line
  (`docs/compatibility.md`). `provenance.ingested_at` is unchanged; a document's date, if a
  surface ever needs one, will be declared by its author, never inferred from the
  filesystem or from Git.

### Fixed

- **The reference profile generates the corpus it names** (roadmap 7.6,
  [BUG-0034](docs/bugs/2026/09/BUG-0034-the-reference-profile-harvests-one-of-the-two-corpora-it-names.md),
  [BUG-0035](docs/bugs/2026/09/BUG-0035-a-generated-reference-title-can-be-yaml-the-parser-refuses.md)).
  `tools/benchmark_reference_profile.py` named a source directory that never existed and
  skipped it in silence, so every generated corpus since roadmap 6.4 was this repository's own
  prose under a docstring claiming two sources; it now harvests `eval/corpora/uv-docs/docs` and
  refuses a missing source by name. A harvested heading could also become a title YAML refuses,
  quarantining the document and compiling the thousand-document corpus at 998; titles are
  written as YAML strings, and a run whose build compiled fewer documents than it generated is
  refused rather than reported (`compiled_all`, called by the cold-build, profile and
  cache-ceiling measurements). `--harvest-root` takes a clean export for a published run.
  The before and after at one commit are published
  (`docs/benchmarks/2026-09-24-the-corpus-the-profile-names.md`): the harvest grows from
  5 998 to 8 767 blocks, and reading every earlier manifest found that **no published
  reference-profile run had compiled the size it named** — 998 of 1 000, 249 of 250 — so the
  1 000-document cold-build budget is measured at 1 000 for the first time.

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
