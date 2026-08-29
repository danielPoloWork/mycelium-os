# 07 — Assessment: legacy `mycelium-os` — Rebuild or Refactor?

- **Status:** Draft
- **Subject:** `D:\gh\mycelium-os` @ `9bc2610` (tag `v2026.6.7-alpha.1`, last commit 2026-06-07)
- **Naming note (D-024):** in this document, code-font `mycelium-os` means the **legacy
  codebase** assessed here (being renamed `mycelium-os-legacy` by the owner); prose
  "Mycelium OS" means the **new engine** specified in documents 00–06, whose repository
  takes the `mycelium-os` name after the rename. Paths below reflect the pre-rename state.
- **Question:** given the Mycelium OS specification (documents 00–06), should the existing
  `mycelium-os` codebase be massively refactored into compliance, or should Mycelium OS be built
  greenfield?
- **Verdict:** **Greenfield rebuild in `mycelium`, with a systematic salvage plan from
  `mycelium-os` — which is archived as reference, brand holder, and eval corpus.**
  "Massive refactor" is rejected. §6 is the operational salvage map.

---

## 1. What `mycelium-os` actually is (measured, not remembered)

| Dimension | Finding |
|---|---|
| Size | ~45 k LOC Python (~29 k source + ~16 k smoke tests), plus ~90 YAML contracts/schemas/policies, 80+ docs pages, 30 ADRs |
| History | 131 commits (130 by the owner, 1 dependabot), single alpha tag, dormant ~8 weeks |
| Product shape | An **installer/bootstrap** (`.bootstrap-os/` hidden dir, `install.sh/ps1`, platform agent-templates) that scaffolds a knowledge vault into a target project — Obsidian-aware, pre-MCP |
| Knowledge model | **Claim-atomic**: LLM extraction (Claude) on every ingestion → S/P/O claims with bitemporal validity, conflict records, epistemic governance, entity resolution; retrieval unit = claim |
| Pipeline | Ingest (pymupdf/docx/bs4/yt-dlp, Gemini OCR) → extract claims → canonical graph → FTS5 lexical + numpy dense indexes → RRF fusion → LLM wiki synthesis |
| Serving | CLI + agent-template files (`CLAUDE.md` instructing agents to shell out). **No MCP anywhere** (one passing mention in `adapters.yaml`) |
| Also built | Multi-agent orchestrator, nightly consolidation runtime, Prometheus observability (server + 7 dashboards), backup/restore engine, migration DSL, supply-chain verify (cosign/gitsign/SLSA/SBOM), i18n × 11 languages, 10 translated READMEs |
| Quality signals, positive | Disciplined docstrings tracing to ADRs; careful error taxonomies; FTS5 used correctly; unit-normalized vectors (cosine = dot); content fingerprinting with normalization (`ingest/fingerprint.py`); deterministic RRF with tie rules; dependency minimalism in the data layer |
| Quality signals, negative | Packaging installs **unnamespaced top-level packages** (`ingest`, `backup`, `wiki`, `migration`, …) — collision-prone and un-shippable as-is; two conflicting dependency manifests (`pyproject.toml` vs `static/requirements.txt`); committed `egg-info`; indexes rebuild **fully** every time ("full rebuild every time", `indexer/lexical.py`); tests are smoke-level scripts, no property/golden/eval discipline; 1 file uses pydantic, validation is a hand-rolled JSON-Schema subset |
| Process signals | ~Half of all commits are `docs(status): post-merge catch-up` bookkeeping; 20+ stale remote branches. High ceremony per unit of product |

Credit where due: for a solo, agent-driven effort this is disciplined work, and several
fragments are genuinely good. The problem is not craftsmanship. The problem is that it is
a **different product** than the one the specification defines — and it embodies, in
working code, the same scope inflation that documents 00–06 were written to stop.

## 2. The five fundamental divergences from the Mycelium OS spec

These are not module-level gaps; each one crosses every layer of the codebase.

| # | Divergence | `mycelium-os` | Mycelium OS spec | Blast radius of converging |
|---|---|---|---|---|
| 1 | **Atomic unit of knowledge** | LLM-extracted claim (S/P/O, bitemporal, conflict-governed) | Verbatim chunk/section with resolvable citation; extracted semantics optional, `status: extracted`, off by default (D-004/D-009) | Data model, every index, retrieval unit, resolver, wiki, consolidation, all test fixtures |
| 2 | **Role of LLMs in the truth path** | Mandatory at ingestion (extraction) and serving (wiki/synthesis) — cost + fabrication surface inside trust | Deterministic compilation; LLM stages optional, recorded, quarantined from truth | Ingestion pipeline, provenance, eval methodology, cost profile |
| 3 | **Incrementality** | Content-fingerprinted ingestion, but **full index rebuilds** | Content-addressed incremental DAG as the core differentiator (D-008) | Build orchestration — the heart of the product doesn't exist yet |
| 4 | **Serving surface** | CLI + agent-template prompt files (pre-MCP world) | MCP-first, 4 read-only tools, snapshot-pinned, cited (D-011) | New serving layer + snapshot/publication semantics |
| 5 | **Product shape & packaging** | Hidden-dir bootstrap installed *into* projects; top-level unnamespaced packages | `uvx mycelium` tool + library, standard `mycelium.*` namespace, `.mycelium/` derived store | Every import statement in 45 k LOC; installer model discarded |

## 3. The refactor arithmetic

What "massive refactor to spec" would actually require:

1. Re-namespace every module (`ingest` → `mycelium.ingest`, …) — touches every import in the repo.
2. Replace the claim-centric data layer with the chunk/document model — `dataio`,
   `indexer`, `retrieval`, `wiki`, `consolidation` all consume claim shapes; nearly all
   16 k LOC of smoke tests assert claim-shaped fixtures and die with the model.
3. Build the incremental DAG (doesn't exist), snapshot manifests + atomic publish
   (doesn't exist), MCP server (doesn't exist), eval harness (doesn't exist), local ONNX
   embedding default (doesn't exist).
4. Delete or park ~60–70 % of the LOC as out-of-scope per D-001/D-004 (orchestrator,
   consolidation runtime, observability server, backup/migration engines, verify suite,
   i18n, wiki synthesis, installer engines).
5. Re-found the test suite (pytest, property tests, golden determinism, eval gates).

End state: **≈ 85 % new or rewritten code, achieved by archaeology through 30 ADRs that
anchor every deletion to a negotiation with the past.** There is a second, subtler cost
specific to agent-driven development: a large in-repo corpus of old ADRs, old schemas,
and old conventions continuously steers coding agents back toward the old architecture.
In a greenfield repo, the only context is the spec.

The classic "never rewrite from scratch" rule (Netscape) protects battle-tested,
user-derived edge-case knowledge. `mycelium-os` has an alpha tag, no known users, and
smoke-level verification: the protected asset barely exists, and the parts that do encode
real learning (fingerprinting, FTS5 setup, RRF ties, extractor wrappers) are small,
self-contained, and **portable** — which is exactly what §6 does with them.

## 4. Why not "keep both goals" inside `mycelium-os`

Because the repo's own gravity is the risk. The claim/epistemics machinery is the most
intellectually attractive part of the codebase and the least appropriate for the wedge
(document 01 §3: coding agents need cited sections and symbols, not S/P/O triples).
Keeping it in-tree guarantees it keeps pulling scope. Deleting it in-tree burns weeks.
Parking it *out-of-tree* (archive) costs nothing and loses nothing — Git remembers.

## 5. Correction of record (document 00, G-6)

Document 00 flagged `gpt-specs`' claim "the repository currently carries the MIT License"
as a factual error. Root cause now identified: **`mycelium-os` is MIT-licensed** — the
claim leaked from the adjacent repo's context. It remains false for `mycelium` (no LICENSE
file), and D-018 (Apache-2.0 for Mycelium OS) stands. Relicensing note: 130/131 commits are the
owner's; the single dependabot commit touches only a GitHub Actions manifest, so porting
code fragments from `mycelium-os` (MIT, sole-authored) into Apache-2.0 Mycelium OS is legally
clean, with a courtesy provenance note per ported file.

## 6. Salvage map (the actual value of `mycelium-os`)

### 6.1 Port as code (adapt + type + test to Mycelium OS standards)

| Asset | From | Into (Mycelium OS) | Notes |
|---|---|---|---|
| Byte/text normalization + `sha256:` fingerprinting | `ingest/fingerprint.py` | data model §1 canonical hashing | Nearly a drop-in implementation of the spec'd rules |
| FTS5 build/query patterns (incl. `optimize`, escaping) | `indexer/lexical.py`, `retrieval/lexical.py` | store + lexical candidate generator | Re-target from claims to chunks; keep the craft |
| RRF fusion with deterministic tie-breaking | `retrieval/fusion.py` | retrieval §3 | Matches spec; port with property tests |
| Query planner scaffolding (stop-words, phrase detection, FTS escaping, bounds) | `retrieval/planner.py` | retrieval §2 heuristic planner | Same transparent-rules philosophy |
| Unit-normalized vector store (cosine = dot) | `indexer/vector.py` | interim vector path until sqlite-vec lands | numpy fallback keeps Phase 1 unblocked |
| File extractor wrappers (pymupdf, docx, bs4) | `ingest/extractors/*`, deps list | Phase-2 fallback parsers behind KIR adapters | docling stays primary (D-007); these become fallbacks + test oracles |
| CI workflow patterns | `.github/workflows/*` | mycelium CI | pr-check/release skeletons are reusable |

### 6.2 Port as ideas (spec/ADR references, no code)

- **Source-trust scoring** (ADR-030) → informs `trust_class` ranking weights (retrieval §4).
- **Pipeline determinism doc** (`docs/.../pipeline-determinism.md`) → cross-check against
  compiler golden tests.
- **Raw-state machine for ingestion staging** (ADR-010 §3) → quarantine/staging states in
  the Phase-2 connector contract.
- **Bitemporal model, conflict records, epistemic governance** (ADR-002/003) → the
  long-horizon "assertions" layer; explicitly parked behind the deferred-decision trigger
  for the acceptance workflow (document 06 §3). This is good thinking for a **later,
  different layer** — possibly a Mycelium OS plugin, possibly its own product.

### 6.3 Reuse as assets

- **Eval corpus:** `mycelium-os`'s own docs tree (80+ pages, 30 ADRs, runbooks) becomes
  the second Phase-0/1 evaluation corpus (retrieval §7.6) — real, heterogeneous,
  technical, and the owner can author ground-truth judgments for it quickly.
- **Brand:** the Mycelium name, logo set, and Discord remain candidate branding for the
  1.0 launch (product strategy §9). The repo holds them; nothing is lost by archiving.
- **Fixtures:** hostile/edge-case files accumulated in tests feed the Phase-2 ingestion
  fixture corpus.

### 6.4 Explicitly parked (do not port; do not delete — archived)

Multi-agent orchestrator; consolidation runtime; wiki LLM synthesis; observability
server + dashboards; backup/restore + migration DSL (Git + deterministic rebuild cover
v1 per D-016); supply-chain verify suite (returns as release *process* at Phase 4, mostly
config); i18n × 11 (post-1.0 docs concern); installer/bootstrap engines (obsolete under
the `uvx mycelium` model).

## 7. Archival plan for `mycelium-os`

1. Merge or delete the ~20 stale remote branches (they are bookkeeping, not work).
2. Tag `archive/pre-mycelium` at `main`; add a README banner: *"Superseded by Mycelium OS (link).
   This repository remains as design archive, brand holder, and evaluation corpus.
   MIT-licensed; fragments are ported into Mycelium OS under Apache-2.0 with provenance notes."*
3. GitHub: mark repository as archived (read-only) **after** the salvage ports of §6.1
   land in Mycelium OS with tests — not before, to keep `git blame`/reference friction low
   during porting.
4. Do not rewrite history, do not delete: it is the project's provenance.

## 8. Risks of the rebuild decision (stated honestly)

| Risk | Reality check | Mitigation |
|---|---|---|
| **Second-system effect** — greenfield invites rebuilding the same over-scope with nicer types | This is R1 in document 06 and the single biggest danger | Mycelium OS v1 is *strictly smaller* than `mycelium-os` (5 stable contracts, 2 surfaces, phase gates); any scope addition needs a deferred-decision trigger |
| Rebuild discards working code | §3: convergence would rewrite ≈ 85 % anyway; §6 ports the rest deliberately | Salvage map is part of the Phase-0/1/2 backlogs, not an afterthought |
| Morale cost of archiving 131 commits | Real, and worth naming | Nothing is deleted; the archive is load-bearing (corpus, brand, fixtures, ADR quarry) — `mycelium-os` becomes Mycelium OS's research repo, which is an honorable role, not a failure |
| "Rebuild" drifts into months of silence | The failure mode of rewrites | Phase 0 exit gate is a *running* skeleton in 2–3 weeks (document 06 §1); if Phase 0 slips materially, revisit this assessment |
