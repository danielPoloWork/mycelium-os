# ADR-0057: Drop the function words, and score the seam that ships

- **Status:** Accepted
- **Date:** 2026-09-05
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.28 (this item), 4.23 (where it was filed), 4.19, 4.26; RFC-0001;
  spec 04 §§3, 7.1; D-010, D-013;
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md),
  [ADR-0048](0048-index-the-stem-beside-the-surface-form.md),
  [ADR-0050](0050-report-what-each-query-term-reached.md),
  [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md),
  [ADR-0054](0054-gate-the-query-not-the-documents.md)

## Context

Roadmap 4.28 was filed at 4.23 with a bounded, specific failure: `means` stems to `mean`,
which is morphologically correct and semantically empty, and at a stem weight of 0.09 and
above the uv dev case `u-0007` ("what does resolution mean") loses its definition to a
passage whose only claim on the query is the phrase "this means that". ADR-0054 bounded it
by shipping `STEM_WEIGHT = 0.05` — a 1.8× margin to that edge — and named three candidate
fixes, all thresholded heuristics: an IDF floor on the stem side, a stop-list, or a
content/function-word test. None could be calibrated while 0.0003 separated two candidate
weights and one case decided a slice, so the item waited for roadmap 4.26 to grow the sets.

4.26 has landed. Measuring the item first inverted its premise, twice.

**The IDF floor's premise is false.** Its idea is that a function word is identifiable by
being everywhere. Measured on both corpora (`tools/measure_ranking.py --stems`), document
frequency does not separate a function word from a corpus's own central nouns:

| corpus | function words | the corpus's own vocabulary |
|---|---|---|
| this repository, 839 chunks | `what` 36.9 %, `does` 22.4 % | `adr` 60.0 %, `document` 40.4 % |
| `uv`'s documentation, 568 chunks | `what` 1.1 %, `mean` 2.8 % | `uv` 88.0 %, `package` 43.3 %, `resolution` 12.0 % |

A floor that dropped `what` on this repository would drop `adr`; one that dropped `mean` on
uv's documentation — at **2.8 %** — would drop everything that corpus is about. And the
direction is wrong in principle as well as in fact: BM25 already discounts by IDF, so the
stem that broke `u-0007` hurt *because it is rare*. `mean` occurs in **zero** chunks of uv's
documentation as a surface word and reaches sixteen through its stem, which `mycelium search
--explain` now says out loud. An IDF floor makes that case worse.

**The bounded failure was the small half of a larger one.** The item, and ADR-0054 before
it, measured `u-0007` through the evaluation harness. The harness calls `terms_of(query)`
before it searches — a stop-list that has lived in `mycelium.eval.retrievers` since the grep
baseline was written, applied to both retrievers so neither got an easier question. **The
product never applied it.** So `mycelium search "what does resolution mean"` searched on
`what` and `does` at full field weight, and returned a section titled *"What is CycloneDX"*
at rank 1 with the judged definition at **rank 5** — at the shipped stem weight, with no
stem involved. The harness reported that case as 1.000.

Scored across the four judged sets, through the product's own tokenisation against the
harness's:

| set | the product | the harness | gap |
|---|---:|---:|---:|
| ours/dev | 0.5332 | 0.5496 | +0.0165 |
| ours/release | 0.4954 | 0.5014 | +0.0060 |
| uv/dev | 0.5101 | 0.6727 | **+0.1626** |
| uv/release | 0.5772 | 0.5858 | +0.0086 |

And the sentence that settles it: measured against its own committed baselines, **the
product as it stood would have failed gate G3** — `fact` −4.8 % on ours/release,
`relationship` −12.0 % on uv/release. The only enforcing gate in the project was being
passed on the product's behalf by a harness that normalised the query first.

## Decision

**Refuse all three of the item's candidates for the case it was filed about, and fix the
larger instance the measurement found.**

1. **The IDF floor is refused on evidence**, above: the classes are not separable by
   document frequency, and the offending stem is rare rather than common. This is not a
   "cannot calibrate on thin sets" refusal — there is no signal to calibrate.
2. **The content/function-word test collapses into the stop-list.** Any test that does not
   ship a part-of-speech model *is* a list, and a model is out (D-013: offline, no weights).
3. **The stop-list ships — in the product, where it was missing.**
   `mycelium.retrieval.query_terms` drops function words before the **lexical** leg, and the
   vector leg is still given the whole question, because an embedder reads grammar. The list
   moves to `mycelium.retrieval` and the harness imports it, so there is one definition
   rather than two that can drift.

**Its membership is not re-chosen here.** The list is adopted exactly as it has been for
four milestones. Choosing which words belong in it, on these sets, would make it the fitted
parameter the item warned about; adopting an artifact that predates the measurement cannot
be fitted to it.

**And the mechanism that hid this is closed.** `MyceliumRetriever` scored
`store.search_chunks` directly — a re-implementation of the query path — which is why no
number anywhere could show the divergence. It now goes through
:func:`mycelium.retrieval.search`, the seam the CLI and the MCP server use. Fusion over a
single rank list preserves that list's order, so this moved **no case on any set**: verified
case-by-case before the change, and re-verifiable as `query: stopped` scoring exactly
`baseline (ships)`.

**`u-0007` at stem weight 0.09 is still not fixed, and must not be.** `mean` is a function
word in *this* query and a content word in "the arithmetic mean", so it does not belong in a
stop-list; and the shipped weight is 0.05, where the case does not occur. The margin stands
where ADR-0054 left it — 1.8× — and the item's literal request is answered with a refusal.

## What it costs, and the numbers

`python tools/measure_ranking.py --release` — `query: raw` is the product before this
decision, `query: stopped` is the product now.

| set | `query: raw` | `query: stopped` | Δ |
|---|---:|---:|---:|
| ours/dev | 0.533 | **0.550** | +0.017 |
| uv/dev | 0.510 | **0.673** | +0.163 |
| ours/release | 0.495 | **0.501** | +0.006 |
| uv/release | 0.577 | **0.586** | +0.009 |

**The change trades cases, and the losses are the interesting half.** `u-1004` ("how do I
pin one package to a specific index") goes 1.000 → 0.333: its judged section is titled
*"Pinning a package to an index"*, so `to` and `a` were matching a **heading** at weight
2.0 and carrying the right answer for the wrong reason. That is the same mechanism as the
`u-0007` failure, pointing the other way — which is what makes giving it up correct rather
than merely net-positive. `u-1008` ("how do I add a dependency to my project") goes
0.000 → 0.356 the other way. Four more cases move by under 0.05 in each direction.

**The evaluation shows almost nothing, and that is the finding.** `mycelium eval` reads
0.501 / 0.586 / 0.615 on the three corpora — unchanged, because the harness has been
measuring this fix since before it existed. Gates G1, G3, G4, G5, G6 pass on all three, with
G3 enforcing five of six slices on both frozen corpora. A change whose only visible effect
is that the *instrument* now agrees with the *product* has to be argued from the product,
which is what the table above is for.

**Latency.** One list comprehension per query, and a shorter MATCH expression than before.
Query p95 unmoved at 18 ms against a 150 ms budget; G5 unchanged.

## Alternatives Considered

- **An IDF floor on the stem side** — refused on measurement, above. The premise that
  function words are the common ones is false on both corpora, and BM25 already applies IDF.
- **A content/function-word test** — collapses into a stop-list without a POS model, and a
  model is refused by D-013 (offline by default, no weights).
- **Extend the list** so that `mean` is dropped in "what does X mean". Rejected: `mean` is a
  content word elsewhere, and choosing membership against these sets is exactly the fitted
  parameter roadmap 4.28 was filed to avoid.
- **Down-weight function words instead of dropping them** — a floor on their field
  contribution rather than removal. Rejected as the same thresholded heuristic in a new
  place, with no evidence that the middle is better than the end: the harness has run the
  drop for four milestones and it is the behaviour every published number describes.
- **Strip in the store's query builder** rather than at the retrieval seam. Rejected: a
  `Store` that silently rewrites the query it is handed is a store that cannot be trusted to
  answer what was asked, and the seam is where serving policy already lives (ADR-0024).
- **Remove the stripping from the harness instead**, so the evaluation reports what the
  product does. It would have made the numbers honest by making them worse, and left the
  product answering "what does resolution mean" with "What is CycloneDX". The harness was
  right and the product was wrong; the fix belongs where the defect is.
- **Leave `MyceliumRetriever` on `store.search_chunks`** and fix only the product.
  Rejected: that leaves the blind spot open for the next query-path change, and closing it
  costs nothing — proved, not assumed.

## Consequences

- **A user's question is answered by its content words.** `mycelium search "what does
  resolution mean"` returns the definition at rank 1 rather than rank 5. The MCP server gets
  it for free — same seam.
- **`--explain` reports the terms that ran, and names the ones that did not.** A note gives
  the query the lexical leg actually used and the words dropped; the per-term table covers
  only what was searched, because a report crediting a word the search never used explains
  someone else's query (ADR-0050).
- **The published numbers are now the product's.** Every nDCG in `README.md`, in the
  baselines and in seven earlier ADRs was measured through `terms_of`. They do not move
  here — but before this change they described a query path no user had, and now they
  describe the shipped one.
- **The harness scores the product's seam.** A query-path change can no longer reach the
  product without reaching every measurement of it. The cost is that the harness's numbers
  now depend on `retrieval.search`'s fusion, which for a single leg is order-preserving and
  tested as such.
- **The run manifest records the boundary** (`stopwords: 33`), so a reader of an older
  manifest can tell whether it predates this decision.
- **Two instruments are added rather than described.** `tools/measure_ranking.py` gains the
  `query:` family — the only rows in that file that vary the query rather than the index or
  the ranking — and `--stems`, which prints the document-frequency table that refuses the
  IDF floor. A refusal nobody can re-run is a claim.
- **`u-0007` at 0.09 remains open by decision**, not by omission: the weight bounds it, the
  stop-list must not contain `mean`, and no fix that survives inspection exists. If the stem
  weight is ever raised, this is the case that has to be re-examined first.

## References

- Measured this session, on `main` at `908be68`, both corpora built with `--no-pin`:
  the four-set product-vs-harness table; the stem document-frequency tables; the
  `query: raw` / `query: stopped` rows with gate G3's own verdict on the former.
- `python tools/measure_ranking.py --release --stems` re-runs all of it.
- [ADR-0048](0048-index-the-stem-beside-the-surface-form.md) and
  [ADR-0054](0054-gate-the-query-not-the-documents.md) — the stem side, and the weight that
  bounds the case this item was filed about.
- [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md) — which
  sets a gate can live on, and therefore which of the numbers above G3 enforced.
