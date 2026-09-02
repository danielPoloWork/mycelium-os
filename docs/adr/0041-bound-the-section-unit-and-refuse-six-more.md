# ADR-0041: Bound the section unit, and refuse six more re-rankings

- **Status:** Accepted
- **Date:** 2026-09-02
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §3, §7.1, §7.3
- **Related:** [ADR-0031](0031-refuse-three-rerankings.md) (which named this hypothesis),
  [ADR-0029](0029-let-a-judgment-name-a-section.md),
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0007](0007-adopt-structure-first-chunking.md); D-010; roadmap 4.8

## Context

ADR-0031 refused three re-rankings and left the item open with an ordered plan:

> **A hypothesis worth testing next, in order**: index and score at the *section* level —
> a second FTS table whose documents are sections — so length normalisation compares
> comparable units, then return the best chunk of the winning section.
>
> **One interaction must be disentangled before section aggregation is proposed again.**
> […] Whether the release regression is retrieval or bookkeeping is answerable — by judging
> those cases from the documents first, and re-testing afterwards.

Roadmap 3.17 did the judging (thirteen cases re-scoped, PR #47). This item does the
re-testing, and then the hypothesis itself.

**Step one is closed: the regression was retrieval, not bookkeeping.** Re-measured after the
re-judging, `section:max` still fails gate G3 on the second corpus — `conceptual` 0.3770 →
0.1836, **−51.3 %**, the same number ADR-0031 recorded. The suspicion that a chunk-exact
judgment was scoring a correct retrieval as zero is answered, in the direction that costs us
the excuse.

## Decision

**The section-level indexing hypothesis is refused, in all six forms it has, and the family
is closed with an upper bound rather than with one more refusal.** Nothing in the query path
changes.

Six ways to make a section the unit were built and measured. The section index is real — an
FTS5 table whose documents are sections, exactly as ADR-0031 specified — built in memory from
the store's own chunks, because a hypothesis that fails should cost an afternoon and not a
schema version.

| dev set | ships | section:max | section-fts | section-open | section-ordered | section-fused | open-if-cand | grep |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ours | 0.538 | **0.567** | 0.541 | 0.510 | 0.506 | 0.552 | 0.518 | 0.403 |
| uv | 0.403 | 0.444 | **0.564** | **0.564** | 0.472 | 0.457 | 0.444 | 0.576 |

And the gate view, which is what settles it — the worst per-slice change against the
committed baseline on each **release** set:

| strategy | ours/release | uv/release | G3 |
|---|---|---|---|
| section:max | fact +0.0 % | conceptual **−51.3 %** | fail |
| section-fts | exact **−33.7 %** | conceptual **−39.2 %** | fail |
| section-open | exact **−33.7 %** | fact +10.9 % | fail |
| section-ordered | exact **−48.2 %** | fact **−37.7 %** | fail |
| section-fused | exact **−33.7 %** | conceptual **−39.2 %** | fail |
| open-if-candidate | fact +0.0 % | relationship +0.0 % | **pass** |

**`open-if-candidate` passes gate G3 on both release sets and is refused anyway.** That
sentence is the substance of this ADR, so it gets its own reason below.

## Why the one that passes the gate is still refused

`open-if-candidate` represents a section by the chunk that *opens* it, but only when BM25 put
that opener in the candidate set — the retriever's own evidence rather than an assumption. It
improves the second corpus by 22 % (0.280 → 0.341, R@10 0.500 → 0.607), improves ours/release
by 1 %, and regresses no slice on either release set.

It also **loses 3.7 % on our own dev set**, and the loss is one case whose mechanism is
understood. The query is `BEGIN IMMEDIATE transaction`:

```text
docs/adr/0009-…#decision/0   (14 tokens)   ← returned at rank 1
    Decision
    Publication order. One writer, one transaction, one swap::

docs/adr/0009-…#decision/1   (92 tokens)   ← judged, demoted to rank 2
    acquire .mycelium/lock                 # O_CREAT|O_EXCL; heartbeat = mtime
    BEGIN IMMEDIATE                        # readers keep the old committed state (WAL)
    …
```

The opener qualified as "evidence" on the strength of one incidental word — *transaction* —
and displaced the block that contains the phrase the query asked for. nDCG on that case goes
0.956 → 0.169.

That is **the same defect roadmap 4.8 exists to fix, produced by the fix**: a short fragment
outranking the passage that answers. ADR-0031 diagnosed it as BM25 length normalisation over
heterogeneous chunks; here it arrives through the representative rule instead. A change that
reproduces the disease it was written to cure is refused whatever the aggregate says.

**And the gate could not see it.** G3 reads per-slice means on the *release* sets; the broken
case lives in the dev set. ADR-0027 introduced the split to catch a change fitted to the sets
it was developed on, and it did that in ADR-0031. Here it caught the mirror image: **a real
regression sitting in the half the gate does not read.** The dev set is not only where tuning
is allowed to look — it is where a regression the release gate is blind to becomes visible,
which is a second, independent reason the split earns its keep.

## The bound that closes the family

Every member of the family wins one corpus and loses the other, which raises the obvious
question: is the answer to choose the unit *per query* rather than globally — the planner
spec 04 §2 reserves? That is answerable without building a planner. Take, for each case, the
best score **any** of the seven strategies achieves. No rule can beat that, because it chooses
with foresight the query does not carry:

| set | chunk unit | best section unit | oracle | vs grep |
|---|---:|---:|---:|---:|
| ours/dev | 0.538 | 0.574 | 0.574 | +0.171 |
| ours/release | 0.472 | 0.514 | 0.514 | +0.245 |
| uv/dev | 0.403 | 0.601 | 0.601 | +0.025 |
| uv/release | 0.280 | 0.486 | 0.486 | **+0.015** |

On the corpus this item is about, **the whole family's ceiling is 0.486 against the
incumbent's 0.471** — a 3 % margin, available only with per-case foresight, while every
realisable member either fails G3 or regresses a dev set. The unit of indexing is not where
this gap closes, and that is now a measured statement rather than an opinion.

The per-case winners say the same thing from the other side: on uv/release the section unit
wins all 3 `conceptual` cases, 4 of 7 `fact`, 1 of 2 `exact`, 1 of 2 `relationship`. There is
no query-shape rule in that distribution — the split is by *document*, and whether a section's
answer sits in its opening chunk or in its fifth depends on how the author wrote it.

## What the measurement reframed

Beating grep on the second corpus turns out not to be the hard part. **Three of the ten
strategies already do it** — `length>=120` scores 0.503, `grep-formula` 0.511, `length>=60`
0.481, against the incumbent's 0.471. Every one of them fails gate G3 on *our* corpus.

So roadmap 4.8's framing — "the product loses to the grep incumbent on the second corpus" —
understates the problem. The product can beat that incumbent several ways. What it cannot yet
do is beat it **without paying for it on the corpus it already wins**, and no re-ranking in
ten attempts has managed both.

## Alternatives Considered

- **Ship `open-if-candidate` because it clears the gate.** Rejected above: the gate is blind
  to the case it breaks, and the break is the item's own pathology.
- **Ship `section-open`** — the best of the family on the second corpus (uv/release 0.451, no
  slice regressed there). Rejected: `exact` −33.7 % on our release set. The regressing case is
  a query (`Conventional Commits`) whose answer exists in two near-duplicate documents, and
  the change swaps which one ranks first — plausibly benign, and *not testable in this change*,
  because deciding it means editing a release judgment and `tools/check_frozen_release_sets.py`
  refuses a PR that moves both retrieval and the judgments. Recorded as work, not used as an
  exemption (the same discipline ADR-0031 set and 3.17 followed).
- **Re-judge `Conventional Commits` first, in its own PR, then re-test.** Rejected for now:
  ADR-0031 already refused "re-judge the release cases so the change passes", and doing it
  across two PRs does not change what motivated it. A judgment may be revisited when a reader
  of the *document* finds it incomplete — not when a candidate needs it to be.
- **Borrow the incumbent's ranking function** — `(distinct terms, total occurrences)`, with no
  length normalisation anywhere. Genuinely different from the `coverage-first` ADR-0031 refused,
  which kept BM25 as its tie-break and so kept the length bias in the second key. Measured, and
  it collapses: 0.003 on ours/release. The incumbent's selection and its ranking are a package;
  applied to a BM25-preselected candidate set the formula promotes long chunks with incidental
  repeats. **Refused, and worth having measured** — "just rank like grep" is the obvious
  suggestion and now has a number attached.
- **A planner that picks the unit per query.** Rejected on the bound above: the ceiling of
  perfect routing is +0.015 over grep, and the per-case winners carry no query-shape signal.
  The planner still arrives with the symbol leg (spec 04 §2, roadmap 5.2); it is just not the
  answer to *this*.

## Consequences

- **Roadmap 4.8 stays open for a second time.** Nine strategies measured across two ADRs, none
  shipped. The item asked for a fix; ticking it would make the roadmap's boxes mean less than
  they say.
- **The hypothesis ADR-0031 named is closed, not merely unproven.** Its open question is
  answered (retrieval, not bookkeeping), its named fix is refused in six forms, and the family
  it belongs to has an upper bound 3 % above the incumbent.
- **The remaining hypothesis is a *chunking* one, and it is now the one standing.** ADR-0031
  listed "merge short code chunks into their surrounding prose at chunk time" and set it aside
  as a chunking decision that could not be smuggled in as a ranking fix. Six ranking variants
  and a bound later, the evidence points there: every failure in this ADR traces to chunks of
  wildly unequal size, and no ranking rule repairs a unit that is wrong before ranking sees it.
  Filed as roadmap **4.11**, with its real costs stated — it moves every boundary in every
  corpus, re-blesses the determinism golden, and invalidates judged anchors that are not
  section-scoped (ADR-0029's durability argument becomes load-bearing).
- **The dev/release split earns its keep a second time, differently.** ADR-0031 recorded it
  catching an overfit. This ADR records it catching a regression the release gate cannot see,
  because the case lives on the other side of the split. Both directions are worth having.
- **`tools/measure_ranking.py` is the instrument, not the prose.** It now carries all ten
  strategies, the section index, `--release` for the gate view, and `--oracle` for the bound.
  Every number in this ADR is one command.
- **No product code changed, so no user-visible behaviour changed** and nothing is re-blessed.

## References

- Spec 04 §2 (planner), §3 (candidate generation), §7.1 (dev/release split), §7.3 (gate G3); D-010
- [ADR-0031](0031-refuse-three-rerankings.md) — the three earlier refusals and this hypothesis
- [ADR-0029](0029-let-a-judgment-name-a-section.md) — section-scoped judgments, and why
  durability now matters to roadmap 4.11
- `tools/measure_ranking.py --release --oracle` — every table above, re-runnable
