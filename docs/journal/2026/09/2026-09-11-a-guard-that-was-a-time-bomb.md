# 2026-09-11 — a guard that was a time bomb (roadmap 5.20)

- **Session scope:** roadmap 5.20 — the grep baseline's competence guard, found 0.0024 from
  failing while building 5.10, re-derived deliberately on `main` with the guard green.
- **PR:** #108 (`test/grep-baseline-floor`). Follows #107 (5.9), merged as `2a12626`.
- **Milestone 5:** 5.20 done. 5.10 is on its own branch, unmerged, waiting for this.
- **ADR:** [ADR-0081](../../../adr/0081-check-the-incumbents-reach-not-its-ranking.md).

## How it was found, and why nothing was fixed where it was found

5.10 added one ADR and the suite went red: `test_the_grep_baseline_is_fair` asserts
`grep.ndcg_at_10 > 0.3` and grep read **0.2959**. The obvious move — the number is close,
lower the floor — is the one this project has refused fourteen times, and ADR-0072 says it in
as many words: *redefining a guard while it is red is the fitted parameter*.

So the first job was to find out what actually moved. Three measurements, each cheap:

- **Without the new ADR**, grep reads 0.3024. The guard had been sitting 0.0024 above its
  floor before anything in 5.10 was written.
- **Our own score does not move at all** — 0.5435 with the ADR and without it.
- **A same-size ADR on an unrelated subject** leaves grep at 0.3024. So this was not general
  dilution.

The cause is narrow and slightly uncomfortable. The new ADR documents the `supersedes`
relation, and `q-0014` asks *"which ADR supersedes the cross-language source layout"*. A
term-counting incumbent ranks the document that talks about the relation above the two
documents that **are** the relation. Writing documentation about a subject our own benchmark
asks about widened our measured lead without improving the product by a single point.

That is the second time this corpus has done something of the kind — ADR-0072 was the first,
from the restatement side — and it is worth carrying forward as a fact about every ours/dev
number.

## The question went to the maintainer, and the answer set the order

Four resolutions were defensible and they mean different things about what the project
publishes, so it was not mine to pick. The maintainer chose: land 5.10 unchanged, and
re-derive the floor deliberately in its own PR, with the diff in its body — the shape 4.22
used for a stale baseline.

The ordering that falls out of that is the good part. This PR branches from `main`, where the
guard is **green at 0.3024**. Re-deriving it here is not changing a guard while it is red; it
is deciding, with the failing change set aside and unmerged, and then measuring that change
against the result rather than the other way round.

## What the trend says, and what it changed

Five release points, with the judged set, the retriever, the chunker and the scorer all held
at today's so that only the documents vary — ADR-0044's method:

| corpus | documents | grep nDCG@10 | grep recall@50 | ours nDCG@10 |
|---|---:|---:|---:|---:|
| v0.1.0 | 37 | 0.0961 | 0.281 | 0.2119 |
| v0.2.0 | 54 | 0.5198 | 0.948 | 0.6316 |
| v0.3.0 | 81 | 0.4854 | 0.948 | 0.5647 |
| v0.4.0 | 128 | 0.3580 | 0.812 | 0.5402 |
| today | 138 | 0.3024 | 0.812 | 0.5435 |

v0.1.0 is not about dilution — today's cases name documents that did not exist then, and both
retrievers are near the floor. From v0.2.0 on, grep's **ranking** falls monotonically with
corpus size, 42 % in total, while its **reach** steps once and holds. Ours is flat across the
last two points.

Which turns the finding from "the number is stale" into something better: the assertion was
measuring the wrong quantity. nDCG@10 *is the thing under test* — spec 04 §7.4 says the real
incumbent is the agent's grep loop, and the claim is that a compiled index out-ranks term
counting as a corpus grows. A floor on the incumbent's ranking therefore fails hardest exactly
when the claim is most validated. It was never going to survive; 5.10 was just the PR holding
it when it went off.

The guard now asserts `recall_at_50 >= 0.75` — the answer is inside the incumbent's reach,
which is what makes the comparison fair — and keeps its two companions untouched. Where the
answer lands after that is the measurement, and a measurement cannot also be its own guard.

Worth noting that this makes the check *stronger* in one direction: at v0.4.0 grep's nDCG
cleared the old floor while its recall had already dropped a full step, which the old
assertion could not see at all.

## Lesson

When a guard fails, ask what quantity it is asserting before asking whether the number is
right. This one had been asserting a floor on the very thing the product exists to beat, which
made it a countdown rather than a check — and no choice of constant would have fixed that. The
tell was in the data the moment it was plotted rather than sampled: one number sliding
monotonically while the one beside it held still.
