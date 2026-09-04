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

Six of them: a **dev** and a **release** set per corpus (spec 04 §7.1, ADR-0027).

| set | cases | corpus |
|---|---:|---|
| [`dev.jsonl`](dev.jsonl) | 20 | this repository's documentation |
| [`release.jsonl`](release.jsonl) | 19 | this repository's documentation |
| [`corpora/uv-docs/eval/dev.jsonl`](corpora/uv-docs/eval/dev.jsonl) | 12 | [`uv`'s documentation](corpora/uv-docs/README.md) |
| [`corpora/uv-docs/eval/release.jsonl`](corpora/uv-docs/eval/release.jsonl) | 16 | the same |
| [`corpora/uv-docs-ingested/eval/dev.jsonl`](corpora/uv-docs-ingested/eval/dev.jsonl) | 12 | [the same documents, ingested](corpora/uv-docs-ingested/README.md) |
| [`corpora/uv-docs-ingested/eval/release.jsonl`](corpora/uv-docs-ingested/eval/release.jsonl) | 16 | the same |

The third corpus is the second one **put through `mycelium ingest`** — the same 81 upstream
documents rendered into DOCX, HTML and PDF, and scored as the evidence documents the
projector wrote from them (roadmap 4.10). Its cases are not judged here: every query, grade
and slice is copied from the `uv-docs` sets and only the anchor is recomputed, so the
document is the only thing that varies. Every case carries today; the two that once lost
every anchor cleared the coverage floor when packing landed (roadmap 4.15).

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

`tools/build_ingested_cases.py --check` regenerates the carried set and compares instead of
writing; it runs in CI, because a derived artifact whose generator no longer reproduces it is
a defect rather than a cue to regenerate ([BUG-0018](../docs/bugs/2026/09/BUG-0018-carried-ingested-cases-do-not-reproduce.md)).
`eval/corpora/uv-docs-ingested/eval/carry.json` is that carry's receipt: every mapped anchor's
twin and its coverage, committed so drift reads as a diff of numbers.

```bash
python tools/build_eval_cases.py           # this repository's documentation
python tools/build_uv_docs_cases.py        # the second corpus
python tools/build_ingested_corpus.py      # the third corpus's evidence documents
python tools/build_ingested_cases.py       # ...and the judgements carried onto them
```

The judgments live in those scripts as data, so every anchor is validated against a real
build before a set is written.

## Did the retriever get worse, or did the corpus get bigger?

```bash
python tools/measure_slice_decay.py <git-ref> [--set release]
```

Gate G3 refuses to enforce across a corpus change ([BUG-0014](../docs/bugs/2026/08/BUG-0014-g3-compares-incomparable-corpora.md)),
which is right — this repository's documentation *is* its corpus, so every PR moves the
numbers — and the cost is that a slow decay can cross several milestones unremarked. That is
what happened to `relationship` on our own release set: 0.304 to 0.106, unnoticed
(roadmap 4.17). A *chunking* change is no longer one of the cases it abstains on: comparability
is judged on the documents, so moving every boundary in the corpus is gated (ADR-0045).

This tool asks the question the gate cannot. It holds the judgments and the compiler fixed and
varies only the corpus — the named ref goes into a throwaway worktree, today's judged sets are
copied in, both sides are compiled with today's compiler — then prints per-slice deltas and,
for the slices that moved, the per-case ranks behind them. A slice that moves here moved
because documents arrived; one that does not is telling you to look at the code.

**Read the per-case lines, not the slice mean.** A slice mean cannot distinguish a regression
from one case's luck, which is a finding about the sets rather than a caveat about the tool
([ADR-0044](../docs/adr/0044-name-what-a-two-case-slice-can-and-cannot-say.md)). Roadmap 4.20
acted on it — G3 now prints the cases behind any row it reports or fails, and enforces only
the rows that can carry it
([ADR-0052](../docs/adr/0052-give-a-slice-cases-or-stop-gating-it.md)) — but at these set
sizes the per-case lines are still where the answer is.

### What a baseline records

`eval/baselines/<set>.json`, per retriever:

| field | what it holds | what G3 does with it |
|---|---|---|
| `per_slice`, `overall_ndcg_at_10` | the frozen scores | compares against them |
| `content_digest` | what the corpus *says*, from chunk text | **decides whether it enforces** |
| `corpus_digest` | how the corpus was *cut*, the fold of chunk digests | reports it, names a re-cut |
| `cases_digest` | which judgements the means were taken over | **decides whether it enforces** |
| `cases` | how many, for whoever reads a diff | nothing |
| `per_case` | each case's nDCG@10, per slice | names the case behind a move (ADR-0052) |
| `blessed_from_snapshot`, `toolchain` | provenance | nothing |

A baseline missing one of the digests keeps the comparison it was written for, and the
verdict says which one is unarmed — reading an absent field as a match would let a stale
baseline enforce, and reading it as a mismatch would disarm the gate everywhere at once.
`tools/stamp_baseline_fingerprints.py` arms an older baseline without re-blessing, and
refuses when it cannot verify that the corpus or the case set was frozen before the bless.

**The committed baselines predate roadmap 4.19's index.** Stemming moved every release set
up by nine to eleven points with no slice regressing, and the baselines were deliberately
*not* re-blessed with it: how this repository's baseline is re-blessed at all is roadmap
4.22's open decision, and it says it cannot ride along with a retrieval change. Until it
does, G3 has that much headroom on the vendored sets — a change that gave the gain back
would pass it — and 4.22 should now re-bless against the retriever that actually ships
([ADR-0048](../docs/adr/0048-index-the-stem-beside-the-surface-form.md)).

## Candidate re-rankings, and why none of them shipped

```bash
python tools/measure_ranking.py                     # the dev sets - what tuning may read
python tools/measure_ranking.py --release           # the gate view, per slice
python tools/measure_ranking.py --oracle            # the ceiling no planner can beat
```

Ten candidate strategies live in that tool and **all ten are refused** — four rows by
[ADR-0031](../docs/adr/0031-refuse-three-rerankings.md) (a length prior at two floors,
coverage-first, section aggregation) and six by
[ADR-0041](../docs/adr/0041-bound-the-section-unit-and-refuse-six-more.md) (five more ways to
make a section the unit, plus the incumbent's own ranking function). They are kept rather
than deleted, because a refusal nobody can re-run is a claim, and the next attempt should
start from the numbers.

`--oracle` is the instrument worth knowing about: it scores, per case, the best any strategy
achieves. Nothing realisable can beat it, so when its ceiling sits 3 % above the incumbent
the family is closed — which is how roadmap 4.8 stopped being a search for one more re-rank
and became a chunking item (4.11).

**A judgment must be true under every configuration the set is scored under.** The rule
above assumes one chunker. When a chunking change is pending — `[chunking] pack_atomic` was
the first, measured at roadmap 4.11 and flipped on at 4.15 — a judgment naming a chunk that
the change deletes scores zero however good the retrieval was. So the unit a judgment names is the smallest one holding
the answer under *both* settings: still the chunk where the chunk survives, the section where
the change merges it away. Five cases were re-anchored on that basis at 4.12 and nothing else
was widened; the reasoning, and the one case where it overrides ADR-0029's caution with the
cost measured, is in
[ADR-0043](../docs/adr/0043-judge-across-the-configurations-a-set-is-scored-under.md).

**Freezing is a conjunction, not an immutability.** Sets have to grow, so
`tools/check_frozen_release_sets.py` refuses a change that edits a release set *and* touches
retrieval, chunking, the store or the metrics. One change may move the retriever, or move
the judgments, and not both — which is the failure that actually happens: a run comes back
worse, a judgment looks wrong in hindsight, and the set quietly becomes the thing that fits.

A **derived** set may not move in the same change as its source either, and that rule has a
cost nobody had walked into until roadmap 4.20: it makes a source set unable to grow at all,
because a source that gains cases must regenerate its carry (CI byte-checks it) and a
regeneration alone has nothing to regenerate from. The `uv` sets are blocked on it, together
with a second coupling — the third corpus assigns formats by rotation over the *judged* set,
so growing that set re-rolls renderings that are committed provenance. Both are roadmap
4.26's to settle ([ADR-0052](../docs/adr/0052-give-a-slice-cases-or-stop-gating-it.md)).

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

### Which slices gate G3, and which it only reports

A slice's score is a mean, and a mean over one case is that case wearing a slice's name: the
smallest move it can make is the case's whole range, against a 2 % threshold. So G3 enforces
a slice only when all three of these hold, and **names the row and the reason** when one does
not ([ADR-0052](../docs/adr/0052-give-a-slice-cases-or-stop-gating-it.md)):

| | why |
|---|---|
| it is not `unanswerable` | that slice scores 0.0000 by construction and a *fall* in it means the system got better at staying silent; **G4** gates it |
| the baseline is above zero | a relative threshold cannot fail a zero, so a row blessed at 0.0000 is unfailable whatever it does |
| it holds ≥ 4 judged cases | below that the row is one case relabelled — and 4 is a line drawn on a continuum, not a statistic: at these set sizes no honest threshold exists |

The verdict says so out loud — `4 of 6 slice(s) enforced; reported only: symbol (blessed at
0.0000: a relative threshold cannot fail it); …` — because a gate that reports "6 slices
compared" while four of them cannot fail is describing its own coverage inaccurately.

Every gated slice on **our own** release set now holds at least four cases; five were judged
at 4.20 for exactly that. The `uv` sets — the ones G3 actually enforces on, since ours is
never comparable — could not grow in the same change and read `1 of 6 slice(s) enforced`
until roadmap 4.26 lifts them. What makes G3 a regression gate rather than a single-case
alarm is set size, and that is spec 04 §7.6's ≥ 1 000 cases at 1.0, not a constant chosen
here.

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

## What projection costs

The third corpus exists to answer one question the other two cannot: **is an evidence
document projected from a binary source as retrievable as the Markdown a human would have
written?** `python tools/measure_projection_cost.py` scores both corpora over the cases they
share and prints the difference per format. On the release set, the same 14 cases twice:

| | n | nDCG@10 | MRR | R@10 | R@50 | judged passage |
|---|---:|---|---|---|---|---|
| overall | 14 | 0.327 → 0.385 | 0.266 → 0.387 | 0.583 → 0.583 | 0.958 → 0.958 | |
| docx | 2 | 0.587 → 0.587 | 0.600 → 0.600 | 0.750 → 0.750 | 1.000 → 1.000 | 1.0× |
| html | 3 | 0.167 → 0.167 | 0.135 → 0.136 | 0.333 → 0.333 | 1.000 → 1.000 | 1.0× |
| pdf | 5 | 0.379 → 0.517 | 0.260 → 0.550 | 0.800 → 0.800 | 1.000 → 1.000 | **10.6×** |

**Recall does not move.** Where structure survives — DOCX and HTML — the numbers are
identical, not merely close. The one apparent gain is PDF's ranking, and the last column is
why it is not one: a PDF has no headings, so its chunks are page-sized and the carried
anchor is ten times the size of the Markdown chunk it came from. A bigger target is easier
to rank highly. Reported, never gated: with two to five cases per format there is no
threshold anyone could defend ([ADR-0039](../docs/adr/0039-measure-what-projection-costs.md)).

The same run also found what projection costs that nobody was measuring: the Markdown corpus
compiles **229 edges** and its ingested twin **10**. A relative link between two documents
does not survive rendering and re-projection. Filed as roadmap 5.7.

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
- **The ingested corpus's anchors were carried, not judged — and the rule is not neutral.**
  `build_ingested_cases.py` picks the twin chunk with the most word overlap with the judged
  passage, which is mildly favourable to the ingested side. Every conclusion drawn from that
  corpus is stated in the direction the bias does not help.
- **93 cases is the floor the spec asks for at this phase, not a benchmark.** 1.0 wants
  ≥ 1 000. Small sets move a lot on single-case changes, so read differences of a few points
  as noise — and that remains true of every gated slice, four cases or not (ADR-0052).
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
| G3 No regression | **Enforced against `baselines/<set>.json`** when the corpus *and the judgements* are the ones the baseline was taken on, and only on the slices that can carry it — no enforced slice may fall more than 2 %, and a slice that is `unanswerable`, blessed at 0.0000, or thinner than four cases is reported by name with the reason (ADR-0052). "The same corpus" means the same *documents*, not the same chunk boundaries, so a chunking change is gated rather than excused (roadmap 4.13, ADR-0045) and the verdict names the re-cut. "The same judgements" means the same cases with the same grades: a slice's score is a mean over its cases, so a set that grew reads as a regression unless the gate can tell the two apart (roadmap 4.24, ADR-0051). When either has changed the numbers are not comparable, so the gate *reports* the movement instead of failing on it — and calls it movement, not regression. `--bless` writes a baseline and records all three fingerprints |
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
