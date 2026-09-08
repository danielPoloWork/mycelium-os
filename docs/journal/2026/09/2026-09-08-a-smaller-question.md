# 2026-09-08 — a smaller question (roadmap 4.36)

- **Session scope:** roadmap 4.36 — the leaf heading and its ancestors are not the same
  evidence (spec 04 §§3, 7.1; ADR-0058).
- **PR:** #86 (`feat/split-leaf-heading-from-ancestors`). Follows #85 (4.34), merged as
  `4d65b2a`.
- **Milestone 4:** 4.36 done; 4.33, 4.37, 4.38 open, plus 4.39 filed here.

## The item's unblock condition was not going to arrive

4.36 was filed refused, with a condition attached: *"It needs a dev set on which the effect
is visible before it can be proposed; the corpus growth 4.26 began is the way to get one."*
4.26 has since landed and it grew **uv/release** from 14 judged cases to 25. `uv/dev` is
still the twelve cases it has always had — one `exact`, one `symbol`, no `relationship` —
and a set that thin is flat under a field-weight change by construction. Waiting for the
stated condition meant waiting for an item nobody had written.

So the question got smaller instead. The candidate ADR-0058 refused had **two** free
parameters, `heading 3.0/0.5`, and one of them — the leaf weight — is where all the release
gain sits and where dev says nothing at all. Measuring only the other one, across its whole
range at the leaf weight the spec already fixes, turns out to be answerable on a dev set:

| ancestors (leaf 2.0) | ours/dev nDCG | MRR | R@10 |
|---|---:|---:|---:|
| 2.0 *(unsplit)* | 0.537 | 0.572 | 0.719 |
| 0.75 / 0.5 / 0.25 | 0.540 | 0.581 | 0.719 |
| 0.0 | 0.523 | 0.577 | 0.688 |

A plateau bounded below by zero. Splitting helps; anything from 0.25 to 0.75 is
indistinguishable, so dev cannot choose inside the band and 0.5 is the middle of it rather
than a fitted optimum; and dropping the ancestors entirely *loses*, which says where a chunk
sits is real evidence — weaker than what it is about, not worthless. Two of those rows
(`0.75`, `0.25`) were added this session, because a three-point grid cannot tell a plateau
from a peak.

## The defect, in four rows of SQL

The mechanism had been described three times and never reproduced. It reproduces easily:
two chunks with identical bodies, one under `Retries` and one under `Retries / Retries
schedule`, query `retries`.

```text
joined   child  -1.636e-6   parent -1.457e-6    <- the subsection wins
split    parent -1.457e-6   child  -1.418e-6    <- the section the query is about wins
```

A superset can carry the query term *more often* than the set it contains, which is the
whole defect in one line. It is now a test rather than a paragraph, and it is the test that
would have failed before this change.

## What shipped, and what was refused again

`heading_path` splits into `heading` (2.0, the spec's own weight, unchanged) and `ancestors`
(0.5). The leaf increase is refused a second time: `3.0/0.5` and `4.0/0.5` are worth
uv/release 0.611 and 0.616 against the shipped 0.604 — three to four times the split's own
gain — and score *identically to the shipped setting* on both dev sets. A benefit visible
only on the held-out set is indistinguishable from a fit to it, whatever the mechanism story
sounds like. That is filed as 4.39, which is the item 4.36 was really waiting for and which
nobody had written down.

## The verdict was read before anything was re-blessed

The order is the point (PR #67 recorded it). G3, against the **committed** baselines:

- **uv/release** — enforced, *"same corpus, same boundaries, same judgements, no enforced
  slice regressed"*. 0.6021 → 0.6035, `exact` +0.9 %.
- **uv-docs-ingested/release** — enforced, same verdict. 0.6300 → 0.6306, `fact` +0.4 %.

Per case, on the two sets G3 enforces, **exactly one case moves on each and both move up**:
`u-1003` from rank 10 to rank 8, `u-1008` by 0.014. Every other judged case is unchanged to
six decimal places. So the honest claim is that the correction is *free*, not that it is a
win — the reason to make it is that the field was wrong. `u-1006` does not move at all,
which ADR-0058 predicted: that gap is in `text` length normalisation and this was never its
lever.

Our own baseline was deliberately **not** re-blessed. It is stale by construction (4.22,
ADR-0053) and folding a milestone of corpus growth into it here would attribute that growth
to this change.

## Found on the way

`tools/measure_ranking.py` crashed with an arity mismatch the moment the store's weight
tuple grew, because two whole families of recorded refusals — the section family, the
tokenizer family — build four-column indexes and borrowed the store's constants for them.
A refusal whose numbers move when an unrelated field is split is not re-runnable, which is
the one thing that file exists to be. Their weights are now pinned locally, and
`heading 2.0/2.0` is kept as the row that reproduces the pre-change index exactly.

## What this leaves

The store schema is v5, so the next build in any checkout recreates the store — FTS5 columns
cannot be altered, and this is what rebuild-as-migration is for (D-016). The pre-change code
meeting a v5 store refuses it by name, which I saw for real while measuring the before-state
of the agent-task loop, and which is the guard behaving exactly as designed.
