# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

- **The first public benchmark report, measured at the conditions the budgets are stated for**
  (roadmap 6.4, ADR-0120). `tools/benchmark_reference_profile.py` generates the 10⁵-chunk
  reference corpus spec 04 §1 names — from prose harvested out of the vendored corpora, under
  a seed, so it reproduces without being committed — builds it, and measures the three
  performance claims across a curve of corpus sizes.
  [`docs/benchmarks/2026-09-17-reference-profile.md`](docs/benchmarks/2026-09-17-reference-profile.md)
  publishes what it found, with its run manifest committed beside it; the report says the
  product misses three of its own budgets, files the fixes as roadmap 6.18–6.23, and records
  [BUG-0031](docs/bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md) —
  writing a chunk deletes from an FTS5 table by an `UNINDEXED` column, which SQLite answers
  with a full scan, so compiling *N* chunks costs O(*N*²) and the 10⁵-chunk reference corpus
  takes about nine hours to load. The
  manifest carries the machine **and what a file open costs on it**, because every build
  figure is dominated by that constant and it is not a property of the compiler.
- **`mycelium eval --tasks --gate`** — the agent-task suite's *integrity* gate (roadmap 6.4,
  ADR-0120). It fails when a task requires a passage the snapshot no longer holds. Whether
  Mycelium beats grep stays qualitative until 1.0 (spec 04 §7.4); whether the comparison still
  measures retrieval is decidable now, and it did not: four of the twenty-two tasks had been
  scoring as misses for *both* strategies since the packed chunker merged three chunks of one
  ADR into one and shifted every ordinal after it. CI and `tools/verify.py` now run it gated.
- **A `benchmarks` congruence check** in `tools/consistency_lint.py`: a published report is in
  the index and cites a run manifest that exists, and no manifest is orphaned — spec 04 §7.5's
  *"a report without a manifest is exploratory and cannot satisfy a gate"*, enforced.
- **The threat-model-derived test suite** (roadmap 6.3, ADR-0119). A test file that holds a
  trust boundary of `docs/security/threat-model.md` now says so — `pytestmark =
  pytest.mark.boundary("B4")` — so `uv run pytest -m boundary` runs exactly the tests that
  hold the model's controls, and `tests/test_threat_model.py` fails when a declared boundary
  has no test behind it or a marker names a boundary the model does not declare. Thirty-seven
  existing files are marked; the model's new §4 gives the reading.
- **The injection corpus** spec 04 §6 asks for: twenty-three authored documents under
  `tests/fixtures/injection/`, one attack class each — an instruction in prose, in a heading,
  in a callout, in a title, in alt text; a fenced tool call; an envelope spoof; a fake
  `mycelium://` citation; a hidden comment and a hidden block; zero-width joins, a bidi
  override, a homoglyph; a status forged in the body and in frontmatter; a duplicate identity;
  references outside the tree; a forged `mycelium_search` symbol; a credential in prose; and
  the small forms of a YAML alias bomb and an emphasis run — declared in `attacks.json` and
  asserted by `tests/test_injection.py`: every served payload comes back verbatim and only
  inside its typed fields, the envelope and the graph are the server's whatever the document
  says, and a document built to cost unbounded time is refused by name. It is a fixture
  corpus, not part of the judged evaluation corpus; the deviation from spec 04 §6 is recorded.
- **`tests/test_security_controls.py`** holds each bound the review added at the size that
  used to break it, and gives the pandoc subprocess's `--sandbox`, stdin and timeout — claimed
  since 4.1 — their first test.
- **The security register of the review**, `docs/security/audit-2026-09-17-review-pass.md`:
  findings F6–F14, four confirmed defects, no critical finding, no advisory. The threat model
  is corrected where it undersold the product (three boundaries marked *design* four
  milestones after they went live) and extended where the review found new rows.
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
- **The same tool now watches the risk register's deferrals** (roadmap 6.16, ADR-0118). A
  finding accepted *for now, revisit when X* must state X in a form a machine can evaluate;
  one that cannot is not granted. `--triggers-only` evaluates the conditions with no
  administrative rights and no secret, and a remedy that cannot be read is reported as
  unverifiable rather than as installed. It runs at `release.md` step 0b rather than in CI,
  because reading these settings unattended would need a long-lived token.
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

- **The agent-task suite's success rate is now over *scorable* tasks** (roadmap 6.4,
  ADR-0120). A required anchor the snapshot does not hold is reported as `unresolved` and
  excluded from the rate rather than scored as a retrieval miss, because neither strategy can
  hand a model a passage that does not exist. Rates taken before this change are not
  comparable with rates taken after it: ADR-0022's 64 % / 27 % was read off a 22-task
  denominator that had four unanswerable tasks in it. The four are re-anchored to the chunks
  that now carry the same passages.
- **Three statements the reference profile falsified are corrected** (roadmap 6.4): the MCP
  store handle's *"opening costs microseconds"* (it costs 10–12 ms), the store benchmark's
  deferral of the real measurement to roadmap 3.7 (which never took it), and spec 06's
  Phase-1 exit gate recorded as met on a measurement that was never made.

### Deprecated

### Removed

### Fixed

### Security

- **A document's cost to read is bounded in both lanes** (roadmap 6.3, ADR-0119). Frontmatter
  is loaded through an alias-free bounded YAML loader under a 64 KiB block ceiling — nine
  lines of aliases had held `mycelium build` past ninety seconds (BUG-0027). The Markdown
  adapter measures a document's nesting before building its syntax tree and refuses one past
  markdown-it's own `maxNesting` of 100 as a typed `MarkdownError` — forty kilobytes of
  asterisks had crashed `mycelium ingest` with a `RecursionError` and stalled the build for
  thirteen seconds (BUG-0029). An authored document over the file connector's 64 MiB ceiling
  is quarantined instead of read whole. Each is a per-document refusal that names itself.
- **The secret scan is linear in the text, every rule included** (BUG-0028). The
  `private-key-block` rule scanned to the end of the text once per footerless PEM header, so
  twenty thousand headers had not finished in a minute; it now matches the header and extends
  forward once. A key with a truncated footer, which used to match nothing, now flags and has
  its body redacted; a header with nothing under it is documentation and flags nothing.
- **`mycelium chats import` refuses deeply nested JSON instead of dying on it** (BUG-0030):
  a `RecursionError` out of `json.loads` is a typed `ReaderError` in every reader and a
  `SegmentationError` in the segmenter.
- **One finding stays open by decision**: a query of twenty thousand terms holds the
  single-threaded server for 57 s. The cap is a retrieval change and is filed as roadmap 6.17.
- **The private disclosure channel `SECURITY.md` points at is not enabled**, and the risk
  register finding that covers it is re-rated **low → medium** (roadmap 6.16, ADR-0118).
  Register F3 accepted it in August on the premise that *"there are no external reporters
  (private repo), so exposure is nil"*; the repository has been public for weeks and was
  forked by an outside account on 2026-09-14, so a reporter who follows the policy now finds
  a form they cannot submit. Enabling it is a repository setting under the owner's account;
  `SECURITY.md` carries an interim route until it is on, and it is **not** "open an issue
  describing the problem".
- **Branch protection on `main` is still absent** and its deferral has expired (register F2).
  The plan constraint that justified waiting ended when the repository went public, so
  AGENTS.md's rule against pushing to `main` is kept by agents rather than enforced by GitHub.
- **Threat model B1 corrected**: its assumption line read *"repo currently private (no
  external contributors yet)"* and both clauses were false. The controls it lists still hold
  and are the right ones for a public repository.

## Released versions

| Version | Date | Notes |
|---|---|---|
| [v0.5.0](docs/changelog/v0/v0.5.0.md) | 2026-09-14 | Milestone 5 — Structure (spec Phase 3). Release notes: [docs/releases/v0.5.0.md](docs/releases/v0.5.0.md). |
| [v0.4.0](docs/changelog/v0/v0.4.0.md) | 2026-09-09 | Milestone 4 — Ingestion (spec Phase 2). Release notes: [docs/releases/v0.4.0.md](docs/releases/v0.4.0.md). |
| [v0.3.0](docs/changelog/v0/v0.3.0.md) | 2026-08-31 | Milestone 3 — The compiler (spec Phase 1). Release notes: [docs/releases/v0.3.0.md](docs/releases/v0.3.0.md). |
| [v0.2.0](docs/changelog/v0/v0.2.0.md) | 2026-08-30 | Milestone 2 — Walking skeleton (spec Phase 0). Release notes: [docs/releases/v0.2.0.md](docs/releases/v0.2.0.md). |
| [v0.1.0](docs/changelog/v0/v0.1.0.md) | 2026-08-29 | Milestone 1 — Project bootstrap & CI. Release notes: [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md). |
