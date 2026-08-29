# RFC-0001: Mycelium OS v1 — knowledge compiler and serving layer

- **Status:** Accepted
- **Author:** tech-lead (EADOS delivery agent, session 2026-08-29) · **Reviewers:** reviewer + enterprise-architect (cross-cutting) · **Approver:** tech-lead
- **Date:** 2026-08-29
- **Related:** specification package [`.draft-specs/`](../../.draft-specs/README.md) (docs 00–08, decision log D-001…D-026); manifest [`orchestrator/project.yaml`](../../orchestrator/project.yaml) (milestones 2–7); legacy assessment [doc 07](../../.draft-specs/07-mycelium-os-assessment.md)

> Import-mode RFC: the design of record is the reviewed specification package
> `.draft-specs/`, produced 2026-07-31 and amended by owner direction the same day
> (doc 00 §4). This RFC validates that package into the EADOS delivery pipeline: it
> distills the load-bearing decisions, fills the design folds, and carries the approval
> that gates `design → plan`. Where this summary and the package disagree, **the package
> wins** — and the discrepancy is a bug in this RFC.

## Context

Coding agents (Claude Code, Codex CLI, and every MCP-capable successor) operate on
repositories with no knowledge layer: they re-grep and re-read the same documents every
session, have no structural map of what is authoritative or superseded, cannot see across
the repo boundary into the PDFs and wikis that govern the code, and receive context
assembled by ad-hoc heuristics with no citations and no way to measure quality. Teams
compensate with hand-maintained `CLAUDE.md`/`AGENTS.md` files — knowledge compilation *by
hand*. The practice proves the need; the tooling is missing (package doc 01 §2).

Two prior artifacts explored this product: a 40-page ideation discussion and a rigorous
but strategically inverted specification package (`gpt-specs`, not vendored in this
repository). Both were critically reviewed in doc 00: the discussion contributes the
differentiating idea (deterministic, incremental, hash-based knowledge compilation —
"Bazel for knowledge") wrapped in requirements inflation; `gpt-specs` contributes
professional-quality invariants (authority layering, loss-aware fidelity, snapshot
semantics, evaluation doctrine, threat framing) sequenced fortress-first. The package
renders a verdict on every major claim of both.

What forces the decision now: the repository exists under the decided name (D-024), the
legacy codebase has been assessed and archived (`.mycelium-os-legacy/`, doc 07 — verdict:
greenfield rebuild with a salvage map), and the Phase-0 backlog cannot start without an
approved design. Constraints: open-source bootstrap with initial bus factor 1 (risk R7),
design for the corpus scale that exists — 10²–10⁵ documents, local, single-tenant
(D-002) — and time-to-first-value as the adoption driver (< 10 minutes, doc 01 §3).

## Decision

Adopt the specification package `.draft-specs/` (docs 00–08) as the **v1 design of
record**, and deliver it per the manifest milestones 2–7. The load-bearing decisions
(full log: doc 00 §3):

| Decision | Substance |
|---|---|
| D-001 | Knowledge **compiler + serving layer** for AI agents — not an agent runtime, not a RAG framework, not a chat product |
| D-002 | v1 scale: repo-scale, local-first, single-tenant; `namespace`/`trust_class` reserved in every schema |
| D-003 | Python 3.12+, single language; Rust only for profiled hotspots post-1.0 |
| D-004 | Layered authority: evidence bytes (CAS) → authored Markdown (Git) → derived artifacts (disposable); agent memory out of scope |
| D-005/D-006 | Sources in Git; derived store `.mycelium/` gitignored; SQLite (WAL + FTS5 + vector) as engine; JSONL as interchange only |
| D-007 | KIR: thin versioned JSON document AST over ecosystem parsers (docling, markdown-it); Mycelium owns the representation, not parsers |
| D-008 | **Content-addressed incremental build DAG** with deterministic stages, golden tests, snapshot manifests — the technical differentiator |
| D-009/D-014 | Hybrid retrieval (BM25 + vector, RRF; optional gated graph expansion); typed edges with controlled vocabulary, no ontology |
| D-010 | Evaluation harness ships Phase 0, permanent release gate; the baseline to beat is the agent's built-in grep |
| D-011 | v1 public surfaces: **CLI + MCP (stdio) only** |
| D-012/D-023 | Plugins: in-process typed Protocols + four generic extension mechanisms (stages, hooks, CLI subcommands, opt-in MCP tools); no runtime capability negotiation |
| D-013 | Default embedder local (ONNX, zero keys, offline); providers opt-in; vectors keyed `(chunk_digest, model_id)` |
| D-015 | Single-writer lock; WAL concurrent readers; atomic snapshot-pointer publication; rollback = repoint |
| D-016 | `schema_version` everywhere; v1 migration policy: rebuild |
| D-017 | All source content untrusted (tested injection doctrine); read-only MCP; secret scan; offline by default; no telemetry |
| D-018 | License **Apache-2.0** (owner reconfirmed 2026-08-29 over the on-disk MIT file) |
| D-019 | Enterprise/platform profile is Phase 5, `gpt-specs` as blueprint, on unchanged v1 contracts |
| D-020/D-021 | Dual-lane ingestion (deterministic evidence lane always; LLM synthesis lane authoring cited candidate docs) + folder-encoded verification workflow (`verified`/`candidate`/`evidence`, `mycelium verify`/`promote`) |
| D-022 | Authored format: Mycelium Markdown Profile v1 (Obsidian-flavored); wikilinks are first-class edge sources |
| D-024/D-026 | One name everywhere: `mycelium` (import, binary, config, URIs, entry points, MCP tool prefix); plugin ids are capability nouns (`wiki`, `chats`) |
| D-025 | First contrib module: `chats` (doc 08), built only on public extension points — the plugin-API validation |

Delivery sequence: manifest milestones 2–7 map the package's Phases 0–5 one-to-one, each
with the package's own exit gates as the milestone goal. Phase 5 items enter only through
their deferred-decision triggers (doc 06 §3) and their own future RFCs.

### API contract (`api` / `systemdesign`)

The public surface is exactly two consumer-facing contracts plus one contributor-facing
contract (spec doc 05; aligned with manifest `spec.public_api`):

- **MCP tools** (stdio transport, read-only, every response carries `snapshot_id`):
  - `mycelium_search` — in: `query`, `k`, `budget_tokens`, `include_text: full|snippet|none`,
    `filters` (collection/tag/path/trust), `explain`; out: `results[]` (each: `uri`,
    `title`, `heading_path`, verbatim `text`, `lines`, `trust_class`,
    `verification_status`, `score`, `via`), `truncated`/`omitted`, and the
    data-not-instructions `notice`.
  - `mycelium_fetch` — in: `uri`, `context: chunk|section|document`; out: verbatim content +
    provenance (trust, fidelity warnings). Dead anchor → typed `ANCHOR_GONE` + nearest
    surviving ancestor URI.
  - `mycelium_neighbors` — in: `uri`, `types[]`, `depth` (1 in v1), `limit`; out: typed,
    weighted neighbors, each edge labeled `authored|extracted`.
  - `mycelium_explain` — in: `query`; out: chosen plan + matched rule, per-stage timings,
    per-candidate signal scores, dedupe/stitch decisions, gate-relevant config.
- **CLI** (`mycelium init|build|ingest|verify|promote|demote|search|show|neighbors|eval|export|snapshots|rollback|gc|doctor|serve`):
  exit codes 0/1/2 (ok / operation failed / usage error), `--json` on every read command,
  no interactive prompts in non-TTY contexts, `NO_COLOR` honored.
- **Plugin SDK** (`mycelium.sdk`): typed Protocols `Parser`, `Chunker`, `Embedder`,
  `Extractor`, `Synthesizer`, `Reranker`; generic extension points `PipelineStage`,
  lifecycle hooks, CLI sub-apps, opt-in MCP tools. Resolution is pinned by config and
  recorded in build keys + snapshot manifest — never "best available".
- **Error model** (MCP): `INVALID_ARGUMENT`, `NOT_FOUND`, `ANCHOR_GONE`,
  `SNAPSHOT_UNAVAILABLE`, `BUDGET_EXCEEDED`, `INTERNAL`. Failure taxonomy for builds:
  quarantine (per-document), degraded snapshot (e.g. `vectors: absent`), never a torn
  publish.
- **Versioning:** SemVer. Pre-1.0: minor may break with CHANGELOG migration notes.
  At 1.0 the **five stable contracts** freeze — identity rules, KIR schema, snapshot
  manifest schema, MCP tool contracts, plugin protocols (spec doc 02 §10) — and breaking
  any of them is a MAJOR bump. Plugins declare a `mycelium_api_version` range; the registry
  refuses incompatible plugins with a precise error. MCP protocol: pin stable revision,
  negotiate forward.

An OpenAPI/IDL stub (`capabilities.api_spec`) is deliberately **off**: v1 has no HTTP
surface (D-011); the MCP tool contracts above live in spec doc 05 §3 and freeze at 1.0.

### Data & schema (`database`)

Within ADR-0004's frame: SQLite is a secondary **store component** behind the store
interface, not a language, and explicitly replaceable (spec doc 02 §10).

- **Entities & relations** (spec doc 03): `documents` (ULID identity, folder-derived
  `verification_status`, provenance, trust) ← `chunks` (heading-path anchors, content
  digests) ← `vectors` keyed `(chunk_digest, model_id)`; `symbols`; typed `edges`
  (controlled vocabulary of 8 types, `authored|extracted` status); optional `entities`;
  immutable `snapshots`; `build_cache` keyed by build key. Citation URIs
  (`mycelium://<doc_id>#<heading-path>/<ordinal>`) key on `doc_id`, so citations survive
  folder moves — including `candidate/ → verified/` promotion.
- **Normalization:** read-mostly derived store; deliberately denormalized JSON columns
  (`provenance_json`, `stats_json`, `heading_path_json`) because every row is a build
  artifact rebuilt from source — there is no update path to anomalies. FTS5 and the
  vector table are derived indexes over `chunks`.
- **Migration policy:** v1 = **rebuild** (D-016). Every record carries `schema_version`;
  a newer Mycelium refusing an older snapshot must say so and offer `mycelium build` — never
  reinterpret silently. Forward migration machinery is deferred until derived data stops
  being disposable (platform phase).

### Scalability budgets (`scalability`)

Numeric targets, one per hard axis (manifest `spec.nonfunctional_reqs`; spec docs 01 §8,
04 §1; enforced as eval/CI gates per doc 04 §7.3):

| Axis | Budget |
|---|---|
| Query latency | `mycelium_search` end-to-end **p95 ≤ 150 ms** (stage budgets: candidates 60 / fusion 20 / graph 30 / stitch+pack 40 ms) on the reference profile: 10⁵ chunks, laptop, warm store |
| Incremental build | single-document edit rebuild **< 2 s p95**, byte-equal to a clean rebuild |
| Adoption | install → cited answers over MCP **< 10 min** (TTFV, Phase-0 exit gate) |
| Trust | citation coverage **= 1.00** every release (G1); false-answer rate on `unanswerable` **≤ 5 %** (G4) |
| Corpus envelope | 10²–10⁵ documents (D-002) — budgets are stated against the top of this envelope |
| Determinism | byte-identical rebuild for deterministic stages (G6) — a correctness budget with value 0 tolerance |
| Grounding (promotion, G7) | a synthesized doc is promotion-eligible only at `cites` coverage **≥ 0.95** of claim-bearing statements AND sampled entailment **≥ 0.90** — config defaults in `mycelium.toml`, ablatable, not frozen contract |

No RAM/GPU ceiling is asserted: the package deliberately leaves memory as
measured-not-budgeted at v1 scale (laptop reference profile); absolute IR-quality numbers
(Recall@50 ≥ 0.90 etc.) are GA-phase goals, not v1 gates (doc 00 G-5, doc 04 §7.3).

### Algorithm sketch (`pseudocode`)

The incremental build core (spec doc 02 §4.2), language-free:

```text
build(repo, config):
    acquire_writer_lock()
    plan    = discover(repo, config)              # doc set + per-doc source digests
    dirty   = docs whose source digest, config slice, or stage version changed
    removed = docs in previous manifest but absent from plan
    for doc in dirty (parallel, bounded):
        for stage in topo_order:                  # parse → normalize → chunk → … → index
            key = SHA256(stage_id, impl_version, input_digests, config_digest, schema_version)
            artifact = cache.get(key) or run_stage(stage, doc)
    rebuild global artifacts whose inputs changed  # graph closure, stats
    staging = assemble(unchanged ∪ rebuilt − removed)
    validate(staging)                              # schema, referential integrity,
                                                   # citation resolvability, counts
    manifest = write_snapshot_manifest(staging)    # immutable, ULID
    atomically swap CURRENT → manifest.id          # tmp file + rename + fsync
    gc_unreferenced(after retention window)
    release_writer_lock()
```

Invariants: readers never observe a torn state (they read the snapshot pinned by
`CURRENT`); an interrupted build leaves `CURRENT` untouched; ordered chunk texts
reproduce the normalized document text exactly (property-tested).

### Cross-cutting

- **Security (D-017):** all source content is untrusted data — retrieved text returns as
  typed, quoted evidence; Mycelium never interprets instructions found in content; injection
  resistance is a *tested property* (adversarial fixture corpus in the release gates).
  Read-only MCP; secret scan at ingestion with index exclusion; path-safe connectors; zero
  network calls unless configured; no telemetry.
- **Performance observability:** `mycelium build --profile`, `journal.jsonl` structured events,
  `mycelium doctor`; OTel deferred post-1.0 with event names chosen now.
- **Namespace deviation (EADOS mechanics):** D-024 fixes a **flat** import package
  `mycelium` — the manifest records `group_path = group_dotted = namespace = "mycelium"`,
  a deliberate deviation from EADOS's reverse-domain `{group}.{slug}` convention. If
  `/eados scaffold` is run, the rendered tree must honor the flat `src/mycelium` layout
  (Python src-layout), not `src/main/python/<group>/<slug>`; this needs a project ADR at
  scaffold time.
- **Two RFC tracks, one log:** EADOS delivery RFCs live here (`docs/rfc/`); the *public*
  contributor-facing RFC process (self-contained `rfcs/`, doc 06 §4 — no external process
  framework required to contribute, G-7) starts at the contribution-ladder milestone.
  Decisions land in the doc-00 decision log either way.

## Alternatives

Each rejected on a concrete reason (full analyses: docs 00 and 07):

1. **Refactor the legacy `mycelium-os` codebase** — rejected: convergence to this design
   rewrites ≈ 85 % of it anyway (doc 07 §3); its full-index-rebuild architecture lacks the
   product's core differentiator (incremental DAG). Salvage map feeds Phases 0–2 instead.
2. **Implement `gpt-specs` as written** (Rust+Python polyglot, transactional catalog,
   CLI+HTTP+MCP, policy labels, OTel from day one) — rejected: a quarter of platform work
   before a single user can feel value (G-1/G-2); re-sequenced to Phase 5 on preserved
   contracts rather than discarded.
3. **Build on an existing RAG framework** (LlamaIndex, GraphRAG, Cognee) — rejected: none
   provides deterministic, content-addressed incremental compilation with snapshot
   semantics and a verification workflow — the differentiator would sit on foundations
   that cannot guarantee it (doc 01 §5 positioning).
4. **Event-sourced system of record** — rejected: duplicates Git for file-based truth
   (F-4); the derived world is a deterministic function of sources — rebuild is recovery.
5. **Graph-first retrieval / day-one ontology** — rejected: signal selection is empirical
   (F-8); an ontology is a curation cost center without an owner (F-9). Typed edges +
   ablation gates instead.
6. **Being an agent runtime** (memory, planner, executor) — rejected: different product,
   crowded fast-churning segment; Mycelium serves runtimes over MCP (F-10, D-001).
7. **JSONL/flat files as the query engine** — rejected: conflates interchange with
   querying (F-7); SQLite wins on indexes, transactions, concurrent readers; JSONL stays
   as the export format.
8. **MIT license** (the file currently on disk) — rejected by owner reconfirmation of
   D-018 (2026-08-29): Apache-2.0's explicit patent grant removes the main enterprise
   objection; swap is milestone item 1.a.

## Consequences

- **Easier:** trust story (citations + folder-encoded verification + injection doctrine)
  is testable from Phase 0; adoption needs no accounts or keys (local embedder, offline
  default); Phase-5 platform can be built on frozen contracts without an identity
  migration; benchmark honesty (manifest-pinned eval runs) doubles as marketing.
- **Harder:** every pipeline stage must participate in build keys and determinism
  discipline — contributor friction by design; dual-lane ingestion doubles the ingestion
  test surface (fidelity + grounding); folder-encoded status makes Git hygiene
  load-bearing; the grep baseline (D-010) can kill features honestly — including the
  whole product if it never beats grep (risk R2 accepted with a stop-honestly clause).
- **Migration path:** legacy salvage per doc 07 §6 (ported deliberately, never wholesale);
  `.draft-specs/` stays the reference package until superseded by in-repo docs
  (milestone 6.2); changes to the five stable contracts require an RFC from Phase 1 on.
- **Follow-up roadmap:** manifest milestones 2–7 (`orchestrator/project.yaml`), with
  milestone-1 governance items 1.a–1.c (LICENSE swap to Apache-2.0, `master → main`
  rename, SECURITY/CONTRIBUTING/CoC) — all human-gated through the EADOS plan phase next.

## Approval

Filled by the approver **after** review (this is the `rfc-approved` gate's record):

```
approved-by: tech-lead (2026-08-29)
```

Owner decision recorded: the maintainer approved in-session on 2026-08-29 (EADOS design
gate); the tech-lead role adds this record on that authority — no self-approval.

Reviewers (structured findings addressed): reviewer — resolved; enterprise-architect — resolved.

| # | Role | Finding | Resolution |
|---|---|---|---|
| F1 | reviewer | `architecture_style: Hexagonal` in the manifest is an inference — the package names no style | Kept, explicitly annotated as inference in the manifest comment; this RFC does not assert it as package fact |
| F2 | reviewer | G7 grounding thresholds (0.95 / 0.90) were referenced but not stated among the numeric budgets | Added to the scalability table, marked as ablatable config defaults, not frozen contract |
| F3 | enterprise-architect | Checkpoint `confirmed_by: danielPoloWork` records the owner handle; the session git identity is "Daniel Polo" — identities not mechanically verifiable in-session | Surfaced to the owner at this approval gate; ledger is a one-line correction if the confirmer differs |
| F4 | enterprise-architect | The factory's YAML subset rejects folded scalars (`>-`); first manifest write failed validation | Manifest prose fields rewritten as literal blocks (`\|`); `render.py --check` now OK |
| F5 | reviewer | Milestone goals must quote the package's exit gates faithfully | Verified line-by-line against doc 06 §1 — no drift found |

## References

- Specification package: [`.draft-specs/README.md`](../../.draft-specs/README.md) — reading order and status semantics
- Decision log: [`.draft-specs/00-verdict-and-decisions.md`](../../.draft-specs/00-verdict-and-decisions.md) (D-001…D-026 + amendment record)
- Architecture: [`.draft-specs/02-architecture.md`](../../.draft-specs/02-architecture.md) · Data model: [`.draft-specs/03-data-model.md`](../../.draft-specs/03-data-model.md)
- Retrieval & evaluation: [`.draft-specs/04-retrieval-and-evaluation.md`](../../.draft-specs/04-retrieval-and-evaluation.md) · Interfaces & plugins: [`.draft-specs/05-interfaces-and-plugins.md`](../../.draft-specs/05-interfaces-and-plugins.md)
- Roadmap & governance: [`.draft-specs/06-roadmap-and-governance.md`](../../.draft-specs/06-roadmap-and-governance.md) · Legacy verdict: [`.draft-specs/07-mycelium-os-assessment.md`](../../.draft-specs/07-mycelium-os-assessment.md) · Chats module: [`.draft-specs/08-module-chats.md`](../../.draft-specs/08-module-chats.md)
- Manifest: [`orchestrator/project.yaml`](../../orchestrator/project.yaml)
- `gpt-specs/` — prior specification package, **not vendored here**; Phase-5 reference blueprint (D-019), summarized in doc 00 §2
