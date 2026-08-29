# 04 — Retrieval and Evaluation

- **Status:** Draft
- **Depends on:** [03-data-model.md](03-data-model.md)

Doctrine (D-009/D-010): **no retrieval feature ships on architectural charisma.** Every
signal beyond the lexical baseline must demonstrate lift on frozen evaluation sets — and
the system as a whole must demonstrate lift over what agents already have for free:
grep. This document specifies both the pipeline and the harness that disciplines it.

---

## 1. Query pipeline

```text
parse query ─▶ plan ─▶ candidate generation ─▶ fusion ─▶ boosts ─▶ (graph expand)
             (class,   (parallel: FTS5 BM25,   (RRF)     (structure, (1-hop, budgeted,
              filters)  vector kNN, symbol       │        trust,      Phase 3+)
                        exact)                   │        dedupe)
                                                 ▼
                                    diversify (MMR) ─▶ stitch ─▶ pack ─▶ respond
                                                     (adjacent    (token   (results +
                                                      chunks →     budget)  citations +
                                                      sections)             explain)
```

Latency budgets (local profile, 10⁵ chunks, reference laptop, warm store):

| Stage | p95 budget |
|---|---|
| plan + candidates (parallel) | 60 ms |
| fusion + boosts + dedupe | 20 ms |
| graph expansion (when active) | 30 ms |
| stitch + pack | 40 ms |
| **end-to-end `mycelium_search`** | **150 ms** |

Optional reranking (cross-encoder plugin) is excluded from the default path and budget;
when enabled it declares its own budget and appears in `explain`.

**Token frugality contract:** the query path reads **only the derived store** (the SQLite
tables built from the same records `mycelium export` emits as JSONL). Tier-1/2 source files
are never opened, parsed, or LLM-processed at query time — results are pre-extracted
chunk records plus citation URIs, and an agent pulls more context only through an
explicit `mycelium_fetch` on a URI it has decided is relevant. Search cheap, fetch on demand.

## 2. Planning (transparent, not clever)

The planner is a small, deterministic, logged rule set — not a model call (v1):

| Signal in query | Plan |
|---|---|
| Quoted phrase / identifier-like token (`CamelCase`, `snake_case`, dotted path) | FTS exact/phrase + symbol lookup first; vector as backfill |
| Natural-language question | Hybrid (BM25 ∥ vector), RRF |
| Relationship phrasing ("what depends on…", "related to…") or `--related` | Hybrid + graph expansion |
| Filters `collection:`, `tag:`, `path:`, `trust:` | Pre-filter candidate set in every generator (never post-filter only) |
| `k`, `budget_tokens` from caller | Propagated to pack stage |

Every response's `explain` includes the chosen plan and why (matched rule), so planner
behavior is auditable and debuggable rather than folkloric.

## 3. Candidate generation and fusion

- **Lexical:** FTS5 BM25, field-weighted (title 3.0, heading_path 2.0, body 1.0),
  unicode61 tokenizer + prefix support for identifiers.
- **Vector:** kNN over `vectors` for the configured `model_id` (sqlite-vec), k=50 default.
- **Symbol:** exact lookup in `symbols` for identifier-like tokens.
- **Fusion:** Reciprocal Rank Fusion, k=60, over rank lists — raw scores from different
  backends are never added (adopted from `gpt-specs` §8.3). Weights configurable per
  profile; defaults committed with eval evidence.

## 4. Boosts, deduplication, stitching, packing

- Boosts (multiplicative on fused rank score, each individually ablated): heading-level
  proximity (H1/H2 sections over deep fragments), `trust_class` (authored ≥ curated ≥
  ingested ≥ external), verification (default weights: `verified` 1.0 > `evidence` 0.85 >
  `candidate` 0.7 — D-021; defaults are ablatable config, and every `candidate`/`evidence`
  result is explicitly labeled so the agent knows what it is quoting; a
  `trust: verified` filter excludes candidates entirely), recency (**only** when the
  query asks for it — no global recency prior in a knowledge base).
- Dedupe: near-identical chunks (digest or high lexical overlap) collapse to the highest-
  ranked instance; the duplicate set is noted in `explain`.
- Diversity: MMR across documents so one document cannot monopolize the result set unless
  it uniquely holds the answer.
- **Stitching:** when several top candidates are adjacent chunks of one section and the
  budget allows, return the coherent section once instead of shingled fragments — agents
  handle one coherent passage better than three overlapping ones.
- Packing: fill the caller's `budget_tokens` (default 4 000) in rank order with verbatim
  text + citations; truncation is explicit (`truncated: true`, `omitted: [anchors…]`).
  Callers choose the text payload via `include_text`: `full` (default, budgeted verbatim
  chunks), `snippet` (first ~160 chars per result — triage ~20 results for ~100 tokens),
  `none` (URIs + titles + scores only). **Link-only results are deliberately not the
  default**: forcing the agent to fetch every candidate to judge relevance costs *more*
  tokens than returning budgeted snippets (pogo-sticking); the cheap modes exist for
  reconnaissance, not as the primary contract.
  v1 returns **verbatim evidence only** — LLM summarization/compression is a deferred
  plugin because it introduces non-determinism and a fabrication surface into the trust
  path.

## 5. Graph expansion (Phase 3, gated)

1-hop expansion from top-k fused candidates over typed edges, budget-capped (≤ 10 nodes,
≤ 30 ms), edge types weighted (`defines`/`supersedes` high; `mentions` low). Expanded
candidates enter fusion with a discount and are labeled `via_edge` in `explain`.
**Gate:** graph expansion ships enabled-by-default only if ablation shows ≥ +3 % nDCG@10
on the `relationship` slice with no overall regression; otherwise it remains an opt-in
flag until it earns the default (F-8 discipline).

## 6. Injection resistance (tested property)

- Retrieved content is data. It is returned inside a typed `results[].text` field, never
  concatenated into tool descriptions or system-level fields.
- The eval corpus includes documents carrying adversarial instructions ("ignore previous
  instructions", tool-call lookalikes, encoding tricks); the harness asserts they are
  returned verbatim as quoted evidence — flagged `trust_class`, never elided, never acted on.
- Mycelium OS itself executes nothing found in content (no shell-outs, no template evaluation on
  document text). What the *client agent* does with returned text is the client's
  responsibility; Mycelium OS's MCP tool descriptions state this explicitly (adopted from
  `gpt-specs` TM-02 residual-risk note).

## 7. Evaluation harness (`mycelium eval`)

### 7.1 Assets

- **Eval cases:** JSONL per document 03 §10, living in `eval/` in the repo, versioned.
- **Slices** (v1 set): `exact`, `symbol`, `fact`, `conceptual`, `relationship`,
  `unanswerable`, `injection`, `synthesized` (queries whose ground truth lives in
  synthesized docs — measures whether the synthesis lane helps or hurts). Metrics are
  always reported per slice; an overall win never excuses a protected-slice loss
  (adopted from `gpt-specs` eval principles).
- **Frozen sets:** dev / release split; the release set is frozen before any tuning of
  the change under test.

### 7.2 Metrics

Recall@10, Recall@50, nDCG@10, MRR; citation coverage (fraction of returned passages
whose anchors resolve — must be 1.0); abstention correctness on `unanswerable` (the
system returns "insufficient evidence" rather than confident noise); latency percentiles.

### 7.3 Gates (CI-enforced)

| Gate | Rule |
|---|---|
| G1 Citations | Citation coverage = 1.00, every release, no exceptions |
| G2 Earn hybrid | Hybrid ≥ +5 % nDCG@10 vs BM25-only overall AND no slice worse than −2 % — otherwise the shipped default config is lexical-only and the README says so |
| G3 No regression | No release may regress any protected slice > 2 % vs the previous release on the frozen set |
| G4 Abstention | False-answer rate on `unanswerable` ≤ 5 % (v1), tightening at 1.0 |
| G5 Performance | Budgets in §1 and document 01 §8, measured on the reference profile |
| G6 Determinism | Byte-identical rebuild check (compiler gate, runs with eval in CI) |
| G7 Grounding (per-document promotion gate, D-021) | A synthesized doc is *eligible* for promotion only if `cites` coverage ≥ 0.95 of claim-bearing statements AND sampled entailment vs cited evidence ≥ 0.90. Below threshold it stays `candidate`. Auto-promotion is opt-in config; the default is human `mycelium promote`. |

Absolute quality targets (e.g. `gpt-specs`' Recall@50 ≥ 0.90, nDCG@10 ≥ 0.75) become
**GA-phase goals** once corpora are large enough for the numbers to mean something (G-5
in document 00); pre-GA, relative discipline is what is enforceable and honest.

### 7.4 The grep baseline (D-010)

The real incumbent is not BM25 — it is the agent's built-in `grep`/`glob`/`read` loop.
Therefore, in addition to IR metrics:

- **Agent-task suite:** ≥ 20 realistic tasks (from Phase 1, grown continuously): "answer
  this question about the corpus with citations", "find where X is defined and what
  supersedes it". Run agent-with-Mycelium OS-MCP vs agent-with-grep-only; score task success,
  wall time, and tokens consumed. Qualitative scoring pre-1.0; quantified gate at 1.0.
- If Mycelium OS does not visibly beat grep on these tasks, the correct response is to fix the
  product, not the benchmark.

### 7.5 Run manifests

Every `mycelium eval` run writes a manifest (snapshot id, config digest, retriever config,
metric table, per-case results, hardware) under `.mycelium/eval/`. Released benchmark reports
are committed to the repo with their manifests; a report without a manifest is
exploratory and cannot satisfy a gate (adopted verbatim in spirit from `gpt-specs` §3).

### 7.6 Corpus plan

- Phase 0–1: self-hosting corpus (Mycelium OS's own docs and specs) + one public docs corpus
  (e.g. a well-known OSS project's documentation), ≥ 60 judged cases.
- Phase 3: ≥ 200 judged cases across ≥ 3 corpora incl. one ingestion-heavy (PDF) corpus.
- 1.0: ≥ 1 000 judged cases; publish the redistributable subset + judgment guidelines so
  the community can reproduce and extend (the `gpt-specs` 2k/10k targets apply to the
  Phase-5 platform claim, not to 1.0).
