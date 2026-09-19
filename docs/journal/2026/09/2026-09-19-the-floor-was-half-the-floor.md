# 2026-09-19 — the floor was half the floor (roadmap 6.20)

- **Session scope:** roadmap 6.20 — the incremental build's floor was the whole corpus; decide
  between raising it and restating the budget, on a measurement.
- **PR:** #168 (`perf/incremental-build-floor`). Follows #167, merged as `4ecf8a6`.
- **Milestone 6:** 6.20 closed; 6.32 filed from its profile.
- **Decision it records:** [ADR-0133](../../../adr/0133-raise-the-floor-off-the-contents-and-state-the-corpus-the-budget-holds-for.md).

## The item named one pass, and the measurement found four

The item said `_plan` reads and digests every file on every build, called that the floor, and
asked whether to raise it or to give NFR-3 the corpus size it never had. Before touching
anything I timed every whole-corpus pass a no-op rebuild of 1 000 documents makes, one at a
time. The read was **2 625 ms of 4 890** — 54 %. Then three passes nobody had named:
restorability asking `exists()` twice per live document (376 ms — more than reading the whole
`doc_state` table), the graph asking `exists()` 3 922 times for 1 963 unresolved links (570 ms),
and discovery's `rglob` (485 ms). Together another third. The edited document's own chain, when
there was one, was about 190 ms of a 5.6 s rebuild.

So the answer to the item's either/or was both. The floor comes off the filesystem, and the
budget gets the corpus size it should have carried since Phase 1 — 1 000 documents, the same
corpus the cold-build budget names — because what remains is O(corpus) by construction and a
number with no size is met or missed by machine, not by design.

## The memo, and the three guards

`doc_state` remembers the size and mtime a file had when its digest was computed; a file whose
stat still matches keeps the digest unread. The digest is still the only identity anything
downstream compares — the memo only decides whether to recompute it — so nothing below the plan
step changed, and G6's golden is byte-identical.

The case a size-and-mtime memo cannot see is a same-size edit that also restores the old mtime.
Git's index has lived with the same blind spot for twenty years and closes its racy half with a
rule it calls *racily clean*; ours reads any file modified within two seconds of the previous
build's start regardless of the memo. The deliberate half gets a flag — `mycelium build
--rescan`, the old floor once and nothing more — and a detector: `mycelium doctor` re-digests
every document on demand and names the drift. The blind spot itself is a test, so narrowing or
widening it is a decision rather than a diff.

One design point worth keeping: the racy-window clock is the previous build's start, kept in
the store's `meta`. It must not go in the snapshot's restore blob — a wall-clock reading there
would make two builds of one unchanged corpus address two blobs, and the property
`record_snapshot_state` exists for is that they address one. The memo's facts (size, mtime)
*do* go in the blob, so a rolled-back snapshot trusts what the build it restores trusted.

## The second round was pathlib

After the first change the no-op rebuild was 2.05 s and the profile said something I would not
have guessed: `Path.relative_to` — 1.3 s of profiled time across discovery and the plan — and
four thousand `WindowsPath` constructions for the link probes. Not I/O; Python parsing path
strings. Discovery now carries each document's corpus path out of the walk it already did, and
the link probe joins strings. That took the no-op rebuild to **1.57 s** and the edit to
**1.72 s**, with `discover` at 93 ms where `rglob` had cost 485 and `plan` at 343 where the
reads had cost 2 625.

## The curve, and where it crosses

The tool's own curve, before and after, same machine: the single-document edit went from
1 618 to **717 ms p95** at 250 documents and from 8 755 to **1 754 ms** at 1 000 — inside the
budget at the size it now names — and reads 3 805 ms at 2 500 and 6 961 ms at 5 000. Above a
thousand it is a straight line of about 1.35 ms a document over ~200 ms of publication, so the
2 s line is crossed again near 1 200 documents here, where the unmodified compiler crossed it
near 250. That crossing is the whole argument for stating the corpus size in the budget: the
floor is O(corpus) by construction — a `stat`, a row, a share of two global resolutions, an
entry in the restore state — and a reader with three thousand documents deserves the number,
not a promise that cannot hold for them.

## The stray process

Every number this session took was taken on a machine with a `find / -iname fable-review.md`
walking the whole disk — left running by an earlier agent session, nine CPU-hours in, its parent
gone. The permission model refused `taskkill`, and I did not look for another way to do what it
refused. So the cold build read 114.5 s where 6.19 measured 91.7 idle, and the baseline
rebuild's p95 sat far above its p50. The report says this in its method section before any
number, the before and after share the contention, and the ratios — read against stat, probe
against listing — are what travel. The idle numbers are one command away, and the maintainer
can take them once the process is gone.

## What the guard looked like from inside the instrument

Twice my own measurement script failed its own assertion: a no-op rebuild had *read* 175
documents, then an edit rebuild had read three. Both were the racy window working — the last two
seconds of the generator's writes on the first, the previous two edits on the second — and both
looked, for a moment, like the memo not working. A guard that fires correctly is
indistinguishable from a bug to an instrument that does not know about the guard. The script
warms up once now, and the report has a paragraph saying what the extra reads are.

## What is left, and filed

The profile of the remainder points at `symbol_edges`: some 20 000 symbol uses decoded from
every document's state and ~3 500 `references` edges each digested twice, once to key the edge
and once when the store writes it. Content-proportional Python work, two obvious economies,
filed as 6.32 rather than fixed — the 6.19 discipline, and the same reason 6.4 filed six items
instead of six patches.

## Lesson

A floor is not one line. The read everyone knew about was half of it, and the other half was
three "cheap enough" probes that nobody had ever timed together — and then, under those, the
cost of building path objects in Python. Measure every pass a rebuild makes before deciding
which one is the floor; the named mechanism is where to start looking, not where to stop.
