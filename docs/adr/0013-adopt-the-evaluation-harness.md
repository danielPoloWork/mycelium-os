# ADR-0013: Evaluate against the grep incumbent, and publish the harness's limits with its numbers

- **Status:** Accepted
- **Date:** 2026-08-30
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7
- **Related:** [ADR-0012](0012-adopt-the-g6-determinism-gate.md) (the other gate),
  [ADR-0008](0008-adopt-sqlite-store-behind-a-store-protocol.md) (the lexical index),
  [BUG-0005](../bugs/2026/08/BUG-0005-fts-and-semantics-zeroes-queries.md); spec 04 §7;
  D-009, D-010, D-017; roadmap 2.11

## Context

D-010 makes evaluation a permanent release gate rather than a launch exercise, and names
the standard: "the real incumbent is not BM25 — it is the agent's built-in
`grep`/`glob`/`read` loop… If Mycelium OS does not visibly beat grep on these tasks, the
correct response is to fix the product, not the benchmark."

Spec 04 §7 fixes the assets (JSONL cases in `eval/`), the slices, the metrics (Recall@10,
Recall@50, nDCG@10, MRR, citation coverage, abstention, latency), the gates, and the rule
that a run without a manifest cannot satisfy a gate. What it leaves open is what a *v0*
harness can honestly claim, and that turns out to be the whole design problem: a harness
that reports numbers without its own limits is how benchmarks become marketing.

## Decision

**Ship the grep baseline in the first version, not later.** `mycelium eval --retriever
grep` scans the same corpus, extracts terms the same way, returns the same anchor space,
and ranks the way a person reading grep output would — by how many query terms a passage
contains, then by how often. It lacks only what the compiler adds: field weighting, term
saturation, length normalisation, structure. A comparison run only against yourself
measures nothing, and a baseline built to lose measures less.

**Enforce the two gates that are meaningful now, and say why the others are not.** G1
(citation coverage = 1.00) and G4 (false-answer rate ≤ 5 %) are checked on every run. G2
needs hybrid retrieval (3.3), G3 needs a frozen release set (3.7), G5 needs the
10⁵-chunk reference profile (3.7), G6 is a compiler gate (2.10). Each is named in the
harness and in `eval/README.md` with the reason it is absent, because a gate list with
silent gaps reads as a gate list that passed.

**No absolute thresholds.** Pre-GA the spec enforces *relative* discipline, so the test
suite asserts that Mycelium beats grep on nDCG@10, MRR, and latency — not that nDCG
exceeds a number someone invented. The one absolute is G1, which is absolute by nature.

**Ranking metrics average over answerable cases only.** An unanswerable case has no
relevant anchor, so scoring it nDCG 0 would punish the system for behaving correctly and
would let the mean be moved by changing the ratio of case types. Unanswerable cases are
scored by the false-answer rate instead.

**Judgments are validated, versioned, and attributed.** `tools/build_eval_cases.py` holds
them as data and refuses to write a set citing an anchor no build produces. Every case
carries a `note` explaining why it exists. And the provenance is stated plainly: these
grades were assigned by the same agent that wrote most of the documents being judged,
which makes the set a seed for regression detection and for the grep comparison, not an
independent benchmark.

## Alternatives Considered

- **Defer the grep baseline to the agent-task suite (3.7)**, since that is where the spec
  formally puts it. Rejected: the comparison is the point of the exercise, and a harness
  that cannot say "better than what?" produces numbers with no denominator. The
  agent-task suite measures a different, harder thing — task success and tokens — and
  still belongs at 3.7.
- **Adopt absolute quality targets now** (Recall@50 ≥ 0.90 and similar). Rejected by the
  spec itself: those are GA-phase goals, and on twenty cases an absolute threshold is
  noise dressed as a standard.
- **Score unanswerable cases as nDCG 0 in the overall mean** — simpler arithmetic.
  Rejected: it makes the headline metric a function of how many unanswerable cases the set
  happens to contain, which is an invitation to tune the set instead of the product.
- **Measure abstention with a score threshold** instead of empty results. Rejected *for
  now*: BM25 scores are unnormalised, so any threshold today would be invented rather than
  calibrated. The limitation is documented instead, and calibration belongs with the query
  planner (3.7).
- **Generate cases from the corpus automatically** (query = heading, relevant = its
  chunk). Rejected: it measures whether retrieval can find a heading by its own words,
  which is the one thing lexical search cannot fail at, and it would make the numbers
  meaningless while looking rigorous.
- **Keep judgments in hand-edited JSONL.** Rejected: nothing would stop a case from citing
  an anchor that no longer exists, and a silently broken case is worse than a failing one.

## Consequences

- **The harness found a high-severity defect on its first realistic run**
  ([BUG-0005](../bugs/2026/08/BUG-0005-fts-and-semantics-zeroes-queries.md)): FTS5's
  implicit `AND` meant a single absent word zeroed an entire query, so *every*
  natural-language question returned nothing, through CLI and MCP alike. Twenty short
  test queries across three milestones had not caught it. That is D-010 working exactly as
  intended, and it is the strongest argument for having built the baseline now rather than
  at 3.7.
- First measured result on this repository's own docs, 20 cases: Mycelium nDCG@10 0.70 vs
  grep 0.55, MRR 0.83 vs 0.62, p95 latency 3 ms vs 52 ms. The product beats the incumbent.
- It also names its own weaknesses, which is the more useful half: `relationship` scores
  0.32 (the typed edge graph does not exist until milestone 5) and `conceptual` 0.66,
  barely ahead of grep — precisely the gap hybrid retrieval must close to earn G2 (3.3,
  D-009).
- The manifest's `schema_versions` was corrected while adding the eval records: it had
  been reporting every exported contract rather than the artifact classes the snapshot
  published. The determinism golden was re-blessed accordingly — the workflow ADR-0012
  built for exactly this.
- Judged anchors depend on heading text in our own documents. When a heading moves, the
  test says so and the case must be re-judged. That is maintenance the eval set is
  supposed to have.
- Twenty cases is short of the spec's Phase 0–1 target of ≥ 60 across two corpora; the
  second corpus and the balance arrive at 3.7.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §7 (assets, metrics, gates,
  manifests, the grep baseline) · `.draft-specs/03-data-model.md` §10 (eval-case record)
- Decision log: D-009 (hybrid must earn its keep), D-010 (evaluation as a permanent gate,
  the grep incumbent), D-017 (untrusted query text)
- [`eval/README.md`](../../eval/README.md) — what the set proves, and what it does not
