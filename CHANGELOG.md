# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

- **Every release is now signed and inventoried** (roadmap 6.6, ADR-0117). `release.yml`
  attests the build provenance of the wheel and the sdist through Sigstore, builds a
  CycloneDX 1.6 SBOM of everything the wheel can install, and attests that SBOM against the
  wheel's digest. There is no signing key: an identity is minted per run, the same property
  Trusted Publishing gives the upload. A consumer checks a download with
  `gh attestation verify <file> --repo danielPoloWork/mycelium-os`, and
  [`docs/workflow/packaging.md`](docs/workflow/packaging.md) carries the command.
- **`tools/build_sbom.py`** builds that SBOM from the wheel installed into an *empty*
  environment, and refuses to emit one that describes anything else — a development tool in
  the output, or a root component that cannot name its own release, fails the run. The
  generator itself runs in an environment of its own and is declared in none of this
  project's dependencies: installing it changed what the compiler produces, because it pulls
  `chardet` and BeautifulSoup binds to that whenever it is importable.
- **`tools/check_repo_settings.py`** reports which of `docs/workflow/github-setup.md`'s
  one-time steps are actually installed on GitHub. It reports and never changes anything.
  Three had never been run: `main` has no branch protection, private vulnerability reporting
  is off while `SECURITY.md` points reporters at it, and two labels carry colours the
  manifest does not declare.
- **A contribution ladder with rungs that are real** (ADR-0117). `CONTRIBUTING.md` names five
  ways in, lowest first, and says which are open pre-1.0 — writing a plugin needs no core
  change and no permission. An issue labelled `good first issue` is **reserved**: AGENTS.md
  §6.1 forbids the agent pipeline from taking one, which is what makes the label true in a
  repository that closed 43 items in five days. `.github/labels.yml` declares both ladder
  labels, and `CODEOWNERS` now names the paths that carry a frozen contract.

- **A publish pipeline, and the checks that make an upload safe to make** (roadmap 6.11,
  ADR-0116). `publish.yml` uploads a tagged release to PyPI or TestPyPI over **Trusted
  Publishing** — an OIDC token minted per run, so no API token exists in repository secrets.
  It fires on `workflow_dispatch` and nothing else, defaults to TestPyPI, and runs inside a
  GitHub Environment, so no tag push can publish as a side effect. `docs/workflow/packaging.md`
  § *Turning the publish on* lists the three index-side actions that remain, all of them the
  maintainer's; until then nothing is published.
- **`tools/check_distribution.py`**, run at `code` mode and in CI's new `distribution` job:
  it builds both archives, asserts the sdist carries only what it declares, runs
  `twine check --strict`, and installs the wheel into a clean environment to walk it from
  `mycelium init` to a cited answer. Nothing had ever opened or installed a built artifact.
- **The package describes itself to an index**: keywords, classifiers (whose Python versions
  a test compares against the CI matrix), and the `Documentation`, `Changelog` and `Source`
  URLs `docs/workflow/packaging.md` has promised since M1.

### Fixed

- **The source distribution no longer ships the working directory.** It was declared by one
  exclusion, which meant the archive built at v0.5.0 carried 14.5 MB across thirty top-level
  entries — a 1,248-file machine-local Hypothesis cache, the vendored delivery factory, 2.7 MB
  of judged corpora, and **untracked working files that happened to be in the builder's tree**.
  A published version is immutable, so an artifact whose contents depend on who built it is not
  reproducible and an in-progress document that reaches an index cannot be recalled. The sdist
  is now an allowlist — the package, what builds it, and what states its terms — 1.5 MB across
  six entries (roadmap 6.11, ADR-0116).
- **The install instructions say what is true.** The README had none at all, and the tutorial's
  `pip install mycelium-os` could not work; both now give the tag install, verified in a clean
  environment, and say in one line what it becomes once the first release is published.

- **The docs site** (roadmap 6.2, ADR-0115): a built, `--strict`-checked mkdocs-material
  site under `docs-site/` — a tutorial (install to a cited MCP answer inside spec NFR-4's
  ten-minute budget), four task-oriented how-to guides, the plugin-author guide, and a
  generated API reference over `mycelium.sdk` from its own docstrings. Canonical content
  (the spec, the ADRs, the pattern catalogue, `docs/compatibility.md`) is linked to, not
  duplicated. Build it locally with `uv run mkdocs serve`.
- **The plugin cookiecutter** (`tools/cookiecutter-mycelium-plugin`, roadmap 6.2): generates
  a complete, installable `Connector`, `Parser` or `Module` plugin — entry point wired to
  the right group, a minimal-but-correct implementation, a conformance test, a rendered
  Apache-2.0 `LICENSE` — after checking the plugin id against spec 05 §4.4's naming rule.
  Every kind is checked by rendering it and running this repository's own `ruff`,
  `ruff format --check`, `mypy --strict` and pytest against the output
  (`tests/test_plugin_cookiecutter.py`). `Synthesizer` is deliberately not offered: there
  is no entry-point resolution path to a third-party synthesizer today, stated in the
  plugin-author guide rather than left for a reader to discover the hard way.
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
