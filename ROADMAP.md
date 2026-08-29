# Roadmap — mycelium-os

The project's plan as a numbered, checkbox-driven list. When an item completes in a PR,
flip its checkbox (`- [ ]` → `- [x]`) **in the same PR**. New work goes at the bottom of
its section with a fresh `<milestone>.<task>` number; never renumber.

- **Versioning start:** pre-1.0 milestone-driven.
- **Session journal:** see [`docs/journal/`](docs/journal/). Latest checkpoint: _none yet_.
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
- [ ] 1.4 Stand up the CI matrix (Linux / Windows / macOS on CPython 3.12+) with build + test + format + lint. (RFC-0001) — size: S · route: fast / low
- [x] 1.5 Seed the version constant (__version__ = 'X.Y.Z') in `src/mycelium/__about__.py`. (RFC-0001) — size: XS · route: fast / low — delivered alongside 1.1 in PR #5 (hatch's dynamic version reads this file; the two are inseparable at build-system stand-up)
- [x] 1.6 Replace LICENSE MIT → Apache-2.0 (D-018; owner-confirmed 2026-08-29) (RFC-0001) — size: XS · route: fast / low — delivered in the scaffold bootstrap PR
- [x] 1.7 Rename default branch master → main (owner operation on GitHub; owner-confirmed 2026-08-29) (RFC-0001) — size: XS · route: fast / low — done by the owner 2026-08-29 (origin/HEAD → main)
- [ ] 1.8 Add SECURITY.md (private disclosure channel), CONTRIBUTING.md (DCO), CODE_OF_CONDUCT.md (spec 06 §4) (RFC-0001) — size: S · route: fast / low — SECURITY.md complete (channel = GitHub private vulnerability reporting; activate the repo feature at public launch — register F3); CONTRIBUTING.md + CODE_OF_CONDUCT.md remain

---

## Milestone 2 — Walking skeleton (spec Phase 0)

Mycelium OS builds and serves its own repository; TTFV < 10 min end-to-end via Claude Code; byte-identical rebuild in CI; mycelium eval runs and reports

- [ ] 2.1 Repo scaffold: uv workspace, ruff + mypy --strict + pytest, CI matrix Linux/macOS/Windows on CPython 3.12+ (RFC-0001) — size: XS · route: fast / low — reconciled: the tooling is delivered by M1 items 1.1–1.5; this item closes when the skeleton is green on all three OSes
- [ ] 2.2 mycelium.sdk.types: pydantic records v0 + JSON Schema export (spec 03 §§3–7) (RFC-0001) — size: M · route: frontier-reasoning / high (sets-pattern: the record schemas are the contracts everything else builds on)
- [ ] 2.3 Canonical hashing + ULID + anchor-slug identity library, property-tested (spec 03 §2) (RFC-0001) — size: M · route: standard / medium
- [ ] 2.4 Markdown→KIR adapter (markdown-it) + frontmatter contract + Mycelium Markdown Profile v1 (D-022) (RFC-0001) — size: M · route: standard / medium
- [ ] 2.5 Heading-bounded chunker with the no-content-loss property test (RFC-0001) — size: M · route: standard / medium
- [ ] 2.6 SQLite store: DDL, WAL, field-weighted FTS5, meta table (spec 03 §8) (RFC-0001) — size: M · route: standard / medium
- [ ] 2.7 Build orchestrator v0 (sequential) + snapshot manifest + atomic CURRENT swap + single-writer lock (RFC-0001) — size: L · route: frontier-reasoning / high (sets-pattern: publication/crash-safety semantics set here bind every later phase)
- [ ] 2.8 CLI skeleton (typer): init/build/search/show/doctor with --json (RFC-0001) — size: S · route: fast / low
- [ ] 2.9 MCP server (stdio): mycelium_search + mycelium_fetch, typed errors, data-not-instructions notice (RFC-0001) — size: M · route: standard / medium
- [ ] 2.10 Determinism golden test wired into CI (gate G6) (RFC-0001) — size: S · route: standard / medium
- [ ] 2.11 Eval harness v0 + first 20 judged cases on Mycelium OS's own docs (RFC-0001) — size: M · route: standard / medium

---

## Milestone 3 — v0.1 — The compiler (spec Phase 1)

Incremental single-doc rebuild < 2 s p95 equal to clean output; search p95 < 150 ms on the 10^5-chunk reference corpus; gates G1/G2/G6 green (lexical-only default is a legitimate G2 outcome)

- [ ] 3.1 Content-addressed incremental DAG + build cache + dirty detection (D-008) (RFC-0001) — size: L · route: frontier-reasoning / high (sets-pattern: the product's technical differentiator)
- [ ] 3.2 Snapshot list/rollback + GC (mycelium snapshots, rollback, gc) (RFC-0001) — size: S · route: standard / medium
- [ ] 3.3 Local ONNX embedder default (zero keys, offline) + vectors keyed (chunk_digest, model_id) + hybrid RRF (D-013/D-009) (RFC-0001) — size: M · route: standard / medium
- [ ] 3.4 mycelium_neighbors on authored links + mycelium_explain (RFC-0001) — size: M · route: standard / medium
- [ ] 3.5 Watch mode: debounced FS events → incremental builds (RFC-0001) — size: S · route: standard / medium
- [ ] 3.6 mycelium export JSONL interchange bundle (D-006) (RFC-0001) — size: S · route: fast / low
- [ ] 3.7 Eval slices + CI gates G1–G6; agent-task suite v0 (≥ 20 tasks) vs the grep baseline (D-010) (RFC-0001) — size: M · route: standard / medium

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
| §2 | Functional requirements | 2.2–2.11, 3.1–3.7, 4.1–4.7, 5.1–5.6 | ⏳ |
| §3 | Non-functional requirements | 2.10, 3.7, 6.1, 6.3 | ⏳ |
| §4 | Logical architecture | 2.7, 3.1 | ⏳ |
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
