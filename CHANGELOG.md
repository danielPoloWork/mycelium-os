# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Changed

- **The adoption gates are re-cut onto acts we can observe, and the one number that looked
  like adoption was our own CI** (roadmap 6.12,
  [ADR-0138](docs/adr/0138-recut-the-adoption-gates-onto-acts-we-can-observe.md), D-030).
  Spec 06's *"≥ 10 external repos dogfooding"* could only be asserted — there is no telemetry
  and there will be none (D-016) — while GitHub's **3 988 clones from 340 unique cloners** over
  a fortnight sat against **1 unique visitor**, and on the two days no workflow ran the clones
  were **8** and **14**: fourteen checkouts per CI run. Phase 3 now exits on **≥ 3 engaged
  external actors** with the package resolving on an index, Phase 4 on **≥ 3 external authors of
  ≥ 2 merged pull requests** and **≥ 1 `contrib/` plugin authored outside the maintainer** — the
  last because *≥ 5 community plugins* before 1.0 asked for what **D-029** reserves for after
  the freeze. Clone traffic, stars and commit-less forks are excluded by name.

- **The symbol leg ships off again, because the slice that judges it grew fourteen times**
  (roadmap 6.8,
  [ADR-0137](docs/adr/0137-let-a-gated-default-follow-its-ablation-and-narrow-the-rule-that-would-refuse-it.md)).
  `[retrieval] symbol_lookup` was switched on at roadmap 5.25 on a held-out gain measured over
  **four** judged `symbol` cases. Authoring the release sets took that slice to **58**, and at
  that size the reading inverts on the corpus the gain was claimed for: `uv/release` earns it
  (+5.0 % on the slice, +0.7 % overall) and `uv-ingested/release` **regresses** (−5.8 %,
  −0.7 % overall). The bar is unchanged — a release-set gain with no overall regression on any
  set — so the flag follows the measurement back off. Nothing about the leg changed; turn it on
  with `[retrieval] symbol_lookup = true`. `tools/check_frozen_release_sets.py` is narrowed to
  let a **gated default** — one an ablation runner already holds — move in the same change as
  a release set, because the direct check is stronger than the proxy (the ADR-0056 argument,
  applied a second time).

- **The judged release sets are authored to the count their own slices need, and gate G3 can
  enforce for the first time** (roadmap 6.8,
  [ADR-0136](docs/adr/0136-author-the-judged-sets-to-the-count-their-own-bar-needs.md)).
  Six hundred and forty-six new judgements, written from the documents and validated against a
  clean build before either generator would write them: `eval/release.jsonl` **19 → 286**
  cases, `eval/corpora/uv-docs/eval/release.jsonl` **25 → 404**, and the ingested twin
  carried from it at **404** — every case survives, with 27 anchors dropped and printed.
  Judging documents the rotation had never given a format meant extending
  `format-rotation.json` and **re-rendering 25 of the third corpus's binary sources** (ADR-0056),
  after which the evidence was re-projected and the carry re-derived. Every gated slice on every release set now
  holds at least the count `enforceable_at` derives for it (ADR-0123), which closes the
  consequence that ADR recorded: until now **G3 enforced nothing, on any set**. The grading
  conventions are the ones already on the record (ADR-0062, ADR-0065, ADR-0101, ADR-0029); no
  bar is re-cut, and the one retrieval change that travels with this is the symbol default
  above, which these sets falsified rather than were fitted to. All three release baselines are re-blessed,
  both arms, in a clean checkout of the merge tree. The dev sets are unchanged and filed as
  roadmap 6.33. Spec 04 §7.6's 1.0 target of ≥ 1 000 judged cases now reads **1 158
  committed across six sets**.

- **An incremental build no longer reads a document whose size and mtime have not changed**
  (roadmap 6.20, ADR-0133). `doc_state` now records the size and mtime a file had when its
  digest was computed — a *stat memo* — and a file whose stat still matches keeps that digest
  without being read; the digest remains the only identity anything downstream compares. Three
  guards bound the one case the memo cannot see (a same-size edit that also restores the old
  mtime): a file modified within two seconds of the previous build's start is read regardless,
  `mycelium build --rescan` reads every document once, and `mycelium doctor` re-digests the
  corpus and names the drift. The three other whole-corpus filesystem passes a rebuild made go
  with it — restorability now costs one listing per cache shard instead of two probes per
  document, an unresolved link's target is answered from one listing per directory instead of
  one `exists()` per link, and discovery walks the corpus without entering directories it
  excludes. On the 1 000-document reference corpus a rebuild in which nothing changed goes
  **5.1 s to 1.6 s** and a single-document edit **5.8 s to 1.7 s** (p50, on the machine of
  record while it was contended — the report says how). **The store schema version bumps to
  `mycelium/store/v8`** for the two new columns, so an existing `.mycelium/` is rebuilt on the
  next build (D-016); no DDL of the lexical index changed, so gate G2's recorded verdict is
  untouched. Report:
  [`docs/benchmarks/2026-09-19-the-floor-was-the-whole-corpus.md`](docs/benchmarks/2026-09-19-the-floor-was-the-whole-corpus.md).
- **NFR-3 states the corpus it holds for.** The incremental budget — a single-document edit
  rebuilds in < 2 s p95 — now names the 1 000-document reference corpus and local reference
  hardware, the same corpus the cold-build budget names, and the curve above that size is
  published in the report rather than promised (spec 01 NFR-3, spec 02 §4.2, spec 06 §Phase 1).

### Added

- **`tools/adoption_report.py`, which counts the re-cut gates and names everybody it counts**
  (roadmap 6.12,
  [ADR-0138](docs/adr/0138-recut-the-adoption-gates-onto-acts-we-can-observe.md)). It asks
  GitHub and the indexes, subtracts this repository's own CI, and reports **1 of 3** engaged
  actors where the roadmap believed zero: `blamevlan` took a reserved `good first issue`,
  finished it in their fork and could not open the pull request. Running it corrected it twice
  — a default-branch comparison had hidden that contributor, and comparing every branch then
  counted **our own** commits back to us off a fork's copy of an undeleted upstream branch.
  `docs/workflow/adoption.md` holds the three owner actions no workflow can perform.

- **The agent-task comparison now runs on documentation this project did not write**
  (roadmap 6.23, [ADR-0135](docs/adr/0135-judge-the-agent-tasks-on-a-corpus-we-did-not-write-and-carry-them-rather-than-re-judge-them.md)).
  Twenty-two tasks over `eval/corpora/uv-docs` — ten `answer`, six `locate`, six `relate` —
  judged by reading uv's documentation and committed before anything was scored on them
  (`tools/build_uv_docs_tasks.py`, with a `--check` that refuses a hand edit), plus the same
  suite **carried** onto the ingested twin by `tools/build_ingested_cases.py`: only the anchor
  is recomputed, through the coverage and `whole` floors the judged cases already cross, and a
  task that loses any required anchor is dropped whole rather than carried one anchor lighter.
  This is the third and last of the preconditions
  [the reference profile](docs/benchmarks/2026-09-17-reference-profile.md) states for arming
  the verdict gate at 1.0, and it is the one ADR-0053 has required of a gating measurement
  since Milestone 4. `mycelium eval <corpus> --tasks --gate` now runs on all three corpora in
  CI and in `tools/verify.py`, and `tools/measure_agent_task_band.py` takes the suite to run
  as `--tasks`. **What it reads:** 18/22 against the grep loop's 13/22 at a median 2 274
  tokens against 15 251 on `uv-docs`, 17/22 against 11/22 on its ingested twin — wider on
  both than this repository's own corpus gives, where the lead is now +1. The verdict stays
  reported rather than armed (spec 04 §7.4 conditions it on 1.0) and the question of *which
  corpus the rule is read on* travels to roadmap 7.3 with the report:
  [`docs/benchmarks/2026-09-19-the-suite-on-a-corpus-we-did-not-write.md`](docs/benchmarks/2026-09-19-the-suite-on-a-corpus-we-did-not-write.md).

- **The HTML lane decides its own encoding** (roadmap 6.15, ADR-0134, BUG-0032).
  `mycelium.ingest.encoding` reads a document's bytes by a rule this project states — a
  byte-order mark, then an encoding the document declares, then UTF-8, then windows-1252,
  and a quarantine if none of them decodes it — instead of leaving the answer to whichever
  encoding detector happens to be importable beside it. Two contributors with different
  packages installed now ingest the same HTML into the same evidence. A reading the bytes
  did not determine on their own — a declaration that does not decode them, a fallback, or
  a UTF-8 decode producing the NUL characters that mean UTF-16 without a mark — is recorded
  on the document and reaches its fidelity report.
- **`mycelium build --rescan`** reads and digests every document instead of trusting its size
  and mtime, keeping every cache — the old incremental floor and nothing beyond it, and the
  remedy `mycelium doctor` names. `--json` reports `read` (documents whose bytes were read this
  build) and `rescan` beside the other incremental counters.
- **`mycelium doctor` gains an `index` check**: every indexed document re-digested against its
  row, warning on the ones that changed under an unchanged size and mtime.
- **The reference-profile tool measures the floor on its own**: a *no-op* rebuild beside the
  single-document edit, both carrying the compiler's per-stage timings into the manifest.

### Fixed

- **What HTML ingestion projects no longer depends on which unrelated packages are
  importable** ([BUG-0032](docs/bugs/2026/09/BUG-0032-an-importable-package-changes-what-html-ingestion-projects.md),
  roadmap 6.15, ADR-0134). BeautifulSoup binds an encoding detector at import time from the
  first of `cchardet`, `chardet` and `charset-normalizer` it can import, and asked it about
  every document that declares no charset — which is every HTML source in the vendored
  ingested corpus. Installing a package with nothing to do with ingestion therefore changed
  what the compiler produced: seven of that corpus's evidence documents, replayed, and the
  figure moves with the *version* of the detector, which is why declaring one would not have
  fixed it. The decoded text is now handed to the backend with a byte-order mark, which
  BeautifulSoup takes as definite, so the detector is not asked at all. The committed corpus
  is byte-identical.
- **Writing a chunk no longer scans the whole lexical index, so a cold build is linear in the
  corpus** ([BUG-0031](docs/bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md),
  roadmap 6.19, ADR-0132). A `chunks_fts` row now carries the `rowid` of the `chunks` row it
  indexes, so the writer addresses it by the one key FTS5 can seek on instead of deleting by an
  `UNINDEXED` anchor — which SQLite answered with a full scan, once per chunk. The 1 000-document
  cold build goes **193.5 s to 91.7 s**, and the cost per document stops growing: **93 ms at 250
  documents and 92 at 1 000**, against 134 and 194 before. Deleting a twenty-chunk document from a
  twenty-thousand-chunk store goes from 339 ms to 1 ms. **The store schema version bumps to
  `mycelium/store/v7`**, so an existing `.mycelium/` is rebuilt on the next build (D-016); no DDL
  changed, so gate G2's recorded verdict is untouched. Report:
  [`docs/benchmarks/2026-09-19-the-quadratic-in-the-lexical-index.md`](docs/benchmarks/2026-09-19-the-quadratic-in-the-lexical-index.md).

- **The agent-task suite's grep baseline reads a bounded window, not the first matching file
  whole** (roadmap 6.22, ADR-0131). One read now costs at most the caller's own
  `budget_tokens` and the loop opens the five files `MAX_GREP_FILES` has always claimed; a
  document that fits is still read whole, one that does not is read around the hit, and a
  section larger than the window carries no evidence. On this repository's corpus the incumbent
  had been reading **one document on 22 of 22 tasks**, with 93 % of its measured cost in a
  single 88 000-token file. **The repaired comparison is much less flattering to us**: grep's
  evidence rate goes 1/22 → **14/22**, its mean context 52 529 → **15 268**, our lead **+15
  tasks → +2**, and the context ratio 19.2× → **5.6×** on means. The verdict gate quantified at
  6.4 no longer passes its first condition, and is deliberately not re-cut. Both constants of
  the loop are parameters now, and `tools/measure_agent_task_band.py` publishes the band each
  one traces. Report:
  [`docs/benchmarks/2026-09-18-the-incumbent-reads-a-window.md`](docs/benchmarks/2026-09-18-the-incumbent-reads-a-window.md).

### Added

- **The hybrid path is measured at 10⁵ chunks** (roadmap 6.21, ADR-0130), which the reference
  profile had explicitly left open. `tools/benchmark_reference_profile.py --vectors` writes one
  synthetic vector per chunk, lets the store pack them, and times the vector leg, the whole
  hybrid query, the same queries lexical-only, and the per-query precondition. The vector leg
  is **inside** spec 04 §1's 60 ms candidate budget at the top of the v1 corpus envelope:
  **43.2 ms** on a fresh handle, **12.1 ms** on a warm one. Report:
  [`docs/benchmarks/2026-09-18-the-hybrid-path-at-the-reference-profile.md`](docs/benchmarks/2026-09-18-the-hybrid-path-at-the-reference-profile.md).

### Fixed

- **Three statements about the vector scan at 10⁵ chunks disagreed, and all three are
  retired** (roadmap 6.21). The benchmark said ~70 ms citing ADR-0026 — the re-map-per-query
  figure [BUG-0015] found no code path has, and ADR-0030 had taken that label away from it five
  milestones ago. `search_vectors`'s own docstring said ~31 ms, correct about the arithmetic
  and low about the method, which also resolves the pack, filters in SQL and hydrates fifty
  results. `tools/measure_vector_index.py` still called 10⁵ the size *"where the exact scan
  misses the budget"*, which the same ADR had disproved. All three now carry the measured pair
  and point at the report.

- **A pasted document no longer holds the server for two minutes** (roadmap 6.17, ADR-0129).
  Every other cost on the serving path was bounded — `k` at 50, `budget_tokens` on the answer,
  the embedder at its sequence length, a candidate budget per leg — and the *question* was not,
  so the server's cost was a function of what a caller pasted rather than of what the corpus
  holds. Pasting this repository's own `README.md` as a query took **146 s** (62 KB, 7 384
  terms); `AGENTS.md` 25 s; a 9 KB page 5 s. All three now take **~94 ms**, the same 94 ms.
  `mycelium_search`, `mycelium_explain` and `mycelium search` read the first **64 terms** of a
  question — seven times the longest query this project measures itself on — and `explain` says
  how many terms went unread. Nothing is refused: the answer to a bounded question is the answer
  to its first terms, and no judged score moves. Closes the 6.3 security review's F11 and the
  threat model's B6 denial-of-service row.

- **`mycelium_search` is 7x faster, and meets its latency budget for the first time**
  (roadmap 6.18, ADR-0128). Reading `mycelium.toml` asked which modules are installed, which
  re-read the metadata of every installed distribution on **every tool call**: 262 ms of a
  302 ms call, against NFR-2's 150 ms budget for the whole thing. The scan is a property of
  the environment, so it is now done once per process; `mycelium.toml` is a property of the
  repository and is still read per call, so an edit under a running server is still honoured
  on the next query. Measured on this repository's corpus: `load_config` 262 ms → **2.1 ms**,
  `handle_search` 302 ms → **45 ms mean / 58.6 ms p95**. The budget's own condition — 10⁵
  chunks — is still missed by the query path itself (roadmap 6.21); this fixes the constant,
  which no corpus of any size had ever escaped.
- **Reading the configuration no longer imports the ingestion subsystem.** It reached
  `mycelium.ingest.registry` for the names of four built-in parsers, and importing anything
  under `mycelium.ingest` costs 126 modules — 63 of them `markdown_it` — for four dictionary
  keys. The ids are declared instead, with a test that fails if they ever disagree with the
  registry: `load_config` goes from +127 modules to **+2** in a fresh process.

### Added

- **The docs site is published**, from a workflow artifact to GitHub Pages, tracking `main`
  (roadmap 6.14, ADR-0127). `.github/workflows/pages.yml` deploys on every push that touches
  `docs-site/`, `mkdocs.yml`, or `src/mycelium/`; never on a release tag, and not versioned —
  the site links canonical content at `main` rather than duplicating it. Enabling Pages itself
  is a repository setting under the owner's account and is reported (`tools/check_repo_settings.py`),
  never executed by CI. `pyproject.toml`'s `Documentation` link now names the Pages URL.

### Changed

- **`docs-site/` joins this repository's own corpus** (roadmap 6.13, ADR-0126), resolving the
  provisional exclusion 6.2 filed rather than decided. Measured, not defaulted: grep's release
  score is unchanged bit-for-bit and its dev score moves within noise, while ours moves up on
  release and is flat on dev net of one case — the opposite of the incumbent-dilution pattern
  that excluded `docs/changelog`. `eval/baselines/release.json` is re-blessed to the
  206-document corpus, both arms.
- **The root `CHANGELOG.md` leaves this repository's own corpus** (roadmap 6.10, ADR-0125),
  closing the gap ADR-0072 left when it excluded `docs/changelog` and `docs/releases`:
  `[Unreleased]` is not a draft of a future restatement, it *is* one, staged one release early
  and moved into `docs/changelog` verbatim at the next cut. Measured today: our own score is
  unchanged to the fifteenth decimal on both judged sets, and grep's nDCG@10 moves up 0.0055 on
  `dev` and 0.0082 on `release` — the corpus, not the retriever, was carrying part of the
  reported lead. A narrower fix that kept the small "Released versions" index table indexed was
  considered and refused on ADR-0072's own precedent: no exclusion mechanism exists below file
  granularity, and the content spared is worth almost nothing in either direction.

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

### Added

- **Citation precision: `mycelium eval` now scores what an anchor *names*, not only where a
  passage ranked** (roadmap 6.7, ADR-0122). Every other metric ranks chunks, and citation
  coverage asks only whether an anchor resolves; a run could be perfect on gate G1 and hand
  back ten citations a reader cannot find. Each run reports the share of its top-ten anchors
  whose passage sits under a heading, and the mean size of those passages, per case and per
  slice. Reported, not gated, with the condition that would arm it pinned by a test. Two
  findings came with it: the PDF lane of the ingested corpus reads **0.000** — the text layer
  recovers no headings, so every PDF passage is cited by ordinal alone, which is the benefit
  ADR-0040 refused a 2.4 GB pipeline over and could not score — and the product's citations
  are **two to twenty-nine times smaller** than the grep incumbent's, which is the widest
  margin this project has measured against it. `tools/measure_citation_precision.py` reports
  the corpus-wide breakdown; `tools/measure_pdf_structure.py` carries the new columns so
  ADR-0040's re-take is one command.

### Changed

- **`tests/` and `contrib/chats/tests/` are type-checked under `mypy --strict`, like
  everything else this repository writes** (roadmap 6.9, ADR-0124). 212 errors resolved; 216
  files check clean. Roadmap 6.9 proposed a non-strict override for tests, and the measurement
  refused it: `arg-type`, `union-attr` and `attr-defined` — the classes it wanted
  forgiven — are mypy's base checks and stay on at every setting, while what the override
  would have switched off is `disallow_untyped_defs`, whose absence means a function body is
  not checked at all. Most errors had a better fix than an ignore: a string where a `date`
  belongs, six unchecked `Optional` reads, a test narrowing one variable and using another.
  Seven deliberate sites keep a commented per-line ignore, which is the vocabulary for saying
  a value is invalid on purpose. Measured cost: none — 69.5 / 55.2 s without the suites
  against 60.1 / 56.8 s with.
- **`mycelium.eval.harness._gate_g3` takes a `Mapping` rather than a `dict`**, found by
  the above: it only reads the baseline, and `dict` is invariant, so a caller holding a
  `dict[str, float]` could not pass one without copying. Nineteen of the 212 errors were
  that one signature.
- **`mycelium-chats` ships `py.typed`** (roadmap 6.9, ADR-0124). The core advertised its
  types from roadmap 4.43; the module became a distribution of its own at 5.5 and never got
  the same marker, so a consumer installing it received none — and mypy could not see into a
  package this repository already type-checks.
- **Gate G3 enforces a slice only when the slice can carry the bar, and says what it needs
  when it cannot** (roadmap 6.8, ADR-0123). The count is derived from the blessed baseline —
  `n >= q / (0.02 * m)`, with `q` the median non-zero per-case score — rather than compared
  against the constant of four guessed at roadmap 3.7. Two findings came with it: the
  requirement is **50 to 97 cases a slice, median 67**, roughly double what roadmap 6.8
  budgeted, because the bar has to survive a case leaving the top ten rather than the median
  loss observed; and every slice cleared the old constant, so G3 had been reporting *"6 of 6
  slice(s) enforced"* while no row could tell a regression from one case moving. The honest
  consequence: **G3 now enforces nothing on any set**, because no set was ever large enough
  and the constant was hiding it. The gate arms itself per slice as the judged sets grow, and
  `tools/measure_slice_power.py` prints the shortfall. No committed number moves.

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
- **Corrected the trademark note in `.draft-specs/01-product-strategy.md` §9** (roadmap 6.5,
  ADR-0121): the Mycelium Bitcoin Wallet mark (MRD X-Change GmbH, US Reg. 6352173) is
  registered in the *same* Nice class as this project's own software, not "a different
  trademark class" as previously stated. The maintainer's decision, taken against a
  landscape scan of this and three other software-adjacent marks: ship as-is under D-024,
  revisit before any commercial or paid branding push.

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
