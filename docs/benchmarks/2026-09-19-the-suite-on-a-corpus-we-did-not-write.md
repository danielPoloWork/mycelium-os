# Benchmark Report: the agent-task suite on a corpus we did not write

- **Date:** 2026-09-19
- **Version / commit:** v0.5.0 @ `fa6757d`, with roadmap 6.23's second suite
- **Environment:** see [`manifests/2026-09-19-the-suite-on-a-corpus-we-did-not-write.json`](manifests/2026-09-19-the-suite-on-a-corpus-we-did-not-write.json), [`manifests/2026-09-19-the-suite-on-the-ingested-twin.json`](manifests/2026-09-19-the-suite-on-the-ingested-twin.json) and [`manifests/2026-09-19-the-suite-on-this-repository.json`](manifests/2026-09-19-the-suite-on-this-repository.json) — the machine of record, as in the [reference-profile report](2026-09-17-reference-profile.md)
- **Command:** `python tools/build_uv_docs_tasks.py && mycelium build eval/corpora/uv-docs --no-pin && python tools/measure_agent_task_band.py eval/corpora/uv-docs`
- **Roadmap:** 6.23 · **Decision:** [ADR-0135](../adr/0135-judge-the-agent-tasks-on-a-corpus-we-did-not-write-and-carry-them-rather-than-re-judge-them.md)

## Scenario

The [reference profile](2026-09-17-reference-profile.md) quantified the agent-task verdict
gate and named three things that have to hold before it can carry weight. Two were closed:
the integrity gate is green (6.4) and the incumbent reads what its own model says it reads
(6.22, [the window report](2026-09-18-the-incumbent-reads-a-window.md)). The third —
**the suite runs on a corpus we did not author** — is what this measures.

Until now every agent task was anchored into this repository's own documents, which means
every property that moves the comparison was ours to change: which documents exist, how large
they are, where a chunk boundary falls under an anchor. ADR-0053 settled that shape for the
judged sets a year of milestones ago; the task suite never got the second half.

So there is now a second suite — twenty-two tasks over `eval/corpora/uv-docs`, judged by
reading uv's documentation and committed before anything was scored on it — and a third,
derived from it by carrying the same judgements onto the ingested twin (ADR-0135). Nothing in
the third is re-judged; only the anchor is recomputed.

**Corpora.** `eval/corpora/uv-docs`: **81 documents, 568 chunks**, vendored, none of it
written here. Its ingested twin: the same 81 documents projected from rendered PDF, DOCX and
HTML copies. This repository's own corpus is measured too, for comparison, and it was
measured in a **clean checkout of `fa6757d`** rather than in the working tree — because the
corpus is self-hosting, and the working tree contains this report.

## Results

### The comparison, at the shipped budget

Twenty-two tasks, 4 000-token budget, five files for the grep loop — the shipped point of
both bands. Zero unresolved anchors on all three corpora.

| Corpus | Mycelium | grep | Lead | Median context (ours / theirs) |
|---|---:|---:|---:|---:|
| `uv-docs` — documentation we did not write | **18 / 22** | 13 / 22 | **+5** | 2 274 / 15 251 (**6.7×**) |
| `uv-docs-ingested` — the same, projected | **17 / 22** | 11 / 22 | **+6** | 2 479 / 15 173 (**6.1×**) |
| this repository, at `fa6757d` | 16 / 22 | 15 / 22 | +1 | 2 697 / 15 130 (5.6×) |

**The three rows are three measurements, not one measurement with error bars.** The tasks
differ, the documents differ and the questions differ; what they share is the instrument. The
row to read for a *verdict* is the first, which is the point of ADR-0053 — and the row that
says most about the instrument is the third.

### What the third row says

On 2026-09-18, one day and three merges ago, this repository's corpus gave **16/22 against
14/22**, a lead of +2. Re-measured here at `fa6757d` on a clean checkout, the same suite on
the same instrument gives **16/22 against 15/22** — a lead of **+1**. Nothing about retrieval
changed; three pull requests landed, and the incumbent found one more task.

That is the ADR-0112 failure in miniature, on a denominator nobody can freeze: our own corpus
grows every merge, and the comparison drifts with it in whichever direction the new documents
happen to push. Roadmap 6.23 exists because a gate cannot be armed on a number that moves
when the project writes documentation.

### Where the evidence comes from, task by task

On `uv-docs`, Mycelium wins seven tasks the incumbent misses and loses two:

| | Tasks |
|---|---|
| Mycelium only | `ut-0001`, `ut-0003`, `ut-0011`, `ut-0012`, `ut-0013`, `ut-0014`, `ut-0016` |
| grep only | `ut-0008`, `ut-0022` |
| Neither | `ut-0018`, `ut-0021` |

Five of the seven we win alone are `locate` tasks — *find where X is defined* — which is the
shape the incumbent is worst at, because a term-matching loop ranks documents and a `locate`
task is answered by one section of one of them. Both of our losses and both of the shared
misses are tasks requiring **two** passages: `ut-0018`, `ut-0021` and `ut-0022` each need
evidence from two documents (or two sections), and a ten-hit result that spends four slots on
one document has fewer left for the second. That is roadmap 6.29's finding arriving
independently on a corpus that has never been ours.

### The band: our side cannot spend what it is given

| Budget (also the read window) | Mycelium | grep | Ours, median | Theirs, median |
|---:|---:|---:|---:|---:|
| 1 000 | 13 / 22 | 10 / 22 | 866 | 4 086 |
| 2 000 | 16 / 22 | 12 / 22 | 1 884 | 8 787 |
| **4 000** | **18 / 22** | **13 / 22** | **2 274** | **15 251** |
| 8 000 | 18 / 22 | 13 / 22 | 2 274 | 20 476 |
| 16 000 | 18 / 22 | 13 / 22 | 2 274 | 20 476 |

Our evidence rate and our median context are **identical at 4 000, 8 000 and 16 000 tokens**.
`_mycelium_context` asks the retriever for ten hits whatever `budget_tokens` says, so above
about 2 500 tokens the budget stops binding and the *limit* does — which is roadmap 6.28,
filed at 6.22 and confirmed here. Every figure in this report is therefore taken with our own
side of the comparison unable to use the budget it is handed; the incumbent's ceiling, by
contrast, is `MAX_GREP_FILES`, and it reaches it.

The incumbent's own band on this corpus is the same shape the window report measured on ours:

| Files opened | Evidence | Mean context |
|---:|---:|---:|
| 1 | 4 / 22 | 3 113 |
| 2 | 7 / 22 | 5 778 |
| 3 | 9 / 22 | 8 710 |
| 5 | 13 / 22 | 14 653 |

About three thousand tokens and two to three tasks per additional file — a straight line, and
a reminder that the incumbent's evidence rate is a purchase rather than a property.

## Interpretation

**1. The third precondition is met, and the verdict it exposes is better than ours, not
worse.** On documentation nobody here wrote, the suite reads +5 tasks and 6.7× the context —
both of ADR-0120's conditions pass with room. This is the opposite of the outcome a sceptic
should expect from *"they finally tested on someone else's corpus"*, and the reason is
visible in the task table rather than mysterious: our corpus's documents are unusually large
and unusually cross-linked, which suits a loop that reads whole files.

**2. It is still not armed, and this report is not the argument for arming it.** Spec 04 §7.4
conditions the gate on 1.0, which ADR-0113 places at M7. What this adds is the last missing
precondition and a second reading to argue with.

**3. The rule's first condition now fails on one corpus and passes on another, and that is a
question, not an answer.** *More than two tasks* is failed by this repository (+1 today, +2
yesterday) and passed by both vendored corpora (+5, +6). Someone arming the gate has to say
**which corpus the rule is read on** before they say whether it holds — and ADR-0053's answer,
*gate on the one we do not write*, is the one this project already gave for the judged sets.
Roadmap 7.3 carries that decision, with this report in front of it. What must not happen is
re-cutting the bar to whichever number passes: that is the benchmark-fixing D-010 forbids, and
ADR-0131 already refused it once.

**4. The projection costs about one task.** The twin scores 17/22 where its source scores
18/22, and the incumbent drops from 13 to 11. Both suites ask the same questions of the same
prose, so the difference is what rendering to PDF, DOCX and HTML and re-extracting did to the
passages — the measurement `uv-docs-ingested` exists to take (ADR-0039). Notably `ut-0001`
(the licence question, the cheapest in the suite) is a Mycelium win on the source and a miss
on the twin, while `ut-0008` goes the other way.

## What these numbers do not say

- **Evidence in front of a model is not a task completed.** The suite measures the substrate
  each loop hands a model, never what the model did with it (ADR-0022). A quantified verdict
  with a model in the loop remains 1.0's own question.
- **The tasks are ours even though the documents are not.** Which questions get asked, and
  which passage counts as the evidence, were decided by the same agent that builds the
  retriever. A second corpus removes the phrasing advantage — a prompt cannot echo words its
  document's author chose, because we did not choose them (ADR-0027) — and removes nothing
  else.
- **Our side is budget-capped at ten hits** (roadmap 6.28). Read every Mycelium figure here as
  *what ten hits contain*, not as what the budget bought.
- **The incumbent is a model of a loop, not a loop.** Five files, a bounded read, ranked by
  term matches (ADR-0131). The band is published so the choice can be argued.
- **No wall-clock is quoted.** Both strategies' latencies were recorded, and this machine was
  not idle enough for them to mean anything; the token and evidence counts are deterministic
  for a given corpus, which is why they are the figures here.

## Reproduce

From a clean checkout, with `uv sync --all-extras --dev`:

```bash
python tools/build_uv_docs_tasks.py --check        # the suite reproduces from its generator
python tools/build_ingested_cases.py --check       # the twin's copy derives from it
mycelium build eval/corpora/uv-docs --no-pin
mycelium eval eval/corpora/uv-docs --tasks --gate  # integrity: every anchor still resolves
python tools/measure_agent_task_band.py eval/corpora/uv-docs \
    --manifest docs/benchmarks/manifests/<date>-the-suite-on-a-corpus-we-did-not-write.json
```

For the third row, check `fa6757d` out into a separate tree first — a measurement of a
self-hosting corpus taken in the working tree includes whatever is being written about it.
