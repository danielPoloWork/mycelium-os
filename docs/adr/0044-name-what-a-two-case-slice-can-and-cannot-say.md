# ADR-0044: Name what a two-case slice can and cannot say

- **Status:** Accepted
- **Date:** 2026-09-02
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.1, §7.3
- **Related:** [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md)
  (the split), [ADR-0029](0029-let-a-judgment-name-a-section.md),
  [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md),
  [ADR-0043](0043-judge-across-the-configurations-a-set-is-scored-under.md),
  [BUG-0014](../bugs/2026/08/BUG-0014-g3-compares-incomparable-corpora.md); D-010; roadmap 4.17

## Context

Roadmap 4.12 re-blessed the baselines and something in the diff did not belong there:
`relationship` on our own release set read **0.1064** where the previous bless had recorded
**0.3040**. Not caused by 4.12 — its controlled before/after read 0.106 on both sides — and
not catchable by gate G3, which refuses to enforce across a corpus change by design and
correctly ([BUG-0014]). Which is also the point: **the decision that keeps G3 honest is the
decision that lets a slow decay cross several milestones unremarked.**

The item asked two questions. Are two documents merely getting harder to find among more
documents, or is this a real regression in how relationship queries are served? And can a
two-case slice carry a gate at all?

## Decision

**Both questions are answered from measurement, and the second answer is the one that
changes something.** No code changes, no judgment changes, and no re-blessing here.

### One: it was the corpus, it was one case, and that case was never being retrieved

`tools/measure_slice_decay.py` is the instrument G3 cannot be. It holds the judgments and the
compiler fixed and varies only the corpus — checking the older ref out into a throwaway
worktree, copying *today's* judged sets in, and compiling both with *today's* compiler:

```text
before  9adad70: 88 docs, 741 chunks
after   HEAD:   103 docs, 913 chunks

  slice              before    after     delta
  conceptual         0.3785   0.4507    19.1%
  exact              0.9845   0.9833    -0.1%
  fact               0.4354   0.4354     0.0%
  relationship       0.3040   0.1064   -65.0%

  r-0006  nDCG@10 0.2128 -> 0.2128   first judged hit at  2 ->  2
  r-0011  nDCG@10 0.3951 -> 0.0000   first judged hit at  4 -> 26   <<< this one
```

So: **corpus growth, and exactly one of the two cases.** `conceptual` went *up* over the same
fifteen documents, so this is not dilution as a general force.

The scores are stable but that rank is not, and the reason is worth stating: adding this ADR
and its journal entry to the corpus moves the judged section from 26 to 30 on the next run.
Once a passage is outside the top ten its exact rank is noise, which is why the metric is
`nDCG@10` and why the *slice* numbers above reproduce while the rank drifts. A reader
re-running the tool later should expect the same verdict and a different integer.

The interesting part is why r-0011 was ever scoring 0.3951. Its query is *"who signs off that
a contribution may be contributed"*, which `terms_of` reduces to
`signs OR off OR contribution OR may OR contributed`. Searching each term alone, against the
current corpus:

| term | hits | first judged hit |
|---|---:|---|
| `signs` | **0** | — |
| `contributed` | **0** | — |
| `contribution` | 7 | not found |
| `may` | 51 | not found |
| `off` | 52 | rank 19 |

Two of the five terms match **nothing in the corpus**, and the only term that reaches the
answer at all is `off`. The document says *"Every commit must be signed off, certifying you
wrote it…"* — `signed`, not `signs`; `contribution`, not `contributed`. FTS5's `unicode61`
tokenizer does no stemming, so those are different words.

**The case was being answered by the word `off`.** It stopped being answered when ADR-0042
arrived with a section called *"Why it ships switched off"* — `heading_path` carries weight 2.0
(spec 04 §3) — and six of that one document's chunks took the head of the ranking. Removing
`off` from the query drops the judged section out of 200 candidates entirely.

**The judgment is correct and is not touched.** Read from the document, `CONTRIBUTING.md`'s DCO
section is exactly what *"who signs off that a contribution may be contributed"* asks for. The
0.3951 was luck; the 0.0000 is the honest score of a lexical retriever on a query that shares
almost no vocabulary with its answer. Re-judging would be repairing the measurement instead of
the product.

### Two: no — and the numbers say how badly

A slice of *n* cases moves in steps of 1/n of one case's swing. G3 enforces a **−2 %**
per-slice threshold. Every gated row across the three committed release baselines, with the
number of cases behind it:

| set | slice | cases | blessed |
|---|---|---:|---:|
| ours/release | conceptual | 4 | 0.4507 |
| ours/release | **exact** | **1** | 0.9833 |
| ours/release | fact | 6 | 0.4354 |
| ours/release | **relationship** | **2** | 0.1064 |
| ours/release | unanswerable | 2 | 0.0000 |
| uv/release | conceptual | 3 | 0.4953 |
| uv/release | exact | 2 | 0.0000 |
| uv/release | fact | 7 | 0.3482 |
| uv/release | **relationship** | **2** | 0.5710 |
| uv/release | symbol | 1 | 0.0000 |
| uv/release | unanswerable | 2 | 0.0000 |
| uv-ingested/release | conceptual | 3 | 0.3333 |
| uv-ingested/release | **exact** | **2** | 0.2500 |
| uv-ingested/release | fact | 5 | 0.5519 |
| uv-ingested/release | **relationship** | **2** | 0.5710 |
| uv-ingested/release | symbol | 1 | 0.0000 |
| uv-ingested/release | unanswerable | 2 | 0.0000 |

Seventeen gated rows, and they are thin in two different ways.

**Six are blessed at 0.0000** — `unanswerable` everywhere, `symbol` on both `uv` sets, `exact`
on `uv/release`. A slice at zero cannot regress, so G3 cannot fail those rows however bad they
get, and it equally cannot notice one that improves and then falls back.

**Of the eleven rows G3 *can* fail, five hold two cases or fewer**, and `exact` on our own
release set holds **one**. On a one-case slice the smallest possible move is that case's entire
range; on a two-case slice it is half. A −2 % threshold there is not a sensitive gate — it is a
gate that cannot be tripped by anything *except* a single case, and that is tripped by every
single case, including ones moving for reasons that have nothing to do with retrieval quality.
This one moved because a word in a new heading outranked a lucky match.

That is a **benchmark-design** defect, not a gate-threshold one, and it is filed as roadmap
**4.20** rather than fixed here: the remedy is more judged cases in the thin slices, or not
gating them, and both are judgment work that must not travel with a retrieval change
([`eval/README.md`](../../eval/README.md)'s conjunction, and the reason 3.15 → 3.17 and
4.11 → 4.12 were each split in two).

## What the diagnosis exposed, measured but not adopted

The mechanism — `signs` matching nothing because the corpus says `signed` — is a product
defect with an obvious candidate: FTS5 ships a `porter` tokenizer. Measured in memory over the
same chunks, all four sets, so roadmap **4.19** starts from evidence:

| set | ships (`unicode61`) | `porter unicode61` |
|---|---:|---:|
| ours/dev | 0.5361 | 0.5295 |
| ours/release | 0.4499 | **0.5972** |
| uv/dev | 0.4025 | 0.4204 |
| uv/release | 0.3056 | **0.4032** |

It does answer r-0011: `relationship` on ours/release goes 0.106 → **0.531**, and `fact` on
both release sets gains 45 % and 47 %. **And it fails gate G3 as a straight swap** —
ours/release `conceptual` 0.451 → 0.375 (**−16.8 %**) and `exact` 0.983 → 0.958 (−2.5 %) —
which is the same shape as every candidate in ADR-0041: a large win, one slice paying for it.
Recorded so that 4.19 begins knowing it, and so that nobody reads the +32 % as a free win. The
variant worth measuring first is *expansion* rather than replacement — index both the surface
form and the stem, so `exact` keeps its literal match — which is 4.19's work, not this item's.

## Alternatives Considered

- **Re-judge r-0011 so the slice recovers.** Rejected, and it would have been easy to dress up:
  no retrieval change is in flight here, so the frozen-set guard would have allowed it. The
  judgment is right on the document's own terms; the retrieval is what is wrong. This is the
  failure `tools/check_frozen_release_sets.py` exists to make hard, and the guard permitting a
  change is not the same as the change being honest.
- **Loosen G3, or exempt thin slices from it.** Rejected: the gate is reporting something real
  — that slice's number *did* halve. The defect is that the slice cannot distinguish causes,
  which is fixed by giving it cases, not by lowering what is asked of it.
- **Ship stemming here, since it fixes the case that started this.** Rejected: it fails G3 on
  our release set, it is a store-schema change requiring a re-index, and folding a retriever
  change into the change that diagnosed the slice would destroy the single-variable discipline
  that made the diagnosis possible in the first place.
- **Treat this as dilution and accept it.** Rejected by the same table that proves it was the
  corpus: `conceptual` rose 19.1 % over exactly those fifteen documents. "More documents make
  retrieval worse" is not what happened; one query was standing on one weak word.
- **Add the instrument as a CI gate.** Rejected: it compiles the corpus twice and needs a git
  ref to compare against, and a gate that has to be told what "before" means is a question a
  human asks, not a check a runner runs. BUG-0014's reasoning still holds.

## Consequences

- **Roadmap 4.17 closes**, with both its questions answered and neither answer implemented
  here — the actions are 4.19 (stem the index) and 4.20 (thin slices).
- **`relationship` 0.1064 stands as the honest number** and is not re-blessed. It records that
  one of the two cases is not served by a lexical retriever at all, which is true.
- **A new instrument, `tools/measure_slice_decay.py`.** Point it at any ref and it separates
  "the corpus grew" from "the retriever changed", per slice and then per case. This is the
  question that went unanswered for two milestones, and it now takes one command.
- **The dev/release split earns its keep a third way.** ADR-0031 recorded it catching an
  overfit; ADR-0041 recorded it catching a regression the release gate could not see; here the
  *release* set caught a decay the dev set never showed — and the reason the decay was
  legible at all is that the two sets are scored side by side.
- **A third finding, filed as 4.21**: two of five query terms matched no document, and nothing
  in the product says so. `mycelium_explain` is the trust surface (spec 04 §2); reporting
  unmatched terms would have turned this afternoon into a single command.
- **Nothing in the query path changed**, no set was edited, and no baseline was re-blessed.

## References

- Spec 04 §2 (explain), §3 (field weights), §7.1 (dev/release split), §7.3 (gate G3); D-010
- [BUG-0014](../bugs/2026/08/BUG-0014-g3-compares-incomparable-corpora.md) — why G3 cannot
  enforce across a corpus change, and therefore why this decay was invisible
- [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md) — the "large win, one slice
  pays" shape the stemming measurement repeats
- `python tools/measure_slice_decay.py 9adad70 --set release` — the table above, re-runnable
