# 2026-09-07 — two cases, not a corpus (roadmap 4.25)

- **Session scope:** roadmap 4.25 — `fact` on the second corpus is still the incumbent's
  (spec 04 §§7.1, 7.4; D-010).
- **PR:** #81 (`feat/fact-slice-second-corpus`). Follows #80 (4.28), merged as `ae5208e`.
- **Milestone 4:** 4.25 done; 4.29, 4.32–4.35 open, plus 4.36 filed here.

## The item told me how to start, and that instruction was the whole session

*"Start by reading the seven cases against the documents rather than by proposing a
ranking."* The family it belongs to is thirteen refusals deep, so this was not advice about
manners — it was the one thing that had not been tried.

Read per case, `fact 0.431 vs 0.497` is not a slice losing. It is **two cases of seven**:

| case | ours | grep |
|---|---:|---:|
| u-1006 which Python version formats can I request | 0.431 | 1.000 |
| u-1004 how do I pin one package to a specific index | 0.333 | 0.631 |
| the other five | ties, and +0.337 on u-1001 | |

And one of the two is not a defect at all. ADR-0057 gave u-1004 up on purpose two PRs ago:
`to` and `a` had been matching the heading *"Pinning a package to an index"* at weight 2.0
and carrying the right answer for the wrong reason. That decision has its evidence
recorded, and nothing I measured is new evidence against it.

So the item — filed as a corpus-shaped problem — is one open case.

## Two premises, both wrong, and the second one matters more

**"A property of that documentation."** `fact` on uv/**dev**, drawn from the same corpus:
**0.893 against the incumbent's 0.752**. We lead it by +0.141. A property of the
documentation cannot reverse between two judged sets over the same documents.

**"The third corpus concedes the same slice."** The third corpus's release set *is*
uv/release — same twenty-five case ids, same twenty-five queries, carried onto the ingested
projection with the anchors re-pointed at their twins (4.16). Two sets that share their
queries are one observation. "Both concede it" was that observation counted twice, and it
was the sentence that turned a number into a theory.

Reading them per case is what makes the double-count visible, because the two projections
concede on **different cases**:

```text
uv/release        fact is conceded on 2 of 7: u-1006 -0.569, u-1004 -0.298
ingested/release  fact is conceded on 2 of 7: u-1004 -0.569, u-1008 -0.014
```

The same −0.569 twice, on a different case each time. That number is one grade-3 answer at
rank 4 rather than rank 1, and which case wears it depends on where the chunk boundaries
fell — u-1006's judged anchor is a section in one set and a document's lead chunk in the
other. ADR-0044 said a slice this size measures a case rather than a property; here the
aggregate held still at −0.066 and −0.019 while everything underneath it moved.

## The one hypothesis worth testing, tested, and refuted

u-1006 is real: we return `Requesting a version / Python version files`, which says *"Any of
the request formats described above can be used"*, ahead of `Requesting a version`, which
lists them. Right neighbourhood, not the answer — exactly what ADR-0029 refuses to credit.

A chunk's `heading_path` is its whole ancestor chain, so a subsection's heading field is a
strict superset of its parent's: every word that matched the parent matches the child too,
at the same weight, and the child adds its own. That is a real structural asymmetry, it is
an *indexing* change rather than a re-ranking — the family the two changes that actually
closed the gap came from — and nobody had tried it. It is now the twelfth family in
`measure_ranking.py`.

**It does not move u-1006. At any setting. Including ancestors at zero.**

I had already "refuted" it on paper by adding up per-column BM25 contributions, and that
arithmetic was unsound: FTS5's `bm25()` is not additive across columns, because the weighted
term frequency appears in its own denominator. Checking that — 11.52 by the sum, 9.27 by
measurement — is what sent me to build the index instead of writing the refusal. The
one-hot readings still order the columns correctly, and the ordering is the finding: the
child wins on `text` (10.075 against 7.752), at 164 tokens against 385. Length
normalisation, whose `b` SQLite does not expose. ADR-0031 named that mechanism three
milestones ago and it is still the answer.

## The lead I found and did not take

`heading 3.0/0.5` — leaf at 3.0, ancestors at 0.5 — is the **first** candidate in that file
to win or tie on all four sets *and* pass gate G3 on both release sets. ours/release 0.505 →
0.527, uv/release 0.586 → 0.603, `symbol` 0.585 → 0.658. The unsplit controls fail G3 on
`exact`, so the split is doing the protective work rather than the weight alone.

It is refused, on two grounds and either would do. It does not fix this slice — `fact` goes
0.431 → 0.438, still short of 0.497, and u-1006 does not move — so taking it here would be
smuggling an unrelated gain in under this item's name. And on **uv/dev** every safe setting
scores exactly the baseline: I tried five parameter pairs and kept the one that won on the
held-out sets, which is the definition of what the dev/release split is for. Filed as 4.36
with the blocker stated: it needs a dev set on which the effect is visible.

## What ships instead

The line that started this item now decomposes itself:

```text
still conceded: fact 0.431 vs 0.497
  fact is conceded on 2 of 7 case(s): u-1006 0.431 vs 1.000 (-0.569), u-1004 0.333 vs 0.631 (-0.298)
```

The run had been scoring the incumbent case by case since 4.8 and throwing the results away.
Gate G3 has named the cases behind a slice since 4.20 — for the reason that applies here
word for word — and the comparison against the incumbent was the last number in the project
a reader had to go and investigate. A slice conceded by every case prints no list, because
there the mean really is the finding.

That is the part of this session I would want back if I had to lose the rest: not the
refusal, but the instrument that makes the next reader's first look the one I had to spend
an afternoon on.
