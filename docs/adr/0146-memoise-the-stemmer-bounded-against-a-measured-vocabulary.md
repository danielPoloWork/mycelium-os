# ADR-0146: Memoise the stemmer, bounded against a measured vocabulary

- **Status:** Accepted
- **Deciders:** tech-lead (EADOS delivery agent) with the maintainer, per RFC-0001 /
  spec 04 §3
- **Date:** 2026-09-21
- **Related:**
  [ADR-0132](0132-address-the-lexical-index-by-rowid-and-profile-what-is-left.md)
  (roadmap 6.19, which measured the redundancy and named this item),
  [ADR-0048](0048-index-the-stem-beside-the-surface-form.md) (the three stem columns
  `put_chunks` writes per chunk),
  [ADR-0145](0145-let-the-digest-be-the-durability-and-stop-paying-for-a-second-name.md)
  (roadmap 6.30, this item's sibling from the same profile, and the discipline of
  alternating arms on an idle machine that this record reuses);
  D-011 (a knob nobody has evidence for is a liability); spec 04 §3; roadmap 6.19, 6.31

## Context

Roadmap 6.19 profiled a 1 000-document cold build and, once the file-write ceremony
(6.30) and the quadratic it replaced were accounted for, found the lexical index's
stemming pass costing **7.44 s** on its own. `put_chunks` writes three stem columns
beside the surface ones (ADR-0048), so four fields per chunk — text, title, heading,
ancestors — are stemmed word by word. Measured on the profiled corpus:

| | |
|---|---:|
| word occurrences stemmed | 620 293 |
| distinct words among them | **10 339** |
| calls a cache would serve from memory | **98.3 %** |
| stemming every occurrence | 7.44 s |
| the same, memoised | **0.31 s** (23.6×) |

`stem()` is a pure function of an already-lowercased word — no state, no configuration,
no corpus dependence — so memoising it is safe by construction: the same input always
produces the same output, and a cache built from it can never disagree with the
function underneath.

**What needed a moment's thought, and is the reason this is a decision rather than a
decorator.** An unbounded cache holds one entry per distinct word for the life of the
process. For a build, that is fine — the vocabulary is whatever the corpus contains and
the process exits when the build finishes, 10 339 entries here and tens of thousands on
a larger one. For the MCP server (`mycelium.mcp.server`, a stdio process that runs for as
long as a client keeps it open), it is not: the same function runs on every query's
terms, for the life of the process, and an unbounded cache's growth is then a function of
how many distinct words a caller has ever sent rather than of the corpus. The item names
this directly — *"the bound, if any, belongs to the measurement of a realistic vocabulary
rather than to taste."*

## Decision

**Memoise `stem` with `functools.lru_cache`, bounded at `_VOCABULARY_CACHE_SIZE = 131_072`
— roughly 11× this project's own largest built corpus.**

The bound is sized against measurement, not chosen for its shape. This project builds and
gates three corpora; the largest indexes:

| corpus | documents | distinct FTS terms (surface + stem, all columns) |
|---|---:|---:|
| `ours` | 233 | **11 734** |
| `uv-docs` | ~1 000 pages | 4 592 |
| `uv-docs-ingested` | (the twin) | 4 593 |

131 072 leaves an order of magnitude of headroom above the largest of the three, at a
cost measured directly rather than assumed: 100 000 short-string cache entries hold
**~9 MB** (`tracemalloc`, this machine) — negligible next to the embedding model
threat-model boundary B8 already loads into the same process when hybrid retrieval is
configured. A corpus whose vocabulary exceeds the bound pays an ordinary cache miss and
recomputes; nothing about correctness depends on staying inside it, because eviction
removes a memo, never the algorithm.

`cap 1` through `cap ≥ DEPTH` is not this decision's shape — there is no tuning curve
here, because a memoisation cache is correct at every size, unlike the diversity
policies ADR-0144 measured and refused. The only question was *how much* headroom to
buy, and D-011's rule against a knob nobody has evidence for cuts the other way here: a
*configurable* bound would be exactly that knob, so the constant is fixed and named, not
exposed.

### What it measures

Two figures, both re-runnable:

**The unit claim**, re-taken on a real repository document rather than a synthetic word
list (`tests/bench/test_stemming_bench.py`, `AGENTS.md`'s own prose, ~4 100 words): a
cold pass (cache cleared before every round) costs a median **25.0 ms**; the same words
stemmed warm cost **1.5 ms** — a **16.7×** ratio, the same shape as ADR-0132's 23.6× at a
smaller, less-repetitive vocabulary.

**The end-to-end claim**, arms alternated on an idle machine (ADR-0145's discipline, three
rounds), cold build at 250 documents:

| | before | after | |
|---|---:|---:|---|
| cold build, 250 documents | 22.50 s | **19.67 s** | **−12.6 %** |

Two measurements taken in the same runs, on paths this change cannot touch, calibrate
what counts as noise on this machine: the incremental rebuild floor moved **+4.3 %** and
warm in-process search **+9.9 %**. A single-digit-to-low-double-digit swing here is
noise, consistent with the +7.8 % floor ADR-0145 recorded the day before on the same
machine; **−12.6 % on the cold build is the signal**, and it is larger than a naïve
linear scaling of ADR-0132's ~8 %-of-build figure would predict at a quarter of the
corpus size — plausibly because small-corpus builds pay proportionally more of their
time in Python-level work and less in I/O, which is exactly where a per-word cache
pays off hardest.

## Consequences

**Positive.** A pure function is memoised without changing what it returns; every
existing stemming test passes unmodified, and two more pin the new behaviour: the cache
and a cold call must agree (a correctness property that would otherwise be provable only
by inspection), and the cache must evict rather than grow past its bound under a flood
of never-seen words — the direct test of the "slow leak" the item worried about, run
against a live server-shaped scenario without needing to run a server.

**Negative, and accepted.** The bound is a judgement anchored to today's corpora, not a
law: a future corpus with a genuinely larger vocabulary loses some of the memoisation's
benefit, gracefully, as ordinary cache misses — never as a wrong answer. If that ever
becomes a real cost, the fix is to widen `_VOCABULARY_CACHE_SIZE` against the corpus that
justified it, the same way this one was chosen, not to make it configurable pre-emptively.

**The Linux reading arrived, and it confirms the win is the algorithm's, not the
machine's.** `tests/bench/test_stemming_bench.py` ran on this PR's own CI (`ubuntu-24.04`,
no filter driver): cold **9.99 ms**, warm **0.52 ms** — a **19.1×** ratio, in the same band
as the Windows figure (16.7×) and closer to ADR-0132's own 23.6× at corpus scale. Unlike
ADR-0145's write ceremony, where the two machines paid for different things and the ratio
moved by 7×, memoisation's saving is the same shape on both: it removes repeated work,
and repeated work costs roughly what it costs wherever the process runs.

**What this does not touch.** `stem_text`, which lowercases and maps `stem` over a
token list, is unchanged — the memoisation lives entirely inside the one function that
benefits from it, so a caller iterating a list of terms gets the speed-up for free and
pays nothing extra for the wrapper.

**A second defect, found by this change failing to prove itself.** `tools/verify.py`'s
mode derivation ran the `retrieval`-yielding rules (`TUNING_PATHS`, `EVAL_DATA_PREFIXES`)
before the `full`-yielding ones (`BENCH_PREFIXES`, `CI_PREFIXES`) as a flat sequence of
early-return loops — so a diff touching **both** a tuning path and a full-only path
returned `retrieval` and stopped, never reaching the rule that should have widened it.
This PR is exactly that diff: `src/mycelium/store/stemming.py` (a tuning path) beside
`tests/bench/test_stemming_bench.py` (ADR-0145's `BENCH_PREFIXES`), and it derived
`retrieval` — silently skipping the benchmark this record cites. The bug was live from
the day `CI_PREFIXES` was added (roadmap 4.31) and had no test exercising the
combination; `BENCH_PREFIXES` (roadmap 6.30, the day before) made it reachable by an
ordinary PR rather than a contrived one. `derive` now classifies each path on its own
and takes the genuinely widest mode — `MODES.index`, maximised — with ties broken by
each rule's declared priority, which is what `test_a_tuning_path_outranks_an_eval_path`
already required and what the loop-order accident had been standing in for. Three new
tests pin the combination directly, in both list orders.
