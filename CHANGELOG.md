# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

- **`tools/measure_result_rules.py`, which decides the result-set rules spec 04 §4 described
  but never had** (roadmap 6.38,
  [ADR-0153](docs/adr/0153-decide-spec-04-s4s-result-set-rules-on-evidence.md)). §4 names
  five behaviours; diversity was measured and refused at 6.29, packing exists, and boosts,
  dedupe and stitching did not exist anywhere under `src/`. **Three of the four boosts are
  refused by arithmetic**: a multiplicative boost is order-preserving when the field it
  reads holds one value, and every corpus here is single-valued in `trust_class`,
  `verification_status` and `curated`. Recency has no judged query asking for it and no
  field to read — `updated_at` is a build timestamp spanning 0.7 seconds across uv's 81
  documents. **Heading proximity was swept across eight weights in both directions,
  pool-wide and confined to the served ten: none of the 96 arms gains on any set**, the best
  is −0.69 %, and the family's optimum is the shipped ranking. A permutation control shows
  any perturbation of that size costs 8–25 %, while heading depth beats the control by
  +15.2 points on the ingested twin and loses to it on the authored corpus. **Dedupe never
  fires** (zero same-digest pairs; 0.4–5.2 % under a Jaccard ≥ 0.8 test). **Stitching is
  deferred rather than refused** — it has occasions (5.7–10.6 % authored, 29.6–32.1 %
  ingested) but nDCG punishes collapsing a slot on principle, so it goes to the agent-task
  suite. **Nothing about retrieval changes**; spec 04 §4 is amended so each rule records
  what was measured and what ships.

- **`tools/measure_ranking_gap.py`, which says where the ranking's remaining headroom
  actually is** (roadmap 6.37,
  [ADR-0152](docs/adr/0152-the-ranking-loss-is-ordering-not-recall.md)). Roadmap 6.29
  measured that re-ordering the same 50 fused candidates by their judged grade is worth
  **+36 % to +86 %** and filed the shape of that number as a follow-up. The shape: **the
  pool almost always holds the answer** — candidate generation finds **93.0 %–99.8 %** of
  the judged passages, and a pool four times deeper than anything ships adds only
  **+3.8 %–13.7 %** of the ceiling — so the loss is neither BM25 nor recall depth.
  **Between 58.4 % and 72.1 % of the entire ceiling is reachable by permuting the ten
  chunks already returned**, worth **+23.8 % to +53.7 %** on its own with no new leg and no
  additional retrieval. A case's best-graded judgment sits at median rank 1 on four of six
  sets but is *first* on only 35.5 %–59.1 % of the cases that serve it. Two candidate
  explanations were measured and refused: document length shows no consistent signal, and
  restricting the measurement to the passages that answer outright moves the ceiling by
  −1.7 to +4.4 points. The runner joins `verify.py`'s `retrieval` rung, where `--check`
  guards the conclusion rather than a default. **Nothing about retrieval changes**; spec
  06 §3's learned-reranker trigger is explicitly **not** met, because no deterministic
  re-ordering of the served set has ever been tried.

### Changed

- **`mycelium --version` no longer imports the ingestion subsystem and the embedder**
  (roadmap 6.36, [ADR-0151](docs/adr/0151-let-the-command-line-import-what-it-parses-with.md)).
  `import mycelium.cli.app` loaded **481 modules in ~1.9 s**, because the CLI is the front
  door to every subsystem and reached them all at module scope. Three things were paying for
  that and none was the one the item predicted: Typer needs three `StrEnum`s while building
  its command tree and they were defined beside twenty-five pydantic models (954 ms for
  18 ms of enums, now `mycelium.sdk.enums`); Typer also evaluates *default values*, and five
  literals imported from four subsystems cost 1 229 ms and 253 modules (now
  `mycelium.defaults`, a module with no imports); and twelve imports that looked stuck in
  signatures belonged to private helpers nothing introspects (now `TYPE_CHECKING`). Both new
  modules are re-exported by their previous homes, so **no documented import changes**.
  Measured: `import mycelium.cli.app` **1 894 → 420 ms / 481 → 164 modules**, and end to end
  `mycelium --version` **2 454 → 1 057 ms (−56.9 %)** with no module installed — with a
  module installed the gain is ~11 %, because `mount()` imports every installed module so
  that `--help` stays complete (ADR-0077), and that cost is the module's. `--help` output is
  byte-identical for the top level and all seventeen commands.

- **The reference profile now reports each query stage against spec 04 §1's budget for it**
  (roadmap 6.35,
  [ADR-0150](docs/adr/0150-report-the-stage-budgets-where-they-mean-something-and-gate-the-total.md)).
  Four of the five latency budgets had never been measured against, so the only thing
  anybody knew was the total. The stages are read from the query path's *own* timings —
  `SearchOutcome.timings_ms`, a seam that already existed and was already paid — so the
  report costs nothing new and cannot drift from the path it times. **At the 10⁵-chunk
  reference profile the warm query is 2 349.7 ms p95 against a 150 ms budget, and
  `lexical` alone is 2 348.0 ms of it — 99.9 %, and 39× its own 60 ms candidate budget**,
  with every other stage at zero. The whole miss is candidate generation, which is the
  diagnosis the end-to-end number could not give. No new gate: two of the four stages name
  work the product does not do (`boosts`, `dedupe` and `stitch` appear nowhere under
  `src/`; diversity was measured and refused at ADR-0144), a third ships off by default,
  and `fusion` reads 0 ms on every query of every committed corpus. G5 keeps gating the
  150 ms call alone, and the spec-versus-product divergence is filed as roadmap 6.38.

- **`tools/consistency_lint.py` now catches a merged item that still reads as open**
  (roadmap 6.34, [ADR-0149](docs/adr/0149-lint-the-delivered-checkbox-convention.md)). PR
  #163 merged on 2026-09-18 and wrote a full delivery record onto roadmap item 6.18 while
  leaving its checkbox at `- [ ]`; nothing caught it for two days, because the PR
  template's checkbox line is advisory and the lint had no opinion about the mismatch. A
  new `roadmap-delivery-checkbox` check fails, naming the item, whenever an unchecked
  ROADMAP entry's own text contains `delivered by PR #<digits>` — the phrase every closed
  item since M1 already uses. The mirror rule (a checked item with no delivery record) is
  deliberately not enforced: 31 of the roadmap's 160 checked items close on other grounds
  (an owner action, a sibling item's evidence, work delivered or reconciled alongside
  another item) with no unambiguous replacement phrase to require.

- **The three dev sets are authored to the count the dev/release gap needs** (roadmap 6.33,
  [ADR-0148](docs/adr/0148-author-the-dev-sets-to-the-count-the-gap-needs.md)). A dev set is
  reported and never gated, so the number it exists to produce is the *gap* against the
  release set — and at 20, 22 and 22 cases that gap rested on two to five questions a slice.
  Measured first: on **nine of fourteen** comparable rows a single dev case was worth more
  than the entire gap its row printed, the worst being `uv`'s `conceptual` at **11.5×**. Each
  dev slice is now authored to the count `enforceable_at` derives for the release slice it is
  subtracted from — derived rather than guessed, and read from the only frozen baseline the
  comparison has. `eval/dev.jsonl` **20 → 239**, `eval/corpora/uv-docs/eval/dev.jsonl`
  **22 → 333**, and the twin carried at **329**. Every row now reports a gap larger than one
  case can move (worst 0.92×, eleven of fourteen at or below 0.3×), and all three gaps are
  positive again — ours at **+0.1271**, against the **+0.115** ADR-0027 measured before either
  set was re-authored. No baseline is re-blessed (a dev set has none), no release set changes,
  and gate G2's verdict is re-recorded because it digests the dev sets — though only its
  release rows decide the default, which stays `lexical`. The committed sets now hold **1 995
  judged cases across six sets**.

- **The symbol stage decodes and hashes once instead of twice** (roadmap 6.32,
  [ADR-0147](docs/adr/0147-decode-and-hash-the-symbol-stage-once.md)). `resolve_symbols`
  and `symbol_edges` run back to back on every build and each independently decoded every
  document's `symbols`/`symbol_uses` from `doc_state`'s stored JSON. A shared `_Facts`
  record, built once by `_facts_of`, now threads through both passes via a new
  `resolve_symbols_and_edges` entry point — the two production call sites use it;
  `resolve_symbols`/`symbol_edges` stay public and independently decoding for anyone who
  only needs one. `SqliteStore.put_edges` also stopped serializing an edge's provenance to
  canonical JSON twice per edge, deriving the digest from the same bytes it already writes.
  Measured on an idle machine at 1 000 documents: the no-op floor's `symbols` stage fell
  **250 → 188 ms (−24.8 %)** against a same-code repeat of 218 ms, and the whole floor
  fell **1 918.9 → 1 676.2 ms (−12.6 %)**. Nothing published moves.

- **`tools/verify.py`'s mode derivation now genuinely takes the widest mode a diff
  touches** (roadmap 6.31, ADR-0146). It checked `retrieval`-yielding rules before
  `full`-yielding ones as a sequence of early-return loops, so a diff touching both a
  tuning path and a full-only path (this PR's own stemmer change beside its own new
  benchmark) derived `retrieval` and silently skipped the benchmark it was added to
  back. Live since roadmap 4.31; found when roadmap 6.30's `BENCH_PREFIXES` made the
  combination reachable by an ordinary PR. Each path is now classified on its own and
  the widest wins, ties broken by declared rule priority.

- **The stemmer is memoised, bounded against this project's own measured vocabulary**
  (roadmap 6.31,
  [ADR-0146](docs/adr/0146-memoise-the-stemmer-bounded-against-a-measured-vocabulary.md)).
  `put_chunks` stems four fields per chunk (text, title, heading, ancestors), and roadmap
  6.19 measured **620 293** word occurrences over **10 339** distinct words on a
  1 000-document build — 98.3 % of the calls already answered. `stem()` is a pure function,
  so `functools.lru_cache` is safe by construction; unbounded it is fine for a build and a
  slow leak in the MCP server's long-lived process, so the bound (**131 072**) is sized at
  ~11x this project's largest built corpus (11 734 distinct terms), costing **~9 MB** for
  100 000 entries. Cold build at 250 documents: **22.50 → 19.67 s (−12.6 %)**, arms
  alternated on an idle machine, against a same-run noise floor of +4.3 % to +9.9 %.

- **A cold build is 29 % faster, because the content-addressed cache stopped paying for a
  second name** (roadmap 6.30,
  [ADR-0145](docs/adr/0145-let-the-digest-be-the-durability-and-stop-paying-for-a-second-name.md)).
  `cas_put` wrote every blob through a temp file, an fsync and a rename. A blob's name *is*
  the digest of its bytes and `cas_get` re-hashes on read, so a torn write was already
  indistinguishable from a cache miss and the ceremony bought nothing the content addressing
  had not (D-005). Decomposed, the fsync costs **~2.0 ms** and the second name **~6.7 ms** —
  the opposite of where roadmap 6.19 put it. Blobs now go straight to their final name:
  cold build **29.35 → 21.96 s at 250 documents** and **132.68 → 94.13 s at 1 000**, arms
  alternated on an idle machine, against a +7.8 % noise floor. Snapshot publication, the
  `CURRENT` pointer, tier-1 custody and quarantine keep the atomic write — none of them is
  recomputable. Still short of spec 01 §8's 60 s budget on this machine.

- **A change to a benchmark now runs the benchmarks** (roadmap 6.30, ADR-0145). A file under
  `tests/bench/` counted as `tests/` and derived `code`, so `tools/verify.py` ran everything
  *except* the suite the change belonged to: a broken benchmark landed green and `main`
  discovered it on the next push. It derives `full` now, by the rule that already sends a
  judged-set change to `retrieval` — the gate that would judge a change is the one it
  changes (ADR-0055).

- **Spec 04 §4's diversity rule is measured and refused, and the specification now says
  so** (roadmap 6.29,
  [ADR-0144](docs/adr/0144-measure-the-whole-diversity-family-and-refuse-it.md)). *"MMR
  across documents so one document cannot monopolize the result set"* was a flat
  requirement of the pipeline that nothing implemented - the only diversity rule in the
  code bounds the **graph leg**, which ships off. Swept across both families on six judged
  sets, **no per-document cap and no multiplicative decay gains on any release set**: cap 1
  costs `ours/release` −25 %, cap 5 costs it −1.1 %, and the arms that gain do so on dev
  sets by +0.2 % to +1.6 %. The reason is arithmetic - a 50-deep RRF pool spans `110/61 =
  1.80x`, so a discount inside it is inert or total, which is ADR-0075's *no operating
  point under RRF* reached by a second mechanism. Nothing ships and no knob is added
  (D-011); `_expand`'s docstring stops implying §4 is satisfied.

- **The agent-task comparison can spend the budget it is given** (roadmap 6.28,
  [ADR-0143](docs/adr/0143-take-the-result-count-from-the-contract-and-sweep-it-like-the-incumbents.md)).
  Our side of the comparison asked `search` for a hard-coded **ten** results whatever budget
  the caller declared — neither the tool's default `k` (8) nor its cap (50) — so the arm
  saturated at about 3 100 tokens while the incumbent went on scaling, and the comparison
  understated us. It now asks for `MAX_SEARCH_K = 50` and lets `budget_tokens` bound the
  answer, and the packing loop **skips** an over-budget result instead of stopping, which is
  what `mycelium_search` does. `run_task_suite` takes `search_k`, and
  `tools/measure_agent_task_band.py` sweeps it beside the incumbent's two constants. At the
  shipped 4 000-token budget: 16/22 unchanged on this repository, **18→19** on `uv-docs`,
  **17→18** on the ingested twin; at 16 000: **19/22, 22/22, 21/22**. Measurement-only —
  no shipped behaviour changes, and no gate moves.

- **The hybrid precondition stops counting and starts probing** (roadmap 6.27,
  [ADR-0142](docs/adr/0142-probe-for-the-vector-precondition-instead-of-counting.md)).
  Before running the vector leg, `search` asks whether the snapshot holds vectors for the
  configured model (ADR-0025). It asked by `GROUP BY` over the whole `vectors` table, once
  per query: **91 ms p50 at 10⁵ vectors**, 8.2× the warm vector leg it guards.
  `SqliteStore.has_vectors()` answers the same yes/no with an `EXISTS` probe that stops at
  the first row — **0.013 ms** — and caches it under the vectors generation, the key the
  packed matrix already uses, so a write invalidates it from any process.
  `vector_counts()` is unchanged for `doctor` and the manifest. Hybrid only: the shipped
  lexical default never paid this.

- **The MCP server no longer imports the compiler to read one pointer** (roadmap 6.25,
  [ADR-0140](docs/adr/0140-resolve-the-build-facade-on-first-access.md)). `read_current` opens
  `.mycelium/CURRENT`; reaching it ran `mycelium/build/__init__.py`, whose eager re-exports
  pulled the orchestrator, the build DAG, `markdown_it`, the symbol extractors, the embedding
  provider with `ssl`, and the whole ingestion subsystem. `import mycelium.mcp.tools` goes from
  **367 modules / 1 880 ms to 234 / 1 460**, with `markdown_it` and `mycelium.ingest` at
  **zero**. The package now resolves each export on first access (PEP 562 `__getattr__`,
  catalogued as *Lazy Initialization*): same names, same modules, same types, and deliberately
  invisible to the type checker so an unknown attribute stays an error. Startup only — NFR-2's
  per-call budget is untouched.

- **Gate G5 now reads the number NFR-2 names, and an unmeasured call fails it** (roadmap
  6.24,
  [ADR-0139](docs/adr/0139-time-the-tool-call-in-the-harness-and-keep-the-retriever-as-a-floor.md)).
  Spec 04 §1 states 150 ms p95 for `mycelium_search`; the gate read the harness's timing of the
  **retriever**, which excludes resolving the snapshot, reading the configuration, opening the
  store and packing the answer — **274 ms of constant** until roadmap 6.18 cached the worst of
  it, so the gate ran green for five milestones over a call that missed its own budget on every
  corpus. The harness now times the handler on a hundred of the run's own queries, spread by
  stride, after a discarded warm-up, and gates on it; the arm's retriever p95 is kept beside it
  as a floor, and **both** must hold. A tool call that cannot be timed fails rather than
  passes. Measured before arming and read back out of the armed gate: **98 ms p95** on this
  repository, **40 ms** and **37 ms** on the two `uv-docs` corpora, against the 150 ms budget
  (a quieter pass read 84 / 45 / 45 — the worst observed is the number to hold it against).
  `EvalRunManifest.tool_call` records the calls and both percentiles — an optional field, so
  manifests written before today still load.

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

- **`tests/bench/test_symbol_resolution_bench.py`, comparing the two coexisting code
  paths directly** (roadmap 6.32,
  [ADR-0147](docs/adr/0147-decode-and-hash-the-symbol-stage-once.md)). Rather than a
  git-history before/after, it benchmarks `resolve_symbols_and_edges` against the old
  `resolve_symbols` + `symbol_edges` pattern on the same synthetic corpus, plus
  `SqliteStore.put_edges` on a batch of edges — a low-variance regression guard for both
  halves of the fix.

- **`tests/bench/test_stemming_bench.py`, cold against memoised** (roadmap 6.31,
  [ADR-0146](docs/adr/0146-memoise-the-stemmer-bounded-against-a-measured-vocabulary.md)).
  Re-takes roadmap 6.19's 23.6x comparison on a real repository document rather than a
  synthetic word list: cold (cache cleared every round) **25.0 ms**, warm **1.5 ms**, a
  16.7x ratio.

- **`tools/measure_cas_write.py` and `tests/bench/test_cas_bench.py`, which price a blob
  write** (roadmap 6.30,
  [ADR-0145](docs/adr/0145-let-the-digest-be-the-durability-and-stop-paying-for-a-second-name.md)).
  The tool decomposes the write into nested arms — plain, +fsync, +second name — interleaved
  so machine drift cannot land on one of them, and sweeps 4/12/64 KiB so a reader can tell a
  per-byte cost from a per-operation one. The benchmark records the same three numbers where
  CI re-takes them on a runner with no filter driver in the path.

- **`tools/measure_document_diversity.py`, which reports the ceiling before it reports an
  arm** (roadmap 6.29,
  [ADR-0144](docs/adr/0144-measure-the-whole-diversity-family-and-refuse-it.md)).
  `--concentration` takes the statistic roadmap 6.22 found on the agent tasks onto the
  judged sets, where it is worse: one document takes half the top ten on **42 %** of
  `ours/release`, and all ten on at least one query. `--oracle` prices the whole family
  with hindsight (**+1.4 % to +4.2 %**) against a perfect re-ranking of the same candidates
  (**+36 % to +86 %**), which is how the ablation concluded that concentration is not where
  the loss is. It joins `verify.py`'s `retrieval` rung, where `--check` guards a
  *refusal* - it fails only if an arm ever starts earning the default nothing carries.

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
