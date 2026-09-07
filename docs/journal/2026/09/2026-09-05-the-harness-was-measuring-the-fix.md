# 2026-09-05 — the harness had been measuring the fix for four milestones (roadmap 4.28)

- **Session scope:** roadmap 4.28 — a correctly stemmed function word can outrank a
  definition; decide between an IDF floor, a stop-list, and a content-word test now that
  4.26 has grown the sets (spec 04 §3, ADR-0044/0048/0054).
- **PR:** #80 (`feat/stem-idf-floor`). Follows #79 (4.26), merged as `908be68`.
- **Milestone 4:** 4.28 done; 4.23, 4.25, 4.29, 4.32–4.35 open.

## The branch is named after the fix I did not ship

I opened `feat/stem-idf-floor` because the item names an IDF floor on the stem side first
and it is the one that sounds principled: a stem that reaches most of the corpus is not
evidence, so put a floor under it. Measuring the document frequencies took twenty minutes
and refused it outright.

| corpus | function words | the corpus's own vocabulary |
|---|---|---|
| this repository | `what` 36.9 %, `does` 22.4 % | `adr` 60.0 %, `document` 40.4 % |
| `uv`'s documentation | `what` 1.1 %, `mean` **2.8 %** | `uv` 88.0 %, `package` 43.3 % |

There is no threshold. Not "no threshold these sets can settle" — the classes are not
ordered by frequency at all, because a self-describing corpus's central nouns are as
ubiquitous as its function words. And the direction is backwards on top of that: BM25
already discounts by IDF, so the stem that broke `u-0007` hurt **because it is rare**.
`mean` occurs in *zero* chunks of uv's documentation as a surface word and reaches sixteen
through its stem — which `--explain` now prints, and which I only looked at because the
floor had already failed.

The third candidate collapsed on inspection: a content/function-word test without a
part-of-speech model *is* a stop-list, and a model is refused by D-013.

## Then the small failure turned out to be the small half of a large one

The item, and ADR-0054 before it, measured `u-0007` through the harness. The harness calls
`terms_of(query)` before it searches. **The product does not.** So:

```text
$ mycelium search "what does resolution mean" --path eval/corpora/uv-docs
  1 …/export.md#cyclonedx-sbom-format/what-is-cyclonedx/0
  …
  5 …/resolution.md#/0        <- the judged definition
```

`what` and `does` matching a *heading* at twice a body's weight. No stem involved, at the
shipped stem weight, on the case the item was filed about — and the harness reported that
case as **1.000**.

The stop-list has been in `mycelium.eval.retrievers` since the grep baseline was written,
where its docstring says what it is for: words a grep user would not bother typing, removed
from both retrievers so neither gets an easier question. It was never a model of the
product. It has been hiding a product defect for four milestones and seven ADRs.

Scored through the product's own tokenisation, uv/dev reads **0.510** where the harness
reported 0.673. And the sentence I did not expect to be able to write: measured against its
own committed baselines, **the product as it stood would have failed gate G3** — `fact`
−4.8 % on ours/release, `relationship` −12.0 % on uv/release. The only enforcing gate in
this project was being passed on the product's behalf.

## What shipped, and the discipline that constrained it

The list moves into `mycelium.retrieval` and the lexical leg drops those words; the vector
leg still gets the whole question, because an embedder reads grammar — and the comment in
`HybridRetriever` that already *claimed* "the lexical leg inside `search` still tokenises as
it always did" is now true.

**Its membership is not re-chosen.** That was the temptation: `my` and `one` are not in it,
and `u-1004` would score better if they were. Choosing words against these sets is precisely
the fitted parameter 4.28 was filed to avoid, and adopting an artifact that predates the
measurement cannot be fitted to it. So it ships exactly as it has been.

**The mechanism is closed, not just the symptom.** `MyceliumRetriever` now scores
`retrieval.search` rather than re-implementing it. Fusion over one rank list preserves that
list's order, so it moved no case on any set — checked case-by-case first, then left as the
standing check that `query: stopped` scores exactly `baseline (ships)`.

## The loss is the interesting number

`u-1004` — "how do I pin one package to a specific index" — goes 1.000 → 0.333. Its judged
section is titled *"Pinning a package to an index"*, so `to` and `a` were matching a heading
and carrying the right answer for the wrong reason: the same mechanism as the `u-0007`
failure, pointing the other way. Giving that up is correct rather than merely net-positive,
and I would rather the item recorded it than that the aggregate hid it. `u-1008` moves
0.000 → 0.356 in the other direction.

## A change the evaluation cannot see

`mycelium eval` reads 0.501 / 0.586 / 0.615 — unchanged, because the harness has been
measuring this since before it existed. All gates pass, G3 enforcing five of six slices on
both frozen corpora. So the argument had to come from somewhere else, and that is why two
instruments landed rather than two paragraphs: the `query:` family, and `--stems`. A refusal
nobody can re-run is a claim, and so is a fix whose only evidence is that the numbers did
not move.

## What stays open, by decision

`u-0007` at stem weight 0.09. `mean` cannot go in the list — it is a content word in "the
arithmetic mean" — and the shipped 0.05 keeps the case at rank 1 with a 1.8× margin. The
item's literal request is answered with a refusal, which is the honest close. If anyone ever
raises `STEM_WEIGHT`, this is the case to re-examine first.
