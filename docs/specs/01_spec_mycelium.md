# Software Specification: Mycelium OS (Python 3.12+)

> Rendered from the intake interview (Phase 5). Frozen contract: diverging implementation
> updates this spec in the same PR or adds an ADR superseding the relevant section.

## 1. Objective & Business Context

Compile a project's knowledge — authored Markdown plus ingested sources (PDF, DOCX,
HTML, wikis) — into a deterministic, versioned, queryable substrate, and serve it to
AI agents over CLI and MCP with citations they can trust. Mycelium OS is a knowledge
compiler and serving layer: not an agent runtime, not a RAG framework, not a chat
product (D-001). v1 targets repo-scale, local-first, single-tenant corpora of
10^2–10^5 documents (D-002).

## 2. Functional Requirements

- FR-1 Compiler: content-addressed incremental stage DAG (discover→acquire→parse→normalize→chunk→extract→embed→index→manifest) with pure typed stages, build keys, and immutable snapshot manifests (D-008; spec 02 §4)
- FR-2 Serving: read-only retrieval over exactly two public surfaces — the mycelium CLI and a stdio MCP server exposing mycelium_search / mycelium_fetch / mycelium_neighbors / mycelium_explain; every response carries snapshot id + citations (D-011; spec 05)
- FR-3 Retrieval: hybrid BM25 + vector with RRF fusion, transparent rule-based planner with explain output; graph expansion Phase 3 behind an ablation gate (D-009; spec 04)
- FR-4 Ingestion, dual-lane: deterministic evidence lane (CAS custody → KIR → verbatim projection + fidelity report) always; LLM synthesis lane authoring cited candidate docs when a provider is configured (D-020; spec 02 §5)
- FR-5 Verification workflow: folder-encoded status knowledge/{verified,candidate,evidence}; mycelium verify computes grounding (cites coverage + sampled entailment, gate G7); promotion/demotion is a human/Git action (D-021)
- FR-6 Authored format: Mycelium Markdown Profile v1 (Obsidian-flavored — wikilinks, callouts, frontmatter contract); wikilinks compile to typed edges; knowledge/ doubles as an Obsidian vault (D-022; spec 03 §3.1)
- FR-7 Plugins: in-process typed Protocols (Parser, Chunker, Embedder, Extractor, Synthesizer, Reranker) via entry points, plus four generic extension mechanisms — pipeline stages, lifecycle hooks, CLI subcommands, opt-in MCP tools (D-012/D-023; spec 05 §4)
- FR-8 Evaluation harness: mycelium eval with frozen dev/release sets, per-slice metrics, CI gates G1–G7, injection-resistance corpus, and the agent-task grep baseline (D-010; spec 04 §7)
- FR-9 Interchange: mycelium export writes JSONL bundles (documents/chunks/symbols/edges + manifest); JSONL is interchange, never the query engine (D-006; spec 03 §9)
- FR-10 Snapshot lifecycle: atomic CURRENT pointer publication, rollback by repointing, single-writer advisory lock, WAL concurrent readers, GC of unreferenced blobs (D-015; spec 02 §7)


## 3. Non-Functional Requirements

<!-- Scalability / load budgets belong here as NUMBERS, not adjectives (the design "scalability"
     fold): a value per hard NFR axis — throughput / concurrency, p99 latency, memory ceiling,
     target FPS, cold-start budget — each phrased so CI could prove a violation. -->
- NFR-1 Determinism: identical (sources, config, toolchain) ⇒ byte-identical artifacts for deterministic stages; CI golden rebuild gate G6 (D-008)
- NFR-2 Search latency: mycelium_search end-to-end p95 ≤ 150 ms (local profile, 10^5 chunks, warm store; spec 04 §1)
- NFR-3 Incremental build: single-document edit rebuilds < 2 s p95 with output equal to a clean rebuild (spec 06 Phase-1 gate)
- NFR-4 Time-to-first-value: install → agent answering with citations over MCP in < 10 min (spec 06 Phase-0 gate)
- NFR-5 Citation integrity: citation coverage = 1.00 every release (gate G1); abstention false-answer rate ≤ 5 % on the unanswerable slice (gate G4)
- NFR-6 Security: all source content untrusted with tested injection resistance; read-only MCP by default; secret scan at ingestion; zero network calls unless configured; no telemetry (D-017; spec 02 §8)
- NFR-7 Crash safety: an interrupted build never corrupts CURRENT; readers never observe a torn state (D-015)
- NFR-8 Compatibility: SemVer; the five stable contracts (identity, KIR, snapshot manifest, MCP tools, plugin protocols) freeze at 1.0 with CI compatibility tests (spec 02 §10)
- NFR-9 Test coverage ≥ 80 % lines (EADOS gate); mypy --strict clean


## 4. Logical Architecture & Core Algorithm

<!-- For a non-obvious core algorithm, include a short LANGUAGE-FREE pseudocode sketch (control
     flow + invariants) alongside the prose + diagram (the design "pseudocode" fold); skip it when
     the approach is standard. If the design owns persistent state, capture the data model here —
     entities, relations, normal form, migration policy — within ADR-0004's secondary-SQL frame. -->
Single Python package, local-first (D-002/D-003). Three-tier authority model (D-004):
tier 1 evidence (content-addressed original bytes + KIR under .mycelium/cas), tier 2
authored truth (knowledge/**.md in Git, folder-encoded verification status), tier 3
derived store (.mycelium/: SQLite WAL + FTS5 + sqlite-vec, snapshot manifests,
journal — gitignored, disposable; the compiler is a pure function of tiers 1–2 +
config). Serving is one core query library wrapped by two thin shells (CLI, stdio
MCP). Ingestion is dual-lane (deterministic evidence + gated LLM synthesis). Plugins
are in-process typed Protocols resolved via entry points, pinned by config, recorded
in build keys and manifests. Full reference: .draft-specs/02-architecture.md.

## 5. Public Interface

<!-- The API contract (the design "api" fold): each operation with its payload shapes, the error
     model (the failure taxonomy, not just the happy path), and the versioning / SemVer surface.
     A service/web project may keep the written-out contract under docs/api/ (capabilities.api_spec). -->
Consumers import via `from mycelium.sdk.types import KirDocument`. The public surface:

- MCP tools (stdio, read-only): mycelium_search, mycelium_fetch, mycelium_neighbors, mycelium_explain (spec 05 §3)
- CLI: mycelium init|build|ingest|verify|promote|demote|search|show|neighbors|eval|export|snapshots|rollback|gc|doctor|serve (spec 05 §1)
- mycelium.sdk plugin Protocols + PipelineStage/lifecycle-hook/CLI/MCP extension points (spec 05 §4)
- mycelium:// citation URI scheme + identity rules (spec 03 §2)
- KIR schema mycelium/kir/v0 and snapshot manifest schema mycelium/manifest/v0 (spec 03 §§4,7)
- mycelium.toml configuration contract (spec 05 §2)


## 6. Verification & Test Strategy

Layered verification (spec 04): (1) static — mypy --strict and ruff as CI gates;
(2) property tests via pytest + hypothesis — chunk no-content-loss invariant,
identity/hashing laws, crash-safety; (3) determinism golden rebuild test (gate G6);
(4) the evaluation harness (mycelium eval --gate) on frozen dev/release sets with
per-slice metrics enforcing gates G1–G7, including the injection-resistance corpus
and the agent-task suite against the grep baseline (D-010) — a failed gate fails CI;
(5) coverage.py ≥ 80 % lines.

Toolchain: built with Hatch (PEP 517/518, pyproject.toml), tested with pytest (+ hypothesis for property tests), checked with
mypy --strict (type soundness), pytest -p no:cacheprovider under faulthandler, tracemalloc leak checks, coverage target ≥ 80% line. Every functional and
non-functional requirement above maps to a CI gate (see [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)).
