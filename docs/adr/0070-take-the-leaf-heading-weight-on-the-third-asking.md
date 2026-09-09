# ADR-0070: Take the leaf heading weight on the third asking, because the dev set can now see it

- **Status:** Accepted
- **Date:** 2026-09-09
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.42 (this item), 4.39 (where it was filed), 4.36, 4.25; RFC-0001;
  spec 04 §§3, 7.1, 7.3; D-010;
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md),
  [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md),
  [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md),
  [ADR-0063](0063-split-the-leaf-heading-from-its-ancestors.md),
  [ADR-0067](0067-grow-the-dev-set-before-asking-it-a-question.md),
  [ADR-0068](0068-give-gate-g2-a-runner-by-dating-its-verdict.md),
  [ADR-0069](0069-read-g2s-slices-case-by-case-and-keep-the-bar.md)

## Context

`heading 3.0/0.5` — the leaf heading field raised from spec 04 §3's 2.0 to 3.0, the
ancestors left at 0.5 — has been measured three times and refused twice.

ADR-0058 refused it as one of twelve ranking families. ADR-0063 refused it again while
shipping the *split* it depends on, and stated the ground precisely: the candidate gains
three to four times as much on the held-out sets as the split does, and scores **exactly
the baseline on both dev sets**. A value whose entire benefit is invisible where tuning may
look and visible only where it may not is indistinguishable from a value read off the
held-out set, whatever the mechanism story. Both ADRs named the same remedy rather than
leaving the candidate to be re-proposed on enthusiasm: *a dev set thick enough to see a
field-weight question.*

Roadmap 4.39 built one. It grew `uv/dev` from twelve judged cases to twenty-two, written
from the documents and **committed before anything was scored on them** — the commit order
is the evidence that the set was not chosen to fit a setting (ADR-0067). Ten cases,
selected by the mechanical criterion of which slices were thin, eight of them naming
documents that carried no judgement before.

This ADR is what that set was built to answer.

## Decision

**`heading` moves from 2.0 to 3.0. One line, one parameter, and the ancestors stay at 0.5.**

The refusal is lifted because the ground it stood on is gone — and because the dev set does
not merely agree, it **discriminates**:

| uv/dev (22 judged cases) | nDCG@10 | MRR | R@10 |
|---|---:|---:|---:|
| `heading 2.0/0.5` *(shipped since 4.36)* | 0.609 | 0.630 | 0.692 |
| **`heading 3.0/0.5`** *(this change)* | **0.614** | **0.632** | **0.717** |
| `heading 4.0/0.5` | 0.599 | 0.607 | 0.717 |

The third row is the load-bearing one. At twelve cases every safe setting of this family
read *identically*; at twenty-two the parameter has an **interior optimum** — 3.0 above the
baseline, 4.0 below it. A dev set that can distinguish 3.0 from 4.0 is a dev set that can
choose, and it chooses against the held-out sets, which prefer 4.0 (uv/release 0.616 at
4.0/0.5 against 0.611 at 3.0/0.5). That disagreement is the split working in the direction
it exists for.

**4.0 is now refused from a second direction too.** Measured against the new baseline, on
this repository's own release set it reads `conceptual` **−18.1 %**, because `r-0009`
collapses 1.0000 → 0.6309. The best row on one held-out set is a large loss on another.

## Verification, read before anything was re-blessed

Gate G3 was read against the **committed** baselines first — the order that makes a gate
mean something (the discipline PR #67 recorded, and ADR-0063 followed) — and only then were
the two enforceable baselines re-blessed.

| set | before | after | worst enforced slice | G3 |
|---|---:|---:|---|---|
| uv/release | 0.6035 | **0.6109** | none regressed: `exact` +0.6 %, `fact` +1.8 %, `symbol` +3.4 % | *enforced* — **pass** |
| uv-ingested/release | 0.6341 | **0.6370** | `fact` −0.9 % | *enforced* — **pass** |
| ours/release | 0.511 | **0.531** | `conceptual` −2.1 % | *reported, never enforceable* (4.22, ADR-0053) |
| uv/dev | 0.609 | **0.614** | — | dev, not gated |
| uv-ingested/dev | 0.548 | **0.550** | — | dev, not gated |
| ours/dev | 0.540 | **0.539** | — | dev, not gated |

Neither enforced set's `cases_digest` or `corpus_digest` moved, so both re-blesses are a
pure retrieval move with no corpus or judgement drift folded into them.

**Two rows above are uncomfortable and are not being smoothed.** `ours/dev` is a hair
*worse*, and `ours/release` trips the −2 % slice bar. Both are read case by case below,
which is ADR-0058's method and is now what this project does before believing a slice.

### Per case, across all six judged sets

Of **119 answerable cases**, fourteen move: nine up, five down.

| | set | case | slice | before → after |
|---|---|---|---|---:|
| ↑ | ours/release | `r-0010` | fact | 0.6309 → **1.0000** (+0.3691) |
| ↑ | uv-ingested/release | `u-1007` | symbol | 0.3390 → 0.4365 (+0.0975) |
| ↑ | uv/release | `u-1007` | symbol | 0.3742 → 0.4665 (+0.0923) |
| ↑ | uv/dev | `u-0021` | relationship | 0.0000 → 0.1016 (+0.1016) |
| ↑ | uv-ingested/dev | `u-0004` | conceptual | 0.4307 → 0.5000 (+0.0693) |
| ↑ | uv/release | `u-1004` | fact | 0.3333 → 0.3869 (+0.0535) |
| ↑ | uv/release | `u-1003` | exact | 0.3333 → 0.3562 (+0.0229) |
| ↑ | uv-ingested/dev | `u-0021` | relationship | 0.1064 → 0.1202 (+0.0137) |
| ↑ | ours/release | `r-0017` | exact | 0.3228 → 0.3361 (+0.0132) |
| ↓ | ours/release | `r-0004` | conceptual | 0.4307 → 0.3869 (−0.0438) |
| ↓ | uv-ingested/dev | `u-0011` | conceptual | 0.3869 → 0.3562 (−0.0306) |
| ↓ | uv-ingested/release | `u-1004` | fact | 0.3869 → 0.3562 (−0.0306) |
| ↓ | ours/dev | `q-0014` | relationship | 0.3368 → 0.3241 (−0.0127) |
| ↓ | uv-ingested/dev | `u-0022` | relationship | 0.1064 → 0.1016 (−0.0049) |

Gains total +0.833, losses −0.123. The largest single movement is a correction anyone can
check by reading it: `r-0010` asks *"how should a branch be named"*, and the section whose
leaf heading is **Branch naming** goes from rank 2 to rank 1.

**`u-1004` moves in both directions**, +0.0535 on `uv/release` and −0.0306 on the ingested
projection of the same corpus. Same query, same judgement, different chunk boundaries —
worth recording as the clearest instance yet that the projection is a genuinely different
retrieval problem, not a copy of its source.

### The two losses, read from the ranking

**`r-0004` — "may an agent merge its own pull request"**, the case behind the whole −2.1 %.
Its judged answer drops from rank 4 to rank 5, both inside the top ten. What overtook it is
`git-workflow.md#4-pull-requests/0`, rising from rank 8 to rank 4 — a chunk whose leaf
heading is literally **Pull Requests** for a query containing *pull request*. That is the
mechanism doing exactly what it was raised to do, on a query whose better answer happens to
be a boundary table elsewhere in the same document. Real, small, and not a malfunction.

**`q-0014` — "which ADR supersedes the cross-language source layout"**, the reason ours/dev
reads 0.539. The grade-3 answer sits at rank 8 both before and after; what moved is
`AGENTS.md#5-source-tree-cross-language-layout/0` from rank 6 to rank 3, demoting a grade-2
anchor by one place.

### Why the ours/release slice does not block this

Three reasons, in the order they matter.

1. **It is one case losing 0.0438 on a four-case slice whose bar is 0.0417.** ADR-0069
   measured this exact arithmetic two PRs ago and wrote down what it means: at four to seven
   cases a slice, the −2 % condition is *"a per-case veto wearing a percentage's clothes"*,
   catching real harm and unmeetable by any change large enough to be worth making, both at
   once. The denominator is filed as **6.8** (~35 cases a slice), and it is the only fix.
2. **The same set gains four points overall** — 0.511 → 0.531 — because `r-0010` gains
   0.369 where `r-0004` loses 0.044. Refusing on the slice would refuse a change that
   improves the set it is measured on.
3. **G3 does not enforce there, and not for a convenient reason.** ADR-0053 made ours/release
   *reported, never enforceable* because this repository's corpus grows with every PR, so its
   baseline is stale by construction — a standing decision taken long before this candidate
   existed. The number above is nevertheless a real same-build comparison from
   `measure_ranking.py`, which is why it is in this table rather than behind that ruling.

**What is not done about it:** the bar is not moved. ADR-0069 refused to loosen it two PRs
ago and filed 6.8 instead, and moving a bar with a candidate in flight is precisely what
that ADR forbids.

### Gate G2, and the fingerprint that fired

Roadmap 4.40 built `retrieval_identity()` to digest field weights, stem weight, fusion
constants and the FTS schema, and named **this change** as the one that would otherwise have
left the recorded verdict looking current. It worked, first time it was tested by something
real:

```
gate G2: the recorded verdict does not describe this product
  - the retrieval configuration changed since the verdict was recorded on 2026-09-09
    (field weights, stem weight, stopwords, fusion constants or the FTS schema)…
```

The verdict was re-measured on all six sets and re-recorded. **The decision does not move**:
three of six sets pass, the release rows still put the default at `lexical`, and hybrid keeps
the burden of proof. The lexical arm having improved, hybrid's relative gain narrows where it
wins (ours/release +20.9 % → +15.6 %) — which is the verdict staying true rather than
changing.

### And two copies the sweep missed, found by being the change that exposes them

ADR-0068 fixed this defect in the run manifest, where the field weights were *"a hand-typed
string in two places"*. There were two more, in `mycelium.mcp.tools`: the `explain` payload
and `mycelium_explain`'s `config` block each carried
`{"title": 3.0, "heading": 2.0, "body": 1.0, "ancestors": 0.5}` as a literal.

So after the one-line weight change, **`mycelium_explain` reported a ranking the ranker was
not doing** — and the full suite went green, 1559 tests, because the two assertions that pin
those weights were literals agreeing with literals rather than with the product. The tool
whose stated purpose is to be *"the debugging and trust surface"* (spec 05 §3.4) was the last
place in the codebase still describing the old configuration.

Both now read `field_weights()`; the tests keep their literals, which is the correct division
— the code derives, the test pins — and the guard is verified by mutation: reverting
`_SURFACE_WEIGHTS` to 2.0 fails both tests, where before this change it failed nothing.

### And one carve-out G2's runner was missing, found the same way

`tools/verify.py` then went red at `gate G2`, and not on the fingerprint:

```
gate G2: the recorded verdict does not describe this product
  - ours/release: recorded pass, measured fail (lexical 0.530738 -> 0.5283,
    hybrid 0.613777 -> 0.5903)
```

The cause is this ADR. `ours` is this repository, so writing the document that explains a
change alters the corpus the change is measured on — three new documents about retrieval and
heading weights, which are excellent distractors for exactly the queries `ours/release`
judges. The vector arm lost 0.023 and the set's G2 verdict flipped.

`DATED_CORPORA` already states this principle, and states it well: *"`ours` is this
repository, and every pull request moves it — this file, an ADR, a roadmap line… a check that
failed on it would demand a re-measurement of gate G2 for a typo in a README."* Both
`_check_corpora` and `_check_sets` honour it. **`compare_measurement` did not** — it compared
verdicts on every set, undated ones included, one function below the constant declaring the
exemption.

The omission had a shape worth naming. `compare_measurement` runs **only where the embedding
model is present**, and CI has none (D-013), so CI never re-measures and never saw it. The
only person who could see it was a contributor with the model — and what they saw was
`verify.py` failing because they had documented their own change. That is precisely the
local-versus-CI divergence ADR-0059 exists to remove, arriving through the one code path that
runs in only one of the two.

So a verdict flip on an **undated** corpus is now a note carrying its numbers, and a flip on a
dated one stays a failure. The **decision** comparison is untouched: if the measurement stops
supporting the default the record names, that fails wherever the drift came from. Four new
tests in `tests/test_g2_verdict.py` cover every branch — dated flip, undated flip, undated
flip with no notes list, and a moved decision — and the carve-out is verified by mutation:
inverting the condition fails them.

## Alternatives Considered

- **`heading 4.0/0.5`** — the best row on uv/release (0.616), and the reason a held-out set
  must not choose. Refused **by dev** (0.599, below the baseline) and, against the new
  baseline, by ours/release as well (`conceptual` −18.1 %, `r-0009` 1.0000 → 0.6309).
- **`heading 3.0/1.0`** — uv/dev 0.612, uv/release 0.611, both a shade below the chosen pair.
  Refused because it moves a second parameter that has no dev signal to move it: ADR-0063
  measured the ancestor weight as a plateau from 0.25 to 0.75, so 1.0 would be a value chosen
  by nothing.
- **Refuse it a third time.** The most conservative option and the one this project's habits
  push toward. Rejected because the stated ground was *"no dev signal"*, roadmap 4.39 was
  commissioned to supply exactly that signal, and it did — with an interior optimum, which is
  stronger evidence than the monotone gain that was originally asked for. A condition that
  cannot be discharged by the evidence filed to discharge it is not a condition, it is a veto;
  and 4.39's own numbers were published before this candidate was scored on them.
- **Re-bless ours/release too, so its `conceptual` row starts from the new number.** Rejected
  on ADR-0053's standing grounds: that baseline is stale by corpus growth, and re-blessing it
  here would fold a milestone of unrelated drift into a baseline as though this change had
  caused it.
- **Move the −2 % per-slice bar so ours/release passes.** Rejected, and it is the fitted
  parameter this project has refused repeatedly. ADR-0069 kept the bar two PRs ago on exactly
  this evidence and filed 6.8 for the denominator; loosening it now, with a candidate
  pending, would be the same mistake with better timing.
- **Ship 3.0 *and* grow the sets first (6.8), so the slice bar means something.** The correct
  order in the abstract, and rejected on cost: 6.8 is an XL item aimed at ~35 cases a slice
  across six sets. Blocking a measured, dev-justified one-line change on it would leave the
  improvement unbanked for a milestone, and 6.8's own value does not depend on this change
  waiting.

## Consequences

- **Spec 04 §3 is amended in this PR** — the third amendment to that section's weights, and
  the first that moves a number the section itself set. `title` and `body` are untouched.
- **Two frozen baselines are re-blessed**; ours/release is deliberately not (ADR-0053).
- **The G2 verdict is re-recorded** and its decision is unchanged. This is the first time
  ADR-0068's currency check has been triggered by a real change rather than by a test.
- **`measure_ranking.py`'s controls shift by one.** `heading 3.0/0.5` is now the row that must
  equal `baseline (ships)` — verified, identical to three decimals on every set — and
  `heading 2.0/0.5` becomes the **revert control**, which prices going back at `fact` −11.8 %
  on ours/release.
- **The refusal count is unchanged at fourteen families** (ADR-0066). This is not a fifteenth
  candidate accepted; it is a parameter *inside* a family that already partly shipped, taken
  on its third asking. It is, as far as this record goes, the first refusal in this project
  lifted by evidence commissioned specifically to lift it.
- **A standing weakness, restated rather than resolved:** on ours/release the `conceptual`
  slice now sits 2.1 % below where it was, on one case, and the set that would have caught it
  as a *gate* cannot. Until 6.8 grows the slices, any change of this size is un-gateable there
  in both directions — it could as easily have hidden a real regression as this one hid a
  correction.
- **Nothing about compilation changes.** These are query-time BM25 weights over an unchanged
  FTS schema, so there is no store version bump, no rebuild, and gate G6's golden does not
  move.
- **`mycelium_explain` derives its field weights**, and two assertions now pin the shipped
  ones. Before this change the tool could report a ranking the product was not doing, and
  1559 tests agreed with it.
- **G2's re-measurement no longer fails on this repository's own corpus.** A verdict flip
  there is reported; the decision is still gated. The generalisable half is the ADR's lesson
  rather than its decision: **a fingerprint proves a record is current, and says nothing
  about the other places the same fact was copied by hand** — the sweep at 4.40 found two of
  four, and the two it missed were in a different package.

## References

- Spec 04 §3 (field weights, amended here), §7.1 (dev/release split), §7.3 (the gates).
- Measured this session and re-runnable: `python tools/measure_ranking.py --release` for the
  family table and the G3 column, `python tools/measure_hybrid_gate.py --check` for the
  verdict's currency, `mycelium eval <corpus> --set eval/release.jsonl --gate` for the three
  release rows.
- [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md) and
  [ADR-0063](0063-split-the-leaf-heading-from-its-ancestors.md) — the two refusals, and the
  condition both of them named.
- [ADR-0067](0067-grow-the-dev-set-before-asking-it-a-question.md) — the dev set that answers it.
- [ADR-0069](0069-read-g2s-slices-case-by-case-and-keep-the-bar.md) — the per-slice arithmetic
  the ours/release row is read under, and the reason the bar is not moved here.
