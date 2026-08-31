# 2026-08-31 — the split caught me (roadmap 3.18)

- **Session scope:** roadmap 3.18 — the grep incumbent beats the product on the second corpus,
  and D-010 says fix the product.
- **PR:** #48 (`fix/rank-short-chunks`). Follows #47 (3.17), merged as `d7a241b`.
- **Milestone 3:** 3.1–3.17 done; **3.18 stays open**, deliberately.

## The diagnosis is the good part

Printing what actually comes back first, on the dev set:

```text
'what does resolution mean'   1. [  8t code ] resolution.md#resolution-strategy/1
'uvx'                         2. [  3t code ] guides/tools.md#running-tools/1
'what is a workspace'         1. [ 18t prose] internals/metadata.md#…/2
```

Three-, eight-, eighteen-token fragments above the paragraphs that answer. BM25 normalises by
document length; our "documents" are chunks of wildly different sizes; a three-token code fence
with the query term has maximal term density and wins. On our own corpus — long prose sections
— it barely shows. On task documentation full of command blocks it dominates.

That is why the shape of the loss was worth reading: winning Recall@50 while losing nDCG, MRR
and Recall@10 said the right passages were *there*, ranked below the wrong ones.

## Three tries

**A length prior** takes the second corpus from 0.403 to 0.636 and ours from 0.546 to 0.484.
Refused — and the reason is not "it needs tuning": **short chunks are sometimes the answer.**
`## License` and one line is 24 tokens and answers "what licence is this" completely. Length
cannot separate an answer from a fragment. That is the third time this milestone that a
threshold looked decisive and could not tell two populations apart.

**Coverage-first** — prefer passages containing more distinct query terms, which is what grep
ranks by — loses on *both* corpora. Whatever grep does right, it is not term coverage. I would
have guessed otherwise.

**Section aggregation** — one section competes once, represented by its best chunk — improved
**both** dev sets, carried no constant, and had a clean story. I implemented it, updated the
tests, and ran the gates.

## G3 failed it on the held-out set

`conceptual` 0.3770 → 0.1836, **−51.3 %**. `fact` −14.6 %. Reverted.

This is the machinery from 3.13 working on its first real use, on its author. Everything about
that change looked like a change that should ship: two corpora improved, no free parameter, a
principled justification, and a test pinning the property. The only thing that said no was the
set I had not been allowed to look at while building it.

Without the dev/release split it would have shipped, with a table of improvements attached, and
the regression would have surfaced whenever someone next measured something else.

## What I did not let myself do

The release regression is concentrated where judgments are still chunk-exact, and section
aggregation returns a *different chunk of the right section* — which scores zero against a
chunk-exact judgment. So there is a real chance part of that −51 % is bookkeeping rather than
retrieval.

That is a hypothesis, not an exemption. Acting on it here would mean re-judging cases so a
change passes, which is precisely what `check_frozen_release_sets.py` refuses and precisely
what D-010 warns about. The order that makes the answer mean anything is: judge those cases
from the documents, *then* re-test the ranking. Written into 3.18 as the next step.

## Why 3.18 is still unchecked

The item asked for a fix. Three were measured and none survived. I could tick it and lead with
"diagnosed", the way 3.14 was ticked for reaching a decision — but 3.14 asked for a decision and
this asks for a fix. A roadmap whose boxes are ticked for effort rather than outcome stops
being a roadmap.

What the item gained is a diagnosis specific enough to work from, three eliminated candidates,
and `tools/measure_ranking.py` so the next attempt starts from evidence rather than from this
entry's prose.
