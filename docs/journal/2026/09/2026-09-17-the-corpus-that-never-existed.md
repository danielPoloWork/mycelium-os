# 2026-09-17 — the corpus that never existed (roadmap 6.4)

- **Session scope:** roadmap 6.4 — the public benchmark report with run manifests, and the
  agent-task gate quantified.
- **PR:** `feat/reference-profile-benchmark`, following #154 (6.3, merged as `cf9e197`).
- **Milestone 6:** 6.4 closed. Six items filed from it: 6.18–6.23.
- **Decision it records:** [ADR-0120](../../../adr/0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md).

## The item was two halves and both rested on a measurement nobody had taken

Three performance budgets are stated in three documents, and all three name conditions —
1 000 documents, a single-document edit, **10⁵ chunks**. Nothing had ever been measured above
1 420 chunks, which is this repository's own corpus. *"Search p95 < 150 ms on the 10⁵-chunk
reference corpus"* has been a **closed Phase-1 exit gate since v0.3.0**, and the corpus it
names had never been built.

Nothing was hidden: gate G5 enforces the query budget on whatever corpus ran and says in its
own output that this is *"a floor, not the measurement spec 04 §1 asks for"*. The honest
description is that a gate measured seventy times below its conditions cannot fail, and six
milestones went by.

## What the measurement said

The headline is not that a budget is missed but **where the cost is**. End-to-end
`mycelium_search` misses its 150 ms p95 on *every* corpus size, including a 60-document one,
and the miss is a **constant ~250 ms that is not retrieval**: `handle_search` calls
`load_config` per call, which calls `installed_ids()`, which calls
`importlib.metadata.entry_points()` — a re-read of every installed distribution's metadata,
uncached, costing more than the entire budget before a chunk is ranked.

Gate G5 could never have seen it. It times the retriever *inside the harness*, not the tool
the NFR names.

And at 10⁵ chunks — the condition NFR-2 actually names — the warm query alone is **1 816 ms
p95**, twelve times the whole budget. So removing every millisecond of the constant would
still leave the requirement missed by an order of magnitude.

The other two budgets are missed at their own stated conditions: 1 000 documents compile in
193.5 s against 60 s, and the incremental rebuild crosses 2 s p95 at around **250 documents**.
The incremental mechanism is documented as a deliberate choice rather than hidden — `_plan`
reads and digests every file on every build, and its docstring calls that *"the incremental
floor"* — so the finding is that the floor is above the budget, which is a decision to take
(6.20) rather than a bug to fix.

Trying to build the reference corpus found the sharpest thing here: **the compiler's write
path is quadratic** (BUG-0031). `put_chunks` deletes from `chunks_fts` by an `UNINDEXED`
column, SQLite answers that with a full scan of the index, and it does so once per chunk — so
a thousand chunks into an empty store take 2.7 s and the thousand after nine thousand others
take 68 s. That is ~40 % of the 1 000-document build, and it is why 10⁵ chunks is nine hours
and why the reference corpus had never been built by anyone.

## The instrument was broken in two places, and both had the same shape

**Four of the twenty-two agent tasks required anchors the corpus no longer held.** Not because
anyone edited those documents: the packed chunker (ADR-0047) had merged ADR-0009's three
`Decision` chunks into one and shifted every ordinal after it. Those tasks had been scoring as
retrieval *misses* for both strategies ever since, so the suite's rate had a silent ceiling of
18/22 and had quietly become *retrieval quality plus anchor rot*, with no way to separate them.

**The incumbent reads one document where its model says five.** `MAX_GREP_FILES` is 5, but the
first matching file is taken whole regardless of budget — and `ROADMAP.md` is now ~81 000
tokens, 18 % of the corpus and 45× the median document. grep read exactly one file on 22 of 22
tasks, and that file supplied **93 % of its entire measured cost**. So the 18× context
ratio is mostly a fact about our roadmap file, and grep's 4.5 % is *"its one file was the wrong
file"* rather than *"grep is bad at retrieval"*.

Both defects have the same shape as each other and as the thing 6.4 was sent to find: a
measurement that stopped meaning what it said while the corpus moved underneath it, and
nothing checked. The first is fixed and gated here; the second is filed (6.22) because
answering it means deciding what a grep loop *does* with a file bigger than its budget, and
that must be argued on what an agent does — D-010 cuts both ways.

## Two gates, not one

"Quantified gate at 1.0" was read as one thing and is two. Whether the comparison still
*measures retrieval* is decidable today and was false today, so `mycelium eval --tasks --gate`
now fails on an unresolved anchor and CI runs it. Whether Mycelium *beats grep* is scored
qualitatively until 1.0 by spec 04 §7.4, so its rule and margin are quantified in the report
and it arms at the v1.0.0 tag — the same answer ADR-0114 gave the compatibility promise, for
the same reason.

## Two things that went wrong in the session

**I built the corpus with identity pinning on.** `build(Path("."))` defaults to
`pin_identity=True`, which wrote a `mycelium_id` block into ~190 tracked documents *and* into
the maintainer's untracked `docs/analysis/` and `fable-review.md`. `git status` went from 4
entries to 206. Stripping the block was the easy half; the trap is that rewriting the files
through `read_text`/`write_text` folds CRLF to LF, so 183 files stayed "modified" with correct
content and wrong endings. `git diff --name-only` normalises endings and is therefore the
discriminator: it listed the 17 files whose content had really changed, and `git checkout --`
on the difference restored the rest. This repository builds with `--no-pin` everywhere for
exactly this reason.

**The first agent-task numbers included the maintainer's untracked analysis** — 11 623 tokens
of it, in the corpus. Set aside, rebuilt, re-measured; the numbers were unchanged, but a
baseline that describes a corpus which will not exist on `main` is the one thing a baseline
must not be.

## Lesson

A budget with stated conditions and no measurement at those conditions is not a budget, it is
a sentence — and the gate that appears to enforce it will pass forever. The tell is available
without running anything: **compare the conditions the claim names with the corpus the gate
actually ran on.** G5 printed that comparison in its own output for six milestones and nobody
read it as the admission it was.
