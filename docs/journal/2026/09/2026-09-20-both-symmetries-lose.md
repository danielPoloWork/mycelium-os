# 2026-09-20 — both symmetries lose (roadmap 6.26)

- **Session scope:** roadmap 6.26 — decide whether a repeated query word should weigh
  twice, and whether the two halves of one expression disagreeing about it is a decision or
  an oversight.
- **PR:** #176 (`perf/expression-surface-repeats`). Follows #175, merged as `433a890`.
- **Milestone 6:** 6.26 closed. Open: 6.27–6.36.
- **Decision it records:**
  [ADR-0141](../../../adr/0141-keep-the-repeated-arm-and-say-that-both-symmetries-lose.md).

## The premise had expired

The item says *"two of 155 measured queries repeat a term"* and names them — `t-0015` and
`t-0016`, both agent tasks — and concludes that deduplicating *"is a scoring change on the
agent-task suite and has to be measured there"*.

That was true when it was filed, at 6.17. Roadmap 6.8 then authored the release sets from
19 and 25 cases to **286 and 404** (ADR-0136). The census today: **241 of 1 224 judged
queries repeat a word.** The item described a two-case curiosity in one suite; what is
actually there is a scoring change across most of the judged corpus, and the agent-task
suite is the one place it does *not* land.

This is the third item in a row whose stated diagnosis needed correcting before the work
could start — and the first where the reasoning was sound and only the **numbers** had
aged. An item's premise ages with the corpus it was measured on.

## Inspection could not settle it, because the repetition is not free

FTS5 sums a duplicated arm. Measured directly: `"link"` scores a document at −5.0995 and
`"link" OR "link"` at −10.199 — exactly double, and the doubling reorders the results.
That is the `qtf` component the original Okapi BM25 formula carries, which this expression
has been getting by accident on one half and not the other.

## Two repairs, and both lose

Symmetry was available in both directions, so both were scored rather than one:

| set | A incumbent | B dedup both | C repeat both |
|---|---:|---:|---:|
| `ours/dev` | 0.4705 | +0.00 % | +0.00 % |
| `ours/release` | 0.4815 | −0.01 % | **+0.04 %** |
| `uv/dev` | 0.6143 | +0.00 % | +0.00 % |
| `uv/release` | 0.6903 | **−0.40 %** | +0.01 % |
| `uv-ingested/dev` | 0.6127 | +0.00 % | +0.00 % |
| `uv-ingested/release` | 0.6477 | **−0.11 %** | **−0.10 %** |

Agent tasks: **0.727 / 0.818 / 0.773 in all three arms**, on all three corpora.

The bar is the standing one — a release-set gain with no overall regression on any set
(ADR-0070, ADR-0080, applied again at ADR-0137). B regresses all three release sets; C
gains two and regresses the third. Neither ships.

## What the moved cases say

They are the reason the asymmetry is defensible rather than merely surviving. Under B:
`u-1248` *"the difference between a constraint **file** and an overrides **file**"* falls
1.0 → 0.69; `u-1321` *"why does uv **pip list** show a different package name than **pip
list**"* falls 1.0 → 0.5; `u-1198` *"how do `--index-url` and `--extra-index-url` map onto
uv's own options"* falls 0.88 → 0.79. In each of them the repeated word **is** the subject,
and weighting it twice is what put the right passage first.

And the two halves are not doing the same thing. Deduplicating stems collapses *different*
words that share one — `build` and `building` are two questions of the surface columns and
one of the stem columns. Deduplicating the surface would collapse a word the question said
twice. They look alike in code and are not alike in meaning.

## What ships

Nothing at runtime. What ships is the reason, in the three places a reader will meet it:
the docstrings that own each half, a test that states the measurement and exists precisely
so the next reader reaches the decision instead of tidying the asymmetry away, and
`tools/measure_query_repetition.py`, which re-takes all of it in one run. By hand, not in
the ladder — there is no shippable flag here for a `--check` to hold.

The honest caveat is in the ADR: C's loss is one case wide on one set, and a larger
`uv-ingested` release set could move it either way. The rule is the rule, and a change that
fails it by a case still failed it — but the measurer exists so that a later re-take is
cheap.
