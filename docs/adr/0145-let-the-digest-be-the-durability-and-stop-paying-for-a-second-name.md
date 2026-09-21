# ADR-0145: Let the digest be the durability, and stop paying for a second name

- **Status:** Accepted
- **Deciders:** tech-lead (EADOS delivery agent) with the maintainer, per RFC-0001 /
  spec 01 §8, spec 02 §§3-4
- **Date:** 2026-09-21
- **Related:**
  [ADR-0132](0132-address-the-lexical-index-by-rowid-and-profile-what-is-left.md)
  (roadmap 6.19, which measured the cost and named this item),
  [ADR-0015](0015-adopt-content-addressed-incremental-builds.md) (the derived
  store, whose recovery story is `mycelium build`),
  [ADR-0033](0033-keep-the-original-and-bound-the-hostile.md) (tier-1 custody,
  which keeps the ceremony), [ADR-0016](0016-make-snapshots-restorable.md)
  (restorability, which `cas_inventory` answers),
  [ADR-0055](0055-run-the-gates-the-change-implicates.md) (the mode ladder this widens);
  D-005 (the derived world is disposable), D-016; spec 01 §8 (the cold-build budget);
  roadmap 6.19, 6.30

## Context

Roadmap 6.19 profiled a 1 000-document cold build and found **~79 s of 91.7 s** in
**2 995 `cas_put` calls** — a parse, a chunks and a document artifact per document, at
26.4 ms each. It offered an attribution: a real-time scanner in the write path costs
12.6 ms for a plain 4 KiB write, and *"the atomic ceremony doubles it — `atomic_write_bytes`
creates a temp file, fsyncs it, and renames, so the scanner charges for two names instead
of one."*

Roadmap 6.30 exists to decide what to do about it, and the item set one condition before
choosing: **measure on a machine without a scanner first**, because the ratio that makes
this look decisive is this machine's.

### The attribution was half right, and the half it got wrong is the one that decides

`tools/measure_cas_write.py` decomposes a blob write into nested arms, each adding exactly
one operation, interleaved so a slow minute cannot land on one of them. On the machine of
record, medians over 60 samples per arm:

| arm | 4 KiB | 12 KiB | 64 KiB | per 2 995 blobs (12 KiB) |
|---|---:|---:|---:|---:|
| plain write | 7.10 ms | 7.60 ms | 8.55 ms | 22.8 s |
| write + fsync | +1.87 | **+2.01** | +1.41 | 28.8 s |
| tmp + rename | +7.45 | **+6.68** | +6.64 | 42.7 s |
| tmp + fsync + rename (ships) | +8.99 | **+9.00** | +8.68 | 49.7 s |

Two readings, and both matter:

1. **The cost is flat across sizes.** A 64 KiB write costs within 20 % of a 4 KiB one, so
   it is charged **per file operation**, not per byte. That is a filter driver in the path,
   and it says the remedy is *fewer operations* rather than smaller ones.
2. **The fsync is not the expensive half.** 6.19 framed the question as *what durability
   does a derived store owe* — an fsync question — and the fsync costs **~2 ms**. The
   **second name costs ~6.7 ms**, three times as much. The ritual is **2.1x** a plain
   write, and nearly all of that is the rename.

An aside worth recording because it corrects the earlier note: the scanner is **Trend Micro
Apex One**, not Windows Defender, whose real-time protection is switched off on this machine
precisely because Apex One replaced it. Apex One is centrally managed, so it cannot be
disabled here — which is why the no-scanner reading is a CI matter and not a local one (see
*Consequences*).

### What the ceremony was protecting

`atomic_write_bytes` exists so that a name never appears before its content is durable.
For a snapshot, the `CURRENT` pointer, an acquired original or a quarantine record, that is
a real guarantee: those are not recomputable, and a half-written one is a loss.

For the sweepable CAS it is not, and the reason is in the module's own design. **A blob's
name is the digest of its bytes.** A crash mid-write leaves a short file under the digest of
the whole artifact, and `cas_get` re-hashes every blob it reads — so the torn blob is
discarded and the stage recomputes, which is *exactly* what would have happened had the
blob never existed. The ceremony was buying protection against a failure that content
addressing had already made indistinguishable from a cache miss (D-005, ADR-0015).

## Decision

**`cas_put` writes straight to the final name — no temp file, no fsync, no rename — and
the re-hash on read is the integrity story.** `mycelium.layout` gains `write_bytes` beside
`atomic_write_bytes`, so the choice between them is a documented durability decision rather
than an accident of which helper was imported. Snapshot publication, the `CURRENT` pointer,
tier-1 custody and quarantine are unchanged.

Of the item's four candidates, this is the only one whose benefit does not depend on the
scanner. *Fsync once per build* saves the 2 ms term, which is the small one. *Batching the
three artifacts into one blob* would cut operations by two thirds — a large win here and
nearly nothing on a machine where a file operation is 30 µs — so it would be a design fitted
to this laptop, which is what the item warned against. Writing directly removes work on any
filesystem.

### What it measures, end to end

Both arms alternated so drift cannot land on one of them, machine otherwise idle, medians of
three runs at 250 documents and two at 1 000:

| | before | after | |
|---|---:|---:|---|
| cold build, 250 documents | 29.35 s | **21.96 s** | **−25.2 %** |
| cold build, 1 000 documents | 132.68 s | **94.13 s** | **−29.1 %** |

The ranges do not overlap at either scale. For calibration of what *does* count as noise
here: warm in-process search, which this change cannot touch, moved **+7.8 %** across the
same runs — so a single-digit reading on this machine means nothing, and a 29 % one does.

**The build saves more than the microbenchmark predicts.** 2 995 blobs at the measured
9.0 ms delta is ~27 s; the 1 000-document build gained **38.5 s**. The microbenchmark is
taken on an idle machine one write at a time, and a build issues three thousand of them
back to back — so the idle figure *understates* what a second name costs under a build's
write pressure. The honest form of the claim is the end-to-end number, with the
decomposition explaining its shape.

**It does not reach the budget.** Spec 01 §8 asks for a 1 000-document cold build under
**60 s** and this machine now does it in 94 s. 6.19's remaining findings — 6.31's stemmer,
6.32's symbol stage — are what is left, and the manifest records the calibration so a reader
can scale.

## Consequences

**One behaviour changes for a reader, and it is bounded.** A concurrent reader can now
observe a blob mid-write, where before the final name only ever appeared complete. It
re-hashes, does not match, and reports a miss: a recompute, never bad bytes. Two related
adjustments follow, both narrow:

- `cas_get`'s delete-on-mismatch became `_discard`, which **tolerates failure**. It can now
  race a writer still filling the file, and on Windows the delete then fails with a sharing
  violation — the right outcome there is the miss the function is already returning, not an
  exception in a reader.
- `cas_inventory` lists an in-flight blob as present, because its name is already final.
  The imprecision is bounded by what that set answers: it reports *restorability* while
  `cas_get` reports *readability*, so an in-flight blob counts as present, then reads as a
  miss, and the stage recomputes it.

**The `.tmp` filter in `cas_inventory` stays** although this module no longer writes one:
an older cache may hold debris, and a filter that costs nothing is cheaper than a migration.

**A benchmark now derives `full`, and that is this ADR's second finding.** The item asked
for a measurement on a machine without a scanner. There is none here — Apex One is managed —
so the only one available is a CI runner, and the benchmark job runs at `full` only. A
benchmark file counted as `tests/`, which derives `code`: **adding or editing a benchmark ran
everything except the benchmarks**, so the PR that introduced a broken or meaningless one was
green and `main` discovered it on the next push. That also made AGENTS.md §10's *"performance
claims backed by a reproducible benchmark"* unverifiable at the moment a claim is made, which
is exactly the position this item was in. `tests/bench/` and `contrib/chats/tests/bench/` now
derive `full`, by the same rule that makes a change to the judged sets derive `retrieval`:
**the gate that would judge a change is the one it changes** (ADR-0055's principle, applied to
a rung that had been missing it).

**The no-scanner reading arrived, and it is the opposite of the worry.**
`tests/bench/test_cas_bench.py` ran on this change's own CI run (`ubuntu-24.04`, no filter
driver), medians:

| | Windows, Apex One | Linux, CI runner | |
|---|---:|---:|---|
| plain write | 12.36 ms | **59.3 µs** | 208x cheaper |
| `cas_put` | 14.40 ms | **92.4 µs** | |
| tmp + fsync + rename | 20.62 ms | **708.8 µs** | |
| **ceremony / plain write** | **1.67x** | **12.0x** | |

The absolute cost collapses by two orders of magnitude and the **ratio gets seven times
worse**. The two machines pay for different things — Windows pays a filter driver ~7 ms for
a second name, Linux pays a real disk flush ~650 µs for the fsync — and on Linux that flush
is *eleven times* the write it protects. So the item's caution (*the ratio that makes this
look decisive is this machine's*) resolves in the direction that strengthens the decision
rather than weakening it: dropping the ceremony is worth **more**, relatively, on the
machine without the scanner.

It also says the earlier worry was aimed at the wrong candidate. What is local to this
laptop is the *attribution* — rename-dominated here, fsync-dominated there — which is
precisely why *batching three artifacts into one blob* was refused: that one pays only where
per-operation overhead dominates, and Linux says it would have bought almost nothing.

**What is not claimed.** Nothing here makes the cold build portable, and the 60 s budget
conversation belongs to 6.19's other two children. Note also that the Linux `atomic_write`
row has a 178 ms maximum against a 709 µs median — fsync latency on a shared runner is
spiky, which is one more reason the shipped path no longer waits on it.
