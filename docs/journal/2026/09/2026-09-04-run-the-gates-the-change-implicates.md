# 2026-09-04 — two refusals and a 124-second install (roadmap 4.31)

- **Session scope:** roadmap 4.31 — runner, matrix, declared mode, and the trust boundary a
  scoped verification opens.
- **PR:** #78 (`ci/declared-mode`). Follows #76 (4.27), merged as `e444785`.
- **Milestone 4:** 4.31 done; 4.25, 4.26, 4.28, 4.29 open, and 4.32 filed here.

## The obvious fix was wrong, and measuring it was the cheapest hour of the item

The local suite takes 721 s on this machine. Twenty cores sat idle through all of it, so
`pytest-xdist` was the first thing tried. Twice:

| configuration | wall | against serial |
|---|---:|---:|
| serial (shipped) | 721 s | — |
| `-n auto --dist loadfile` | 562 s | −22 % |
| `-n auto --dist load` | **1389 s** | **+93 %** |

`loadfile` disappoints because the cost is concentrated in a handful of expensive files: one
worker holds the critical path and nineteen finish early. `load` is *worse than serial*
because per-test distribution destroys the fixture reuse this suite is built on — every
worker rebuilds the stores and corpora that a module-scoped fixture used to make once. It
also disables `pytest-benchmark` outright and turned four hypothesis timing deadlines into
failures under contention.

So parallelism is refused, and the reason is a property of this suite rather than a fact
about xdist. That is worth more than the 22 % would have been: the next person to look at
twenty idle cores now finds the measurement instead of repeating it.

## The gap is Windows, and CI already solved it

| the same suite | wall |
|---|---:|
| CI, `ubuntu-24.04` | **110 s** |
| CI, `macos-14` | 82 s |
| CI, `windows-2022` | 279 s |
| this machine (Windows, 20 cores) | **721 s** |

6.5× slower than the ubuntu cell that runs the identical tests, on hardware five times
larger. It is Windows twice over — 2.6× on the runner comparison, and more again for a
developer machine with a scanner and a working tree full of build output.

Which reframes the item. The local loop is not under-parallelised; it is *duplicating*, in
series and on the slowest platform available, work that CI does in parallel a minute later.
The fix is not to make the full suite faster locally. It is to stop running it locally.

## Derived, not declared — and that is the whole design

The item was framed as a *declared* mode. I built it derived, and the difference is the
security property rather than a preference: a mode a person declares can be narrowed, and
the failure is not malice but haste — "this is only a docs change" said about a branch with
uncommitted work in the ranker. `tools/verify.py` reads the diff, including the working tree
(the gates run *before* the commit, so a committed-only diff would derive `docs` for exactly
that branch), and picks `docs`, `code`, `retrieval` or `full`. `--mode` widens; a narrowing
request is refused by name, listing what it would skip.

It is still *declared* in the sense that matters: every run prints the mode and the path that
decided it, `--json` hands it to CI, and CI prints it as a notice. What ran is on the record
instead of inferred from a green tick.

Two decisions inside it worth keeping:

- **The classifier fails wide.** An extension it cannot classify raises the mode to `full`.
  A list nobody remembers to update should over-verify, not skip.
- **The matrix is not narrowed by mode.** Only `docs` skips it. A pure-Python change is
  precisely what breaks on Windows and not on Linux, and this repository has already paid
  for that once — the drive-letter path bug at 4.1, caught because Windows was in the matrix.
  A rule that predicted which Python changes are platform-sensitive would be a rule nobody
  can write.

## 124 seconds nobody had looked at

CI's critical path is windows-2022 at 444 s. Its steps:

```text
124s  Install pandoc     <- choco
279s  Test
 30s  everything else
```

Against 45 s for apt and 8 s for brew. And the deeper problem was not the time: three package
managers shipped three pandoc versions, so the engine version the parser adapter records
differed per cell and nothing said so — in a repository where a parser test is supposed to
assert behaviour rather than tolerate it (ADR-0032). One pinned release archive, verified
against a digest *before* extraction, fixes both. It is a supply-chain input (B2), so pinning
without verifying would have traded a slow install for an unreviewed binary.

## Writing the new boundary found an old duplicate

A change deciding which gates run on it is a trust boundary, so it needed one: **B13 —
verification scope**, whose control is the refusal above. Writing it exposed that **B10 was
issued twice** — LLM egress at 4.4 and tier-1 custody at 4.2 — with six STRIDE rows citing
`B10` and meaning two different things.

Twenty minutes after 4.27 closed the identical defect in `ROADMAP.md`. Same rule applied:
move the half nothing points at, so tier-1 custody becomes **B12** (one citation) and LLM
egress keeps **B10** (five). And the same durable half: `consistency_lint.py` gained a
`threat-boundaries` check — unique ids, and no STRIDE row citing a boundary nothing declares.
The second half is the one worth having; a row pointing at a boundary that does not exist
reads as coverage.

That the same defect surfaced twice in two artifacts on the same day is the argument for
lints over care.

## What this does not fix, stated

`pytest` on this machine spends ~16 s before the first test, 12 s of it collection, and a
session start also cleans the temp trees of previous runs. A scoped run is cheaper than a
full one and never free. The honest claim is that the *shape* changed: the full suite runs
once, in CI, in parallel with everything else, instead of two or three times locally in
series.

And the four hypothesis deadline failures are filed as **4.32** rather than fixed: they pass
in the shipped serial configuration, the deadline is measuring store-creation cost rather
than the property, and since 4.31 refused parallelism they may well stay open as a recorded
limit. Fixing tests that only fail in a configuration we decided not to adopt is work with no
reader.
