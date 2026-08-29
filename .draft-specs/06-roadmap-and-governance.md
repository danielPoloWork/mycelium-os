# 06 — Roadmap, Governance, and Risks

- **Status:** Draft
- **Depends on:** all previous documents

Delivery doctrine: **verified vertical slices, each ending in something a real user can
run.** A phase exits only when its gates are green. No phase builds machinery whose user
does not yet exist — the deferred-decisions table (§3) is the pressure valve that keeps
scope honest.

---

## 1. Phases

### Phase 0 — Walking skeleton (target: ~2–3 weeks of focused work)

**Scope:** repo scaffold (uv, ruff, mypy strict, pytest, CI); pydantic schemas v0 +
exported JSON Schemas; Markdown-only pipeline (discover → parse → chunk → FTS index →
manifest); `mycelium init/build/search/serve`; MCP `mycelium_search`/`mycelium_fetch`; determinism
golden test; first 20 eval cases on Mycelium OS's own docs; LICENSE + governance files (§4).

**Exit gates:** Mycelium OS builds and serves its own repository; TTFV < 10 min demonstrated
end-to-end via Claude Code; byte-identical rebuild in CI; `mycelium eval` runs and reports.

### Phase 1 — v0.1 "The compiler"

**Scope:** content-addressed incremental DAG + build cache; snapshot publication +
rollback + `mycelium snapshots`; vectors (local ONNX default) + hybrid RRF; `mycelium_neighbors`
on authored links; `mycelium_explain`; watch mode; `mycelium export`; eval slices + gates G1–G6
wired into CI; agent-task suite v0 (≥ 20 tasks).

**Exit gates:** incremental single-doc rebuild < 2 s p95 and equals clean-rebuild output;
G1/G2/G6 green (G2 may legitimately conclude "ship lexical default" — that is a pass,
not a failure); search p95 < 150 ms on the 10⁵-chunk reference corpus.

### Phase 2 — v0.2 "Ingestion"

**Scope:** connector/parser plugin protocols exercised for real: docling adapter (PDF,
DOCX, HTML), CAS custody of originals, KIR v0 hardened on hostile fixtures, Markdown
projection with provenance frontmatter, fidelity reports + loss budgets, quarantine
path, secret scanning; ingestion fixture corpus with element inventories.

**Exit gates:** zero silent element loss on the fixture corpus (every element
represented / opaque / dropped-by-policy / failed-and-reported); hostile-file suite
(malformed, zip-bomb-ish, encrypted) quarantines without build failure; an
ingestion-heavy corpus joins the eval set.

### Phase 3 — v0.3 "Structure"

**Scope:** symbol extraction (tree-sitter for code fences/repos, definition syntax for
docs); wiki-link and cross-reference edges; typed-edge graph + `mycelium_neighbors` full;
graph expansion behind its ablation gate (retrieval §5); entity extraction as an
optional off-by-default stage; ≥ 200 judged eval cases across ≥ 3 corpora; **first
contrib module: `chats`** (document 08) built exclusively on the public D-023 extension
points — the end-to-end plugin-API validation before the Phase-4 freeze.

**Exit gates:** graph expansion earns default-on or stays opt-in (either is a valid
outcome — the gate is that the decision is *measured*); the `chats` module passes its
document-08 acceptance gates using zero core patches; ≥ 10 external repos dogfooding;
stale-anchor handling proven on a corpus with heavy refactoring.

### Phase 4 — v1.0 "Stable"

**Scope:** freeze the five stable contracts (architecture §10); compatibility test suite;
docs site (tutorial, how-tos, plugin-author guide, cookiecutter); security review pass
(threat-model-derived test suite incl. injection corpus); public benchmark report with
manifests; agent-task gate quantified; brand/trademark decision (product strategy §9);
contribution ladder (good-first-issues, CODEOWNERS, release automation).

**Exit gates:** all gates G1–G6 green on the frozen release set; ≥ 3 recurring external
contributors and ≥ 5 community plugins; zero critical findings open from security review;
1.0 compatibility promise published.

### Phase 5 — v2.x "Team & platform" (separate RFC cycle; `gpt-specs/` is the blueprint)

Remote build cache (the Bazel move — team-scale value without a server); then the server
profile: HTTP API, authn/z, namespaces/ACL with policy pushdown, Postgres catalog +
object-store CAS adapters, OpenSearch/Qdrant adapters, out-of-process plugin isolation,
OTel. Each item enters only through the deferred-decision triggers below and its own RFC.
This is where `gpt-specs`' requirement tables, threat model, and scale NFRs apply nearly
verbatim — on top of contracts that have not changed since Phase 1.

## 2. First engineering backlog (Phase 0 → 1, reviewable units)

1. Repo scaffold: uv workspace, ruff/mypy-strict/pytest, CI matrix (Linux/macOS/Windows).
2. Governance files: LICENSE (Apache-2.0), SECURITY.md, CONTRIBUTING.md (DCO), CoC.
3. `mycelium.sdk.types` + pydantic records + JSON Schema export (data model §§3–7).
4. Canonical hashing + ULID + anchor-slug library (identity rules, data model §2) — property-tested.
5. Markdown parser→KIR adapter (markdown-it tokens → KIR v0) + frontmatter contract.
6. Chunker (heading-bounded, token-budgeted, atomic tables/code) + no-loss property test.
7. SQLite store: DDL, WAL setup, FTS5 with field weights, meta table.
8. Build orchestrator v0 (sequential) + manifest writer + `CURRENT` atomic swap + lock.
9. CLI skeleton (typer): init/build/search/show/doctor with `--json`.
10. MCP server (stdio): `mycelium_search`, `mycelium_fetch` + typed errors + notice string.
11. Eval harness v0: case loader, metrics, report, `--gate`; seed 20 cases.
12. Determinism golden test + CI wiring.
13. Build cache (content-addressed) + incremental dirty detection.
14. Snapshot list/rollback + GC.
15. Local ONNX embedder plugin + vectors table + hybrid RRF + `mycelium_explain`.
16. Watch mode (debounced) reusing the incremental path.
17. `mycelium export` JSONL bundle.
18. Agent-task suite v0 (20 tasks, scripted via Claude Code headless).

## 3. Deferred decisions with explicit triggers (adopted pattern from `gpt-specs`)

| Decision | Deferred until | Trigger |
|---|---|---|
| Graph database | Post-Phase 3 | In-memory/SQLite traversal measurably fails a named query slice on a real corpus |
| Learned/LLM reranker | Post-Phase 3 | Deterministic pipeline plateaus on frozen sets AND budget exists for the latency/cost |
| LLM summarization in serving path | Post-1.0 | Verbatim packing measurably insufficient for real agent tasks; requires fabrication-risk eval |
| Formal ontology / entity acceptance workflow | Post-1.0 | Controlled vocabulary demonstrably limiting on a real corpus; a named owner exists |
| Plugin sandboxing + signed registry | Ecosystem phase | ≥ 1 third-party plugin with meaningful adoption exists |
| HTTP API + SDKs | Phase 5 | A consumer that cannot use MCP/CLI actually appears |
| Remote build cache | Phase 5 entry | ≥ 1 team dogfooding with measured duplicate-build pain |
| Multi-tenancy, policy engine, RBAC | Phase 5 | An organization commits to deploying the server profile |
| Rust hotpaths | Post-1.0 | Profiling shows a specific stage dominating and Python optimization exhausted |
| SaaS offering | Never by default | Separate business decision with its own RFC; not an engineering milestone |

## 4. Open-source governance

- **License:** Apache-2.0 (D-018), committed in Phase 0, before any external
  contribution. Rationale: explicit patent grant removes the main enterprise-adoption
  objection to MIT; ecosystem-standard for infrastructure. (Note: `gpt-specs`' claim that
  MIT is already in place is false — no LICENSE file exists.)
- **Contributions:** DCO sign-off (lightweight; a CLA adds friction with no benefit at
  this scale). Conventional commits. CODEOWNERS from Phase 1.
- **Decision process:** lightweight RFCs — an `rfcs/` directory, one Markdown file per
  proposal, PR-reviewed, decisions recorded in the document-00 decision log. Changes to
  the five stable contracts *require* an RFC; everything else is a normal PR.
- **Security:** SECURITY.md with a private disclosure channel from Phase 0; documented
  triage targets from 1.0 (critical: 24 h acknowledge / 7 d fix-or-mitigation — adopting
  `gpt-specs` NFR-SEC-005 at the point where it becomes honest).
- **Releases:** SemVer; automated from CI; CHANGELOG (keep-a-changelog); signed artifacts
  + SBOM from 1.0.
- **Community strategy:** the benchmark reports are the marketing — publish honest
  numbers (including "hybrid didn't beat lexical on X") and reproduction manifests;
  integration guides for Claude Code and Codex in the first docs; plugin cookiecutter at
  Phase 2 close; examples gallery of real repos.
- **Process independence:** governance is self-contained in the repository; no external
  process framework is required to contribute (G-7).

## 5. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | **Overbuild** — the project repeats the inputs' failure mode and architect-plays instead of shipping | High (documented tendency) | Fatal | This package: phase gates, deferred-decision triggers, D-002/D-011 scope cuts; every "what about X?" answers with a trigger, not a subsystem |
| R2 | Mycelium OS doesn't beat agentic grep on real tasks | Medium | Fatal (no reason to exist) | Grep-baseline gate from Phase 1 (retrieval §7.4); if it fires, fix product or stop — honestly |
| R3 | Embedding friction (keys, cost, download) kills TTFV | Medium | High | Local ONNX default, lexical-only fallback profile, degraded-snapshot semantics |
| R4 | MCP protocol churn | Medium | Medium | Pin stable revision, negotiate forward, adapter isolated in one module |
| R5 | docling/parser dependency churn or license drift | Medium | Medium | KIR boundary isolates parsers; pandoc fallback; fixture corpus catches regressions |
| R6 | SQLite ceiling reached earlier than expected | Low at wedge scale | Medium | Measured, not assumed; storage behind the store interface; Phase-5 adapters are the answer, not premature abstraction |
| R7 | Maintainer bus factor = 1 | High initially | High | Boring stack (D-003), strict typing, spec-as-onboarding, contribution ladder by Phase 4 |
| R8 | Malicious documents (parser exploits, injection) damage trust | Medium | High | Quarantine path, hostile-fixture suite, injection corpus as release gate, untrusted-content doctrine |
| R9 | Scope capture by adjacent hype (agent memory, agent runtime) | High | High | D-001/D-004 non-goals; complementary-positioning story (product §5) redirects the energy |
| R10 | Naming/trademark collision at launch | Low | Low | Phase-4 trademark search before public branding push |

## 6. What acceptance of this package means

Accepting this package = accepting the decision log (document 00 §3) and the Phase-0
scope. It does **not** mean every detail is frozen: any decision can be overturned by a
recorded counter-decision (RFC), and the evaluation harness exists precisely so that
future arguments are settled by measurement instead of by whoever writes the longest
architecture document.
