# ADR-0017: Ship a local embedder and hybrid retrieval, and let gate G2 choose the default

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §§3, 7.3
- **Related:** [ADR-0013](0013-adopt-the-evaluation-harness.md) (the harness that decided
  this), [ADR-0015](0015-adopt-content-addressed-incremental-builds.md) (the stage DAG this
  adds to), [ADR-0012](0012-adopt-the-g6-determinism-gate.md) (the gate this stage is
  excluded from), [ADR-0014](0014-adopt-partial-strict-configuration.md) (the config
  contract `[retrieval]` now joins); spec 02 §§4.1, 4.3, spec 04 §§1–3, 7.3, spec 05 §2;
  D-009, D-011, D-013, D-017; roadmap 3.3

## Context

D-013 wants the default embedder local and key-free, so first value never depends on an
account. D-009 wants retrieval hybrid — BM25 in parallel with vectors, fused by RRF — with
**every signal earning its place in ablation**. Spec 04 §7.3 turns that into gate G2:
*"Hybrid ≥ +5 % nDCG@10 vs BM25-only overall AND no slice worse than −2 % — otherwise the
shipped default config is lexical-only and the README says so."*

So this item had two halves. The first is engineering: an embedder seam, a model that runs
offline, vectors keyed so unchanged text is never re-embedded, a vector candidate generator,
and rank fusion. The second is a *decision that is not ours to make* — G2 decides whether
hybrid is on by default, and the only honest way to reach it is to run the harness.

Three tensions had to be resolved before either half could land:

1. **A local model weighs 133 MB and lives on a CDN.** D-013 wants it to just work; D-017
   wants **zero network calls unless configured**. Those pull in opposite directions.
2. **ONNX inference is not portably deterministic.** The runtime selects kernels by
   instruction set, so two correct machines can differ in the last bits — and gate G6
   asserts byte-identical rebuilds.
3. **Twenty-odd packages** (`onnxruntime`, `tokenizers`, `numpy`, and their transitive
   closure) is a steep price to charge someone who only wants lexical search.

## Decision

**The embedder is a protocol, and the local ONNX encoder is one implementation of it**
(D-012/D-023). Text in, unit vectors out, plus the identity a manifest must record:
`model_id`, `provider`, `dim`, `deterministic`. A test double satisfies it in a dozen lines,
which is the check that a plugin can too.

**Optional dependency, degrading absence.** `pip install mycelium-os[embeddings]` opts in.
Without it — or without the model — the build **publishes without vectors, marks the
snapshot `degraded: ["vectors"]`, and says how to fix it**, exactly as spec 02 §4.3
prescribes: *"the build still publishes, marked degraded, rather than failing the lexical
index with it"*. `mycelium build --require-vectors` inverts that for a release pipeline that
promised hybrid. Choosing `provider = "none"` is *not* a degradation and is not reported as
one — a stated intent and an unmet one are different facts.

**The model registry pins every file by URL, size, and SHA-256, and nothing is fetched
without consent.** Resolution is `[embedding] model_path` → local cache → refuse. The
refusal names the setting that would permit a download (`allow_download`), the alternative
that needs no network (`model_path`), the size, and what happens meanwhile. Downloaded bytes
are verified against the pin *before* installation, so a substituted artifact never reaches
the destination path even briefly. An air-gapped install never executes the network code.

**The vector stage declares itself non-deterministic** (`deterministic: false`), which
spec 02 §4.1 explicitly allows for exactly this case. Gate G6 therefore builds its corpus
with `provider = "none"` — stated in `observe_build`, not left to ambient configuration, so
the golden cannot depend on whether the machine running CI happens to have a model cached.
G6 continues to claim what it always claimed: the *deterministic* stages are bit-reproducible.

**Vectors are keyed `(chunk_digest, model_id)`** — the DDL has said so since roadmap 2.6,
and the stage now spends it. The work list is "digests this model has not embedded", so an
edit that leaves a section untouched reuses its vector, two documents sharing a chunk share
one vector, and switching models adds rows beside the old ones rather than destroying them.
Embedding runs *inside* the publication transaction, after the chunks are written, so the
work list is exactly what the published corpus needs and vectors commit atomically with the
chunks they describe.

**Fusion is by rank, never by score.** BM25 is unbounded; cosine is [-1, 1]. Adding them
invents an exchange rate that silently becomes an untuned parameter. RRF at k=60 over 50
vector candidates (spec 04 §3) reads positions only. Every hit records which legs produced
it and its rank in each, so `--explain` is an audit rather than a story.

**The vector scan is exact and brute-force, not sqlite-vec — and it does not meet the
latency budget.** The spec names sqlite-vec, but it is a *loadable SQLite extension* and
several stock Python builds ship without `enable_load_extension` (macOS's system interpreter
among them), which would make the default retrieval path unavailable on a supported
platform. So the scan is exact: no recall cliff to tune, and correct by construction.

It is also linear, and the benchmark says so plainly: **94 ms over 10 000 chunks** against
spec 04 §1's 60 ms candidate budget, which extrapolates to roughly a second at the
10⁵-chunk reference profile. Two rounds of optimisation got it there from 168 ms — scoring
now reads only `(key, vector)` and hydrates full chunk rows for the top-k alone (168 → 113
ms), and the unfiltered path skips the joins that exist only to filter (113 → 94 ms) — and
the remaining cost is SQLite row iteration over 15 MB of blobs, not arithmetic. Going
further needs a different representation (one packed matrix per model) or an ANN index.

**This is a limit, not a crisis, precisely because G2 left hybrid opt-in.** Nothing in the
shipped configuration pays it. Making the vector leg fast enough to *be* a default is filed
as roadmap 3.12, and it is now a prerequisite for hybrid ever earning one.

### And the decision G2 made: **hybrid does not earn the default**

Measured on this repository's own snapshot (78 documents, 564 chunks, 559 vectors) against
the 20 judged cases in `eval/`, with `bge-small-en-v1.5`:

| Retriever | nDCG@10 | Recall@10 | Recall@50 | MRR | p50 | p95 |
|---|---|---|---|---|---|---|
| lexical (BM25) | 0.4970 | 0.7292 | 0.9167 | 0.5151 | 3 ms | 5 ms |
| **hybrid (BM25 ∥ vector, RRF)** | **0.5603** | 0.7708 | 0.9167 | 0.5677 | 33 ms | 35 ms |
| grep (the incumbent, D-010) | 0.4304 | 0.7396 | 0.8958 | 0.4277 | 85 ms | 118 ms |

Per-slice nDCG@10, lexical → hybrid:

| Slice | n | Lexical | Hybrid | Δ |
|---|---|---|---|---|
| relationship | 2 | 0.1391 | 0.3025 | **+117.4 %** |
| injection | 1 | 0.1597 | 0.2015 | +26.2 % |
| fact | 4 | 0.5192 | 0.6160 | +18.7 % |
| symbol | 3 | 0.7233 | 0.8463 | +17.0 % |
| conceptual | 5 | 0.4587 | 0.5041 | +9.9 % |
| **exact** | **2** | **0.9531** | **0.7838** | **−17.8 %** |

**Overall, hybrid clears the bar by a wide margin (+12.7 % against +5 %). It fails on the
second condition**: the `exact` slice regresses 17.8 %, against a −2 % limit. The vector leg
dilutes precisely the queries where a literal term is the whole answer — which is what
spec 04 §2's planner exists to fix (route identifier-like queries lexically) and why that
planner is not something to hand-wave now.

**And a worse finding that G2 did not even need:** hybrid **destroys abstention**. On the
four `unanswerable` cases, lexical answers one (a corpus-scoping defect — see below) while
hybrid answers *all four*. The cause is structural: every chunk has non-zero cosine
similarity to every query, so a vector leg asked for 50 candidates always returns 50. We
swept a minimum-similarity floor from 0.50 to 0.75 and **no value separates the two
populations** — unanswerable queries scored 0.6364–0.6677 while answerable ones scored
0.6427–0.8362, overlapping. No floor is shipped, because shipping one would look like a fix
and be a coin toss. Filed as roadmap 3.11.

**Therefore `[retrieval] profile` defaults to `lexical`**, hybrid is one setting away, and
the README says so — which is precisely the outcome spec 04 §7.3 wrote down, and which the
milestone goal already anticipated ("lexical-only default is a legitimate G2 outcome").

## Alternatives Considered

- **Ship hybrid on by default because the headline number is good.** Rejected: it is the
  exact failure D-009's "every signal must earn its place" exists to prevent. An overall win
  does not excuse a protected-slice loss (spec 04 §7.1), and the abstention regression alone
  is disqualifying — a knowledge tool that answers questions its corpus cannot answer is
  worse than one that says nothing.
- **Ship a similarity floor to restore abstention.** Rejected on the data above: the
  distributions overlap, so any floor trades false answers for lost recall at an arbitrary
  exchange rate. Measured, not assumed, and filed for 3.11.
- **Weaken the judged case that fails, or drop the `exact` slice.** Rejected outright: that
  is tuning the benchmark to the product, which D-010 names as the thing not to do.
- **Bundle the model in the wheel.** Rejected: a 133 MB wheel for a feature not everyone
  wants, and a licence-redistribution question for every model we might add.
- **Download the model automatically on first use.** Rejected: D-017's posture is zero
  network calls unless configured, and "it downloaded 133 MB without asking" is exactly the
  surprise that posture exists to prevent. The refusal message makes consent one setting.
- **Make embeddings a hard dependency.** Rejected: twenty-odd packages, one of them a
  ~50 MB runtime, charged to every install including those that only want lexical search.
- **Use sqlite-vec now.** Rejected for v1: extension loading is unavailable in stock Python
  builds on a supported platform, and an exact scan meets the budget inside the documented
  envelope. Revisit when the corpus envelope or the profile changes.
- **Declare the stage deterministic because it is bit-identical here.** Rejected: it is
  reproducible on *this* machine, which is not what reproducibility means. Verified by
  repeated inference in the test suite, and declared `false` anyway.
- **Expose `rrf_k` and the candidate depth as configuration.** Rejected: spec 04 §3 fixes
  both, and a knob with no eval evidence behind it is a compatibility liability (D-011).

## Consequences

- **The shipped default retrieval is unchanged from v0.2.0** — lexical BM25 — but it is now
  a *measured* default rather than an absent feature, and switching is one line of config.
  `mycelium search --hybrid` opts in for a single query.
- **Vectors are built by default** wherever the model is available: a build embeds, the
  manifest records `EmbeddingInfo` (model, dim, provider, `deterministic: false`), and the
  snapshot carries vectors ready for the day hybrid earns its default. Embedding 559 chunks
  cold cost 54 s on a laptop CPU; incremental builds embed only new text.
- **A second gate now fails visibly**: G4 (abstention) reports 25 % for the lexical baseline
  on our own corpus, because the eval corpus includes test fixtures — a pre-existing defect
  this measurement uncovered, recorded as
  [BUG-0007](../bugs/2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md) and filed as
  roadmap 3.10. It is reported, not suppressed: neither 25 % nor hybrid's 100 % is presented
  as a pass.
- **G6 is unaffected in substance**: the golden's only change is `config_digest`, because
  `[retrieval]` and two `[embedding]` keys joined the configuration. Every document, chunk,
  count, and artifact digest is byte-identical — verified field by field before re-blessing.
- **`[retrieval]` leaves the unhonoured set** and is validated strictly, with the two values
  that cannot be satisfied refused by name (`include_candidate = false` → roadmap 3.9,
  `graph_expansion = true` → roadmap 5.2/5.3) rather than silently ignored (ADR-0014).
  *`include_candidate = false` is honoured since [ADR-0024](0024-serve-what-the-configuration-admits.md);
  `graph_expansion` is still refused.*
- **Tests never depend on a developer's downloaded model.** The suite runs against an empty
  model cache by default, so local runs and CI see the same behaviour; the tests that need
  the real model are marked `embeddings` and skip when it is absent, which is always in CI.
  The vector path itself stays covered everywhere through a deterministic stand-in.
- **The planner is still absent** (spec 04 §2). Its first job would be routing
  identifier-like queries lexically — which is the `exact` regression above. That is now a
  measured motivation rather than a design intuition; it arrives with the symbol leg at 3.4.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §§1–3 (budgets, planning, fusion),
  §7.3 (the gates); `.draft-specs/02-architecture.md` §4.1 (stage contract and the
  `deterministic: false` allowance), §4.3 (degraded publication);
  `.draft-specs/05-interfaces-and-plugins.md` §2 (`[embedding]`, `[retrieval]`)
- Decision log: D-009 (hybrid, earned), D-011 (surface as liability), D-013 (local default,
  `(model_id, chunk_hash)` keying), D-017 (no unrequested network calls)
- Model: [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5), MIT,
  384 dimensions, CLS pooling, L2-normalised, pinned by SHA-256 in
  `src/mycelium/embedding/models.py`
- Tests: `tests/test_retrieval.py`, `tests/test_embedding.py`; benchmarks:
  `tests/bench/test_retrieval_bench.py`
