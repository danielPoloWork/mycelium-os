# 2026-09-21 — the answer was already computed (roadmap 6.31)

- **Session scope:** roadmap 6.31 — the Porter stemmer re-stems the same ten thousand
  words six hundred thousand times; memoise it, and decide what a long-lived server
  owes a cache.
- **PR:** #181 (`perf/memoise-the-stemmer`). Follows #180, merged as `7d082c5`.
- **Milestone 6:** 6.31 closed. 6.32–6.37 remain open.
- **Decision it records:**
  [ADR-0146](../../../adr/0146-memoise-the-stemmer-bounded-against-a-measured-vocabulary.md).

## The easy 90 % and the one question that wasn't

`stem()` is a pure function of a lowercased word: no state, no configuration, no corpus
dependence. Memoising it is a decorator, and roadmap 6.19 had already done the
measurement — 620 293 word occurrences over 10 339 distinct words, 98.3 % of the calls
asking for an answer already computed, 23.6x faster memoised.

The item itself named the one part that is not a decorator: *"an unbounded `lru_cache`
... is fine for a build ... and is a slow leak in a long-lived **server**."* The MCP
server is exactly that — a stdio process that runs for as long as a client keeps it
open, calling `stem()` on every query's terms. An unbounded cache there grows with
however many distinct words a caller has ever sent, not with the corpus.

## Sizing the bound against measurement, not a round number

The item's own instruction was to size the bound against *"the measurement of a
realistic vocabulary,"* so before picking a number I measured one. This project's own
three built corpora — the ones `verify.py`'s `retrieval` mode builds and gates —
index at most 11 734 distinct FTS terms (`ours`, 233 documents; the two `uv-docs`
corpora index under 5 000 each). I set the bound at 131 072, about 11x that, and
measured what it costs rather than guessing: 100 000 short-string cache entries hold
about 9 MB on this machine, which is nothing beside the embedding model the process
already loads when hybrid retrieval is configured.

The bound doesn't change correctness at any size. A corpus past it pays an ordinary
cache miss and recomputes — the algorithm underneath doesn't move, only the memo does.

## Two measurements, and a noise floor borrowed from yesterday

A unit benchmark re-took the 6.19 comparison on `AGENTS.md`'s own prose rather than a
synthetic list: cold 25.0 ms, warm 1.5 ms, 16.7x. Smaller and less repetitive than the
corpus-scale figure, same shape.

The end-to-end number needed the alternating-arms discipline ADR-0145 established
yesterday, reused rather than reinvented: three rounds, before and after interleaved on
an idle machine. Cold build at 250 documents moved 22.50 → 19.67 s, −12.6 %. The same
runs gave a noise floor on paths this change cannot touch — the incremental rebuild
floor at +4.3 %, warm search at +9.9 % — which is what makes −12.6 % a signal rather
than a guess: it's larger than either.

## The tests that prove the worry rather than argue it

Two tests go after the server concern directly instead of trusting the docstring:

- a cache hit and a cold call (`stem.cache_clear()` between them) must return the same
  answer — provable because the function is pure, and worth proving because a cache is
  exactly the kind of thing that quietly stops being pure if a later edit gives it
  state;
- pushing `maxsize + 1000` never-seen words through the cache must leave `currsize` at
  or under the bound. That's the "slow leak" scenario, run to its conclusion rather
  than reasoned about.

## A second defect, found because this change had to verify itself

Deriving the verification mode for this PR's own diff — `stemming.py` (a tuning path)
beside the new `tests/bench/test_stemming_bench.py` (ADR-0145's `BENCH_PREFIXES`, a
full-only path) — came back `retrieval`. It should have been `full`; the benchmark this
record cites would have been silently skipped.

`derive()` was a sequence of early-return loops, in mode order `retrieval` before
`full`. A diff touching a tuning path returned `retrieval` and stopped before ever
reaching the rule that would have widened it. That's been true since `CI_PREFIXES` was
added at roadmap 4.31 — nothing had ever tested the combination, because nothing had
needed to touch a tuning path and a full-only path in the same PR until yesterday's
`BENCH_PREFIXES` made it an ordinary shape rather than a contrived one.

Fixed by classifying each path against the rule table on its own and taking the
genuinely widest mode, ties broken by the table's declared order — which is what
`test_a_tuning_path_outranks_an_eval_path` had already required and the loop-order
accident had been standing in for by coincidence. Three new tests pin the exact
combination, in both list orders, so the next full-only rule someone adds finds out
immediately rather than by watching its own CI job go missing.

## What's left

6.32 is next: the symbol stage decodes every use and hashes every edge twice, on every
rebuild — the same discipline (decode once, hash once), on the pass 6.20 found once the
incremental floor came off the filesystem.
