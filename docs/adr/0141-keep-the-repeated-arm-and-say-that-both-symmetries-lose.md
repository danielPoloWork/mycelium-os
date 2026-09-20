# ADR-0141: Keep the repeated arm, and say that both symmetries lose

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §3
- **Related:**
  [ADR-0048](0048-index-the-stem-beside-the-surface-form.md) (the two-halved
  expression this is about),
  [ADR-0129](0129-bound-the-question-once-before-anything-reads-it.md) (the 64-term bound
  that made the *cost* of repetition moot and left the ranking question),
  [ADR-0070](0070-take-the-leaf-heading-weight-on-the-third-asking.md) and
  [ADR-0080](0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md)
  (the bar a ranking change clears),
  [ADR-0137](0137-let-a-gated-default-follow-its-ablation-and-narrow-the-rule-that-would-refuse-it.md)
  (the same bar applied to a leg that had earned its default and lost it),
  [ADR-0136](0136-author-the-judged-sets-to-the-count-their-own-bar-needs.md) (which grew
  the sets this was re-measured on); spec 04 §3; roadmap 6.17, 6.26

## Context

`expanded_query` builds one MATCH expression from two halves (ADR-0048): surface terms
against the surface columns, their stems against the stem columns. The halves disagree
about repetition, and always have:

- the **stem** half deduplicates — `dict.fromkeys(stem_text(terms))`, with a comment
  saying why;
- the **surface** half is a plain comprehension over every match, so a question
  contributes one `OR` arm per **occurrence**.

Roadmap 6.17 bounded the query at 64 terms, which made the cost of that moot — a pasted
document never reaches the expression any more. What it left is the question nobody had
argued: **should a repeated word weigh twice, and is one half of an expression disagreeing
with the other a decision or an oversight?**

It is not free to settle by inspection, because a duplicated arm is not free in FTS5.
Measured directly: `"link"` scores a document at −5.0995 and `"link" OR "link"` scores it at
−10.199 — exactly double, and the doubling reorders results. That is query-term frequency,
the `qtf` component the original Okapi BM25 formula carries and this expression gets by
accident.

**The filing item's premise had expired.** It says *"two of 155 measured queries repeat a
term"*, and names them: `t-0015` and `t-0016`, both agent tasks. That was true at 6.17.
Roadmap 6.8 then authored the release sets from 19 and 25 cases to **286 and 404**
(ADR-0136), and the census today is **241 of 1 224 judged queries** — so what the item
described as a two-case curiosity in the agent-task suite is a scoring change across most
of the judged corpus.

## Decision

**Keep the incumbent. The surface half repeats and the stem half does not, and that is now
a measured decision rather than an unexamined one.**

Symmetry was available in two directions and both were scored
(`tools/measure_query_repetition.py`):

| arm | surface | stems |
|---|---|---|
| **A** incumbent | one arm per occurrence | deduplicated |
| **B** | deduplicated | deduplicated |
| **C** | one arm per occurrence | one arm per occurrence |

| set | A | B | C |
|---|---:|---:|---:|
| `ours/dev` | 0.4705 | +0.00 % | +0.00 % |
| `ours/release` | 0.4815 | −0.01 % | **+0.04 %** |
| `uv/dev` | 0.6143 | +0.00 % | +0.00 % |
| `uv/release` | 0.6903 | **−0.40 %** | +0.01 % |
| `uv-ingested/dev` | 0.6127 | +0.00 % | +0.00 % |
| `uv-ingested/release` | 0.6477 | **−0.11 %** | **−0.10 %** |

Agent-task evidence-found is **identical in all three arms on all three corpora** (0.727 /
0.818 / 0.773), which answers the item's own request to measure there: the suite the item
was worried about is the one place nothing happens.

The bar a ranking change clears is a release-set gain with **no overall regression on any
set** (ADR-0070, ADR-0080, applied again at ADR-0137). **B regresses all three release
sets. C gains two and regresses the third.** Neither clears it, so neither ships.

## Consequences

**Nothing changes at runtime**, and that is the outcome rather than the absence of one. The
value delivered is that the asymmetry has a reason, in three places a reader will find it:
the two docstrings that own the halves, a test that states the measurement and exists so the
next reader reaches the decision instead of tidying it away, and this record.

**The cases that moved are worth reading**, because they say *why* repetition is signal
rather than noise. Under B: `u-1248` *"the difference between a constraint **file** and an
overrides **file**"* falls 1.0 → 0.69; `u-1321` *"why does uv **pip list** show a different
package name than **pip list**"* falls 1.0 → 0.5; `u-1198` *"how do `--index-url` and
`--extra-index-url` map onto uv's own options"* falls 0.88 → 0.79. In each, the repeated
word **is** the subject of the question, and weighting it twice is what put the right
passage first.

**Why the halves are not the same act.** Deduplicating stems collapses *different* words
that share one — `build` and `building` are two questions of the surface columns and one of
the stem columns. Deduplicating the surface would collapse a word the question said twice.
The two operations look alike in code and are not alike in meaning, which is the substance
behind a symmetry that looked like sloppiness.

**What this does not claim.** C's loss is −0.10 % on one set, one case wide; a larger
`uv-ingested` release set could move that either way. The rule is the rule, and a change
that fails it by a case is still a change that failed it — but a later re-measure is a
legitimate thing to want, and `tools/measure_query_repetition.py` is how to take it. It is
run by hand and not in the gate ladder, because there is no shippable flag here for a
`--check` to hold.

**A note on filed items.** This is the third in a row whose stated diagnosis needed
correcting before the work could start, and the first whose *numbers* had expired rather
than its reasoning. An item's premise ages with the corpus it was measured on.
