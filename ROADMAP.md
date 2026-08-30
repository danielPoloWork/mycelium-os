# Roadmap — mycelium-os

The project's plan as a numbered, checkbox-driven list. When an item completes in a PR,
flip its checkbox (`- [ ]` → `- [x]`) **in the same PR**. New work goes at the bottom of
its section with a fresh `<milestone>.<task>` number; never renumber.

- **Versioning start:** pre-1.0 milestone-driven.
- **Session journal:** see [`docs/journal/`](docs/journal/). Latest checkpoint:
  [2026-08-30 — watch mode](docs/journal/2026/08/2026-08-30-watch-mode.md).
- **Traceability:** every item names the RFC it implements (RFC-0001 for the whole v1
  design of record — [`docs/rfc/0001-mycelium-os-v1.md`](docs/rfc/0001-mycelium-os-v1.md));
  milestone goals are the spec phases' exit gates (`.draft-specs/06`). Sizes are T-shirt
  (`XS S M L XL`), negotiated at the EADOS plan phase (2026-08-29; record at the bottom).

## Model & effort routing (advisory)

An item may carry an advisory **route** — `route: <tier> / <effort>` — derived from its intake
signals through the `os/routing` policy's only-raise resolution (ADR-0017: start at the floor;
matched signals only ever raise, never lower). Tiers, cheapest → most capable: fast → standard → frontier-reasoning.
Efforts: low → medium → high → extra → max. An item with no route takes the floor (fast / low). The route
*recommends*; **the human keeps final model authority** — switch with your host's own model
control, never mid-session by the agent.

Tiers map to concrete models only through the dated catalog (as of 2026-07-27;
a stale date is the review cue):

- **claude-code**: fast → Sonnet 5 · standard → Opus 5 · frontier-reasoning → Fable 5
- **codex**: fast → GPT Luna · standard → GPT Terra · frontier-reasoning → GPT Sol
- **gemini**: fast → — · standard → — · frontier-reasoning → —
- **opencode**: fast → Sonnet 5 · standard → Opus 5 · frontier-reasoning → Fable 5

Where the EADOS core is vendored (`.eados-core/`), the authoritative per-issue call once tracker
labels exist is `python .eados-core/tools/route_advice.py --issue <N>`. Routes without a
signal note are the tech-lead's negotiated judgment (plan phase); signal-tagged routes are
mechanical `route_advice.py` resolutions.

---

## Milestone 1 — Project bootstrap & CI

The thinnest slice that compiles, tests, and ships under the full quality bar.

- [x] 1.0 Stand up the EADOS delivery pipeline — manifest, RFC-0001, negotiated roadmap (RFC-0001) — size: M · route: frontier-reasoning / high (sets-pattern) — delivered by PR #1, merged 2026-08-29
- [x] 1.1 Lay down the build system (Hatch (PEP 517/518, pyproject.toml)) and a buildable skeleton under
      `src/mycelium/` (flat src-layout, ADR-0003). (RFC-0001) — size: S · route: fast / low — delivered by PR #5; `python -m build --wheel` produces an installable `mycelium-os` wheel
- [x] 1.2 Wire the test framework (pytest (+ hypothesis for property tests)) with one passing smoke test under
      `tests/` (flat src-layout, ADR-0003). (RFC-0001) — size: XS · route: fast / low — delivered by PR #6; `dev` dependency group declares pytest + hypothesis. Per the BUG-0003 guard note below, `uv.lock` stays uncommitted until 1.3 completes the group (hatch, pytest-benchmark, ruff, mypy) — committing a partial lock would flip the CI bootstrap probe to ready=true before the lint/benchmark jobs have anything to run
- [x] 1.3 Add formatter + linter configs (ruff format (Black-compatible), ruff check + mypy --strict) at the repo root. (RFC-0001) — size: XS · route: fast / low — delivered by PR #7: `[tool.ruff]`/`[tool.ruff.lint]`/`[tool.mypy]` in `pyproject.toml`, dev group completed (hatch, pytest, pytest-benchmark, ruff, mypy), `uv.lock` committed (BUG-0003 guard now `ready=true`), one benchmark added under `tests/bench/`. Locally green: `ruff format --check`, `ruff check`, `mypy --strict src`, `pytest -q`, `pytest tests/bench --benchmark-only`
- [x] 1.4 Stand up the CI matrix (Linux / Windows / macOS on CPython 3.12+) with build + test + format + lint. (RFC-0001) — size: S · route: fast / low — the matrix itself (ci.yml) was scaffolded at 1.0; closed here on evidence, not new code: [run 33264131144](https://github.com/danielPoloWork/mycelium-os/actions/runs/33264131144) (PR #7 merge to main) is green end-to-end — `build` on ubuntu-24.04×{3.12,3.13}/windows-2022×3.12/macos-14×3.12, `lint`, `benchmark`, `consistency` all pass
- [x] 1.5 Seed the version constant (__version__ = 'X.Y.Z') in `src/mycelium/__about__.py`. (RFC-0001) — size: XS · route: fast / low — delivered alongside 1.1 in PR #5 (hatch's dynamic version reads this file; the two are inseparable at build-system stand-up)
- [x] 1.6 Replace LICENSE MIT → Apache-2.0 (D-018; owner-confirmed 2026-08-29) (RFC-0001) — size: XS · route: fast / low — delivered in the scaffold bootstrap PR
- [x] 1.7 Rename default branch master → main (owner operation on GitHub; owner-confirmed 2026-08-29) (RFC-0001) — size: XS · route: fast / low — done by the owner 2026-08-29 (origin/HEAD → main)
- [x] 1.8 Add SECURITY.md (private disclosure channel), CONTRIBUTING.md (DCO), CODE_OF_CONDUCT.md (spec 06 §4) (RFC-0001) — size: S · route: fast / low — SECURITY.md complete (channel = GitHub private vulnerability reporting; activate the repo feature at public launch — register F3); CONTRIBUTING.md (DCO sign-off policy, dev setup, PR process) and CODE_OF_CONDUCT.md (Contributor Covenant v2.1) delivered by PR #9

---

## Milestone 2 — Walking skeleton (spec Phase 0)

Mycelium OS builds and serves its own repository; TTFV < 10 min end-to-end via Claude Code; byte-identical rebuild in CI; mycelium eval runs and reports

- [x] 2.1 Repo scaffold: uv workspace, ruff + mypy --strict + pytest, CI matrix Linux/macOS/Windows on CPython 3.12+ (RFC-0001) — size: XS · route: fast / low — reconciled: the tooling was delivered by M1 items 1.1–1.5; closes here alongside 1.4 on the same green-on-all-three-OSes evidence ([run 33264131144](https://github.com/danielPoloWork/mycelium-os/actions/runs/33264131144))
- [x] 2.2 mycelium.sdk.types: pydantic records v0 + JSON Schema export (spec 03 §§3–7) (RFC-0001) — size: M · route: frontier-reasoning / high (sets-pattern: the record schemas are the contracts everything else builds on) — delivered by PR #14: seven frozen pydantic v2 records (document, kir, chunk, symbol, edge, entity, manifest) in `src/mycelium/sdk/types.py`, byte-deterministic JSON Schema 2020-12 export in `sdk/schema.py`; first runtime dependency (pydantic ≥ 2.11, ADR-0004); spec examples are executable fixtures
- [x] 2.3 Canonical hashing + ULID + anchor-slug identity library, property-tested (spec 03 §2) (RFC-0001) — size: M · route: standard / medium — delivered by PR #16: `mycelium.sdk.identity` (normalization, canonical JSON, SHA-256 digests, in-repo monotonic ULIDs, heading slugs, anchors, citation URIs, edge/symbol/entity reference forms), ADR-0005; property tests cover idempotence, digest-invariance, order-equals-time, and parser round-trips. Writing the constructors against 2.2's contracts surfaced [BUG-0004](docs/bugs/2026/08/BUG-0004-ulid-pattern-admits-overflow.md) (fixed here)
- [x] 2.4 Markdown→KIR adapter (markdown-it) + frontmatter contract + Mycelium Markdown Profile v1 (D-022) (RFC-0001) — size: M · route: standard / medium — delivered by PR #17: `mycelium.markdown` (frontmatter contract with named owners, Profile v1 syntax — wikilinks/embeds/tags/callouts — and the token-stream→KIR mapping), ADR-0006. Settles ADR-0004's deferred question: `KirNode` stays a single record, with a declared per-kind field table enforced on construction (adds `lang`/`variant`/`title`/`target`, and `lines` on `SrcLocator`)
- [x] 2.5 Heading-bounded chunker with the no-content-loss property test (RFC-0001) — size: M · route: standard / medium — delivered by PR #18: `mycelium.chunking` (heading-bounded sections, atomic tables/code, paragraph-boundary splits, dependency-free token estimate behind a pluggable counter), ADR-0007. The invariant is property-tested as an ordered-subsequence check over KIR node texts; anchors are unique by construction (sibling slug numbering — the collision case ADR-0005 deferred here — plus slug-path-scoped ordinals)
- [x] 2.6 SQLite store: DDL, WAL, field-weighted FTS5, meta table (spec 03 §8) (RFC-0001) — size: M · route: standard / medium — delivered by PR #19: `mycelium.store` — the full DDL, WAL + pragmas, a standalone field-weighted FTS5 index (title 3.0 / heading_path 2.0 / body 1.0 per spec 04 §3), meta-table schema versioning that refuses a foreign store rather than reinterpreting it, and read-only connections for concurrent agents. SQL is confined behind a `Store` protocol so the platform-phase store (D-019) is a swap, not a rewrite (ADR-0008)
- [x] 2.7 Build orchestrator v0 (sequential) + snapshot manifest + atomic CURRENT swap + single-writer lock (RFC-0001) — size: L · route: frontier-reasoning / high (sets-pattern: publication/crash-safety semantics set here bind every later phase) — delivered by PR #20: `mycelium.build` — lock (O_EXCL + heartbeat mtime + stale takeover), one-transaction publication with the manifest written before anything names it, atomic `CURRENT` swap (`os.replace` + fsync; `O_BINARY` so manifest bytes are platform-independent), identity pinning as the build's only tier-2 write (resolving spec 02 §2 vs spec 03 §3 in the ownership table's favor — determinism requires it), per-document quarantine, `journal.jsonl`. Crash windows stated in ADR-0009, not hoped away; rebuild-in-place is byte-stable (the G6 seed for 2.10)
- [x] 2.8 CLI skeleton (typer): init/build/search/show/doctor with --json (RFC-0001) — size: S · route: fast / low — delivered by PR #21: `mycelium.cli` — the spec 05 §1 conventions (exit codes 0/1/2, `--json` emitting exactly one document on stdout, diagnostics on stderr, `NO_COLOR`, no prompts anywhere), citation URIs on every search hit, `show` resolving both URIs and anchors with a prose ANCHOR_GONE, and `doctor` carrying the commit-to-swap detector ADR-0009 promised (ADR-0010)
- [x] 2.9 MCP server (stdio): mycelium_search + mycelium_fetch, typed errors, data-not-instructions notice (RFC-0001) — size: M · route: standard / medium — delivered by PR #22: `mycelium.mcp` — the stdio JSON-RPC binding implemented in-repo (no runtime dependency; the official SDK's seventeen packages include an HTTP server, JWT and telemetry, against D-017's posture), with conformance proved by driving this server as a subprocess from the reference client. `mycelium serve` added. ADR-0011
- [x] 2.10 Determinism golden test wired into CI (gate G6) (RFC-0001) — size: S · route: standard / medium — delivered by PR #23: a six-document fixture corpus, a reviewable golden observation (per-document and per-chunk detail, not one opaque hash), `mycelium.determinism` shared by the gate and the re-bless tool, `.gitattributes` pinning fixture line endings, and a `determinism / gate G6` CI job — plus mutation tests proving the gate can fail. ADR-0012 states what determinism claims and what it deliberately does not (`snapshot_id`, `created_at`, `timings_ms`)
- [x] 2.11 Eval harness v0 + first 20 judged cases on Mycelium OS's own docs (RFC-0001) — size: M · route: standard / medium — delivered by PR #24: `mycelium.eval` (metrics, retrievers, harness, run manifests), `eval/cases.jsonl` with 20 judged cases over our own docs, `mycelium eval [--set] [--retriever] [--gate] [--json]`, gates G1/G4 enforced with the rest explained, and the D-010 grep baseline shipped from the start. First result: nDCG@10 0.70 vs grep 0.55, MRR 0.83 vs 0.62, p95 3 ms vs 52 ms. The first realistic run found [BUG-0005](docs/bugs/2026/08/BUG-0005-fts-and-semantics-zeroes-queries.md) — every natural-language query returned nothing. ADR-0013
- [x] 2.12 Brand + README redesign: vendor the legacy brand assets (banner / icon / logo → `docs/assets/brand/`) and rebuild the root README on the legacy skeleton (badges, language selector, Inspiration & Origins credit) with v1-true content — preserve what the lint reads (version badge, milestone table); legacy architecture SVGs are NOT salvaged, superseded design (RFC-0001, D-028) — size: S · route: standard / medium — delivered by PR #25: three brand PNGs vendored with a provenance README recording that `mycelium-os-logo.png` carries the *superseded* legacy tagline and must not be used where it is legible (D-001); root README rebuilt on the legacy skeleton with v1-true content (badges limited to what is actually wired, honest grep-baseline positioning, Karpathy credit kept). The language selector ships as labels, not links — the `docs/i18n/` targets are 2.13's to create, and a front door with dead links is the failure L-0002 warns about
- [x] 2.13 Enable the docs-i18n subsystem, structure only: `capabilities.i18n` on with targets it / zh-Hans / ja, `docs/i18n/` index + `translation-status.md` (all pages pending), `i18n_enabled: True` in the consistency-lint CONFIG — zero translations initially (RFC-0001, D-028; L-0002: a capability flag ships its artifacts) — size: S · route: fast / low — delivered by PR #26: flag, manifest targets, and artifacts land together (L-0002), and the freshness gate was *proved* to bite by temporarily marking a row `translated` against an older source commit. The tracked page set is scoped to reader-facing pages (README, CONTRIBUTING, CoC, SECURITY) with the exclusions argued in `docs/i18n/README.md`. Also closed the contract gap the flag exposed: AGENTS.md §2 (and the CLAUDE/GEMINI adapters) said English-only with no carve-out, which `docs/i18n/` would have contradicted
- [x] 2.14 Configuration loading (`mycelium.toml` → build/chunking/embedding settings, spec 05 §2) — filed at 2.8, which scaffolds the file the spec promises but reads nothing from it; the generated template says so in a comment. Until this lands, edits to `mycelium.toml` have no effect (RFC-0001) — size: S · route: standard / medium — delivered by PR #27: `mycelium.config` loads and validates the file, `[project]`/`[chunking]`/`[embedding]`/`[modules]` are honoured strictly and the remaining documented sections are accepted, digested, and reported by `doctor` as not honoured yet (ADR-0014). The manifest's `config_digest` now digests the real configuration instead of a placeholder — the determinism golden is re-blessed with a **one-line** diff, proving every chunk stayed byte-identical. `target_tokens` is honoured as advisory only; making it steer chunk size is filed as 3.8

---

## Milestone 3 — v0.1 — The compiler (spec Phase 1)

Incremental single-doc rebuild < 2 s p95 equal to clean output; search p95 < 150 ms on the 10^5-chunk reference corpus; gates G1/G2/G6 green (lexical-only default is a legitimate G2 outcome)

- [x] 3.1 Content-addressed incremental DAG + build cache + dirty detection (D-008) (RFC-0001) — size: L · route: frontier-reasoning / high (sets-pattern: the product's technical differentiator) — delivered by PR #31: the spec 02 §4 algorithm end to end — build keys over `(stage, impl version, input digests, config slice, schema)`, a two-level cache (`build_cache` rows indexing canonical-JSON CAS blobs that self-heal on corruption), digest-based dirty detection against the new `doc_state` table (store schema v1; a writer meeting a foreign store recreates it in place, D-016), and manifest corpus digests folded from per-document digests so publication is O(changed). Byte-equality with a clean build is enforced per mutation kind and property-tested over random edit sequences; `mycelium build --clean` is the escape hatch. Measured (200 docs): cold 12.9 s → single-edit 546 ms. ADR-0015; the every-build plan scan (~2 ms/doc, I/O-bound) is the term 3.5's watch mode removes
- [x] 3.2 Snapshot list/rollback + GC (mycelium snapshots, rollback, gc) (RFC-0001) — size: S · route: standard / medium — delivered by PR #32, at size **M**: spec 02 §4.3's "repoint `CURRENT`; nothing rebuilds" assumes a versioned store, and on this milestone's single mutable store repointing alone would publish a snapshot id whose data belongs to another build — the disagreement `doctor` already reports as corruption. So a snapshot now carries the state it can be restored from (one content-addressed blob per publication holding its `doc_state` table — a Memento), and `rollback` restores documents, chunks, and the incremental build state before swapping the pointer, under ADR-0009's order. That same record gives `gc` a defined live set. Store schema v2; ADR-0016. Measured (30 docs): rollback 229 ms vs 500 ms clean rebuild; `snapshots` 13 ms; steady-state `gc` 109 ms
- [x] 3.3 Local ONNX embedder default (zero keys, offline) + vectors keyed (chunk_digest, model_id) + hybrid RRF (D-013/D-009) (RFC-0001) — size: M · route: standard / medium — delivered by PR #33: `mycelium.embedding` (Embedder protocol, a registry pinning every model file by SHA-256, and a local ONNX encoder behind the optional `embeddings` extra), the vector stage as the compiler's one **declared non-deterministic** stage (spec 02 §4.1) keyed `(chunk_digest, model_id)` so unchanged text never re-embeds, and `mycelium.retrieval` fusing BM25 with vector candidates by RRF for the CLI, MCP, and the harness alike. **Gate G2 ran and hybrid did not earn the default:** +12.7 % nDCG@10 overall (bar: +5 %) but −17.8 % on the `exact` slice (bar: −2 %), and it answers every `unanswerable` query where lexical abstains — so the shipped default is `profile = "lexical"` and the README says so, exactly as spec 04 §7.3 prescribes. ADR-0017; found [BUG-0007](docs/bugs/2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md) and filed 3.9–3.11
- [x] 3.4 mycelium_neighbors on authored links + mycelium_explain (RFC-0001) — size: M · route: standard / medium — delivered by PR #34: `mycelium.graph` derives `links_to` edges from what a human wrote (wikilinks, embeds, Markdown links), resolved per spec 03 §3.1 with unresolvable *and ambiguous* links warning rather than guessing. The design call is the split ADR-0018 records: extraction is per-document and cached, **resolution is global and runs every build** from the references kept in `doc_state` (store schema v3) — so adding a document settles dangling links in documents the build never recompiled, without giving up O(changed) compilation. `mycelium neighbors` and the last two spec 05 §3 tools ship, closing ADR-0011's two deferrals; rollback re-resolves the graph and proves it against the manifest's own `edges` digest. Found and fixed [BUG-0009](docs/bugs/2026/08/BUG-0009-mcp-stdio-uses-the-console-code-page.md) — the MCP server's bare-interpreter entry point wrote its protocol stream in the console code page, so one em dash hung the client and any multilingual passage would have done the same
- [x] 3.5 Watch mode: debounced FS events → incremental builds (RFC-0001) — size: S · route: standard / medium — delivered by PR #35: `mycelium build --watch` debounces a save burst into one build and rebuilds until Ctrl-C. The decision ADR-0019 records is a **refusal**: events decide *when* to build and never *what*, because spec 02 §7 asks for "identical guarantees" and an event stream is not a dirty set (dropped events, temp-file-and-rename saves, `git checkout` behind the watcher, a watcher started after an edit). This **corrects 3.1's journal note**, which had promised watch mode would remove the plan-scan floor — it does not, and the honest way to attack that floor is faster scanning, not a less trustworthy one. The derived store is never watched (that loop is infinite), a failed build never ends the session, and the watcher is an optional extra (`mycelium-os[watch]`) with the loop tested through a queue on every platform. The three-OS matrix earned its cost twice on the same test: Linux inotify reports *reads*, so a build's own plan scan would have triggered the next build forever; then macOS failed for a different reason (FSEvents surfaces a read's atime update as a modification, indistinguishable from a write). The fix is a level up — the loop **proves** a change against `doc_state` before building, which no event-type filter could have done
- [ ] 3.6 mycelium export JSONL interchange bundle (D-006) (RFC-0001) — size: S · route: fast / low
- [ ] 3.7 Eval slices + CI gates G1–G6; agent-task suite v0 (≥ 20 tasks) vs the grep baseline (D-010) (RFC-0001) — size: M · route: standard / medium
- [ ] 3.8 Target-aware packing: make `[chunking] target_tokens` steer chunk size instead of being advisory — the packer fills toward `max_tokens` today (ADR-0007), so lowering the target has no effect (ADR-0014). Changing it moves every chunk boundary, so it needs the eval harness to say whether smaller chunks retrieve better, and a determinism re-bless (RFC-0001) — filed at 2.14 — size: S · route: standard / medium
- [ ] 3.9 Serve `verified`+`evidence` only: honour `[retrieval] include_candidate = false`, which needs a "verification status is not candidate" filter the store's single-value filter cannot express (spec 05 §2; the setting is refused by name until then) (RFC-0001) — filed at 3.3 — size: XS · route: fast / low
- [ ] 3.10 Scope the evaluation corpus so test fixtures are not scored as documentation, and re-establish gate G4's number ([BUG-0007](docs/bugs/2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md)): building this repository indexes `tests/fixtures/`, which answers an `unanswerable` case. Decide it with 3.7's eval-scoping work — an exclusion setting, a staged documentation copy, or moving the fixtures out of discovery's reach. Editing the judged case to fit the corpus is not on the table (D-010) (RFC-0001) — filed at 3.3 — size: S · route: standard / medium
- [ ] 3.11 Abstention for the vector leg — the finding that cost hybrid its default (ADR-0017): cosine similarity does not separate answerable from unanswerable queries (unanswerable scored 0.63–0.67 against answerable 0.64–0.84 on our set), so no similarity floor restores G4 and none is shipped. Needs a different signal — lexical agreement as a precondition, score-gap analysis, or a per-corpus calibration — and each is an eval question, measured before it ships (RFC-0001) — filed at 3.3 — size: M · route: frontier-reasoning / high (decision-heavy)
- [ ] 3.12 Make the vector leg meet the candidate-generation budget: the exact scan costs 94 ms over 10 000 chunks against spec 04 §1's 60 ms, and is linear (ADR-0017). Two rounds of query shaping took it from 168 ms; the rest is SQLite row iteration over blob columns, so the next step is a different representation — one packed matrix per model, or an ANN index that does not depend on a loadable SQLite extension. A prerequisite for hybrid ever earning its default (RFC-0001) — filed at 3.3 — size: M · route: standard / high

---

## Milestone 4 — v0.2 — Ingestion (spec Phase 2)

Zero silent element loss on the fixture corpus; hostile-file suite quarantines without failing the build; an ingestion-heavy corpus joins the eval set

- [ ] 4.1 Connector/Parser protocols exercised for real: docling adapter (PDF/DOCX/HTML), pandoc fallback (D-007) (RFC-0001) — size: M · route: standard / medium
- [ ] 4.2 CAS custody of originals; KIR v0 hardened on hostile fixtures; opaque-node escape hatch (RFC-0001) — size: M · route: standard / medium
- [ ] 4.3 Evidence-lane projection with provenance frontmatter, fidelity reports, per-document loss budgets (RFC-0001) — size: M · route: standard / medium
- [ ] 4.4 Synthesis lane via the wiki plugin: LLM-authored candidate docs with mandatory wikilink citations (D-020/D-026) (RFC-0001) — size: L · route: standard / high
- [ ] 4.5 mycelium verify / promote / demote with grounding gate G7 (D-021) (RFC-0001) — size: M · route: standard / medium
- [ ] 4.6 Quarantine path + secret scanning (redact_secrets) (D-017) (RFC-0001) — size: S · route: standard / medium
- [ ] 4.7 Ingestion fixture corpus with element inventories (RFC-0001) — size: M · route: fast / low

---

## Milestone 5 — v0.3 — Structure (spec Phase 3)

Graph expansion earns default-on or stays opt-in (measured either way); chats module passes its acceptance gates with zero core patches; ≥ 200 judged cases across ≥ 3 corpora; ≥ 10 external repos dogfooding

- [ ] 5.1 Symbol extraction: tree-sitter for code, definition syntax for docs (RFC-0001) — size: M · route: standard / medium
- [ ] 5.2 Wikilink + cross-reference typed edges; mycelium_neighbors full (controlled edge vocabulary, D-014) (RFC-0001) — size: M · route: standard / medium
- [ ] 5.3 Graph expansion behind its ablation gate: ≥ +3 % nDCG@10 on the relationship slice, no overall regression (spec 04 §5) (RFC-0001) — size: M · route: standard / medium
- [ ] 5.4 Entity extraction stage — optional, off by default (RFC-0001) — size: S · route: standard / medium
- [ ] 5.5 First contrib module: chats (spec doc 08) built exclusively on the public D-023 extension points — the end-to-end plugin-API validation before the freeze (RFC-0001) — size: L · route: frontier-reasoning / high (sets-pattern)
- [ ] 5.6 Stale-anchor handling proven on a heavily refactored corpus (ANCHOR_GONE semantics) (RFC-0001) — size: S · route: standard / medium

---

## Milestone 6 — v1.0 — Stable (spec Phase 4)

All gates G1–G7 green on the frozen release set; ≥ 3 recurring external contributors and ≥ 5 community plugins; zero critical security findings open; 1.0 compatibility promise published

- [ ] 6.1 Freeze the five stable contracts (identity, KIR, snapshot manifest, MCP tools, plugin protocols) + compatibility test suite (RFC-0001) — size: M · route: frontier-reasoning / extra (adr, decision-heavy)
- [ ] 6.2 Docs site: tutorial, how-tos, plugin-author guide, plugin cookiecutter (RFC-0001) — size: L · route: fast / low
- [ ] 6.3 Security review pass: threat-model-derived test suite incl. injection corpus (D-017) (RFC-0001) — size: L · route: frontier-reasoning / extra (security)
- [ ] 6.4 Public benchmark report with run manifests; agent-task gate quantified (RFC-0001) — size: M · route: standard / medium
- [ ] 6.5 Trademark search + brand decision before the public branding push (product strategy §9) (RFC-0001) — size: S · route: fast / low — owner call
- [ ] 6.6 Contribution ladder: good-first-issues, CODEOWNERS, release automation, signed artifacts + SBOM (RFC-0001) — size: M · route: fast / low

---

## Milestone 7 — v2.x — Team & platform (spec Phase 5; separate RFC cycle)

Each item enters only through its deferred-decision trigger (spec 06 §3) and its own RFC; gpt-specs is the reference blueprint on top of unchanged v1 contracts

- [ ] 7.1 Remote build cache — team-scale value without a server (RFC-0001) — size: L · route: per its own future RFC
- [ ] 7.2 Server profile: HTTP API, authn/z, namespaces/ACL with policy pushdown, Postgres catalog + object-store CAS, OpenSearch/Qdrant adapters, out-of-process plugin isolation, OTel (RFC-0001) — size: XL · route: frontier-reasoning / extra (decision-heavy, security)

---

## Spec Coverage Map

Tracks which spec section is fulfilled by which roadmap item(s). Every spec section has a
row with at least one fulfilling item and a status glyph. Legend: ⏳ not started · 🚧 in
progress · ✅ done · ❎ N/A.

| Spec § | Requirement | Roadmap items | Status |
|--------|-------------|---------------|--------|
| §1 | Objective & business context | 2.9, 2.11 | ⏳ |
| §2 | Functional requirements | 2.2–2.11, 3.1–3.7, 4.1–4.7, 5.1–5.6 | 🚧 |
| §3 | Non-functional requirements | 2.10, 3.7, 6.1, 6.3 | ⏳ |
| §4 | Logical architecture | 2.7, 3.1 | ✅ |
| §5 | Public interface | 2.8, 2.9, 3.4, 6.1 | ⏳ |
| §6 | Verification & test strategy | 2.10, 2.11, 3.7, 6.4 | ⏳ |

---

## Negotiation record (EADOS plan phase, 2026-08-29; reconciled at scaffold)

Anti-theatre: each negotiation step's concrete artifact, per the plan protocol.

- **Propose (product-manager):** priority order = the specification's own phase sequence —
  adoption wedge first (TTFV, M2), technical differentiator second (incremental DAG, M3),
  ingestion moat third (M4), ecosystem validation fourth (M5), freeze fifth (M6), platform
  last (M7); M1 governance front-runs everything because Apache-2.0 must land before any
  external contribution (D-018). No reordering vs the spec: its sequencing logic
  (doc 01 §3, doc 06) already encodes the business priorities.
- **Size & route (tech-lead):** T-shirt sizes per item above; tech debt to pay first:
  none — greenfield; governance items (1.6–1.8) are treated as debt-class blockers. The
  legacy salvage map (doc 07 §6) is an *input* to M2–M4 items, not separate items: port
  deliberately, never wholesale. Signal-tagged routes are mechanical `route_advice.py`
  resolutions; untagged routes are negotiated tech-lead judgment (substantive
  implementation → standard / medium; mechanical work → the fast / low floor).
- **Reconcile (producer):** capacity = one maintainer (risk R7) ⇒ strictly serial
  milestones, no parallel tracks, no calendar dates (pre-1.0 milestone-driven; the spec's
  "~2–3 weeks" for M2 is the spec's own estimate, not a commitment). No scope cuts: v1
  scope was already cut at design (D-002/D-011/D-019); every "what about X?" answers with
  a deferred-decision trigger (doc 06 §3), not a roadmap item. **Scaffold reconciliation
  (2026-08-29):** the template's universal bootstrap (1.1–1.5) and spec-Phase-0 item 2.1
  cover the same tooling — M1 delivers it, 2.1 closes as the all-platform verification;
  numbering is never reused, so 2.1 stays with the reconciliation note inline.
