# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

- `mycelium snapshots`, `mycelium rollback <id>`, and `mycelium gc` (spec 05 §1).
  Snapshots are **restorable**, not just named: every build records the state it can be
  restored from, so rollback reinstates the documents, chunks, and incremental build
  state of a published snapshot from the content-addressed cache — nothing is
  recompiled, and the restored store is verified to reproduce that snapshot's published
  artifact digests before anything is committed (ADR-0016). Measured on 30 documents:
  rollback 229 ms against a 500 ms clean rebuild.
- `mycelium gc [--keep N] [--cache-max-age DAYS] [--dry-run]` removes snapshots beyond
  retention, aged build-cache entries, orphaned CAS blobs, and staging debris. The
  served snapshot is never collected, whatever the retention; every retained snapshot
  stays restorable.
- A build now reports when its snapshot is *not* restorable — for instance after
  `.mycelium/cas/` was deleted by hand, which remains safe — marking the snapshot
  `degraded` and naming `mycelium build --clean` as the repair.
- Incremental compilation (D-008, the technical differentiator): `mycelium build` now
  recompiles only documents whose source digest, mtime, or build environment changed,
  through a content-addressed stage cache (`.mycelium/cas/` blobs indexed by build keys) —
  output is byte-identical to a from-scratch build, enforced by tests per mutation kind
  and property-tested over random edit sequences (ADR-0015). On a 200-document repository
  a single-document edit rebuilds in ~0.5 s against a ~13 s cold build.
- `mycelium build --clean`: recompile everything and consult no cache — same output,
  by construction; the escape hatch when the cache is in doubt.
- Build output (human and `--json`) now reports what was reused vs rebuilt, and
  `journal.jsonl` records per-build cache statistics (`build.published` gains
  `reused`/`rebuilt`/`removed`/`parse_hits`/`chunk_hits`).

### Changed

- Store schema is `mycelium/store/v2` (`doc_state` at 3.1, `snapshot_state` at 3.2). A build that meets an
  older store recreates it in place and recompiles — journaled, no manual deletion
  needed (D-016 rebuild policy); read-only consumers still refuse foreign stores with
  the same message as before.
- Snapshot manifest corpus digests (`artifact_digests.documents`/`.chunks`) are now
  folded from per-document artifact digests in path order instead of digesting the full
  record set, so manifest assembly is O(changed); the G6 golden was re-blessed with a
  two-line diff — every document and chunk record is byte-identical (ADR-0015).

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
