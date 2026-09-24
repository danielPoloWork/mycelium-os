# 2026-09-23 — the pain had no unit (roadmap 7.4)

- **Session scope:** roadmap 7.1, the remote build cache, was asked for. Its entry trigger
  had not fired and could not have, so the maintainer chose to measure what a cache could buy
  and to make the trigger evaluable instead — filed and delivered as 7.4.
- **PR:** #N (`feat/measure-the-remote-cache-ceiling`). Follows #192, merged as `9b8d8cc`.
- **Milestone 7:** 7.4 closed; 7.1 held at its trigger; 7.5, 7.6 and 7.7 filed.
- **Decision it records:**
  [ADR-0154](../../../adr/0154-price-the-remote-cache-before-its-trigger-and-give-the-trigger-a-reading.md).

## The item could not start, and saying so was the first deliverable

Three documents say a Phase 5 item enters only through its spec 06 §3 trigger and its own
RFC, and 7.1's trigger is *≥ 1 team dogfooding with measured duplicate-build pain*. Adoption
stands at one engaged actor of three and the package is on no index, so the first half was
plainly unmet. The second half was worse: nothing could have measured the pain. The right
move was to put that to the maintainer before writing anything, with four courses and a
recommendation, rather than to start an RFC for a feature nobody had asked for from outside —
or to override a gate quietly, which is how this repository has decided milestones stop
meaning anything.

## Ask what a cache can change before pricing it

A cache can only change a cold build, and within one only the two stages the compiler
caches. Once that was said out loud the measurement designed itself: fresh checkouts — a new
path, every file written anew — with only `.mycelium/` varying. The part worth the most care
was making each arm prove it measured its name: hits recorded beside every time, output
digests compared, and the `documents` digest *expected* to differ between checkouts. That
expectation turned out to be the finding.

## The fourth arm was not in the plan

The first run had three arms. Asking why the restored arm could do no better than the ideal
remote cache — it hands over the whole previous store, not just the stage artifacts, and
still rebuilt every document — led to ADR-0009: a document record carries its file's mtime,
a fresh checkout's mtimes are all new, so every document is re-assembled and re-stored
whatever the cache holds. The run was stopped and restarted with a fourth arm. Giving the restored checkout its cache's
mtimes took the thousand-document build from 40 s to **1.6 s**, nothing rebuilt — against
19 s off 55 s for the ideal remote cache. So the largest number in the report belongs to
something 7.1 does not describe, and it is filed as 7.7. Roadmap 6.38 had already met the
same field from the other side: `updated_at` is noise on any clone.

## This machine charges per file, so say which part travels

Seeding the artifacts costs about what the build saves, and at a thousand documents more:
**39 s to write what saves 19 s**. That is the scanner, which the benchmarks README already
calibrates, and it would make a naive headline about the compiler that is really about the
filesystem. Timing the computation in memory — a miss's parse and chunk against a hit's
decode — gives the part that travels: about **9 ms a document**. The report leads with that
and says plainly that on an unencumbered SSD the ordering of the designs could change.

## The inputs were not what the tool said

Exporting the generator's two named sources from a clean tree failed on the second: the
reference profile has harvested one corpus since it was written, beside a docstring saying
two (BUG-0034). And the thousand-document corpus compiled 998, because two harvested
headings are YAML the adapter refuses as titles (BUG-0035). Neither moves a comparison inside
one run, and both change every corpus the generator writes, so they are one item of their
own (7.6) rather than a fix inside a measurement that wants to stay comparable with the
series. The export mattered for a second reason: the working tree's `docs/` holds the
maintainer's untracked files, and harvesting it would have put them in the corpus — the
clean export read 5 874 blocks where the working tree reads 5 935.

## What the next session should know

- **7.1 is held, not refused.** Its trigger fires on one team's report; the magnitude that
  justifies building is the owner's call and is written nowhere in code on purpose.
- **7.3 is the only M7 item with no trigger**, and it must be armed before the v1.0.0 tag.
  7.5 asks 7.2's triggers the question 7.4 asked 7.1's.
- **`tools/verify.py` derives `full` in this working tree** because of the maintainer's
  untracked `.claudeignore`; this change was verified from a clean worktree of the branch.
- **Measure with the maintainer's files out of the harvest.** `--harvest-root` takes a clean
  export; the manifest records its commit and a digest of each generated corpus.
