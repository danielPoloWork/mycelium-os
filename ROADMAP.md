# ROADMAP — Mycelium OS

Negotiated at the EADOS `plan` phase (2026-08-29) from the approved design
[RFC-0001](docs/rfc/0001-mycelium-os-v1.md), which validates the specification package
[`.draft-specs/`](.draft-specs/README.md) as the v1 design of record. Milestones 2–7 map
the specification's Phases 0–5 one-to-one; each milestone's **goal is that phase's exit
gate** — a milestone closes when its gates are green, not when its items are merely
merged (delivery doctrine, spec doc 06).

- **Versioning:** SemVer, pre-1.0 milestone-driven. No calendar dates: capacity is a
  single maintainer (risk R7) and dates would be theatre; sequence and exit gates are the
  commitment.
- **Sizing:** T-shirt (`XS S M L XL`) — macroscopic, not story points.
- **Routes** (`size · route: <tier> / <effort>`): the advisory model tier + reasoning
  effort per item from the `os/routing` policy (ADR-0017) — capability **tiers, never
  model names** (the dated catalog owns names). The human keeps final model authority; a
  mismatch warns, never switches.
- Every item traces to the RFC it implements (`roadmap-covers-rfcs` gate).

## Milestone 1 — Bootstrap & governance

Goal: the repository is legally and procedurally ready for external eyes — license
decided on disk, default branch settled, delivery pipeline merged.

- [ ] 1.0 Stand up the EADOS delivery pipeline — manifest + RFC-0001 (RFC-0001) — size: M · route: frontier-reasoning / high (sets-pattern) — **in review as PR #1**
- [ ] 1.1 Replace LICENSE MIT → Apache-2.0 (RFC-0001, D-018) — size: XS · route: fast / low — owner-confirmed 2026-08-29
- [ ] 1.2 Rename default branch `master → main` (RFC-0001) — size: XS · route: fast / low — **owner operation** on GitHub
- [ ] 1.3 Add SECURITY.md (private disclosure channel), CONTRIBUTING.md (DCO), CODE_OF_CONDUCT.md (RFC-0001) — size: S · route: fast / low

## Milestone 2 — Walking skeleton (spec Phase 0)

Goal (exit gates): Mycelium OS builds and serves its own repository; TTFV < 10 min
demonstrated end-to-end via Claude Code; byte-identical rebuild in CI; `mycelium eval`
runs and reports. Spec's own effort estimate: ~2–3 weeks of focused work.

- [ ] 2.1 Repo scaffold: uv workspace, ruff + mypy --strict + pytest, CI matrix Linux/macOS/Windows on CPython 3.12+ (RFC-0001) — size: S · route: fast / low
- [ ] 2.2 `mycelium.sdk.types`: pydantic records v0 + JSON Schema export (RFC-0001) — size: M · route: frontier-reasoning / high (sets-pattern: the record schemas are contracts everything else builds on)
- [ ] 2.3 Canonical hashing + ULID + anchor-slug identity library, property-tested (RFC-0001) — size: M · route: standard / medium
- [ ] 2.4 Markdown→KIR adapter (markdown-it) + frontmatter contract + Mycelium Markdown Profile v1 (RFC-0001, D-022) — size: M · route: standard / medium
- [ ] 2.5 Heading-bounded chunker with the no-content-loss property test (RFC-0001) — size: M · route: standard / medium
- [ ] 2.6 SQLite store: DDL, WAL, field-weighted FTS5, meta table (RFC-0001) — size: M · route: standard / medium
- [ ] 2.7 Build orchestrator v0 (sequential) + snapshot manifest + atomic CURRENT swap + single-writer lock (RFC-0001, D-015) — size: L · route: frontier-reasoning / high (sets-pattern: publication/crash-safety semantics set here bind every later phase)
- [ ] 2.8 CLI skeleton (typer): init/build/search/show/doctor with `--json` (RFC-0001) — size: S · route: fast / low
- [ ] 2.9 MCP server (stdio): `mycelium_search` + `mycelium_fetch`, typed errors, data-not-instructions notice (RFC-0001, D-011/D-017) — size: M · route: standard / medium
- [ ] 2.10 Determinism golden test wired into CI — gate G6 (RFC-0001) — size: S · route: standard / medium
- [ ] 2.11 Eval harness v0 + first 20 judged cases on Mycelium OS's own docs (RFC-0001, D-010) — size: M · route: standard / medium

## Milestone 3 — v0.1 "The compiler" (spec Phase 1)

Goal (exit gates): incremental single-doc rebuild < 2 s p95 and byte-equal to a clean
rebuild; `mycelium_search` p95 < 150 ms on the 10⁵-chunk reference corpus; gates
G1/G2/G6 green (a lexical-only shipped default is a legitimate G2 outcome).

- [ ] 3.1 Content-addressed incremental DAG + build cache + dirty detection (RFC-0001, D-008) — size: L · route: frontier-reasoning / high (sets-pattern: the product's technical differentiator)
- [ ] 3.2 Snapshot list/rollback + GC (RFC-0001) — size: S · route: standard / medium
- [ ] 3.3 Local ONNX embedder default (zero keys, offline) + vectors keyed `(chunk_digest, model_id)` + hybrid RRF (RFC-0001, D-013/D-009) — size: M · route: standard / medium
- [ ] 3.4 `mycelium_neighbors` on authored links + `mycelium_explain` (RFC-0001) — size: M · route: standard / medium
- [ ] 3.5 Watch mode: debounced FS events → incremental builds (RFC-0001) — size: S · route: standard / medium
- [ ] 3.6 `mycelium export` JSONL interchange bundle (RFC-0001, D-006) — size: S · route: fast / low
- [ ] 3.7 Eval slices + CI gates G1–G6; agent-task suite v0 (≥ 20 tasks) vs the grep baseline (RFC-0001, D-010) — size: M · route: standard / medium

## Milestone 4 — v0.2 "Ingestion" (spec Phase 2)

Goal (exit gates): zero silent element loss on the fixture corpus (every element
represented / opaque / dropped-by-policy / failed-and-reported); hostile-file suite
quarantines without failing the build; an ingestion-heavy corpus joins the eval set.

- [ ] 4.1 Connector/Parser protocols exercised for real: docling adapter (PDF/DOCX/HTML), pandoc fallback (RFC-0001, D-007) — size: M · route: standard / medium
- [ ] 4.2 CAS custody of originals; KIR v0 hardened on hostile fixtures; opaque-node escape hatch (RFC-0001) — size: M · route: standard / medium
- [ ] 4.3 Evidence-lane projection with provenance frontmatter, fidelity reports, per-document loss budgets (RFC-0001, D-020) — size: M · route: standard / medium
- [ ] 4.4 Synthesis lane via the `wiki` plugin: LLM-authored candidate docs with mandatory wikilink citations (RFC-0001, D-020/D-026) — size: L · route: standard / high
- [ ] 4.5 `mycelium verify` / `promote` / `demote` with grounding gate G7 (RFC-0001, D-021) — size: M · route: standard / medium
- [ ] 4.6 Quarantine path + secret scanning (`redact_secrets`) (RFC-0001, D-017) — size: S · route: standard / medium
- [ ] 4.7 Ingestion fixture corpus with element inventories (RFC-0001) — size: M · route: fast / low

## Milestone 5 — v0.3 "Structure" (spec Phase 3)

Goal (exit gates): graph expansion earns default-on or stays opt-in — the gate is that
the decision is measured; the `chats` module passes its doc-08 acceptance gates with
zero core patches; ≥ 200 judged cases across ≥ 3 corpora; ≥ 10 external repos
dogfooding; stale-anchor handling proven under heavy refactoring.

- [ ] 5.1 Symbol extraction: tree-sitter for code, definition syntax for docs (RFC-0001) — size: M · route: standard / medium
- [ ] 5.2 Wikilink + cross-reference typed edges; `mycelium_neighbors` full (controlled vocabulary, D-014) (RFC-0001) — size: M · route: standard / medium
- [ ] 5.3 Graph expansion behind its ablation gate: ≥ +3 % nDCG@10 on the relationship slice, no overall regression (RFC-0001) — size: M · route: standard / medium
- [ ] 5.4 Entity extraction stage — optional, off by default (RFC-0001) — size: S · route: standard / medium
- [ ] 5.5 First contrib module: `chats` (spec doc 08) built exclusively on the public D-023 extension points — the end-to-end plugin-API validation before the freeze (RFC-0001, D-025) — size: L · route: frontier-reasoning / high (sets-pattern)
- [ ] 5.6 Stale-anchor handling proven on a heavily refactored corpus (`ANCHOR_GONE` semantics) (RFC-0001) — size: S · route: standard / medium

## Milestone 6 — v1.0 "Stable" (spec Phase 4)

Goal (exit gates): all gates G1–G7 green on the frozen release set; ≥ 3 recurring
external contributors and ≥ 5 community plugins; zero critical security findings open;
the 1.0 compatibility promise published.

- [ ] 6.1 Freeze the five stable contracts (identity, KIR, snapshot manifest, MCP tools, plugin protocols) + compatibility test suite (RFC-0001) — size: M · route: frontier-reasoning / extra (adr, decision-heavy)
- [ ] 6.2 Docs site: tutorial, how-tos, plugin-author guide, plugin cookiecutter (RFC-0001) — size: L · route: fast / low
- [ ] 6.3 Security review pass: threat-model-derived test suite incl. injection corpus (RFC-0001, D-017) — size: L · route: frontier-reasoning / extra (security)
- [ ] 6.4 Public benchmark report with run manifests; agent-task gate quantified (RFC-0001) — size: M · route: standard / medium
- [ ] 6.5 Trademark search + brand decision before the public branding push (RFC-0001) — size: S · route: fast / low — **owner call**
- [ ] 6.6 Contribution ladder: good-first-issues, CODEOWNERS, release automation, signed artifacts + SBOM (RFC-0001) — size: M · route: fast / low

## Milestone 7 — v2.x "Team & platform" (spec Phase 5 — separate RFC cycle)

Goal: each item enters **only** through its deferred-decision trigger (spec doc 06 §3)
and its own future RFC; `gpt-specs` is the reference blueprint, built on v1 contracts
unchanged since Phase 1. Not scheduled — listed so the seams stay visible.

- [ ] 7.1 Remote build cache — team-scale value without a server (RFC-0001) — size: L · route: per its own RFC
- [ ] 7.2 Server profile: HTTP API, authn/z, namespaces/ACL with policy pushdown, Postgres catalog + object-store CAS, OpenSearch/Qdrant adapters, out-of-process plugin isolation, OTel (RFC-0001) — size: XL · route: per its own RFC (decision-heavy, security)

---

## Negotiation record (plan phase, 2026-08-29)

Anti-theatre: each step's concrete artifact, per the negotiation protocol.

- **Propose (product-manager):** priority order = the specification's own phase sequence —
  adoption wedge first (TTFV, M2), technical differentiator second (incremental DAG, M3),
  ingestion moat third (M4), ecosystem validation fourth (M5), freeze fifth (M6), platform
  last (M7); M1 governance front-runs everything because Apache-2.0 must land before any
  external contribution (D-018). No reordering vs the spec was proposed — its sequencing
  logic (doc 01 §3, doc 06) already encodes the business priorities.
- **Size & route (tech-lead):** T-shirt sizes above; tech debt to pay first: none —
  greenfield; the governance items (1.1–1.3) are treated as debt-class blockers. The
  legacy salvage map (doc 07 §6) is an *input* to M2–M4 items, not separate items: port
  deliberately, never wholesale. Routes resolved with `route_advice.py` where signals are
  declared (sets-pattern → frontier-reasoning/high; adr/decision-heavy/security →
  frontier-reasoning/extra; default → fast/low) and by tech-lead judgment elsewhere
  (substantive implementation → standard/medium).
- **Reconcile (producer):** capacity = one maintainer (risk R7) ⇒ strictly serial
  milestones, no parallel tracks, no calendar dates (pre-1.0 milestone-driven; the
  spec's "~2–3 weeks" for M2 is recorded as the spec's own estimate, not a commitment).
  No scope cuts: v1 scope was already cut aggressively at design (D-002/D-011/D-019);
  every "what about X?" answers with a deferred-decision trigger (doc 06 §3), not a
  roadmap item. Milestone vocabulary: SemVer (software domain).
