# 2026-09-04 — a line drawn against a corpus that no longer existed (roadmap 4.22)

- **Session scope:** roadmap 4.22 — re-bless our own release baseline, and settle whether a
  baseline a gate can never enforce on should exist at all (spec 04 §7.1, §7.3; BUG-0014).
- **PR:** #74 (`feat/rebless-our-release-baseline`). Follows #73 (4.20), merged as `ff7777d`.
- **Milestone 4:** 4.22 done; 4.23, 4.25, 4.26 open, and 4.27 filed here.

## The item was two questions and it was right that they are one

The first was mechanical: our baseline described a corpus that no longer exists, so re-bless
it. The second was the real one: on a corpus whose documentation grows with every PR, G3's
comparability test is *never* satisfied, so does a file full of per-slice thresholds nobody
can trip belong in the repository at all?

They are one question because the answer to the second decides what the first is *for*. If
the baseline is only a gate threshold, it should go — it will never gate. It is not only
that. G3 **reports** the deltas against it on every run, and since ADR-0052 it carries the
per-case scores behind every slice mean, which is the only continuous per-case record of our
own corpus there is. So it stays, and what it must never be is stale: a report against a
corpus that no longer exists is not a weaker measurement, it is a number that looks like one.

Stated as a contract: **G3 reports on the set whose documents we author, and enforces on the
two we do not.** In ADR-0053, in `eval/README.md`, in the root README — and, the part a
reader actually meets, in the verdict itself, which now says the report branch is the
*standing* state on a self-hosting corpus rather than a transient one. The tool pointer
(`measure_slice_decay.py`) stayed out of the product's output: it is this repository's
script, not something an installed user has.

## The number that looked like a regression, and was not

```text
exact 0.9833 -> 0.7560 (-23.1%)      # the verdict that prompted the item
```

That reads like a product regression and is a population change. `exact` held **one** case
at the bless and holds four now (4.20), and the case the 0.9833 was measured on —
`r-0003` — reads **0.9942** today. `relationship` tells the same story from the other side:
0.1064 → 0.2600 over four cases, but 0.1064 → **0.3013** over the two it already held.

That is the whole argument for per-case scores in a baseline, made by the first bless that
has them. A slice mean at these sizes cannot distinguish a retriever from a population, and
the only way to read one is to have kept the cases.

## The item proved itself by accident

I blessed, then wrote the ADR and this entry, then rebuilt out of habit. One document and
eight chunks added to a 115-document corpus moved **four per-case scores and both overall
means** — ours 0.4998 → 0.4982, the incumbent's 0.3332 → 0.3306, `r-0019` 0.4777 → 0.4375 as
the new ADR competes with the documents its case names. Nothing about retrieval changed.

A −0.3 % move caused by writing the document that explains why this gate cannot enforce here
is a better argument than the one I had written. It also means the committed baseline is one
documentation edit behind the tree that merges it, and there is no fixed point to chase:
recording *that* would move it again. So CI will report on our set in this PR, which is the
contract doing its job on its first run.

## The item did not mention the sets a gate *does* enforce on, and it should have

`eval/README.md` had already filed it here: the two vendored baselines predated 4.19's
stemming index, which moved every release set up nine to eleven points. So the only
*enforcing* gate in the project was carrying nine points of headroom — a change that gave
the entire stemming gain back would have passed G3. Re-blessed: `uv/release` 0.4920 → 0.5483,
`uv-ingested` 0.5911 → 0.6469, no slice down on either. `uv-ingested` also gained the `grep`
entry it never had.

One check worth naming: `uv/release`'s **grep scores are identical** before and after, to six
decimals. That is the frozen corpus proving it is frozen, and the incumbent proving it does
not read our index. If that row had moved, the bless would have been measuring something
other than what it claims.

## Two things found and filed rather than absorbed

- **`r-0018` scores 0.0000.** "Can an agent keep querying while a build is running" — the two
  documents hold the two halves of the answer and the query uses neither's noun. Added at
  4.20, its score recorded by nothing until this bless. It is *not* 4.23's inflection
  failure: every word in that query appears in the corpus as spelled. It is the shape graph
  expansion exists for, so it is noted on **5.3**, which now has a named case and a before.
- **The roadmap has two 4.23s** — one closed inside 4.15, one open from 4.19. Filed as
  **4.27** rather than fixed here, and the restraint is the point: the open one is cited by
  name in ADR-0048 (an *Accepted* record), in two tests and in the CHANGELOG, so renumbering
  is a five-file change — inside a PR whose entire thesis is that a re-bless rides along with
  nothing. I had already made the edit before noticing the irony, and reverted it.

## What the next re-bless should know

It is now a documented act rather than a judgement call: its own PR, the per-slice diff in
the body, no retrieval or judgment change alongside, and the per-case attribution read before
any slice is called a regression. The remaining limit is not the sets but their slices — four
rows on the vendored sets still cannot carry a gate (ADR-0052), which is 4.26's to widen.
