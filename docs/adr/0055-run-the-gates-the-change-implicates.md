# ADR-0055: Run the gates the change implicates, and derive which those are

- **Status:** Accepted
- **Date:** 2026-09-04
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.31; RFC-0001; AGENTS.md §10; spec 06 (the quality bar);
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md) (the frozen-set
  conjunction this reuses), [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md) (the
  pandoc engine this pins), [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)

## Context

Every item in this repository has been verified the same way: run everything, usually twice,
and wait. That was right while the gates were few. It is now the largest fixed cost per item,
and it buys less than it appears to, because CI runs the same gates afterwards anyway.

Measured on 2026-09-04, against run 33886166814 and this machine:

| the whole test suite | wall |
|---|---:|
| CI, `ubuntu-24.04` | **110 s** |
| CI, `macos-14` | 82 s |
| CI, `windows-2022` | 279 s |
| this machine (Windows, 20 cores, serial) | **721 s** |

The local loop is 6.5× slower than the CI cell that runs the identical suite, and it is not a
hardware gap — it is Windows, twice over: 2.6× on the runner comparison, and more again on a
developer machine with a scanner and a large working tree.

The obvious remedy was measured and **refused**. `pytest-xdist` on 20 cores gave
`--dist loadfile` 562 s — a 22 % saving, because the cost is concentrated in a handful of
expensive files, so one worker holds the critical path while the rest idle — and
`--dist load` was **1389 s, worse than serial**, because per-test distribution destroys the
fixture reuse this suite depends on. It also disables `pytest-benchmark` and turned four
hypothesis timing deadlines into failures under contention. Parallelism is not the lever.

Meanwhile CI's own critical path had an obvious 124 s in it: `choco install pandoc` on
windows-2022, 28 % of the longest job in the workflow, against 45 s for apt and 8 s for brew.
Three package managers also meant three pandoc versions, so the engine version the parser
adapter records differed per cell and nothing said so.

## Decision

**A change runs the gates it implicates, and which those are is derived from the diff rather
than declared by a person.**

`tools/verify.py` classifies a diff into one of four modes, narrowest to widest, each running
everything the one before it runs:

| mode | derived when | adds |
|---|---|---|
| `docs` | every changed path is documentation | the congruence lint |
| `code` | `src/`, `tests/`, `tools/`, or the build manifest changed | format, lint, types, the suite |
| `retrieval` | a tuning path or anything under `eval/` changed | the frozen-set guard, a build, the gates on this corpus |
| `full` | CI configuration changed, an unclassifiable file, or asked for | the other two corpora |

Three properties make that safe rather than merely fast.

**The mode may only be widened.** `--mode` exists to ask for more; a narrower mode than the
diff derives is refused by name, listing what it would skip. A declaration that could narrow
is a way to land unverified code — boundary **B13** in the threat model, and this refusal is
its control.

**The classifier fails wide.** An extension it does not recognise raises the mode to `full`.
A list nobody remembers to update then over-verifies instead of skipping.

**One implementation, two callers.** CI derives the mode with the same script a contributor
runs, so what a contributor saw and what the workflow decided cannot drift. The mode reaches
the workflow as a `bootstrap` output and gates the jobs; the run prints it as a notice.

**The economy is on the proposal, never on the record.** A push to `main`, a release tag and a
called workflow are `full` by construction. A pull request is where a narrowed scope is
useful and where a mistake is still catchable.

**The matrix is not narrowed by mode.** Only `docs` skips it; a `code` change still runs all
four cells. A pure-Python change is precisely the kind that breaks on Windows and not on
Linux, and this repository has already paid for that once — the drive-letter path bug at
roadmap 4.1, caught because Windows was in the matrix.

**pandoc is pinned and verified instead of installed three ways.**
`.github/actions/setup-pandoc` pulls one release archive, checks it against a digest recorded
in the action *before* extracting, and puts it on `PATH` on every runner. That removes the
124 s and makes every cell adapt the same engine.

## Alternatives Considered

- **Parallelise the local suite.** The first thing tried, and measured twice: `--dist
  loadfile` 562 s (−22 %), `--dist load` 1389 s (+93 %). Refused — the suite's cost is a few
  expensive files with heavy fixtures, which is the shape parallelism helps least.
- **Let a human declare the mode.** What the item was framed as. Rejected: a declaration that
  can narrow is a hole, and the failure mode is not malice but haste — "this is just a docs
  change" said about a branch with uncommitted work in the ranker. Deriving from the diff
  costs nothing and cannot be wrong in the dangerous direction.
- **Read only the committed diff.** Simpler, and wrong locally: the gates run *before* the
  commit, so a branch whose uncommitted work rewrites the ranker would derive `docs`. The
  working tree is included, and in CI it is clean so the two agree.
- **Narrow the matrix on `code` changes** — drop Windows unless a path-handling file changed.
  Rejected: the classification would have to predict which Python changes are
  platform-sensitive, and 4.1's drive-letter bug is the proof that nobody can.
- **Skip pandoc on Windows** to remove the 124 s. Rejected for the same reason it was
  installed there in the first place: subprocess behaviour is exactly what differs between
  Windows and the Unix runners, and the pandoc tests skip silently when the binary is absent —
  which reads as a pass.
- **Cache the package-manager install.** Would have removed most of the time and none of the
  version drift. Pinning does both.

## Consequences

- **A documentation-only PR runs one 7 s job** instead of a nine-job workflow, and locally
  runs the congruence lint instead of the suite. That is most of the saving, and this
  repository writes a lot of documentation.
- **CI's critical path loses 124 s.** windows-2022 was 444 s, of which pandoc was 124 s and
  the suite 279 s.
- **Every runner now adapts the same pandoc**, so a parser test asserts behaviour rather than
  tolerating whichever version a package manager shipped (ADR-0032).
- **A new trust boundary, B13 — verification scope**, with its control stated: derived, may
  only widen, refused by name when narrowed. Writing it exposed that **B10 was issued twice**
  (LLM egress at 4.4, tier-1 custody at 4.2); tier-1 custody becomes **B12** — the half only
  one row pointed at, by the rule roadmap 4.27 established — and `consistency_lint.py` gained
  a `threat-boundaries` check so neither a duplicate id nor a row citing a boundary that does
  not exist can recur.
- **The local loop keeps a fixed cost this does not remove.** `pytest` on this machine spends
  ~16 s before the first test — 12 s of it collection — and a session start also cleans the
  accumulated temp trees of previous runs. A scoped run is cheaper than a full one but never
  free, so the honest claim is that the *shape* changed: the full suite runs once, in CI, in
  parallel with everything else, instead of two or three times locally in series.
- **Refined by [ADR-0059](0059-make-the-plan-one-implementation-too.md).** The ladder this
  ADR chose was implemented twice — as `verify.py`'s `plan()` and as the workflow's job
  conditions — and the two drifted: at `retrieval` CI gated three corpora and the local
  tool gated one. `retrieval` now gates every corpus, `full` keeps the benchmarks alone, and
  a test reads both files and fails when they disagree. Nothing about the *derivation* or
  its measured economy changed; what changed is that the plan is checked (roadmap 4.35).
- **Four hypothesis tests fail under parallel load** with `DeadlineExceeded` — they carry
  timing deadlines on I/O-bound property tests. They pass in the shipped serial
  configuration, so nothing here is broken; it is filed as roadmap 4.32 rather than absorbed,
  because the deadline is measuring store-creation cost rather than the property.

## References

- Measured this session: CI job and step timings from run 33886166814; local suite 721 s
  serial, 562 s `--dist loadfile`, 1389 s `--dist load`; pandoc install 124 s (choco) /
  45 s (apt) / 8 s (brew).
- [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md) — why pandoc is in the matrix
  at all, and why its version is part of what a parser test asserts.
