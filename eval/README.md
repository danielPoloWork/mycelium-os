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

## The case sets

Four of them: a **dev** and a **release** set per corpus (spec 04 §7.1, ADR-0027).

| set | cases | corpus |
|---|---:|---|
| [`dev.jsonl`](dev.jsonl) | 20 | this repository's documentation |
| [`release.jsonl`](release.jsonl) | 14 | this repository's documentation |
| [`corpora/uv-docs/eval/dev.jsonl`](corpora/uv-docs/eval/dev.jsonl) | 12 | [`uv`'s documentation](corpora/uv-docs/README.md) |
| [`corpora/uv-docs/eval/release.jsonl`](corpora/uv-docs/eval/release.jsonl) | 16 | the same |

**The release set is what CI gates. The dev set is what tuning may look at.** A release run
scores the dev set beside it and prints the gap — reported, never gated, because nobody has
the evidence to set a threshold and a constant chosen to look rigorous is worse than a number
a reviewer reads. The gap is the overfitting signal G3 cannot give: G3 compares a run to a
baseline over the *same* cases, so a change that fits those cases better passes it by
construction.

The existing twenty cases became the **dev** set rather than the release set, because four
ADRs' worth of tuning already read them. Relabelling them would have frozen the set the
product was fitted to and called it independent.

Regenerate either corpus's sets with:

```bash
python tools/build_eval_cases.py       # this repository's documentation
python tools/build_uv_docs_cases.py    # the second corpus
```

The judgments live in those scripts as data, so every anchor is validated against a real
build before a set is written.

**Freezing is a conjunction, not an immutability.** Sets have to grow, so
`tools/check_frozen_release_sets.py` refuses a change that edits a release set *and* touches
retrieval, chunking, the store or the metrics. One change may move the retriever, or move
the judgments, and not both — which is the failure that actually happens: a run comes back
worse, a judgment looks wrong in hindsight, and the set quietly becomes the thing that fits.

**Corpus:** this repository's own documentation, as `mycelium.toml` defines it —
`[project] exclude` drops `tests` (fixtures are test data, not knowledge), `docs/journal`
(it grows every session and would churn judgments for no gain), `eval/corpora` (the second
corpus is measured separately, not mixed in), and the legacy tree. That line is not
housekeeping: before it existed, a query about message brokers was answered by a *test
fixture* and gate G4 read 25 %
([BUG-0007](../docs/bugs/2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md)).

**Three guards keep the sets honest**, because each trap is easy to walk back into:

- A judged anchor must exist in the corpus. Headings move.
- An `unanswerable` case must be unanswerable by *either* retriever — grep matches word
  prefixes, so a case that separates the two is measuring tokenisation, not abstention. It
  caught a replacement query this repository's documentation had grown into, and caught
  three more on the second corpus on their first run (`ratio` matches `rationale`).
- A grade-3 anchor that is a heading stub **warns**. It found four mis-judgments the moment
  it existed — and it stays a warning because short is only a proxy for empty: `## License`
  followed by one line naming the licence is 24 tokens and is a complete answer.

**Slices covered:** `exact`, `symbol`, `fact`, `conceptual`, `relationship`, `injection`,
`unanswerable`. Metrics are always reported per slice — an overall win never excuses a
protected-slice loss.

## Chunk or section: the judging rule

A judgment may name a chunk (`docs/a.md#setup/2`) or a section (`docs/a.md#setup/`, with the
trailing slash). A section is satisfied by any chunk under it and **credited once** (ADR-0029).
Which to write is a judgment about the document:

> **Name the section when a reader needs more than one chunk to have the answer** — a
> procedure with the example that shows it, prose plus the table that lists it, a search order
> stated across paragraphs. **Name the chunk when the answer is confined to it** — a literal
> term, one stated fact, a paragraph that stands alone.
>
> When it is genuinely unclear, name the chunk. That is the reading that cannot flatter us.

The rule exists because judging a chunk of a twelve-chunk section measures where the *chunker*
splits, which has nothing to do with retrieval — and because a chunk anchor carries an ordinal,
so [ADR-0023](../docs/adr/0023-make-the-chunk-target-steer-size.md)'s chunking knob invalidates
one and leaves the other standing.

## What this set is not

- **The judgments are still not independent, and only half the problem moved.** Nobody here
  wrote `uv`'s documentation, so a query over that corpus has to be guessed the way any
  reader would guess it. But the same agent that builds the retriever still assigns the
  grades on both corpora. Removing that needs judgments from someone else, which is what
  1.0's published guidelines and redistributable subset are for (spec 04 §7.6).
- **Relevance is chunk-exact, and that is measuring something narrower than it looks.** A
  case naming one anchor for a section the chunker split into twelve scores 0 even when the
  retriever returns five chunks of that very section — which is what happened on the second
  corpus, where the judgments were not written by someone who knew where chunk boundaries
  fall. The cases are left as authored and the question is filed as roadmap 3.15: re-judging
  after seeing a ranking cannot be told apart from fitting the set to the result.
- **62 cases is the floor the spec asks for at this phase, not a benchmark.** 1.0 wants
  ≥ 1 000. Small sets move a lot on single-case changes, so read differences of a few points
  as noise.
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
