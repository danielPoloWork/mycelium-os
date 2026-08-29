# 00 — Verdict and Decision Log

- **Status:** Draft
- **Inputs reviewed:** `Mycelium OS - Knowledge OS.pdf` (40 pp discussion), `gpt-specs/` (6 documents, 2 schemas)

This document is the mentoring core of the package. It is deliberately blunt. Where the
discussion or the prior spec is right, that is said once; where it is wrong, the error is
named, explained, and replaced with a decision.

---

## 1. Verdict on the originating discussion

### 1.1 What survives review

These instincts from the discussion are correct and are carried into the specification:

| Idea | Why it is right |
|---|---|
| Markdown as the human-authoritative format for authored knowledge | Docs-as-code is the adoption wedge; humans must be able to edit truth in their editor and diff it in Git. |
| All indexes are derived and regenerable | The single most important invariant in the system. Everything downstream of source is a build artifact. |
| JSONL over YAML for machine-facing records | Append-friendly, streamable, greppable, mergeable line-by-line. Correct for interchange. |
| Embeddings separated from metadata, keyed by model | Embedding models will be replaced repeatedly; metadata must not churn when they do. |
| Symbol index as a first-class artifact | Genuinely underexploited in the RAG ecosystem; agents ask "where is X defined/used" constantly. |
| Structure-aware (heading/hierarchy) retrieval over naive vector search | Industry evidence agrees; flat top-k chunking is the weakest baseline. |
| Hybrid retrieval (lexical + vector + structure) | Correct and now industry consensus. |
| Incremental, hash-based rebuilds ("Bazel for knowledge") | **The differentiating idea of the whole discussion.** Nobody in the open RAG ecosystem does deterministic incremental knowledge compilation well. |
| Separation of Knowledge Repository / Indexes / Agent Memory | Correct conceptual split; prevents agent state from contaminating truth. |
| Contract-first extension points | Correct — as compile-time interfaces. See §1.2.7 for what went wrong with it. |
| Schema versioning from day one | Correct; cheap now, impossible to retrofit. |
| Writing RFCs before code | Correct instinct; adopted as a lightweight process in document 06. |

### 1.2 Where the discussion fails

**F-1. Requirements inflation without a user.**
The dialogue moves from "my markdown notes for Claude Code" (page 1) to "millions of
documents, tens of billions of relations, thousands of concurrent agents" (page 20) in
nineteen pages, without a single user, corpus, or workload measurement appearing in
between. Every subsequent architectural escalation (event sourcing, microkernel, plugin
buses, capability negotiation) is justified by this imaginary scale. This is the classic
LLM-assisted failure mode: the model mirrors ambition back as architecture, and each
round of "what about X?" adds a subsystem. An architecture must be *earned by evidence*.
The specification therefore targets the scale that actually exists (repo-scale corpora,
10²–10⁵ documents) and preserves growth through **stable contracts**, not pre-built
machinery.

**F-2. The source-of-truth contradiction is never resolved.**
Page 1: "the truth of source will be markdown files." Page 9–10: "Files no longer exist.
Markdown is only `render(KnowledgeObject)`." These are opposite architectures — one keeps
truth in human-editable files under Git; the other moves truth into an internal object
store and demotes Markdown to a report. The discussion adopts both, alternately, and
never notices. The consequence is real: if Markdown is a render, humans can no longer
edit truth in their editor, and the entire docs-as-code adoption path dies.
**Resolution (D-004):** layered authority — original source bytes are evidence; authored
Markdown is authoritative where it is the native source; everything else is derived.
(`gpt-specs` reached the same resolution; it is correct, and adopted.)

**F-3. "Lossless ingestion into Markdown" is impossible, and pretending otherwise is worse.**
PDF page geometry, DOCX tracked changes, spreadsheet formulas, slide layers, and media
timecodes do not survive projection into Markdown. A system that *claims* losslessness
will silently lose information; a system that *accounts for* loss is trustworthy.
**Resolution:** loss-aware custody — preserve original bytes content-addressed, map every
recognized element into the intermediate representation, represent the unrecognizable as
opaque nodes, and emit a per-document fidelity report. (Adopted from `gpt-specs`, which
gets this exactly right.)

**F-4. Event sourcing duplicates Git.**
For file-based truth, Git commits already are the append-only event log — with
authorship, ordering, diffs, and distribution solved. Layering a second event store over
it adds operational surface and consistency questions while providing nothing Git does
not. And the derived world does not need an event log at all, because it is a
*deterministic function of the sources*: rebuild is the recovery mechanism.
**Resolution (D-008):** Git for source history; a content-addressed build cache for the
derived world; an operational journal (append-only log file) for diagnostics only. Event
buses return, if ever, at the distributed phase — as transport, not as the system of
record.

**F-5. "A microkernel — like Linux for knowledge."**
Linux is the most famous *monolithic* kernel in history; it won precisely against
microkernel designs (Minix, HURD) by shipping working software with pragmatic internal
modularity and stable external contracts. The metaphor refutes the argument it decorates.
The correct lesson from Linux/LLVM/Kubernetes is: **small, stable public contracts;
ruthless internal pragmatism; extension points added where third parties actually
appear** — not a plugin bus built in advance of any plugin author.

**F-6. Bazel is invoked, then contradicted.**
The discussion cites Bazel/Buck2 as the model for the Semantic Build System — and
simultaneously proposes committing derived artifacts (indexes, embeddings, caches) to
Git. Build systems version *sources and lockfiles* and treat outputs as cache. Committing
derived JSONL/embeddings to Git produces merge conflicts on hash churn, repository bloat,
and a false sense that the artifacts are authoritative.
**Resolution (D-005):** derived store is gitignored; reproducibility comes from
deterministic builds pinned by a manifest (the lockfile analogue); portable JSONL bundles
are produced by `mycelium export` when interchange is needed; a shared remote build cache is
the eventual team-scale answer, exactly as in Bazel.

**F-7. "Claude works better with JSONL than SQLite" conflates two consumption modes.**
What an agent *reads into context* and what a tool *queries on the agent's behalf* are
different channels. Agents should not page raw index files into context at all — they
call tools (MCP) that execute queries and return compact, cited results. For the query
engine, SQLite (FTS5 + vector extension) beats flat JSONL on every axis that matters:
indexes, transactions, concurrent readers, memory-mapped performance. JSONL remains the
right *interchange* format.
**Resolution (D-005/D-006):** SQLite as the local query engine; JSONL as export; both
derived, both disposable.

**F-8. Graph-first as universal doctrine.**
"Vector is only one signal" is right; "graph traversal first, always" is not. Exact
identifier and symbol queries are best served lexically; conceptual queries need vectors;
relationship queries benefit from the graph. Signal selection is an empirical, per-query
decision — which is why the evaluation harness (document 04) exists. (`gpt-specs`
Alternative F reaches the same conclusion; adopted.)

**F-9. Ontology as a day-one requirement.**
A real ontology is a curation cost center: someone must own it, evolve it, and police it,
forever. Projects die of this. Typed edges with a small controlled vocabulary deliver
most of the retrieval value at a fraction of the cost.
**Resolution (D-014):** controlled edge vocabulary in v1; ontology namespaces are a
deferred decision with an explicit trigger (document 06, §Deferred).

**F-10. The Agent Runtime does not belong in this product.**
Planner/Executor/Critic/Reflection is a different product with different security,
evaluation, and release dynamics — and it is the most crowded, fastest-churning segment
of the ecosystem. Mycelium OS serves knowledge *to* agent runtimes (Claude Code, Codex, LangGraph,
anything MCP-capable); it does not compete with them. (`gpt-specs` Alternative J agrees;
adopted.) This is the single most important scope cut in the package.

**F-11. Forty pages of architecture; zero pages of evaluation, security, or operations.**
A retrieval system without an evaluation harness is unfalsifiable — every architectural
addition can be argued and nothing can be measured. The discussion also never mentions
prompt injection (the defining security problem of agent-facing knowledge systems),
concurrency, crash safety, or observability.
**Resolution:** evaluation is a Phase-0 deliverable and a release gate (document 04);
the untrusted-content doctrine is a v1 requirement (document 02, §8).

**F-12. Seven-level namespace inheritance, multi-tenancy, permission indexes — in a
single-user local tool.** Reserved fields cost nothing; built machinery costs everything.
**Resolution (D-002):** single namespace + collections in v1; `namespace` and
`trust_class` fields reserved in every schema so the platform phase does not require an
identity migration.

---

## 2. Verdict on `gpt-specs/`

### 2.1 Assessment

`gpt-specs/` is a genuinely strong piece of specification work. It independently
identifies and corrects most of the discussion's errors (its Executive Decision list of
six rejected claims is accurate), and its treatment of authority layering, loss-aware
fidelity, snapshot atomicity, evaluation methodology, and threat modeling is of
professional quality. The following are **adopted** into this package, simplified where
v1 scale permits:

- The **authority hierarchy** (evidence → authored content → KIR → assertions → derived → caches).
- The **loss-aware custody** definition of "lossless" (RFC-0001 §2) — verbatim in spirit.
- **Snapshots as the unit of serving** with atomic pointer publication and rollback.
- **Build keys** as content-addressed hashes over inputs + implementation + config + schema.
- The **evaluation principles** (frozen query sets, protected slices, paired comparison,
  benchmark manifests, "sophistication must earn its place").
- The **threat framing** (all source content untrusted; injection resistance as a tested
  property; assertion status so extracted claims never silently become truth).
- The **rejected-alternatives analysis** (A–J), which is almost entirely correct.
- The **deferred-decision triggers** table — the best governance idea in the package.

### 2.2 Where `gpt-specs/` fails

**G-1. It specifies the fortress before the village.**
Its Milestone 1 — the *first* running software — requires: a Rust workspace plus a Python
worker SDK boundary, a transactional catalog, a content-addressed object store, KIR with
fidelity gates, an incremental DAG cache, three index families, CLI **and** HTTP **and**
MCP surfaces, policy labels, OpenTelemetry, benchmark suites, and threat suites. That is
a quarter's work for a staffed platform team, delivered before a single external user can
feel value. For an open-source project bootstrapping from zero, this sequencing is fatal:
the project exhausts itself building invariant machinery for users it does not yet have.
Enterprise-grade is a *discipline* (determinism, evals, compatibility policy, honest
failure modes) — not a feature list. The discipline is kept; the feature list is
re-sequenced.

**G-2. Polyglot Rust + Python + gRPC + Protobuf + OCI from day one.**
Every additional language and IPC boundary doubles CI surface, halves the contributor
pool, and slows iteration during exactly the phase where iteration speed is the scarcest
resource. The knowledge/ML ecosystem (parsers, embeddings, evaluation) is Python-first;
the contributor pool for this product is Python-first.
**Resolution (D-003):** single-language Python v1 with strict typing and measured escape
hatches (Rust extensions only for profiled hotspots, post-1.0).

**G-3. Enterprise personas first, adoption personas last.**
The spec's persona table leads with platform operators, enterprise architects, and
compliance reviewers. Open-source infrastructure wins bottom-up: an individual developer
gets value in minutes, brings it to a team, and *then* the operator persona appears with
requirements and budget. dbt, Grafana, Airflow, and Terraform all climbed this ladder.
The product strategy (document 01) is built around that ladder.

**G-4. No competitive positioning.**
Neither input answers "why does this exist when LlamaIndex, GraphRAG, Cognee, Docling,
and Sourcegraph exist?" A global open-source product lives or dies on a crisp answer.
Document 01 provides it.

**G-5. Launch-grade numbers asserted without a basis.**
Recall@50 ≥ 0.90, nDCG@10 ≥ 0.75, 10M policy probes, 99.9 % availability, RPO ≤ 5 min —
these are plausible *GA aspirations* pasted into a v1 spec. Absolute quality numbers are
meaningless before a corpus and judgment set exist; what is enforceable from day one is
*relative* discipline: baselines, ablations, and no-regression gates. Document 04
restructures the gates accordingly and keeps absolute targets as GA-phase goals.

**G-6. Factual error: license.**
`gpt-specs` states "the repository currently carries the MIT License." No LICENSE file
exists anywhere in the repository. Small, but a reminder that generated specifications
must be verified against reality. The license decision is made explicitly in D-018.

**G-7. Process coupling.**
The package gates itself on an external process framework ("EADOS intake, manifest
confirmation, human-gated phase transitions"). A public open-source project cannot ask
contributors to adopt a private process framework; governance must be self-contained
(document 06).

### 2.3 Shared failure mode of both inputs

Both artifacts optimize for **architectural completeness** over **time-to-learning**. The
discussion does it with imaginary scale; `gpt-specs` does it with real rigor. The
scarcest resource in this project's first year is not architecture — it is *validated
learning from real users*. Every sequencing decision below follows from that.

---

## 3. Decision log

Decisions are numbered and stable. Overriding one requires a recorded counter-decision.

| ID | Decision | Key rationale |
|----|----------|---------------|
| **D-001** | Mycelium OS is a **knowledge compiler + serving layer for AI agents**. It is not an agent runtime, not a RAG framework, not a chat product. | F-10; G-4. Serve agents, don't be one. |
| **D-002** | v1 targets **repo-scale, local-first, single-tenant** corpora (10²–10⁵ documents). `namespace`/`trust_class` fields reserved in all schemas. | F-1, F-12. Design for the scale that exists; keep identity seams for the scale that might. |
| **D-003** | v1 is **Python 3.12+, single language** (uv, pydantic v2, typer; mypy strict). Rust only for profiled hotspots post-1.0. | G-2. Contributor pool and iteration speed dominate at this phase. |
| **D-004** | **Layered authority**: (1) original source bytes (CAS evidence) → (2) authored/curated Markdown (native truth) → (3) derived artifacts (disposable). Agent memory is out of scope entirely. | F-2, F-10. |
| **D-005** | **Sources live in Git; the derived store (`.mycelium/`) is gitignored.** SQLite (WAL) + FTS5 + vector extension as the local engine; content-addressed blob store for evidence/KIR. | F-6, F-7. Version sources and manifests, cache artifacts. |
| **D-006** | **JSONL is the interchange format** (`mycelium export` bundles), not the query engine and not committed by default. Parquet deferred. | F-7. |
| **D-007** | **KIR (Knowledge IR) is a thin, versioned JSON document AST** produced by adapters over existing parsers (docling, markdown-it). Mycelium OS does not build parsers. | F-3. Wrap the parsing ecosystem; own the representation and its guarantees. |
| **D-008** | **The compiler is a content-addressed incremental DAG** with deterministic stages, golden tests, and a snapshot manifest. This is the product's technical differentiator. | §1.1; F-4, F-6. |
| **D-009** | **Retrieval is hybrid (BM25 + vector, RRF fusion) with optional graph expansion, selected by a transparent planner** — and every signal must earn its place in ablation. | F-8. |
| **D-010** | **Evaluation harness ships in Phase 0** and is a permanent release gate. The baseline to beat is not only BM25 — it is *the agent's built-in grep/glob*. | F-11, G-5. If Mycelium OS doesn't beat agentic grep on task outcomes, it has no reason to exist. |
| **D-011** | **v1 public surfaces: CLI + MCP (stdio) only.** No HTTP API, no gRPC, no generated SDKs until the server phase. | G-1. Every public surface is a permanent compatibility liability. |
| **D-012** | **Plugins v1 are in-process Python entry points implementing typed Protocols.** Trust stance: a plugin is installed code, same as any pip dependency. Sandboxing/registry deferred with explicit triggers. | F-5 (contracts, not buses); G-1. |
| **D-013** | **Default embedder is local** (small ONNX model, zero API keys) so first value requires no account; API providers are opt-in config. Embeddings keyed by `(model_id, chunk_hash)`. | Adoption: TTFV must not depend on a paid key. |
| **D-014** | **Graph = typed edges in SQLite + in-memory traversal; controlled edge vocabulary.** No graph database, no formal ontology, until measured triggers fire. | F-8, F-9. |
| **D-015** | **Concurrency**: single-writer build lock; concurrent readers via SQLite WAL; publication = atomic snapshot-pointer swap; rollback = repoint. | F-11; adopted from `gpt-specs` snapshot semantics, scaled down. |
| **D-016** | **Every artifact carries `schema_version`; v1 migration policy is: rebuild.** Derived data is disposable by construction, so migrations are cheap until stated otherwise. | §1.1 schema versioning; G-1 (no migration machinery before it pays rent). |
| **D-017** | **Security v1**: all source content untrusted (injection doctrine, tested); read-only MCP by default; secret-scan at ingestion; telemetry off by default. | F-11; adopted from `gpt-specs` threat model, trimmed to v1 surface. |
| **D-018** | **License: Apache-2.0** (explicit patent grant — a requirement for enterprise adoption), decided before any external contribution. DCO for contributions. Working name was **KOS** — superseded by D-024. | G-6. |
| **D-019** | **The enterprise/scale profile (Postgres, object store, OpenSearch/Qdrant adapters, tenancy, policy engine, plugin sandbox) is Phase 5**, with `gpt-specs/` as its reference blueprint. Contracts in documents 03/05 are designed not to break when it arrives. | G-1. The fortress gets built when the village exists — on the village's road grid. |
| **D-020** | **Ingestion is dual-lane.** Every ingested source always produces the deterministic **evidence lane** (parser → KIR → verbatim projection + fidelity report). An **LLM synthesis lane** additionally authors readable documentation from that evidence (enabled automatically when an LLM provider is configured). Synthesized docs are born `candidate` and must cite the evidence layer per statement. The LLM writes *Markdown documents only* — never index files; all JSONL/indexes remain compiler output. | Owner requirement (LLM-authored docs), made verifiable: "100 % source truth" can only be *proven* against a deterministic extraction. LLM-only ingestion would leave nothing to verify against. |
| **D-021** | **Verification is a first-class workflow.** Folder encodes status: `knowledge/verified/` vs `knowledge/candidate/` (plus `knowledge/evidence/` for regenerable verbatim projections). `mycelium verify` computes grounding (citation coverage + sampled entailment vs evidence); `mycelium promote`/`demote` move docs and stamp verification evidence in frontmatter. Builds never move or edit tier-2 files — promotion is a human/Git action. Retrieval weights and labels by status. | Owner requirement (trusted vs uncertain split), implemented as visible folder convention + auditable Git moves rather than invisible metadata. |
| **D-022** | **Authored format = Mycelium Markdown Profile v1 (Obsidian-flavored):** CommonMark + GFM tables + YAML frontmatter + wikilinks (incl. `[[doc#Heading]]`) + callouts + inline tags. Embeds `![[…]]` are parsed as links (no build-time transclusion in v1). Unknown syntax degrades to plain text, never breaks the build. Wikilinks are a first-class edge source; `knowledge/` doubles as an Obsidian vault (`.mycelium/` stays dot-hidden). | Owner requirement. Cheap to adopt, rich payoff: authored links feed the graph for free, and the KB is browsable in the best local PKM tool. |
| **D-023** | **Future-proofing = four concrete extension mechanisms, still no bus:** plugins may contribute (1) pipeline stages with declared position and build-key participation, (2) lifecycle hooks, (3) CLI subcommands, (4) MCP tools (opt-in, off by default). Every contribution is recorded in the snapshot manifest; determinism rules apply. Runtime capability negotiation remains rejected (F-5). | Owner requirement ("modular for features not yet conceived"). You cannot design sockets for unknown features — you can keep the core small and the extension points cheap; this is the pytest/dbt model that enabled ecosystems their authors never imagined. |
| **D-024** | **Brand and all identifiers = Mycelium** (owner decision, 2026-07-31). Org: Mycelium LABS. Engine repo: `mycelium-os` (freed by the owner renaming the legacy repo to `mycelium-os-legacy`). Python import package `mycelium`; PyPI distribution **`mycelium-os`** (verified 2026-07-31: `mycelium` on PyPI is taken by an unrelated package abandoned since 2019 — a PEP 541 name-transfer request will be filed, and if granted before 1.0 the distribution moves to `mycelium` with `mycelium-os` kept as transitional alias); binary `mycelium`; config `mycelium.toml`; derived store `.mycelium/`; URI scheme `mycelium://`; frontmatter key `mycelium_id`; entry-point group `mycelium.plugins`; MCP tools `mycelium_*`. Local dir `D:\gh\kos` → `D:\gh\mycelium-os` at scaffold. "KOS" is retired; it survives only as history in this log and in `gpt-specs`. Shipping two names is forbidden. | Live founder site, Discord, and logo assets make Mycelium the brand with existing equity; a single name everywhere is a hard coherence rule (product strategy §9). |
| **D-025** | **`chats` is the first optional module** (owner request, 2026-07-31; spec = document 08): local archive of user↔chatbot conversations. Canonical record = **JSONL** (verbatim content, loss-aware `meta`, CAS custody of originals); **Markdown projection** (Obsidian callouts) under `knowledge/evidence/chats/…` for indexing; layout `chats/<project>/<year>/<month>/`; YAML rejected for records. Content is always verbatim — only structure may be inferred, and inference is labeled. Activation via `[modules] enabled`; contrib tier in-repo pre-1.0, own repo (`mycelium-chats`) post-freeze. Ships Phase 3 as the end-to-end validation of the D-023 plugin API. **Not agent memory** — D-004's boundary stands: transcripts are historical sources, not live agent state. | Chats are evaporating knowledge locked in vendor silos; archiving them is squarely "operationalize knowledge". Building it as a true plugin proves the extension points before the 1.0 API freeze. |
| **D-026** | **Plugin naming convention + first two names** (2026-07-31). Convention (05 §4.4): one kebab-case capability-noun id used everywhere; no technology suffixes (`-llm`, `-ai`); core concepts reserved; repo `mycelium-<id>`, display "Mycelium <Id>"; mycological pet names reserved for Phase-4 marketing, never identifiers. Names: default Synthesizer = **`wiki`** (owner proposed "wiki-llm"; the `-llm` suffix is rejected per rule 2 — implementation in a name rots or lies; the llm-wiki heritage is credited in the description); chat module = **`chats`** (archive + resume + port conversations; display "Mycelium Chats", future repo `mycelium-chats`). | Names outlive implementations. A 2-a.m. operator gripping logs needs capability nouns, not brand poetry or tech-era suffixes. |
| **D-027** | **"Skill" is a reserved term** (owner decision, 2026-08-29). The extension taxonomy is two-level and keeps its names: engine extensions are **plugins** (typed Protocols + entry points, D-012/D-023); packaged activatable capabilities are **modules** (`[modules] enabled`, D-025). "Skill" may only ever name a possible **future, separate artifact class**: agent-facing capability/instruction packages that teach an agent runtime to drive Mycelium's surfaces (e.g. an Anthropic-format Agent Skill wrapping the `mycelium_*` MCP flow) — a distinct deliverable with its own naming and lifecycle, **never** a synonym for or rename of plugins/modules. Folder taxonomy unchanged (05 §4.3): core in-package, contrib tier in `contrib/`, community as external `mycelium-<id>` repos. | Positioning: Mycelium serves agent runtimes, it is not one (D-001/F-10; risk R9) — "skill" is agent-side vocabulary industry-wide, and engine-side the standard term is "plugin" (cf. Semantic Kernel's own skills→plugins rename). One name everywhere (D-024): `mycelium.plugins` is frozen vocabulary headed into the 1.0 contract freeze. |

---

## 4. Amendment record — 2026-07-31

Owner direction received after initial acceptance review: (a) LLM-based ingestion that
authors the Markdown documentation is a permanent, central feature; (b) Markdown must be
"100 % source truth, when verified"; (c) split trusted vs uncertain sources into two
folders; (d) authored format is Obsidian Markdown; (e) the plugin system must accommodate
features not yet conceived.

**2026-07-31, naming (D-024):** the owner confirmed the public brand — **Mycelium for
every repository** — and is renaming the legacy projects. This package was mechanically
renamed (`kos` → `mycelium` across identifiers, "KOS" → "Mycelium OS" in prose); D-018's
original wording ("working name KOS") is preserved as history. Document 07 assesses the
*legacy* `mycelium-os` codebase; after the owner's rename it lives as
`mycelium-os-legacy`, and the new engine takes the `mycelium-os` name.

Critical resolution applied: requirements (a) and (b) are contradictory *if the LLM is
the only ingestion path* — a paraphrasing model cannot guarantee source fidelity, and
without a deterministic extraction there is nothing to verify the synthesis against.
D-020/D-021 resolve this: the deterministic evidence lane is the substrate that makes the
owner's own "se comprovata" (when verified) clause enforceable, and the synthesis lane
delivers the LLM-authored documentation the product actually wants. (b) therefore reads:
*verbatim evidence is mechanically faithful by construction; synthesized documentation
earns `verified` status through grounding checks and promotion.* Requirements (c), (d),
(e) are adopted as D-021, D-022, D-023 with the refinements noted in their rows.

**2026-08-29, terminology (D-027):** the owner asked whether role-specific
plugins/modules should be recast as "AI skills", and which folder name (plugin / add-in /
skills) fits an international enterprise project. Decision: keep **plugin** (mechanism)
and **module** (activatable capability); reserve **"skill"** for a possible future
agent-facing instruction-package artifact class, distinct from both; folder taxonomy
unchanged. Recorded as D-027; spec 05 §4.4 gains the matching reservation rule. "Add-in"
was rejected as ecosystem-alien (Office-legacy vocabulary, absent from Python/OSS
infrastructure).
