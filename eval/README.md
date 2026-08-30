# Evaluation

The judged case set behind `mycelium eval`, and the honest account of what it does and
does not prove.

```bash
mycelium eval                      # score the default set against the published snapshot
mycelium eval --retriever grep     # the incumbent, for comparison (D-010)
mycelium eval --gate               # exit non-zero if a gate fails (CI mode)
mycelium eval --json               # the run manifest, machine-readable
```

Runs are written to `.mycelium/eval/<run-id>.json`. A report without a manifest is
exploratory and cannot satisfy a gate (spec 04 §7.5).

## The case set

[`cases.jsonl`](cases.jsonl) — 20 judged cases over this repository's own documentation,
one record per line (`mycelium/eval-case/v0`). Regenerate with:

```bash
python tools/build_eval_cases.py
```

The judgments live in that script as data, so every anchor is validated against a real
build before the set is written: a case citing an anchor the corpus does not contain
cannot be committed.

**Corpus:** `README.md`, `ROADMAP.md`, `AGENTS.md`, `CHANGELOG.md`, `CONTRIBUTING.md`,
`SECURITY.md`, `CODE_OF_CONDUCT.md`, `docs/adr/`, `docs/patterns/`, `docs/workflow/`.
`docs/journal/` is excluded deliberately: it grows every session, and churning judgments
for that buys nothing.

**Slices covered:** `exact`, `symbol`, `fact`, `conceptual`, `relationship`, `injection`,
`unanswerable`. Metrics are always reported per slice — an overall win never excuses a
protected-slice loss.

## What this set is not

- **The judgments are not independent.** They were assigned by the same agent that wrote
  most of the documents being judged. That makes the set useful for regression detection
  and for the grep comparison, and *not* an independent benchmark. Independent judgments
  and a second, public corpus arrive at 3.7.
- **Twenty cases is a seed, not a benchmark.** The spec's Phase 0–1 target is ≥ 60 judged
  cases across two corpora; 1.0 wants ≥ 1 000. Small sets move a lot on single-case
  changes, so read differences of a few points as noise.
- **Absolute numbers are not targets.** Pre-GA the discipline is relative (spec 04 §7.3):
  compare against the previous run and against grep, not against an invented threshold.

## Known limitations

- **Abstention is measured only in the extreme.** A case counts as abstained when the
  system returns nothing at all, which happens only when *every* query term is absent from
  the corpus. A natural-language question about something the corpus does not cover still
  returns low-ranked noise, because retrieval has no confidence signal to abstain on yet.
  Score-calibrated abstention belongs with the query planner (3.7); until then G4 proves
  that the system does not invent matches, and no more than that.
- **The `injection` slice is one case.** The adversarial fixture corpus is milestone 6.3;
  this case only checks that the doctrine is findable, not that the system resists attack.
- **`synthesized` has no cases** — the synthesis lane arrives at 4.4, and there is nothing
  yet to judge.

## Gates evaluated here

| Gate | Status in v0 |
|---|---|
| G1 Citations | **Enforced** — every returned anchor must resolve; must be 1.00 |
| G4 Abstention | **Enforced** — false-answer rate on `unanswerable` ≤ 5 % |
| G2 Earn hybrid | Not applicable — hybrid retrieval arrives at 3.3 |
| G3 No regression | Not applicable — no frozen release set to regress against yet (3.7) |
| G5 Performance | Measured, not gated — the budget is defined against the 10⁵-chunk reference profile (3.7) |
| G6 Determinism | Elsewhere — a compiler gate, enforced in CI (roadmap 2.10) |
