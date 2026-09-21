# 2026-09-21 — the fsync was not the expensive half (roadmap 6.30)

- **Session scope:** roadmap 6.30 — three quarters of a cold build is the ceremony around
  writing three small files per document; decide what durability a derived store owes.
- **PR:** #180 (`perf/write-the-blob-once`). Follows #179, merged as `0c8a875`.
- **Milestone 6:** 6.30 closed. 6.31–6.37 remain open.
- **Decision it records:**
  [ADR-0145](../../../adr/0145-let-the-digest-be-the-durability-and-stop-paying-for-a-second-name.md).

## The item asked an fsync question and the answer was about the rename

6.19 put ~79 s of a 91.7 s build into 2 995 `cas_put` calls and framed 6.30 as *what
durability does a derived store owe?* — which is a question about the fsync. Decomposed
into nested arms, each adding exactly one operation:

| arm | 12 KiB | delta |
|---|---:|---:|
| plain write | 7.60 ms | |
| write + fsync | 9.61 ms | **+2.01** |
| tmp + rename | 14.27 ms | **+6.68** |
| tmp + fsync + rename (shipped) | 16.59 ms | +9.00 |

The fsync is 2 ms. **The second name is 6.7 ms.** The question worth asking was not what
durability costs but what a *rename* costs, and nobody had asked it because the aggregate
number could not tell them apart.

The other reading matters as much: the cost is **flat across 4, 12 and 64 KiB**. It is
charged per file operation, not per byte — a filter driver — so the remedy is fewer
operations and never smaller writes.

## The ceremony was insuring a risk the digest had already retired

A blob's name is the digest of its bytes, and `cas_get` re-hashes everything it reads. So a
crash mid-write leaves a file that fails that test, is discarded, and the stage recomputes —
which is exactly what would have happened had the blob never existed. The tmp-fsync-rename
prevented a name appearing before its content was durable, and here that failure is already
indistinguishable from a cache miss.

`cas_put` writes directly now. `write_bytes` joins `atomic_write_bytes` in `layout`, so the
choice between them is a durability decision somebody made rather than whichever helper was
nearest. Snapshot publication, the `CURRENT` pointer, tier-1 custody and quarantine keep the
ceremony: none of them is recomputable, and for those the guarantee is real.

## Two things I had to redo, and both are method

**I benchmarked while type-checking.** The first before/after pair reported a −44 % cold
build *and* an 88 % change in warm search, which this change cannot touch — the tell that
the machine, not the code, had moved. Discarded and re-run with nothing else going.

**Sequential arms were still not enough.** This machine drifts over minutes, so the arms are
now alternated — before, after, before, after — and read as medians. That gives:

| | before | after | |
|---|---:|---:|---|
| cold build, 250 documents | 29.35 s | 21.96 s | **−25.2 %** |
| cold build, 1 000 documents | 132.68 s | 94.13 s | **−29.1 %** |

Ranges do not overlap at either scale, against a +7.8 % noise floor measured on warm search
in the same runs. Publishing that floor beside the result is what makes the result readable:
on this machine a single-digit percentage is nothing and 29 % is real.

**The build gains more than the microbenchmark predicts** — 38.5 s against ~27 s. An idle
one-write-at-a-time figure understates what a second name costs under three thousand
back-to-back writes. The end-to-end number is the claim; the decomposition explains its
shape.

## The precondition I could not meet, and what it uncovered

The item said: *measure on a machine without a scanner before choosing.* There is none here.
The scanner is **Trend Micro Apex One** — not Defender, whose real-time protection is off
*because* Apex One replaced it — and it is centrally managed, so disabling it is neither
mine to do nor the maintainer's convenience.

The only no-scanner machine available is a CI runner, and the benchmark job runs at `full`
only. A benchmark file counted as `tests/` and therefore derived `code`: **adding or editing
a benchmark ran everything except the benchmarks.** A broken one landed green and `main`
found out on the next push, and AGENTS.md §10's *"performance claims backed by a reproducible
benchmark"* was unverifiable at exactly the moment a claim is made — which is the position
this item was in. `tests/bench/` derives `full` now, by ADR-0055's own rule: the gate that
would judge a change is the one it changes.

So the decision was taken on the property that does not depend on the scanner — writing
directly removes work on any filesystem — while *batching the three artifacts into one
blob*, which would have been the bigger local win, was refused for being fitted to this
laptop. That was the item's warning, and it is the one candidate it rules out.

## What is left

94 s against a 60 s budget. 6.31 (the stemmer) and 6.32 (the symbol stage) are 6.19's other
two children, and the manifest records the calibration so a reader on faster hardware can
scale rather than believe.
