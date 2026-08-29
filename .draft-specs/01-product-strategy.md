# 01 — Product Strategy

- **Status:** Draft
- **Depends on:** [00-verdict-and-decisions.md](00-verdict-and-decisions.md)

Neither input artifact answers the only questions that determine whether an open-source
project reaches global scale: *who feels the pain, why is this the cure, and why now?*
This document answers them, and every technical document downstream is constrained by it.

---

## 1. Mission

> **Compile any project's knowledge into a deterministic, versioned, queryable substrate —
> and serve it to AI agents with citations they can trust.**

One sentence shorter: **the knowledge compiler for AI agents.**

## 2. The problem, concretely

Coding agents (Claude Code, Codex CLI, Cursor, and every MCP-capable successor) operate
on repositories with **no knowledge layer**. Today an agent:

- re-greps and re-reads the same documents every session, spending tokens to rediscover
  what was known yesterday;
- has no structural map — which document is authoritative, what supersedes what, where a
  concept is defined versus merely mentioned;
- cannot see across the boundary of the repo into the PDFs, wikis, and specs that
  actually govern the code;
- receives context assembled by ad-hoc heuristics, with no citations and no way to
  measure whether context quality is improving or regressing.

Teams respond with hand-maintained `CLAUDE.md`/`AGENTS.md` files — which is knowledge
compilation *by hand*. That is the signal: the need is real, the tooling is missing, and
the practice is already docs-as-code. Mycelium OS mechanizes it.

## 3. The wedge (v1 target)

**A developer using a coding agent on a repository with meaningful documentation.**

- Scale: 10²–10⁵ documents; single user; local machine.
- Entry: `uvx mycelium init && mycelium build && mycelium serve` — under ten minutes from install to the
  agent answering with cited knowledge over MCP.
- The corpus is already in Git (docs-as-code), or arrives via ingestion (PDF/DOCX/HTML →
  Markdown projection + preserved originals).

Why this wedge and not "enterprise knowledge management":

1. **Distribution.** Developers adopt CLI tools in an afternoon and evangelize them; MCP
   gives a standard socket into every major agent, so Mycelium OS needs zero partnership deals to
   integrate everywhere.
2. **The corpus is tractable.** Repo-scale knowledge fits a laptop; no infrastructure
   sale precedes first value.
3. **The buyer ladder exists.** Individual → team (shared knowledge, remote cache) →
   organization (server profile, access control). This is the dbt/Grafana/Terraform
   ladder, and it is the only ladder that reliably reaches "global scale" for OSS
   infrastructure.

## 4. Personas by phase

| Phase | Persona | Job to be done |
|---|---|---|
| v0.x | Developer with a coding agent | "My agent should already know what my project knows, with citations, without me pasting context." |
| v0.x | Technical writer / docs-as-code maintainer | "Turn our scattered PDFs and wiki exports into governed Markdown the team and the agents share." |
| v1.x | Team lead | "One knowledge build for the whole team; new members and CI agents get it for free." |
| v2+ | Platform operator | "Serve governed, access-controlled knowledge to hundreds of engineers and their agents." (This is where `gpt-specs/` applies.) |
| all | Plugin author | "Add my parser/embedder/retriever through a stable, typed, boring API." |

## 5. Competitive landscape and differentiation

| Category | Representatives | What they are | Why Mycelium OS is different |
|---|---|---|---|
| RAG frameworks | LlamaIndex, LangChain, Haystack | Code libraries: you assemble a pipeline in Python and own the glue | Mycelium OS is a *product with an artifact model*, not a toolkit: deterministic builds, snapshots, citations, an MCP server — zero glue code to first value |
| Graph-RAG pipelines | Microsoft GraphRAG, LightRAG | Batch corpus→graph pipelines, LLM-heavy, expensive, full-rebuild oriented | Mycelium OS is **incremental by construction** (content-addressed DAG); graph features must pass ablation gates instead of being the premise |
| Agent memory | Cognee, Graphiti, Letta/Mem0 | Store and evolve *the agent's own experience* | Different layer: Mycelium OS is the **shared, governed substrate** (tier-1/2 truth); agent memory is per-agent state and is explicitly out of scope (D-004). Complementary, not competing |
| Document parsers | Docling, Unstructured, MarkItDown | Extraction libraries | Upstream dependencies, not competitors — Mycelium OS wraps them behind KIR adapters (D-007) and adds custody, fidelity accounting, and everything downstream |
| Code/enterprise search | Sourcegraph, Glean | Proprietary/SaaS, code-centric or enterprise-IT-centric | Mycelium OS is open source, local-first, git-native, and covers *knowledge* (docs + ingested sources), not only code |
| Human PKM | Obsidian, Foam, wikis | Human reading/writing surfaces | Complementary by design: `knowledge/` **is** a valid Obsidian vault (D-022 — wikilinks, callouts, frontmatter); Mycelium OS adds the machine side — compilation, citations, budgets, MCP serving — on top of the same files humans read and edit |

**The differentiation thesis, in five properties** (each is a spec requirement, not marketing):

1. **Deterministic incremental compilation.** Same sources + same config ⇒ byte-identical
   artifacts; one changed document ⇒ only its dependents rebuild. "dbt for knowledge" —
   no open competitor has this as a core invariant.
2. **Git-native and local-first.** Truth lives in the user's repo under their VCS; the
   derived store is disposable; nothing requires a service to exist.
3. **Loss-aware ingestion custody.** Originals preserved content-addressed; every
   transformation accounted; fidelity reported — versus the ecosystem's silent lossy
   conversions.
4. **Eval-gated honesty.** Retrieval features ship only with measured lift over the
   lexical baseline *and* over agentic grep; every answer carries citations that resolve.
5. **MCP-first serving.** The agent interface is the product's front door, not an
   afterthought adapter.

## 6. Why now

- MCP standardized the agent↔tool socket (2025); every major agent client speaks it.
- Coding agents crossed into mainstream daily use; their context assembly is now the
  visible bottleneck users complain about.
- The parsing layer matured (Docling et al.), so ingestion no longer requires a research
  team.
- No open project owns "deterministic knowledge builds"; the analogy niche (dbt: 2016 →
  category king) is empty and legible.

## 7. Non-goals (v1, restated from D-001/D-004)

- No agent runtime (planner/executor/critic), no chat UI, no hosted SaaS.
- No multi-tenancy, RBAC, or policy engine (fields reserved; machinery deferred).
- No model hosting or fine-tuning; no universal ontology.
- No claim of byte-perfect Markdown round-trips for arbitrary formats (loss-aware custody
  instead).

## 8. Success metrics

Adoption metrics (product):

| Metric | Target |
|---|---|
| Time-to-first-value (install → cited MCP answer) | < 10 min, no API key required (D-013) |
| Dogfooding | Mycelium OS's own repo builds and serves itself from Phase 0 |
| External validation | ≥ 10 external repos using Mycelium OS by v0.3; ≥ 3 recurring external contributors and ≥ 5 community plugins by v1.0 |

Quality metrics (permanent release gates — details in document 04):

| Metric | Gate |
|---|---|
| Citation coverage | 1.00 — every returned passage resolves to a source anchor |
| Retrieval lift | Hybrid beats BM25-only by ≥ 5 % nDCG@10 overall, no slice regressing > 2 %; otherwise the lexical default ships |
| Agent-task uplift | On the curated task suite, agent-with-Mycelium OS beats agent-with-grep on task success; qualitative pre-1.0, quantified at 1.0 |
| Performance | Cold build 1k docs < 60 s; incremental single-doc rebuild < 2 s p95; search p95 < 150 ms @ 10⁵ chunks (local reference hardware) |
| Determinism | Byte-identical rebuild on identical inputs, verified in CI |

## 9. Naming — DECIDED (D-024, 2026-07-31)

The owner confirmed: **Mycelium, for every repository and every identifier.** Org:
Mycelium LABS; engine repo `mycelium-os` (the legacy codebase is renamed
`mycelium-os-legacy` by the owner, freeing the name); import package `mycelium`; binary
`mycelium`; `mycelium.toml`; `.mycelium/` store; `mycelium://` URIs; `mycelium_id`
frontmatter; `mycelium.plugins` entry points; `mycelium_*` MCP tools. PyPI distribution:
**`mycelium-os`** (verified available 2026-07-31; `mycelium` is held by an unrelated
package abandoned since 2019 — a PEP 541 transfer request is a Phase-0 backlog item, and
if granted the distribution moves to `mycelium` before 1.0, keeping `mycelium-os` as a
transitional alias; the console script is `mycelium` either way). The import-name overlap
with the abandoned package is a theoretical collision only (dead since 2019, and
uvx/venv isolation covers CLI users); PEP 541 eventually removes it. The earlier working
name "KOS" is retired and survives only as history in the decision log. One name
everywhere; shipping two names is forbidden. A trademark search remains a pre-1.0-launch
task (document 06) — note the unrelated "Mycelium" Bitcoin-wallet brand exists in a
different trademark class.

## 10. Ecosystem alignment — Mycelium LABS founder page

The public site describes a nine-repository ecosystem ("one platform, one shared source
of truth"). This spec is deliberately **depth-first** (one engine until 1.0) where the
site is **breadth-first** (an org chart of repositories). The vision is compatible; the
build order is governed here, not by the site (risk register R1/R9 — promised breadth
must not drive engineering sequence).

### 10.1 Repository map

| LABS element | Status in this specification |
|---|---|
| `mycelium-os` — "ingestion, retrieval, knowledge graph, governance, orchestration" | **This product** — with one correction: *orchestration is excluded from the core* (D-001, F-10). Agent runtimes integrate via MCP; the site's engine description should drop or re-scope the word "orchestration" |
| `mycelium-cli` | In-core from Phase 0 (thin shell over the library). A separate repo pre-1.0 multiplies compat/CI surface with zero user value; P1 is satisfied by module boundaries + the five stable contracts, not by repo count |
| `mycelium-codex` (public portal) | Not in v1 — but **enabled by design**: it consumes `mycelium export` bundles (JSONL + Markdown interchange, D-006/data-model §9). Correct home: separate project, post-1.0 |
| `mycelium-app` (GUI cockpit) | Engine non-goal (§7). Future separate product on the same contracts; nothing in v1 blocks it |
| `mycelium-sdk` (TS/Py/Go/Rust) | Phase 5, with the HTTP surface (D-011). In v1 the *APIs are MCP + CLI* — explicit, documented, versioned, which is what "API First" actually requires |
| `mycelium-docs` / `-templates` / `-examples` / `-community` | Phase-4 community infrastructure: docs site, plugin cookiecutter (the templates seed), examples gallery, contribution ladder (06 §1/§4) |
| LABS Phase 4 "Agentic" (autonomous workflows, multi-agent orchestration, Knowledge Operations Center) | **Deliberately not this product** (D-001). It can exist as future LABS repos *on top of* the substrate, built by or with agent runtimes over MCP. The site should present it as ecosystem destination, not engine scope |

### 10.2 Principles and trade-offs → enforcing mechanisms

Every slogan on the site has a mechanism in this spec — this is the founder-facing
strength of the package:

| Site claim | Enforcing mechanism |
|---|---|
| "Docs go stale → kept alive" | Incremental compiler + watch mode (D-008); synthesis lane for readable docs (D-020) |
| "Wikis disconnected → traceable" | Wikilink-first graph (D-022), typed edges incl. `cites`/`derived_from`, `mycelium_neighbors`, `mycelium_explain` |
| "AI lacks context → governed, explainable" | MCP with citations, trust + verification labels on every result, injection doctrine (D-017), read-only default |
| P1 Separation of concerns | Five stable contracts (architecture §10); everything else declared replaceable |
| P2 API first | Contract-first discipline; MCP + CLI as the v1 APIs; compatibility tests in CI |
| P3 Local first | Offline-by-default build, local ONNX embedder, zero cloud runtime dependency (D-005/D-013) |
| P4 Agent ready | MCP is the front door, not an adapter (§5) |
| P5 Knowledge centric | The entire authority model (D-004) |
| "Governance over uncontrolled automation" | Human-in-the-loop promotion default, G7 grounding gate (D-021) |
| "Knowledge preservation over information loss" | CAS evidence custody + loss-aware fidelity reports (D-020, F-3) |
| "Transparency over opacity" | Snapshot manifests, explain payloads, honest published benchmarks — including negative results (G2 policy, 06 §4) |
| "Human–AI collaboration over AI replacement" | Verification workflow: LLM authors, human promotes (D-020/D-021) |

### 10.3 Founder-facing sequencing note

For recruiting technical co-founders, one working engine with honest benchmarks beats
nine scaffolded repositories — sophisticated candidates diligence GitHub and read thin
repos as vaporware. Recommended presentation: keep the ecosystem page as the destination,
mark `mycelium-os` as "in build, spec-complete" with a link to this package, and mark the
other eight as "planned — opens at Phase N". The specification package itself is a
recruiting asset: it demonstrates that the vision has a disciplined delivery plan.
