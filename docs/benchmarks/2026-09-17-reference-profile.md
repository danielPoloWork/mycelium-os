# Benchmark Report: the reference profile

- **Date:** 2026-09-17
- **Version / commit:** v0.5.0 @ `cf9e197`
- **Environment:** Windows 11 (10.0.26200), Intel 12th-gen family 6 model 151, 20 logical
  CPUs, 31.7 GiB, CPython 3.12.10. A warm read of a 4 KB Markdown file costs **1.29 ms** on
  this machine — the calibration constant every build figure has to be read against.
- **Command:** see [Reproduce](#reproduce)
- **Run manifest:** [`manifests/2026-09-17-reference-profile.json`](manifests/2026-09-17-reference-profile.json)

This is the first benchmark report this project has published. It exists because
roadmap 6.4 asked for one and found that the corpus every performance claim is stated
against had never been built.

> **Amended 2026-09-18 by roadmap 6.18 ([ADR-0128](../adr/0128-cache-the-environment-not-the-repository-and-declare-the-names-instead-of-importing-them.md)).**
> A dated report records what was measured on its date, so the figures below stand as taken.
> Two of its *explanations* were wrong, and fixing the constant is what found them.
>
> - **The first-call import cost is not the docling/pandoc/PDFium graph** (see
>   [Where the end-to-end cost goes](#where-the-end-to-end-cost-goes)). Those three parser
>   modules guard their engines behind a factory, and importing
>   `mycelium.ingest.registry` imports **no engine module at all**. What it imports is 126
>   modules of which **63 are `markdown_it`**, reached because `mycelium/ingest/__init__.py`
>   eagerly imports its whole package.
> - **The MCP server does not pay that cost on its first call**; it pays it at *import*,
>   because `mycelium.mcp.tools` already pulls all 20 `mycelium.ingest` modules through
>   `mycelium.build.publish`. It is a startup cost and never appears in the p95. Roadmap
>   6.25 owns it.
>
> **What the fix moved**, same machine, same corpus: `load_config` 262 ms → **2.1 ms**, and
> `handle_search` end to end 302 ms → **45 ms mean / 58.6 ms p95** — inside NFR-2's budget at
> this corpus size for the first time. Interpretation 2 below is unaffected and remains the
> live question: at 10⁵ chunks the warm query alone is 1 816 ms p95 (roadmap 6.21).

## Scenario

Three budgets are stated in three documents, and all three name conditions:

| Claim | Budget | Stated conditions | Where |
|---|---|---|---|
| Cold build | < 60 s | 1 000 documents | spec 01 §8 |
| Incremental single-document rebuild | < 2 s p95 | equals a clean rebuild | NFR-3, spec 06 §Phase 1 |
| End-to-end `mycelium_search` | ≤ 150 ms p95 | local profile, **10⁵ chunks**, warm store | NFR-2, spec 04 §1 |

Nothing had ever been measured above **1 420 chunks** — this repository's own corpus,
seventy times below the third condition. Gate G5 enforces the query budget on whatever
corpus the evaluation ran and states that limit in its own output, so this was visible
rather than hidden; it had simply never been done, and *"search p95 < 150 ms on the
10⁵-chunk reference corpus"* has been a closed Phase-1 exit gate since v0.3.0.

**Method.** `tools/benchmark_reference_profile.py` composes documents from prose
harvested out of the two corpora this repository vendors, under a seed, and measures
across a curve of corpus sizes. Real blocks, real headings, real code fences, so the
lexical index sees documentation's term distribution rather than random words. The
query path is measured twice — warm and in-process, and through the MCP handler that
NFR-2 actually names — because the difference between those two turned out to be the
finding.

## Results

### Against the three budgets

| Claim | Budget | Measured | Verdict |
|---|---|---|---|
| Cold build, 1 000 documents | < 60 s | **193.5 s** | ✗ 3.2× over, at exactly the stated size |
| Incremental rebuild p95 | < 2 s | **2 206 ms** at 250 documents, **6 307 ms** at 998 | ✗ crossed at ~250 documents |
| `mycelium_search` p95, end to end, **at 10⁵ chunks** | ≤ 150 ms | **2 185 ms** (p50 1 267 ms) | ✗ **14.6× over**, at exactly the stated condition |
| *(the same query, warm and in-process, at 10⁵ chunks)* | *(≤ 150 ms)* | 1 816 ms (p50 1 089 ms) | ✗ 12× over — the constant is not the only problem |

### The curve

Generated documents, compiled by the real compiler. Twenty timed single-document edits at
each size; 39 judged queries, run twice with the second pass timed.

| Documents | Chunks | Cold build | Incremental p50 / p95 | Search warm p50 / p95 | Search end-to-end p50 / p95 | File open |
|---:|---:|---:|---:|---:|---:|---:|
| 250 | 1 252 | 33.6 s | 1 950 / **2 206** ms | 19.6 / 30.4 ms | 288 / **585** ms | 1.31 ms |
| 998 | 4 939 | 193.5 s | 6 001 / **6 307** ms | 59.5 / 99.5 ms | 329 / **431** ms | 1.29 ms |

The **file open** column is the calibration constant, not a result.

### The query path at 10⁵ chunks

The condition NFR-2 actually names. The store holds 100 000 chunks of the same harvested
prose, written directly rather than compiled — compiling them takes about nine hours
([BUG-0031](../bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md)) and
the retriever cannot tell the difference, which was checked: at 4 945 chunks a
directly-loaded store and a compiled one answer the same 39 queries within 6 %.

| Measurement | p50 | p95 | Budget |
|---|---:|---:|---|
| `search`, warm store, in-process | 1 089 ms | **1 816 ms** | 150 ms |
| `mycelium_search`, end to end | 1 267 ms | **2 185 ms** | 150 ms |

The query path is close to linear in the corpus — 0.0157, 0.0121 and 0.0109 ms per chunk at
1 252, 4 939 and 100 000 chunks on the p50 — so this is not a cliff. It is the budget being
stated for a corpus seventy times larger than anything that had ever been measured.

### Cross-check: the real corpora

Compiled by the real compiler from real documentation, so the constant cannot be blamed on
the generator. Far too small to test a budget stated at 10⁵ chunks, which is the whole
problem:

| Corpus | Chunks | Search warm p50 / p95 | Search end-to-end p50 / p95 |
|---|---:|---:|---:|
| this repository | 1 410 | 35.6 / 53.3 ms | 307 / **1 083** ms |
| `eval/corpora/uv-docs` | 568 | 7.4 / 17.5 ms | 278 / **344** ms |
| `eval/corpora/uv-docs-ingested` | 592 | 7.4 / 19.1 ms | 214 / **312** ms |

Every one of them misses the end-to-end budget while the retrieval inside it is comfortably
within. A 568-chunk corpus of somebody else's documentation takes 278 ms at the median to
answer a query whose retrieval costs 7 ms.

### Where the end-to-end cost goes

The warm number is inside the budget below ~7 500 chunks and the end-to-end number is
outside it everywhere, so the gap is a constant. Timed on this repository's own corpus,
per call:

| Step in `handle_search` | Cost | What it does |
|---|---:|---|
| `_config(root)` → `load_config` | **230 ms** | re-reads a ten-line `mycelium.toml` |
| ↳ of which `modules.installed_ids()` | **219 ms** | `importlib.metadata.entry_points()`, uncached |
| `_open_store` | 10–12 ms | a fresh read-only SQLite handle |
| `read_current` | 2 ms | the published snapshot pointer |
| the search itself | 7–1 089 ms | grows with the corpus |

`entry_points()` re-reads the metadata of **every installed distribution** on every call,
and `load_config` calls it to decide whether a configuration section names an installed
module (ADR-0077). That one line costs more than the entire 150 ms end-to-end budget,
before a single chunk is ranked. The first call in a process pays a further ~616 ms of
imports, because the configuration validator reaches into the ingest registry and pulls in
the docling/pandoc/PDFium module graph — 129 modules — to check that no connector is
configured as a parser.

Roadmap 6.18 owns the fix. Note what hid this: gate G5 times the retriever *inside the
harness*, so the number NFR-2 actually names has never been on a gate.

### The agent-task comparison

Spec 04 §7.4's suite, 22 tasks, on this repository's corpus as this pull request commits it
(191 documents, 1 420 chunks), after the four rotted anchors were repaired:

| Strategy | Evidence found | Mean context | Median context | Documents read |
|---|---:|---:|---:|---:|
| Mycelium | **16 / 22** (72.7 %) | 2 852 tokens | 2 982 | 5.1 |
| grep | **1 / 22** (4.5 %) | 51 319 tokens | 80 996 | **1.0** |

**Do not quote the ratio.** It is 18.0× on means and 27.2× on medians, and it is mostly a
fact about one file. `ROADMAP.md` is 80 996 tokens — 18 % of the corpus, 45× the median
document — and the grep loop reads it whole on 13 of the 22 tasks, which is **93.3 % of the
incumbent's entire measured cost**. Worse, the loop is documented to read up to five
matching files and read exactly **one on all 22**: the first file already exceeds the
4 000-token budget, so it is taken whole and the loop stops. grep's 4.5 % is therefore not
*"grep is bad at retrieval"* — it is *"grep's one file was the wrong file, and it never got
a second."*

That is the second instrument defect this report found, after the anchor rot, and it has
the same shape: the comparison changed character as the corpus's documents grew, and
nothing noticed. ADR-0022 measured 27 % and a 2× ratio when they were small. Roadmap 6.22
owns the question it raises, which is a real one — what *does* a grep loop do with a file
larger than its budget? — and must be answered on what an agent does, never on what makes
our number better.

> **Answered on 2026-09-18** ([the incumbent reads a
> window](2026-09-18-the-incumbent-reads-a-window.md), ADR-0131): it reads a window, so one
> read now costs at most what one search may and the loop opens the five files its constant
> always claimed. The incumbent gained **13 tasks** (1/22 → 14/22) and shed two-thirds of its
> cost (52 529 → 15 268 mean). **The table above is superseded; do not quote it.** Our lead on
> evidence is **+2 tasks** and the context ratio **5.7×**, and the verdict gate quantified
> below no longer passes its first condition on the repaired instrument.

One more reason these figures are dated rather than durable: writing this report grew
`ROADMAP.md` by roughly a thousand tokens, which moved the incumbent's cost. A benchmark on
a self-hosting corpus is inside its own measurement, and the only defence is to name the
corpus and the commit — which is what the manifest is for.

## Interpretation

**1. The end-to-end budget is missed by a constant, and the constant is not retrieval.**
On a 568-chunk corpus the retrieval costs 7 ms at the median and the tool call costs 278 ms.
On a 4 939-chunk one, 60 ms and 329 ms. The difference is ~250–300 ms that does not move with
the corpus, and most of it is an uncached `entry_points()` scan performed once per call
inside `load_config`. It means **no corpus of any size has ever met NFR-2**, including ones a
hundred times smaller than the condition — and the gate that was supposed to notice measures a
different function. Cheapest finding here to fix, and the most consequential. Roadmap 6.18.

**2. Fixing the constant is necessary and nowhere near sufficient.** At 10⁵ chunks the warm
query alone is **1 816 ms p95**, twelve times the whole budget, so removing every millisecond
of the constant would still leave NFR-2 missed by an order of magnitude. The path is close to
linear in the corpus and crosses 150 ms on its own at roughly **7 500 chunks** — about five
times this repository's corpus, and thirteen times below the profile the budget is stated
for. Either the query path gets an index that is not linear in the corpus, or the budget is
wrong; both are decisions, and neither is made here.

**3. The build budgets are missed at their own stated conditions.** Spec 01 §8 names 1 000
documents and 60 s; the measurement is 193.5 s. Throughput degrades with corpus size — 134
and 194 ms per document at 250 and 998 — and ~40 % of the 1 000-document build is one
quadratic line: `put_chunks` deletes from `chunks_fts` by an `UNINDEXED` column, which SQLite
answers with a full scan of the index, once per chunk
([BUG-0031](../bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md)). A
thousand chunks into an empty store take 2.7 s; the thousand after nine thousand others take
68 s. That is also why the reference corpus had never been built: loading 10⁵ chunks through
the compiler is about nine hours. None of this is the machine — file opens are ~1.3 ms, under
one percent of the build. Roadmap 6.19 owns the fix and the profiling of what remains.

**4. The incremental floor is a decision, not a bug.** `_plan` reads and digests every file
on every build — *"content truth comes from the digest, never from metadata"* — and calls
that read *"the incremental floor"*. The floor is linear in the corpus and crosses NFR-3's
2 s at around 250 documents here (2 206 ms p95, and 6 307 ms at 998). On this machine the
read alone is 1.3 ms × N, so at 1 000 documents it is 1.3 s of a 2 s budget before any work
happens; on a machine with fast opens it would be 20 ms. The answer therefore differs by
machine, which is itself the argument for saying which machine — and for NFR-3 to name a
corpus size the way NFR-2 does. Roadmap 6.20.

**5. The instrument was broken in two places, and both went unnoticed the same way.** Anchor
rot capped the agent-task rate at 18/22; a degenerate incumbent made 93 % of its measured
cost one file. Neither is a retrieval fact. Both happened because a measurement kept
reporting while the corpus moved underneath it — which is the same failure this whole report
is about, one level down.

### The agent-task verdict gate, quantified

Spec 04 §7.4 scores the comparison qualitatively pre-1.0 and makes it a gate at 1.0, which
ADR-0113 places at Milestone 7. The rule, stated now so it can be argued before it binds:

> **Agent-task uplift.** On the frozen agent-task suite, with **zero unresolved anchors**:
> (a) Mycelium's evidence rate exceeds grep's by more than **two tasks** (2/n of the suite);
> and (b) Mycelium's **median** context is at most **half** grep's median.

Two tasks rather than one because one task is the suite's granularity — at n = 22 that is
4.5 points — and a bar a single task can flip is a coin toss, which is the arithmetic
roadmap 6.8 applied to the per-slice conditions. **Median** rather than mean because the mean
is hostage to the largest document in the corpus: measured here, one file is 93 % of the
incumbent's cost, and a mean-based bar would have been measuring our roadmap.

Today both conditions pass by a wide margin — 16/22 against 1/22, and 2 982 tokens against
80 996 — and **neither margin is worth arming on**, because the two instrument defects
produce more of it than the product does. Three things have to hold first:

| Precondition | State |
|---|---|
| The integrity gate is green: no task requires a passage the snapshot lost | **done here** — enforced by `mycelium eval --tasks --gate` in CI and the ladder |
| The incumbent reads what its own model says it reads | **done 2026-09-18** — roadmap 6.22, ADR-0131 |
| The suite runs on a corpus we did not author (ADR-0053) | **open** — roadmap 6.23 |

> **The margin did not survive the second precondition.** With the incumbent's read bounded,
> the lead is **exactly two tasks** (16/22 against 14/22), so condition (a) — *more than* two —
> **fails**, while (b) passes at 5.7× against a bar of 2×. The rule is deliberately not re-cut:
> see [the 2026-09-18 report](2026-09-18-the-incumbent-reads-a-window.md#interpretation) and
> ADR-0131, which carry the question to roadmap 6.23 rather than moving the bar in the act of
> discovering we no longer clear it.

## What these numbers do not say

- **One machine, and a slow one at opening files.** A warm read of a 4 KB Markdown file
  costs ~1.3 ms here, roughly a hundred times an unencumbered SSD, because a real-time
  malware scanner sits in the open path. That constant is most of the incremental-rebuild
  figure and under one percent of the cold-build figure; the manifest records it so a
  reader with a faster disk can scale. The *shape* of each curve travels between
  machines; the absolute values do not.
- **The generated corpus has a closed vocabulary.** Its documents are recomposed from a
  fixed pool of harvested blocks, so a query's matching set grows in proportion to the
  corpus. A real corpus's vocabulary grows as it does, so a real one of the same size
  would match a smaller *fraction*. The query curve is therefore an **upper bound**, not
  a prediction, and the cross-check against the real corpora is what keeps it honest.
- **The generated corpus has almost no link structure.** Its documents do not
  cross-reference each other, so the graph stage is under-exercised and the edge count is
  low for the corpus size. If anything this flatters the build figures.
- **The profile measures the shipped default, which is lexical** (ADR-0017). Nothing here
  says what the hybrid path costs at 10⁵ chunks; the only statement this project makes
  about that is an extrapolation from 10 000 chunks, and roadmap 6.21 owns replacing it.
  **Answered on 2026-09-18** ([the hybrid path at the reference profile](2026-09-18-the-hybrid-path-at-the-reference-profile.md), ADR-0130): the vector leg is 43.2 ms on a fresh handle and 12.1 ms on a warm one at 10⁵ chunks, both inside spec 04 §1's 60 ms candidate budget — and the extrapolation was one of *three* disagreeing statements, all now retired.
- **The end-to-end figure is noisy, and its conclusion is not.** Across runs its p95 moved
  between roughly 330 ms and 700 ms on corpora of the same size, because most of it is an
  environment scan whose cost depends on the filesystem cache. Every reading is 2–5× the
  budget, so the verdict is robust even though the number is not; quote the p50 and the p95
  together, never one alone.
- **The build claims are measured only where the compiler can reach.** Compiling 10⁵ chunks
  takes about nine hours ([BUG-0031](../bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md)),
  so the cold-build and incremental figures stop at 1 000 documents and the query figure at
  10⁵ chunks comes from a store loaded directly. Those are different claims measured
  different ways, on purpose, and the report says which is which.
- **Evidence in front of a model is not a task completed.** The agent-task numbers say
  what reached the model, never what the model did with it (ADR-0022).

## Reproduce

From a clean checkout, with `uv sync --all-extras --dev`:

Everything in the manifest comes from **one invocation on an otherwise idle machine**.
That matters more than it looks: an earlier pass was taken while other work ran on the
same box and reported 1 295 ms where a quiet machine reports ~300 ms, so a contended
benchmark is not a slow benchmark, it is a wrong one.

```bash
# Every measurement in this report, in one pass (~30 min on the machine of record).
python tools/benchmark_reference_profile.py \
    --out <scratch-dir> --scales 250,1000 --no-reference \
    --query-scale 100000 --real-corpora \
    --manifest docs/benchmarks/manifests/2026-09-17-reference-profile.json

# The agent-task comparison, against this repository's own corpus.
mycelium build . --no-pin && mycelium eval . --tasks --json

# Validate every committed manifest (instant; the ladder runs this at every mode).
python tools/benchmark_reference_profile.py --check
```

The corpus is derived from the seed, so the same invocation reproduces the same corpus on
any machine. The numbers will not reproduce — they are wall-clock on the hardware in the
manifest — but the comparison between two sizes on one machine will.

Two measurements are deliberately **not** in that invocation, because they are the
evidence for [BUG-0031](../bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md)
rather than a budget: the per-batch chunk-write timings, and the query plan
(`EXPLAIN QUERY PLAN DELETE FROM chunks_fts WHERE anchor = ?` → `SCAN chunks_fts`). Both
are in the bug record with the code to repeat them.
