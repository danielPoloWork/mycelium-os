# 2026-09-03 — the gate the instrument could not see (roadmap 4.19)

- **Session scope:** roadmap 4.19 — stem the lexical index without paying for it in
  `exact`.
- **PR:** #69 (`feat/stem-the-lexical-index`). Follows #68 (4.18), merged as `1ad442b`.
- **Milestone 4:** 4.19 done; 4.8, 4.20, 4.21, 4.22 open, plus 4.23 filed here.

## The item said measure expansion first, and it was right

ADR-0044 had already measured the obvious fix — swap FTS5's tokenizer to `porter` — and
refused it: a large win with one slice paying, ADR-0041's shape for the tenth time. 4.19's
instruction was to measure *expansion* instead: keep the surface form, add the stem beside
it, so a literal match keeps its edge.

Re-measured against today's corpus and today's chunker, the swap fails harder than it did
when ADR-0044 wrote it down — on **both** release sets now, `conceptual` −18.6 % on ours
and `exact` −18.5 % on uv. The two failures name the mechanism between them: replacing the
tokenizer replaces the surface form, so the document that spells your word exactly becomes
indistinguishable from the one that merely inflects it.

Expansion does what the item predicted. `exact` is held or improved on all four sets while
the overall number rises 8–18 %. The hypothesis was right and the measurement was easy.

## Then the real gate spoke

`tools/measure_ranking.py` said expansion at a stem weight of 0.1 was the best variant on
three of four sets. `mycelium eval --gate` said:

```text
FAIL G4 Abstention: false-answer rate 50.00% on 2 unanswerable case(s); limit 5%
```

The instrument could not see it. `measure_ranking.py` scores answerable cases only — that
is in its own code, `if case.answerable` — so the `unanswerable` slice and gate G4 are
outside its view entirely. A whole afternoon of sweeps had been measuring three quarters of
the question.

And it was not a metric artefact. The failing case is `escapement tourbillon mainspring`,
deliberately absent from a knowledge compiler's corpus. Porter stems `escapement` to
**`escap`**, which is also the stem of `escape` — and this repository is full of escape
hatches. A query about watchmaking retrieved five documents about `mycelium build --clean`.
Answering what you cannot answer is worse than missing it, and G4 exists to say so.

## The fix was already in the codebase, one layer up

ADR-0025 settled this shape for the vector leg: the weaker signal may reorder what lexical
evidence found and may not introduce a document of its own. The same rule, one layer down,
is the whole fix — **a surface hit is the precondition for a stem hit**:

```text
{surface} : (terms) AND ( {surface} : (terms) OR {stem} : (stems) )
```

`escapement tourbillon mainspring` has no surface hit, so there is nothing for the stems to
reorder and the retriever abstains. 4.17's `relationship` case has `off` as a foothold, so
the stems lift its answer from rank 26 back into view. Shipped numbers: ours/release 0.463
→ 0.508, uv/release 0.492 → 0.548, the ingested corpus 0.647, `relationship` on ours 0.169
→ 0.346, no slice regressed on any release set, G1/G3/G4/G5 green on all three corpora.

It cost about a third of open expansion's gain. That is in the ADR's table rather than left
out of it, because a precondition whose price is invisible reads like a free lunch.

## What the tests found that I had not

Two of them failed on their first run, and both were my prose being wrong rather than the
code:

- `signs` **alone** does not reach a document that says `signed`. There is no surface hit,
  so the precondition abstains — the same input as the watchmaking query, and no property
  of the index distinguishes them. Reach is conditional on the query having a literal
  foothold, which is a real limitation and is now `test_a_query_with_no_literal_foothold_still_misses`
  and roadmap 4.23.
- The "literal edge" is not a *ranking* for a single-word query; the inflection-only
  document is excluded outright. Both tests now say what actually happens.

## On not tuning the weight to the gate

The stem weight is the one free parameter and the temptation was obvious, so the order is on
the record: dev sets swept first, release read afterwards, and the whole sweep reported
rather than the value that survived. Dev is a plateau from 0.05 to 0.35 — 1.15 to 1.22 as a
two-set sum against 1.07 for what ships — with a nominal peak at 0.05–0.075 that 32 dev
cases cannot resolve. Release says 0.05–0.25 all clear G3 and 0.35 fails on `conceptual`.

0.1 ships because an order of magnitude below the weakest surface field is the *shape* of
the answer — a stem is weaker evidence than the word the author wrote — and because it
leaves 3.5× margin to a measured cliff. 0.25 was inside the passing region too, and would
have bought a third of a percent while standing against that cliff.

## Loose ends I did not tie

The release baselines still record the pre-change numbers, so G3 now has ten points of
headroom on the vendored sets — a later change could give this gain back and pass. That is
4.22's decision and it says explicitly it cannot ride along with a retrieval change; it
should now re-bless against the retriever we actually ship. Gate G6 did not move at all,
which is worth noticing: a store-schema change with a large retrieval effect re-blessed
nothing, because stems live only in the index and the golden observes chunk records.
