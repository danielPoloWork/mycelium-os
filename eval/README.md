# Evaluation

The judged case set behind `mycelium eval`, and the honest account of what it does and
does not prove.

```bash
mycelium eval                      # score the default set against the published snapshot
mycelium eval --retriever grep     # the incumbent, for comparison (D-010)
mycelium eval --gate               # exit non-zero if a gate fails (CI mode)
mycelium eval --tasks              # the agent-task suite against the grep loop (D-010)
mycelium eval --bless              # freeze this run as gate G3's baseline
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

**Corpus:** this repository's own documentation, as `mycelium.toml` defines it —
`[project] exclude` drops `tests` (fixtures are test data, not knowledge), `docs/journal`
(it grows every session and would churn judgments for no gain), and the legacy tree. That
line is not housekeeping: before it existed, a query about message brokers was answered by
a *test fixture* and gate G4 read 25 %
([BUG-0007](../docs/bugs/2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md)).

**Two guards keep it honest**, because the same trap is easy to walk back into:

- The builder refuses to write a set in which an `unanswerable` case is answerable — by
  *either* retriever, since grep matches word prefixes and would otherwise diverge from us
  for reasons that have nothing to do with abstention. It caught a replacement query that
  this repository's documentation had grown into, on its first run.
- Both builders warn when a grade-3 anchor is a heading stub: fourteen tokens that read
  like the right section and carry none of the answer. That lint found four mis-judgments
  the moment it existed, one of them in the existing case set.

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
  system returns nothing at all, which happens only when every query term is absent from
  the corpus. A natural-language question about something the corpus does not cover still
  returns low-ranked noise, because retrieval has no confidence signal to abstain on
  (roadmap 3.11). G4 proves the system does not invent matches, and no more.
- **The dev/release split is not real yet.** Spec 04 §7.1 wants the release set frozen
  before any tuning; we gate on the same twenty cases we develop against, so G3 detects
  regression but not overfitting. Filed as roadmap 3.13 with the ≥ 60-case, two-corpus
  target spec §7.6 sets for this phase.
- **The judgments are not independent.** They were assigned by the same agent that wrote
  most of the documents being judged — useful for regression detection and for the grep
  comparison, not an independent benchmark.
- **Twenty cases is a seed.** Small sets move a lot on single-case changes; read
  differences of a few points as noise.
- **The `injection` slice is one case**, and it only checks that the doctrine is findable.
  Resistance itself is tested as a property against a hostile fixture corpus
  (`tests/test_injection.py`); the full adversarial suite is milestone 6.3.
- **`synthesized` has no cases** — the synthesis lane arrives at 4.4.

## Gates evaluated here

Every gate spec 04 §7.3 names is accounted for. A table with silent omissions reads as
though the missing gates passed.

| Gate | Status |
|---|---|
| G1 Citations | **Enforced** — every returned anchor must resolve; must be 1.00 |
| G2 Earn hybrid | **Enforced when `--retriever hybrid` runs** — it scores the lexical baseline on the same cases and compares (ADR-0017) |
| G3 No regression | **Enforced against `baselines/<set>.json`** when the corpus is the one the baseline was taken on — no slice may fall more than 2 %. When the corpus has changed the numbers are not comparable, so the gate *reports* the deltas instead of failing on them: this repository's documentation grows with every PR, and a gate that fails on that teaches everyone to re-bless on red. `--bless` writes a baseline, and records the corpus fingerprint it was measured on |
| G4 Abstention | **Enforced** — false-answer rate on `unanswerable` ≤ 5 % |
| G5 Performance | **Enforced, with its limit stated** — query p95 ≤ 150 ms, reported with the corpus size it was measured on. The budget is defined at the 10⁵-chunk reference profile, so passing here is a floor rather than the measurement spec 04 §1 asks for |
| G6 Determinism | **Delegated** — a compiler gate with its own golden and its own CI job (ADR-0012) |
| G7 Grounding | Not applicable — it gates a *synthesized document's* promotion, and the synthesis lane arrives at 4.4 |

CI runs G1–G6 on every push (`eval / gates G1-G6`), reports the grep baseline without
gating on it, and runs the agent-task suite.

## The agent-task suite

[`tasks.jsonl`](tasks.jsonl) — 22 tasks, built by
[`tools/build_agent_tasks.py`](../tools/build_agent_tasks.py) with the same discipline as
the cases: judgments as data, every required anchor validated against a real build.

D-010's standard is not another retriever, it is the agent's own `grep`/`read` loop, so
each task runs through both. Because a model in the loop needs a key, a budget, and a
network — none of which belongs in an offline gate — what is measured is the *substrate*
each strategy hands a model: did the required evidence arrive, and what did it cost?

| | evidence found | mean tokens | p95 |
|---|---|---|---|
| mycelium | 64 % | 2 165 | 13 ms |
| grep | 27 % | 4 333 | 129 ms |

The gap in tokens is the point: a grep hit is a line number, so the loop reads whole files,
and whole files are what the model has to be handed.

**What this cannot tell you:** whether the model then answers correctly. Evidence reaching
the context is necessary and not sufficient, and no number here should be quoted as a
task-success rate without that sentence attached (ADR-0022). The quantified gate with a
real agent arrives at 1.0, where spec 04 §7.4 puts it.
