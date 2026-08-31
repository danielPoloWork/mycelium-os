# 2026-08-31 — the notation ships, the re-judging does not (roadmap 3.15)

- **Session scope:** roadmap 3.15 — decide whether a judged anchor names a chunk or a
  section, after ADR-0027 found three cases measuring anchor-guessing rather than retrieval.
- **PR:** #45 (`feat/judged-anchor-granularity`). Follows #44 (3.14), merged as `7a60bb9`.
- **Milestone 3:** 3.1–3.15 done; 3.16 open, 3.17 and 3.18 filed by this item.

## Measuring the change before making it

Section-scope was applied to the *existing* judgments, without editing them, to see what it
would move:

| set | chunk-exact | section-scoped |
|---|---:|---:|
| ours / dev | 0.567 | 0.567 |
| ours / release | 0.453 | 0.457 |
| uv / dev | 0.403 | 0.403 |
| uv / release | 0.249 | **0.335** |

It moves what the diagnosis predicted and nothing else — our anchors were already
chunk-accurate, theirs were not — and **no comparison changes direction**. A change of unit,
not of verdict, which is what made it safe to adopt with the numbers in view.

## The decision, and the part of it I nearly got wrong

A judgment may name either, and the notation says which: a trailing slash means the section.
My first instinct was to make section-scope the *default*, since it is more robust. That is
wrong, and the reason is worth keeping: a reader who gets chunk 7 when the answer is in chunk
4 **did not get the answer**. Section scope credits the right neighbourhood, and a rule that
cannot tell "found it" from "landed near it" is generous in exactly the direction that
flatters us.

Two smaller things I would have got wrong by not thinking:

- **Credit once.** A section split into twelve chunks would otherwise let a retriever fill
  the top ten with one section and score a perfect run for finding a single thing.
- **The trailing slash is load-bearing.** A heading can slug to digits (`## 2024`), so a bare
  `doc#2024` cannot be told apart from ordinal 2024 of the lead section.

## Not re-judging, on purpose

The sets still judge chunks, a test asserts it, and every number is unchanged — verified, not
assumed. Re-judging is 3.17.

The reason is a rule I built two items ago and then had aimed at me:
`check_frozen_release_sets.py` refuses a change that edits a release set *and* touches the
metrics. This change touches the metrics. Splitting it in two is the rule working, on its
author, in the first case where it was inconvenient — which is the only test of a rule that
counts.

## The finding this item was not looking for

Running the grep baseline on the second corpus for the first time — CI only ever ran it on
ours — the incumbent **wins**:

| | mycelium | grep |
|---|---:|---:|
| nDCG@10 | 0.249 | **0.409** |
| MRR | 0.227 | **0.401** |
| Recall@10 | 0.429 | **0.536** |
| Recall@50 | **0.857** | 0.643 |
| p95 latency | **14 ms** | 195 ms |

D-010 is not ambiguous about this: "if Mycelium OS does not visibly beat grep on these tasks,
the correct response is to fix the product, not the benchmark."

The shape of the loss is the useful part. Winning Recall@50 while losing nDCG, MRR and
Recall@10 means the right passages **are** in the candidate set and come back below the wrong
ones — a ranking failure, not a retrieval one. On short imperative task pages our field
weights (title 3.0, heading_path 2.0) and BM25's length normalisation are the first suspects.
Filed as 3.18, to be developed against the dev set, which is what dev sets are for.
