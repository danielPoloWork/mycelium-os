# ADR-0109: Print the grade beside the share, because a split anchor is only half the reading

- **Status:** Accepted
- **Date:** 2026-09-14
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.1
- **Related:** [ADR-0102](0102-record-whether-the-passage-landed-whole-and-read-a-large-negative-with-it.md)
  (the `whole` column this qualifies, and the clause it amends),
  [ADR-0104](0104-merge-what-the-projection-could-not-tell-apart-and-record-that-it-could-not.md)
  (`shared`, the counterpart mark on the other sign),
  [ADR-0039](0039-measure-what-projection-costs.md) (the twin and the pairing),
  [ADR-0029](0029-let-a-judgment-name-a-section.md) (what a judged anchor names),
  [ADR-0044](0044-read-the-cases-not-the-mean.md) (read the cases, not the mean);
  spec 04 §7.1; D-010; roadmap 5.31, 5.39, 5.41

## Context

Roadmap 5.31 added a `whole` column to `tools/measure_projection_cost.py`'s per-case block —
the share of a judged passage's word occurrences the twin chunk actually holds — and ADR-0102
recorded it as *"the first thing to check on a large negative"*. It also recorded, as the
evidence that the number was worth having:

> Among scored release cases the two largest negatives are the two lowest shares — `u-1004` at
> 0.895 and `u-1019` at 0.509 — which is what makes the number worth recording.

And it filed `u-1019` as roadmap 5.39, unread, asking the narrower question: its 0.509 sits on
an anchor the judgement grades **1**, one whose own note says it *"answers only that the command
exists"*. Does a split on an anchor graded 1 move a case at all?

The item said to read both anchors' ranks on both corpora before concluding. Read:

| | anchor | source rank | twin rank | alone, source | alone, twin |
|---|---|---:|---:|---:|---:|
| grade 3 | `python-versions.md#requesting-a-version/python-version-files/0` | 2 | **10** | 0.6309 | **0.2891** |
| grade 1 | `features.md#python-versions/0` | 1 | **1** | 1.0000 | **1.0000** |

**The grade-1 anchor did not move.** It is first on both corpora and scores a perfect 1.0000
alone on both sides, despite being the anchor whose passage split. The whole of `u-1019`'s
−0.314 is the grade-3 anchor falling from rank 2 to rank 10, and that anchor's share is
**0.836** — unremarkable, and nowhere in the table.

So the answer to 5.39 is *no*, and the reason the split cost nothing is legible once the two
chunks are read. The HTML lane turned the feature list into one heading per feature line, so
the twin chunk is headed `uv python pin: Pin the current project to use a specific Python
version` — the query, verbatim, in a weighted field. Half the passage's occurrences went to a
neighbouring chunk, and the half that stayed is the half the query names.

**The column, as printed, named the wrong anchor.** It is the *minimum* across a case's
anchors, with no grade attached, so on a case whose anchors carry different grades it reports
the worst split rather than the one that moved the score. For `u-1019` those are different
anchors, and ADR-0102's correlation — "the two largest negatives are the two lowest shares" —
holds numerically while being, for one of the two, a coincidence.

It is not noise either, and the same table says so: `u-1004`'s 0.895 *is* on its grade-3 anchor,
and that case went to 0.000. The mark means opposite things depending on which anchor it is on,
and that is precisely what it was not saying.

## Decision

**The per-case `whole` mark prints the grade of the anchor it is on: `0.509@1`, `0.895@3`.**

Still the minimum, so the worst split is still the one shown — a reader looking for a damaged
passage still finds it. What changes is that the mark now carries the one fact that decides how
to read it. The legend says so in a line under the table, and the module docstring states the
rule with `u-1019` as the worked example, because a column whose meaning depends on a second
number should not make a reader reconstruct that dependency from first principles.

With the grade printed, the table reads differently at a glance: the two largest negatives are
`0.895@3` and `0.509@1`, not "the two lowest shares". The grade-1 marks (`u-1019` at 0.509,
`u-1016` at 0.985) sit beside deltas of −0.314 and −0.006 that have nothing to do with them.

**ADR-0102's clause is amended in place** rather than left to be read as it stands, since it is
the sentence that would send the next reader down the same path.

**No judged set, corpus or metric changes.** This is a reading aid for a reporting tool that CI
runs with `|| true`; the numbers it prints are identical.

## Alternatives Considered

- **Report the lowest share among *grade-3* anchors only.** The anchors that carry most of the
  ideal gain, so arguably the only ones worth marking. Rejected: it would have hidden
  `u-0017`'s 0.338 completely, and that one turned out to be a real defect (below). A mark that
  suppresses the lowest number in the receipt to make a correlation cleaner is fitting the
  instrument to the conclusion.
- **Print every split anchor's share, one row per anchor.** The most information. Rejected: the
  per-case block is a one-line-per-case table read alongside three others, and six of
  twenty-five cases are marked. The minimum plus its grade is the smallest thing that stops the
  misreading, and ADR-0102's own framing — a reading aid, not a predictor — argues against
  growing it into a second table.
- **Drop the column, since one of its two supporting cases was a coincidence.** Rejected on the
  other case: `u-1004` is exactly what the column is for, and `u-0017` below is a second. The
  defect was in what the column omitted, not in recording the number.
- **Replace `whole` with the anchor's rank delta**, which is what actually moved. Rejected: the
  ranks need a retrieval run over both corpora, which is what this table already is — the marks
  exist to explain a delta that has already been computed, cheaply, from the committed receipt.
  A mark that needs the thing it explains is not a mark.
- **Fix `u-0017`'s carry here too.** Rejected as scope, and filed as roadmap 5.41: it edits the
  twin's judged set, which re-blesses baselines and stales gate G2's verdict through
  `cases_digest`, and this project's standing rule is that a judgement change never rides with
  anything else (ADR-0104).

## Consequences

- **The two largest negatives are no longer "the two lowest shares".** They are `0.895@3` and
  `0.509@1`, and the second is now visibly not an explanation. Anyone quoting ADR-0102's
  sentence has the amendment beside it.
- **`u-1019` is answered and closed.** A split on a grade-1 anchor that ranks first on both
  corpora costs nothing; the case's −0.314 belongs to a grade-3 anchor at 0.836 that fell eight
  places. Why it fell is a PDF-lane question, not a `whole` question — its twin chunk is one
  page-sized block shared by three judged units (ADR-0104's `shared` 3), which is the mark that
  *does* apply to it.
- **The second read found a defect the column was signalling correctly and nobody had read.**
  `u-0017` (dev) is graded on `features.md#the-pip-interface/0` at grade 1 — share **0.338**,
  the lowest in the receipt, and the closest mapped anchor to the 0.50 coverage floor at 0.5269,
  which ADR-0102's own last bullet had already named as *"a cliff a reviewer should be able to
  see rather than discover"*. The carry landed it on a twin chunk headed `uv pip compile:
  Compile requirements into a lockfile`, which **does not contain the string `uv venv` at all** —
  and `uv venv` is the query. The correct chunk exists, carries the same heading slug
  (`#the-pip-interface/0`), holds the line, and scores **0.4731**: it would have been *dropped*
  as below-floor. Coverage is over distinct tokens, so a feature list whose vocabulary is
  dominated by `uv`, `pip`, `install`, `packages` scored a chunk about a different command above
  the one naming the right one, by 0.054. Filed as roadmap **5.41** with the measurement: as
  carried the case reads 0.5788 against its source's 0.6201; carried correctly it reads 0.6295,
  so the whole of its apparent projection cost is the mis-carry.
- **Nothing else moves.** The tool prints the same numbers; no test asserts on its output and CI
  runs it advisory (`|| true`). No corpus, judged set, baseline, verdict or golden is touched.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §7.1 (judged sets, the frozen pairing).
- Decision log: D-010 (fix the product, not the benchmark — which is why `u-0017` is filed
  rather than re-judged inside a reporting change).
- Re-runnable: `python tools/measure_projection_cost.py`; the ranks above come from
  `build_retriever("mycelium", store).search("uv python pin", 50)` on each corpus.
- The receipt: `eval/corpora/uv-docs-ingested/eval/carry.json`.
