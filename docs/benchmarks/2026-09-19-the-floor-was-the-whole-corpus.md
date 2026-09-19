# Benchmark Report: the floor was the whole corpus — the incremental rebuild before and after roadmap 6.20

- **Date:** 2026-09-19
- **Version / commit:** v0.5.0 @ `4ecf8a6` (the baseline), and the same tree with roadmap 6.20's change. The after manifest's `commit` field also reads `4ecf8a6`: the tool records `HEAD`, and the change was measured before it was committed, so the tree that manifest describes is that commit plus this pull request's diff
- **Environment:** the machine of record, as in the [reference-profile report](2026-09-17-reference-profile.md), **contended throughout** — see [Method](#method). Manifests: [`manifests/2026-09-19-the-floor-was-the-whole-corpus-before.json`](manifests/2026-09-19-the-floor-was-the-whole-corpus-before.json) (before) and [`manifests/2026-09-19-the-floor-was-the-whole-corpus.json`](manifests/2026-09-19-the-floor-was-the-whole-corpus.json) (after)
- **Command:** `python tools/benchmark_reference_profile.py --out <dir> --scales 250,1000 --no-reference` before; `--scales 250,1000,2500,5000 --no-reference` after
- **Roadmap:** 6.20 · **Decision:** [ADR-0133](../adr/0133-raise-the-floor-off-the-contents-and-state-the-corpus-the-budget-holds-for.md)

## Scenario

NFR-3 and spec 06's Phase-1 exit gate say a single-document edit rebuilds in **< 2 s p95**,
on no stated corpus. The [reference profile](2026-09-17-reference-profile.md) measured it at
**2 206 ms p95 at 250 documents and 6 307 ms at 998** — linear in the corpus, not in the edit
— and roadmap 6.20 named the mechanism: `_plan` read and digested every discovered file on
every build, by design, and its docstring called that read *"the incremental floor"*. The item
offered two answers, raise the floor off the filesystem or give the budget the corpus size it
holds for, and asked for the measurement to be taken to the decision.

This report is that measurement: the floor pass by pass before anything was changed, the same
passes after, and the curve of the rebuild against corpus size on both sides.

## Method

Same generator, same seed, same machine as the 2026-09-17 report. Three instruments:

- **The reference-profile tool**, extended here to time a *no-op* rebuild beside the
  single-document edit and to carry the compiler's own per-stage timings into the manifest
  for both. A no-op rebuild is the floor itself; the edit is the floor plus one document's
  chain, and measuring them together says which of the two the budget is spent on.
- **A pass-by-pass script** that times each whole-corpus pass a rebuild makes — discovery,
  `stat`, read, digest, the restorability probes, graph resolution with and without its
  filesystem probe, table rewrites, the restore-state encoding — in isolation on the built
  1 000-document corpus. Its numbers are in the decision record; the manifests carry the
  tool's.
- **A profile of one no-op rebuild after the change**, read the way ADR-0132 says a profile
  must be read: as a hint about where to point a measurement, never as a measurement.

**The machine was not idle, and every absolute figure here is high because of it.** A
`find / -iname …` left running by an earlier agent session was walking the whole disk
throughout, at a steady 17 % of total CPU; the permission model did not let this session stop
it. Its signature is in the baseline itself: the 1 000-document cold build took **114.5 s**
where the 2026-09-19 quadratic report measured 91.7 s on an idle machine, and the baseline
rebuild p95 sits far above its p50. The 2026-09-17 report's own rule — *a contended benchmark
is not a slow benchmark, it is a wrong one* — applies, so this report is read as follows: the
before and after were taken under the same contention, the **shape** (which passes vanished,
which grow with the corpus, where the budget is crossed) is what travels, and the absolute
values are upper bounds. The reproduce section is how to take the idle numbers; the decision
does not depend on them.

## Results

### The floor, pass by pass, before

One no-op rebuild of 1 000 documents (4 891 chunks), the unmodified compiler:

| pass | cost | what it was doing |
|---|---:|---|
| `plan` — read and digest every file | **2 625 ms** | 1.5 ms a read on this machine, 0.1 ms a digest |
| `graph` — resolve every link, probe the filesystem for unresolved ones | 687 ms | **3 922 `exists()` calls** for 1 963 unresolved links over 1 516 distinct paths; 114 ms without the probes |
| `store` — of which restorability | 608 ms, of which **376 ms** | **two `exists()` per live document**; the whole `doc_state` table read in 69 ms |
| `discover` | 485 ms | `rglob("*.md")` over ten directories |
| `symbols` | 250 ms | resolution over every document's state, for 33 symbols |
| restore-state encoding (inside `store`) | 213 ms | a Python walk over 2.4 MB of canonical JSON |
| `compile` | 77 ms | deciding, for 1 000 documents, that nothing was dirty |
| **total** | **4 890 ms p50** | |

The read the item named was 54 % of the floor. Three more filesystem passes it did not name —
restorability's probes, the link probes, discovery — were another 32 %. The edited document's
own chain, when there was one, cost about 190 ms of a 5 563 ms rebuild.

### The floor, pass by pass, after

The same corpus and the same contended machine, with 6.20's change:

| pass | before | after | what changed |
|---|---:|---:|---|
| `plan` — `stat`, the `doc_state` rows, the memo | 2 625 ms | **343 ms** | one `stat` a document; **0 of 1 000 read**. `_plan` alone is 215 ms, the rows 84 ms; a `rescan` of the same corpus reads everything again in 2 022 ms |
| `graph` | 687 ms | **264 ms** | one directory listing per candidate directory instead of 3 922 `exists()` calls; what remains is resolution itself |
| `store` — of which restorability | 608 ms, of which 376 | **188 ms, of which 74** | one `scandir` per cache shard, 256 listings for 3 018 blobs |
| `discover` | 485 ms | **93 ms** | a `scandir` walk that never enters an excluded directory, carrying each document's corpus path so nothing re-derives it |
| restore-state encoding (inside `store`) | 213 ms | **82 ms** | the C encoder, byte-identical to the canonical form |
| `symbols` | 250 ms | 235 ms | untouched — see below |
| **compiler's own timer, no-op** | **4 890 ms** | **1 358 ms** | |
| **no-op rebuild end to end, p50** | **5 110 ms** | **1 565 ms** | the ~200 ms outside the timer is publication: lock, journal, manifest, commit, `CURRENT` swap — roadmap 6.30's ceremony |
| **one-edit rebuild end to end, p50 (worst of five)** | **5 776 ms** (9 364) | **1 719 ms** (1 811) | the edited document's chain is ~125 ms of the difference |

The floor fell by 3.5 s of which 2.4 s is the read that was named and 1.1 s is the three
filesystem passes that were not — and the shape of what remains is different in kind: nothing
left in the table opens a document.

**A file edited within two seconds of a build is read once more on the build after it.** The
first rebuild after the corpus was generated read 175 documents — the last two seconds' worth
of the generator's writes — and none after that; in the edit loop each rebuild read the edited
document and the one or two edited just before it. That is the racy window doing exactly what
ADR-0133 asks of it, and its cost is one read per recently changed file.

### The curve

Before, the unmodified compiler at `4ecf8a6`; after, the same tree with 6.20's change. p95
over 20 rebuilds at 250 and 1 000 documents, 8 at 2 500 and 5 at 5 000, as the tool records.

| Documents | Chunks | No-op p95, before | Edit p95, before | No-op p95, after | **Edit p95, after** | Floor per document, after (no-op p50 ÷ documents) |
|---:|---:|---:|---:|---:|---:|---:|
| 250 | 1 262 / 1 247 | 1 421 ms | 1 618 ms | 541 ms | **717 ms** ✓ | 1.98 ms |
| 1 000 | 4 891 / 4 955 | 8 740 ms | 8 755 ms | 1 564 ms | **1 754 ms** ✓ | 1.42 ms |
| 2 500 | — / 12 346 | — | — | 3 629 ms | **3 805 ms** ✗ | 1.32 ms |
| 5 000 | — / 24 867 | — | — | 6 533 ms | **6 961 ms** ✗ | 1.21 ms |

(The two chunk counts are before / after: the generator's seed advances per scale, so the
after run composed slightly different documents from the same pool; the 2026-09-17 report
measured the unmodified compiler at 998 documents at 6 307 ms p95 idle, against 8 755 here
contended.)

**The budget is met at the size it now names, and the report says where it stops being met.**
The edit rebuild is inside 2 s at 250 and at 1 000 documents and outside it from 2 500. Between
1 000 and 5 000 the curve is a straight line of about **1.35 ms a document** over a constant of
roughly 200 ms — publication: the lock, two journal lines, the manifest write, the commit, the
`CURRENT` swap — so the 2 s line is crossed again near **1 200 documents** on this contended
machine. The unmodified compiler crossed it near 250 with a slope of 5.5 ms a document idle
(the 2026-09-17 report) and 9.5 ms here: the floor fell four to seven times and stayed linear.
The per-document floor *falls* with corpus size because the constant amortises; what it falls
towards is the sum of the passes in the next section.

### What remains, and where the time goes now

A no-op rebuild of the same corpus under cProfile — 2.71 s profiled against 1.36 s timed, so
the shares are a hint about where to point a measurement and nothing more (ADR-0132). Read that
way, four things account for most of what is left, and none of them is the filesystem:

| what | evidence | stage |
|---|---|---|
| **Edge identities, hashed twice.** ~3 500 `references` edges from the symbol table, each keyed by a canonical-JSON digest in `symbol_edges` and digested again by `edge_id` when `put_edges` writes it | 12 325 `canonical_json` calls, 72 824 recursive steps of its Python walk | `symbols`, `store` |
| **Symbol uses, decoded from every state.** The generated prose carries uv's code fences, so a thousand documents hold ~20 000 uses, rebuilt into records on every resolution | 20 153 decoder steps | `symbols` |
| **One `stat` a document** — the floor that was chosen | 1 019 calls, ~130 ms timed in isolation | `plan` |
| **Link resolution itself**, 1 963 unresolved links resolved against the index and probed against 374 directory listings | `_resolve_target` and `links_to_a_non_document`, ~1 960 calls each | `graph` |

The first two are content-proportional Python work with two plain economies — decode once, hash
once — and are filed as roadmap 6.32 rather than fixed here: this report was taken after 6.20's
change, and nothing the profile found is touched in the same pull request (the 6.19
discipline). The third is the floor by construction. The fourth is mostly a property of the
generated corpus, whose links are dangling by the thousand where a real vault's resolve.

## Interpretation

**1. The named floor was half the floor.** The item's mechanism — read and digest every file —
was 54 % of a no-op rebuild. Restorability's two probes per document, the graph's probes for
unresolved links, and discovery's `rglob` were most of the rest, and none of them had been
named: each was individually cheap enough that nobody measured it, and together they were as
much of the budget as the read. A floor is not one line.

**2. The read moved off the contents, not off the digest.** `doc_state` now remembers the size
and mtime a file had when its digest was computed, and a file whose stat still matches keeps
that digest without being read. Nothing downstream — cache keys, artifacts, the manifest, gate
G6 — sees anything but the digest, as before. What the memo cannot see is a same-size edit that
also restores the old mtime; the racy half of that case is closed by a two-second window on the
previous build's start (Git's *racily clean* rule), and the deliberate half by `mycelium build
--rescan` and by `mycelium doctor`, which re-digests the corpus on demand and names the drift.
ADR-0133 has the argument; `tests/test_build_floor.py` pins the blind spot so it is a decision
rather than a surprise.

**3. NFR-3 has its conditions now.** At 1 000 documents the single-document edit rebuilds in
**1 754 ms p95**, inside the budget on a contended machine, where the unmodified compiler read
6 307 ms idle and 8 755 ms contended; at 250 it is 717 ms. The budget is restated as *< 2 s p95
on the 1 000-document reference corpus, local reference hardware* — the same corpus spec 01
§8's cold-build budget names — and the curve above that size is published rather than
promised. A budget with no corpus size is met or missed by machine, not by design.

**4. What remains is O(corpus) by construction, and the report says where it crosses.** One
`stat` a document, one `doc_state` row a document, one entry a document in the restore state,
and a graph and a symbol table resolved whole because resolution is global (ADR-0018,
ADR-0073). At 5 000 documents the no-op floor's 5.5 s of compiler time divides as `plan` 1.4 s
(0.28 ms a document: the `stat` and the row), `graph` 1.1 s (0.22 ms: resolving the generated
corpus's dangling links), `symbols` 0.95 s (0.19 ms: roadmap 6.32's residue), `store` 0.8 s
(0.16 ms: the restore state and the cache listing) and `discover` 0.35 s (0.07 ms) — about
1.2 ms a document, evenly spread, none of it a content read. The 2 s edit budget is crossed
again near 1 200 documents here, which is the number a reader with a larger corpus needs and
the number the restated NFR-3 exists to make visible rather than hide.

**5. The machine, once more.** Every figure here was taken with another process walking the
disk. The ratios — read against stat, probe against listing, before against after — are
robust to that; the absolute values are not, and the idle machine's numbers are one command
away (below).

## What these numbers do not say

- **They are contended.** See Method. An idle run will read lower on every line, and the
  2026-09-19 quadratic report suggests by roughly a quarter on this machine.
- **The generated corpus's links are a pathology, not a vault's.** Its documents are recomposed
  from harvested prose whose relative links point at pages that do not exist in the generated
  tree — 1 963 unresolved links in 1 000 documents, which is what made the filesystem probe
  cost 570 ms. A real vault resolves most of its links and would have paid less for the probe
  before and gains less from the listing after. The generator is unchanged, so the corpus stays
  comparable with the earlier reports.
- **One machine, and a slow one at opening files.** 1.5 ms a read is a real-time scanner in the
  open path; a machine without one would have found the read a smaller share of the floor and
  the remaining O(corpus) passes a larger one.
- **The blind spot is not a performance fact.** A same-size edit under a restored mtime is not
  seen until `--rescan`; how often that happens in practice is a question about editors and
  tools, not about this measurement, and the report makes no claim about it.
- **The query figures at 2 500 and 5 000 documents are not this report's subject.** They are
  recorded because the tool records them; `mycelium_search` leaving its 150 ms budget as the
  corpus grows is the scaling the 2026-09-17 and 2026-09-18 reports already describe.

## Reproduce

From a clean checkout, with `uv sync --all-extras --dev`, on an **idle** machine:

```bash
# After (this tree): the curve, ~40 minutes on the machine of record.
python tools/benchmark_reference_profile.py \
    --out <scratch-dir> --scales 250,1000,2500,5000 --no-reference \
    --manifest docs/benchmarks/manifests/2026-09-19-the-floor-was-the-whole-corpus.json

# Before: check out 4ecf8a6, keep this tree's tools/benchmark_reference_profile.py for the
# no-op measurement, and run the same command with --scales 250,1000.
```

The pass-by-pass figures come from a script kept beside the decision record's references; the
properties they rest on are tests — an unchanged document is not read, restorability asks the
cache once, an unresolved link's directory is listed once — in `tests/test_build_floor.py`.
