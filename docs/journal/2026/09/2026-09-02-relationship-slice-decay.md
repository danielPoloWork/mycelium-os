# 2026-09-02 — the case that was answered by the word "off" (roadmap 4.17)

- **Session scope:** roadmap 4.17 — `relationship` on our own release set halved between two
  blesses, and no gate could have said so.
- **PR:** #64 (`test/relationship-slice-decay`). Follows #63 (4.16), merged as `91c1fb9`.
- **Milestone 4:** 4.1–4.7, 4.9–4.12, 4.16, 4.17 done; 4.8, 4.13–4.15, 4.18 open, and
  4.19–4.21 filed out of this one.

## The question was well posed, which made it answerable

0.3040 at the previous bless, 0.1064 now, across fifteen new documents. Two hypotheses: two
documents getting harder to find among more documents, or a real regression in how
relationship queries are served. They are distinguishable — hold the judgments and the
compiler fixed and vary only the corpus — and nothing in the repository could do that, which
is why the first thing this session built was the instrument rather than the answer.

`tools/measure_slice_decay.py <ref>` checks the older ref out into a throwaway worktree,
copies **today's** judged sets in, compiles both with **today's** compiler, and scores them
side by side. One command, and the answer was not the one I expected:

```text
  slice              before    after     delta
  conceptual         0.3785   0.4507    19.1%
  relationship       0.3040   0.1064   -65.0%

  r-0006  nDCG@10 0.2128 -> 0.2128   first judged hit at  2 ->  2
  r-0011  nDCG@10 0.3951 -> 0.0000   first judged hit at  4 -> 26   <<< this one
```

The corpus, and **one** case. And `conceptual` went *up* over exactly those fifteen documents,
so "more documents make retrieval worse" is not what happened.

## Why the case was ever passing

I had a hypothesis — high-frequency junk terms drowning the signal — and the leave-one-out
refuted it in the most useful way. Searching each of r-0011's five terms alone:

| term | hits | first judged hit |
|---|---:|---|
| `signs` | **0** | — |
| `contributed` | **0** | — |
| `contribution` | 7 | not found |
| `may` | 51 | not found |
| `off` | 52 | rank 19 |

**Two of the five terms match nothing at all.** The query says *signs* and *contributed*; the
document says *"Every commit must be signed off, certifying you wrote it…"* — `signed`,
`contribution`. FTS5's `unicode61` tokenizer does no stemming, so those are simply different
words, and the only term that ever reached the answer was **`off`**.

Which is why ADR-0042 killed it. Its section is called *"Why it ships switched off"*, and
`heading_path` carries weight 2.0 — six of that one document's chunks took the head of the
ranking, and the DCO section fell from rank 4 to 26. The case had been standing on one weak
word since it was written; a new document said that word in a heading and the prop went.

**So the 0.3951 was luck and the 0.0000 is honest.** The judgment is right — I read
`CONTRIBUTING.md`, and its DCO section is exactly what the query asks for — so there is
nothing to re-judge. What is wrong is the retrieval, and it was wrong before the decay too;
the decay only stopped it being flattered.

The easy version of this session would have re-anchored r-0011 and reported the slice restored.
No retrieval change was in flight, so the frozen-set guard would have permitted it. That the
guard allows a change is not the same as the change being honest.

## The second question, with numbers

Can a two-case slice carry a gate? No, and the shape of "no" is worth writing down. A slice of
*n* cases moves in steps of 1/n of one case's swing, and G3 enforces −2 %. Counting the gated
rows across the three release baselines: seventeen of them, thin in two different ways. **Six
are blessed at 0.0000** — `unanswerable` everywhere, `symbol` on both `uv` sets, `exact` on
`uv/release` — and a slice at zero cannot regress, so G3 cannot fail those rows however bad
they get. **Of the eleven it *can* fail, five hold two cases or fewer**, and `exact` on
ours/release holds **one**.

A −2 % threshold there is not a sensitive gate. It is a gate that cannot be tripped by anything
except a single case, and that is tripped by *every* single case — including ones moving for
reasons that have nothing to do with retrieval quality. This one moved because of a word in a
heading.

That is a benchmark-design defect, not a threshold to loosen. G3 was reporting something real:
the number did halve. What it cannot do is tell you why, and on a two-case slice nothing can.

## What I measured and did not adopt

The stemming fix is obvious enough that leaving it unmeasured would have been the same as
leaving it unmentioned. `porter unicode61`, in memory, all four sets: ours/release
0.4499 → **0.5972**, uv/release 0.3056 → **0.4032**, `relationship` on ours/release
0.106 → **0.531**, `fact` +45 % and +47 %.

**And it fails gate G3** — ours/release `conceptual` −16.8 %, `exact` −2.5 %. ADR-0041's shape
exactly: a large win with one slice paying for it. So it is filed (4.19) with the number
attached and with the variant worth trying first named — *expansion* rather than replacement,
indexing both the surface form and the stem so a literal match keeps its edge. Recording the
+32 % without the −16.8 % would have set up whoever picks it up to be surprised by the gate.

## Filed rather than folded in

- **4.19** — stem the index, without paying for it in `exact`. Store-schema change, so it
  bumps the version, re-indexes, and re-blesses the golden.
- **4.20** — give the thin slices enough cases to carry a gate, or state which ones G3 reports
  rather than enforces. Judgment work; must not travel with a retrieval change, the way
  3.15 → 3.17 and 4.11 → 4.12 were each split.
- **4.21** — `explain` should say when a query term matched nothing. Two of five terms matched
  zero documents and the product said nothing; that is what turned this into an afternoon
  instead of a command.

Nothing in the query path changed, no set was edited, and no baseline was re-blessed.
`python tools/measure_slice_decay.py 9adad70 --set release` re-runs the whole diagnosis.
