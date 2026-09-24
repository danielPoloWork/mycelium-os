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

- **Lexical:** FTS5 BM25, field-weighted (title 3.0, heading 3.0, body 1.0,
  ancestors 0.5), unicode61 tokenizer + prefix support for identifiers, and a stem
  column beside each surface field at 0.05 of its weight.
  *Three amendments to the original three weights, all measured:* the stem columns
  are what lets `signs` reach `signed` (roadmap 4.19, ADR-0048); `heading_path` is
  split into the leaf `heading` and its `ancestors` because one field for the whole
  chain made a subsection's heading a strict superset of its parent's (roadmap
  4.36, ADR-0063); and the leaf `heading` then rises from this section's original
  2.0 to **3.0** (roadmap 4.42, ADR-0070). The third amendment is the only one that
  moves a number this section set, and it was refused twice before it was taken:
  it gained on the held-out sets while scoring *exactly* the baseline on the dev
  sets, and became proposable only once roadmap 4.39 grew uv/dev to twenty-two
  judged cases and the parameter acquired an interior optimum there — 3.0 above the
  baseline, 4.0 below it. `title` and `body` are still as this section set them.
- **Vector:** kNN over `vectors` for the configured `model_id` (sqlite-vec), k=50 default.
- **Symbol:** exact lookup in `symbols` for identifier-like tokens.
- **Fusion:** Reciprocal Rank Fusion, k=60, over rank lists — raw scores from different
  backends are never added (adopted from `gpt-specs` §8.3). Weights configurable per
  profile; defaults committed with eval evidence.

## 4. Boosts, deduplication, stitching, packing

- Boosts (multiplicative on fused rank score, each individually ablated): heading-level
  proximity (H1/H2 sections over deep fragments), `trust_class` (authored ≥ curated ≥
  ingested ≥ external), verification (default weights: `verified` 1.0 > `evidence` 0.85 >
  `candidate` 0.7 — D-021), recency (**only** when the query asks for it — no global
  recency prior in a knowledge base).
  **Measured and refused; no boost ships** (roadmap 6.38, ADR-0153). Three of the four are
  refused by arithmetic rather than by an arm: a multiplicative factor applied to every
  candidate alike is order-preserving exactly, and every corpus here holds **one value** of
  `trust_class`, of `verification_status` and of `curated`, so those boosts cannot reorder
  anything that exists to be reordered. Recency has no judged query asking for it and no
  field to read — `updated_at` is a build timestamp (uv's 81 documents span 0.7 seconds),
  not an editorial date. Heading proximity is the one field that varies, and it was swept
  across eight weights **in both directions**, pool-wide and confined to the served ten:
  **none of the 96 arms gains on any set**, the best is −0.69 %, and the family's optimum
  is the shipped ranking reached from both sides. A permutation control — the same
  multipliers dealt to the wrong candidates — shows why: any perturbation of that size
  costs 8–25 %, and heading depth beats the control on the three ingested-or-uv sets while
  losing to it on the two authored ones. `tools/measure_result_rules.py --check` guards the
  refusal, and would re-open it for a corpus that mixes trust classes.
  Trust and verification remain **contracts, not weights**: every `candidate`/`evidence`
  result is explicitly labeled so the agent knows what it is quoting, and a
  `trust: verified` filter excludes candidates entirely (`RetrievalConfig.include_candidate`
  / `served_statuses`). A filter that removes a class is a different mechanism from a boost
  that reweights one, and it is the mechanism that ships.
- Dedupe: near-identical chunks (digest or high lexical overlap) collapse to the highest-
  ranked instance; the duplicate set is noted in `explain`.
  **Measured and refused; nothing collapses** (roadmap 6.38, ADR-0153). Across all six
  judged sets the shipped ten contains **zero** same-digest pairs, and under the looser
  half of the rule's own test — token-set Jaccard ≥ 0.8 — 0.4 % to 5.2 % of cases hold one.
  A rule whose strict form never fires and whose loose form fires on one case in fifty is
  not carrying its own weight in the query path. RRF over a chunked corpus already spends
  its slots on distinct chunks; this rule was written for a pool that does not occur.
- Diversity: MMR across documents so one document cannot monopolize the result set unless
  it uniquely holds the answer. **Measured across both families and refused on the result
  set** (roadmap 6.29, ADR-0144): every per-document cap and every multiplicative decay
  loses on every release set, because RRF's 50-deep pool spans only 1.80x between its best
  and worst candidate and a discount in that range is inert or total. The ceiling of the
  whole family - the arm chosen per query with hindsight, which is what *"unless it
  uniquely holds the answer"* would require - is +1.4 % to +4.2 %, against +36 % to +86 %
  for re-ordering the same pool correctly. So concentration is not where the loss is, and
  the result set carries no diversity rule; the one-per-document rule inside the graph leg
  (ADR-0075) bounds what an expansion may contribute and says nothing about the result set.
  `tools/measure_document_diversity.py --check` guards the refusal.
- **Stitching:** when several top candidates are adjacent chunks of one section and the
  budget allows, return the coherent section once instead of shingled fragments — agents
  handle one coherent passage better than three overlapping ones.
  **Unbuilt, and the only §4 rule not refused** (roadmap 6.38, ADR-0153). It has real
  occasions — the shipped ten holds adjacent chunks of one section on **5.7 %–10.6 %** of
  cases on the authored corpora and **29.6 %–32.1 %** on the ingested twin, where
  projection flattens headings and splits sections further. What it does not have is a
  measurement: stitching *removes* a slot, so nDCG@10 punishes it on principle regardless
  of whether the agent reads better, and the claim it rests on — *"agents handle one
  coherent passage better than three overlapping ones"* — is about comprehension, not
  ranking. It is therefore neither shipped nor refused here; it is **deferred to the
  agent-task suite** (§7.4), which measures evidence-found and tokens-spent and is the only
  instrument in this project that could settle it. Filed rather than guessed at.
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

**Amended at roadmap 6.3 (ADR-0119).** The corpus the second bullet asks for exists as a
**fixture** corpus rather than a part of the eval corpus — `tests/fixtures/injection/`,
twenty-three documents, one attack class each, declared in `attacks.json` — and the property
is asserted by `tests/test_injection.py` rather than by the harness. The deviation is
deliberate: nDCG, recall and MRR rank chunks and cannot say *returned verbatim inside a typed
field*, and an attack document inside the documentation corpus moves every judged number for
no gain. The judged `injection` slice keeps its one case, which checks that the doctrine is
findable. The residual this section names — what the client does — is joined by one the corpus
declares: text a renderer would hide is indexed as the words it is (ADR-0110) and reaches the
agent verbatim, with the notice.

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

**Citation precision, added at roadmap 6.7 (ADR-0122).** Every metric above ranks *chunks*
— did the right passage come back, and how high — and coverage asks only whether the anchor
resolves. Neither asks whether the anchor a reader is handed **names** anything: a passage
returned under `#/7` is a correct answer and a citation nobody can check without this tool.
So a run also reports the share of its top-ten anchors whose passage sits under at least one
heading, and the mean size of the passages they point at. The two move independently, and a
citation is imprecise in both directions — a located anchor into 700 tokens asks a reader to
scan a page, an unlocated one into 60 asks them to find it first.

It is **reported, not gated**, and the reason is stated rather than left as an omission: on
the ingested corpus the number is dominated by the PDF lane, which reads 0.000 because
ADR-0040 refused the pipeline that would fix it, so any threshold picked today would encode
that decision instead of measuring anything. What arms it is the ADR-0040 re-take, which this
metric is what makes possible.

Note that locatedness is read from the **chunk**, never parsed from the anchor: an anchor
omits the document's single level-1 heading (ADR-0007), so a passage under a real title and
one in a document with no headings at all are spelled identically.

### 7.3 Gates (CI-enforced)

| Gate | Rule |
|---|---|
| G1 Citations | Citation coverage = 1.00, every release, no exceptions |
| G2 Earn hybrid | Hybrid ≥ +5 % nDCG@10 vs BM25-only overall AND no slice worse than −2 % — otherwise the shipped default config is lexical-only and the README says so |
| G3 No regression | No release may regress any protected slice > 2 % vs the previous release on the frozen set — enforced on a slice that holds enough cases for that bar to mean more than one case, reported with the count it needs when it does not (roadmap 6.8, ADR-0123) |
| G4 Abstention | False-answer rate on `unanswerable` ≤ 5 % (v1), tightening at 1.0 |
| G5 Performance | Budgets in §1 and document 01 §8, measured on the reference profile |
| G6 Determinism | Byte-identical rebuild check (compiler gate, runs with eval in CI) |
| G7 Grounding (per-document promotion gate, D-021) | A synthesized doc is *eligible* for promotion only if `cites` coverage ≥ 0.95 of claim-bearing statements AND sampled entailment vs cited evidence ≥ 0.90. Below threshold it stays `candidate`. Auto-promotion is opt-in config; the default is human `mycelium promote`. |

**What G5 reads, and what it read for five milestones (roadmap 6.24, ADR-0139).** The
150 ms in §1 is stated for `mycelium_search` — the tool call, which resolves the published
snapshot, reads the configuration, opens the store and packs the answer. Until roadmap 6.24
the gate read the harness's timing of the *retriever* alone, and those wrappers were 274 ms
of constant until roadmap 6.18 cached the worst of them (ADR-0128), so the gate ran green
over a call that missed its own budget on every corpus. It now times the handler on a
hundred of the run's own queries and enforces on that; the arm's retriever p95 is kept
beside it as a floor, because it is the only number that moves with the arm. Both must hold,
and a tool call that could not be timed fails rather than passes. The four *stage* budgets
in §1 remain ungated (roadmap 6.35).

Absolute quality targets (e.g. `gpt-specs`' Recall@50 ≥ 0.90, nDCG@10 ≥ 0.75) become
**GA-phase goals** once corpora are large enough for the numbers to mean something (G-5
in document 00); pre-GA, relative discipline is what is enforceable and honest.

**How large is now computed, per slice (roadmap 6.8, ADR-0123).** A slice of `n` cases at
blessed mean `m` trips its −2 % bar when its total gain falls by more than `0.02 · n · m`, and
the ordinary way a case fails is that it leaves the top ten, costing the slice its whole
score. So the bar means more than one case exactly when `n ≥ q / (0.02 · m)`, with `q` the
median blessed non-zero per-case score. Across the three committed baselines that is **50 to
97 cases a slice** against the four to seven they hold — roughly double this section's earlier
estimate, because that one budgeted for the median loss observed rather than the loss a single
case can inflict. `enforceable_at` computes it from the baseline, G3 reports the rows that do
not meet it, and `tools/measure_slice_power.py` prints the shortfall. §7.6's corpus plan is
what closes it.

### 7.4 The grep baseline (D-010)

The real incumbent is not BM25 — it is the agent's built-in `grep`/`glob`/`read` loop.
Therefore, in addition to IR metrics:

- **Agent-task suite:** ≥ 20 realistic tasks (from Phase 1, grown continuously): "answer
  this question about the corpus with citations", "find where X is defined and what
  supersedes it". Run agent-with-Mycelium OS-MCP vs agent-with-grep-only; score task success,
  wall time, and tokens consumed. Qualitative scoring pre-1.0; quantified gate at 1.0.
- If Mycelium OS does not visibly beat grep on these tasks, the correct response is to fix the
  product, not the benchmark.

**Two gates, not one (roadmap 6.4, ADR-0120).** "Quantified gate at 1.0" was read as one thing
and is two, and only the second waits:

- The suite's **integrity** — does the comparison still measure retrieval? — is gated **now**.
  `mycelium eval --tasks --gate` fails when a task requires a passage the snapshot no longer
  holds, and CI runs it. At 6.4 four of the twenty-two tasks required anchors the packed
  chunker had merged away, and both strategies had been scoring them as misses ever since, so
  the rate had a silent ceiling of 18/22. Such a task is now *unresolved*: reported, and
  excluded from the denominator.
- The **verdict** — does Mycelium beat grep? — was quantified in
  `docs/benchmarks/2026-09-17-reference-profile.md` ahead of arming, and is **armed** since
  roadmap 7.3, before the v1.0.0 tag rather than discovered at it (D-031, ADR-0156). It
  holds when the suite is sound (no unresolved anchor) and both conditions pass: **(a)**
  Mycelium finds the evidence on **more than two** tasks beyond grep *and* a one-sided exact
  **sign test** over the tasks exactly one strategy found gives **p < 0.05** — a lead the
  suite can tell from chance, which a count alone cannot say on twenty-two tasks; **(b)**
  Mycelium's **median** context is at most **half** grep's. It is gated on the corpora we did
  not write — `uv-docs` and its ingested twin, both — by
  `mycelium eval <corpus> --tasks --gate --verdict` in CI and `tools/verify.py`, and reported,
  never gated, on this repository's own.

**What the incumbent is, precisely (roadmap 6.22, ADR-0131).** A grep loop is modelled by two
numbers — how much one read costs, and how many files it opens — and both are now measured
rather than asserted, because leaving either unexamined is what let the comparison rot. One
read costs at most the caller's own `budget_tokens`: a document that fits is read whole, one
that does not is read *around the hit*, and a section larger than the window is read and
carries no evidence, because seeing part of a passage is not being handed it. The loop opens
`MAX_GREP_FILES` of them. `tools/measure_agent_task_band.py` runs the comparison across the
band both constants trace, and `docs/benchmarks/2026-09-18-the-incumbent-reads-a-window.md`
publishes it. Before that bound the loop read the first matching file whole whatever its size,
which on a corpus with one 88 000-token document meant one file on every task and 93 % of the
incumbent's measured cost in it.

**The suite runs on a corpus we did not write (roadmap 6.23, ADR-0135).** The third
precondition above is met: `eval/corpora/uv-docs/eval/tasks.jsonl` holds twenty-two tasks
judged against uv's documentation, and its ingested twin carries the same judgements with only
the anchor recomputed — dropping a task that loses any required anchor, because `found` is a
conjunction and a shorter `requires` list is an easier task rather than the same one. The
integrity gate runs on all three corpora. This matters for the *verdict* rule rather than for
the metric: measured at `fa6757d`, the lead on evidence is **+5 tasks** on `uv-docs` and **+6**
on its twin against **+1** on this repository's own corpus, so which corpus the rule is read on
decides whether its first condition passes. Roadmap 7.3 took that decision the way §7.1
takes it for the judged sets — ADR-0053's rule, report on the corpus we author, gate on the
one we do not (D-031, ADR-0156). Re-measured at `6334571`: **+6** (7 to 1 where the
strategies disagree, p = 0.035) on `uv-docs`, **+7** (8 to 1, p = 0.020) on its twin, and
**+2** (6 to 4, p = 0.38) on this repository, at a median context of about **3.8×** less than
grep's on all three.

### 7.5 Run manifests

Every `mycelium eval` run writes a manifest (snapshot id, config digest, retriever config,
metric table, per-case results, hardware) under `.mycelium/eval/`. Released benchmark reports
are committed to the repo with their manifests; a report without a manifest is
exploratory and cannot satisfy a gate (adopted verbatim in spirit from `gpt-specs` §3).

**Enforced from roadmap 6.4 (ADR-0120), and one thing added.** The rule above held nothing up
for six milestones because `docs/benchmarks/` held no report at all; it now holds one, and
`tools/consistency_lint.py`'s `benchmarks` check refuses a report that cites no manifest, a
citation that resolves to nothing, and a manifest no report cites. The addition is that a
manifest records **what a file open costs on the machine that took it**, measured over the
corpus it is about to build. Every build figure is dominated by that constant — ~1.3 ms on the
machine of record, about a hundred times an unencumbered SSD — and without it a reader cannot
tell a compiler cost from a machine cost.

### 7.6 Corpus plan

- Phase 0–1: self-hosting corpus (Mycelium OS's own docs and specs) + one public docs corpus
  (e.g. a well-known OSS project's documentation), ≥ 60 judged cases.
- Phase 3: ≥ 200 judged cases across ≥ 3 corpora incl. one ingestion-heavy (PDF) corpus.
- 1.0: ≥ 1 000 judged cases; publish the redistributable subset + judgment guidelines so
  the community can reproduce and extend (the `gpt-specs` 2k/10k targets apply to the
  Phase-5 platform claim, not to 1.0).
