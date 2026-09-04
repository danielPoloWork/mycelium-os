# 2026-09-04 — one clause, two rules (roadmap 4.23)

- **Session scope:** roadmap 4.23 — reach for a query with no literal foothold, the gap
  ADR-0048 filed when it gated stem expansion behind a surface hit (spec 04 §3, D-010).
- **PR:** #75 (`feat/reach-without-a-literal-foothold`). Follows #74 (4.22), merged as
  `26bd4ae`.
- **Milestone 4:** 4.23 done; 4.25, 4.26, 4.27 open, and 4.28 + 4.29 filed here.

## The measurement said the item was about something else

The item asked for reach: *"a query whose every word is inflected differently gets
silence."* Before designing anything I asked how much that silence costs, by finding every
judged case with no surface hit on any term across all four sets.

Ten cases. **All ten are `unanswerable`.** Not one answerable case is blocked by the
missing reach. The gap the item was filed to close has no headroom on the judged evidence,
and the two mechanisms it proposed — document frequency of a stem against its surface
forms, a query-side morphological signal — would both have been thresholded heuristics
built to serve a case that does not exist.

That is not a reason to close the item unread. It is a reason to look at what the
precondition *actually* costs, which turned out to be a different thing entirely.

## The clause was doing two jobs and only one of them was needed

ADR-0048's expression is `X AND (X OR Y)` — surface, then surface-or-stem. Written out, it
says two things:

1. **This query** must have a literal footing in the corpus.
2. **Every candidate document** must carry one of the query's words as written.

Abstention needs only the first. The second was excluding documents that share a word's
inflection and nothing else — and that is where the reach was. So: split them. The gate
becomes one `LIMIT 1` probe of the corpus, and the search that follows is open.

No threshold anywhere, which matters because the item's own warning was that *"both are new
heuristics with thresholds, so neither may be chosen on the thin slices 4.20 is open
about"*. A word either appears in the corpus as written or it does not.

## The weight was not a free parameter, and then it was, and then it was not

Removing the duplicated clause removes the extra weight it gave the surface columns, so the
stems get relatively more say than 0.1 was chosen to give them. The dev sets located the
same balance at half the number:

```text
weight   ours/dev    uv/dev      sum
ships      0.5417    0.6527   1.1944      <- ADR-0048, expand-pre 0.1
 0.025     0.5307    0.6124   1.1431
 0.05      0.5496    0.6727   1.2223      <- shipped
 0.075     0.5493    0.6727   1.2220
 0.1       0.5533    0.6358   1.1891
```

Unimodal, with a peak over 0.05–0.075 — and 0.05 against 0.075 is 0.0003 on 32 dev cases,
which is nothing. I did not break that tie on the release sets. I broke it on the margin to
the nearest **observed failure**, and finding that failure is the useful part of the
session: at 0.09 and above, dev case `u-0007` ("what does resolution mean") loses

> Resolution is the process of taking a list of requirements and converting them to a list
> of package versions…

to a passage whose only claim on the query is the phrase "this **means** that". `means`
stems to `mean`. The stem match is morphologically *correct* and semantically empty.

I checked whether that was a judgment problem before treating it as a retrieval one, by
reading both chunks. It is not: the judged chunk defines resolution and the other is about
lockfile version preferences. The case measures what it claims to, so the parameter has to
respect it. 0.05 sits furthest from that edge — 1.8×, narrower than the 3.5× ADR-0048 had,
and the ADR says so rather than rounding it up.

## What the release sets said afterwards

Read after the fact, never tuned against: `uv/release` 0.5483 → 0.5620, `uv-ingested`
0.6469 → 0.6556, ours 0.4982 → 0.4978. **Every point of the gain is in `fact`**, and nothing
else moves by more than a rounding wobble. G3 enforces on both frozen sets and passes —
the first change measured against the headroom-free baselines 4.22 blessed yesterday, which
is what makes the pass mean anything.

`fact` is roadmap 4.25's open concession, and the gap to `grep` on `uv/release` narrows from
0.093 to 0.066. It does not close. 4.25 stays open, and it is worth noticing *why* the
movement is confined to that slice: the candidates this change admits are documents sharing
an inflection and nothing else, which is what a "how do I do X" query has and a definitional
one does not.

## The safety property, measured rather than argued

| | ADR-0048 | open expansion | this |
|---|---:|---:|---:|
| eight footholdless unanswerable cases | 0 | 0 | 0 |
| `r-0014` | 0 | **13** | 0 |
| `u-0010` | 0 | **5** | 0 |

The same search without the gate answers two out-of-domain queries out of two corpora that
hold nothing of the sort. That is the whole reason the gate survives, and it is why "just
remove the precondition" was never available. G4 reads 0.00 % on all three corpora, and p95
went 18 ms → 17 ms: the probe's expression is a subset of the search's own, so it touches
pages the search is about to touch anyway.

## The guard that caught me

The first draft of ADR-0054 spelled out one of `r-0014`'s words while explaining the
over-stemming that makes it dangerous — and
`test_no_corpus_document_answers_an_unanswerable_case` failed, naming the file and the term.
This repository's documentation is its corpus, so writing that word into an ADR makes an
`unanswerable` case answerable and turns G4 red on the prose. ADR-0048 hit this exact trap
and added the test; I hit it while amending ADR-0048. It is BUG-0007's family, and the
test paid for itself twice now.

## Filed rather than absorbed

**4.29**: a hypothesis property test over the Markdown adapter failed once inside a
full-suite run and passed a second full run of the same tree. It touches nothing this change
touched, persisted no falsifying example, and its per-example runtime is 1–5 ms against a
200 ms deadline — so I filed it without a theory, and with the two cheap changes that would
make the next occurrence diagnosable instead of lost: an explicit hypothesis profile (the
project sets no `deadline` anywhere) and a persisted example database in CI. Same family
as 4.18.

**4.28**: a correctly stemmed *function* word can outrank a definition. The weight bounds it
at 0.05 and does not fix it, and every fix is a heuristic with a threshold — an IDF floor on
the stem side, a stop-list, a content/function test — so it wants 4.26's set sizes first.
`tools/measure_ranking.py` carries `index: expand-gate <w>` so the sweep is one flag, which
is the difference between a filed item and a remembered one.
