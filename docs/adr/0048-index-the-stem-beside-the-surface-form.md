# ADR-0048: Index the stem beside the surface form, and let the surface gate it

- **Status:** Accepted
- **Date:** 2026-09-03
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.19 (this item), 4.17 (the diagnosis), 4.20, 4.23 (filed here);
  RFC-0001; spec 03 §8, spec 04 §§3, 7; D-010, D-016; NFR-5;
  [ADR-0008](0008-adopt-sqlite-store-behind-a-store-protocol.md),
  [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md),
  [ADR-0031](0031-refuse-three-rerankings.md),
  [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md),
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md)

## Context

FTS5's `unicode61` tokenizer does no stemming. `signs` does not match `signed`,
`contributed` does not match `contribution`, and a query that inflects a word differently
from the document simply misses it. Roadmap 4.17 found this the hard way: a judged
`relationship` case was reaching its answer through the single word `off`, because the
other four terms of its query matched nothing in a corpus that says `signed` and
`contribution`.

ADR-0044 recorded the obvious candidate and refused it. SQLite ships a `porter` tokenizer;
swapping it in wins overall and **fails gate G3**, which is ADR-0041's "large win, one
slice pays" shape for the tenth time. Re-measured here against today's corpus and today's
chunker, the swap still fails, and now on *both* release sets:

| set | ships (`unicode61`) | `porter unicode61` | worst slice |
|---|---:|---:|---|
| ours/release | 0.4627 | 0.5843 | `conceptual` **−18.6 %** |
| uv/release | 0.4920 | 0.5768 | `exact` **−18.5 %** |

The two failures name the mechanism between them. Replacing the tokenizer replaces the
*surface form*: the index then holds only stems, so a document that spells the query's word
exactly becomes indistinguishable from one that merely inflects it. `exact` pays directly.
`conceptual` pays because its queries share stems with many documents at once.

4.19's instruction followed from that: measure **expansion** before replacement — keep the
surface form and add the stem beside it, so a literal match keeps its edge.

## Decision

**The lexical index carries six indexed columns: `text`, `title`, `heading_path`, and a
stem column for each.** Stems come from an in-repo Porter (1980) implementation
(`mycelium.store.stemming`), written at index time and at query time. The stem columns
carry `STEM_WEIGHT = 0.1` of the same field's surface weight, so spec 04 §3's title 3.0 /
heading 2.0 / body 1.0 is stated once and holds on both sides.

**A surface hit is the precondition for a stem hit.** The MATCH expression is

```text
{surface} : (terms) AND ( {surface} : (terms) OR {stem} : (stems) )
```

so stems *reorder* the documents the surface index already found and can never introduce
one of their own. That is [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md)'s
rule one layer down — the weaker signal is gated by the stronger — and it is not a
refinement, it is what makes the change shippable. Without it the change **fails gate
G4**, and it fails it for a real reason rather than a metric artefact: Porter conflates
`escapement` with `escape`, so a query for `escapement tourbillon mainspring` retrieves
five documents about escape hatches out of a corpus with no watchmaking in it. G4 counts
that as a false answer because it is one.

Everything else stays: one virtual table, one BM25 computation, no fusion stage, no
re-ranking pass, and `unicode61` still the tokenizer. Adding columns is a store-schema
change, so `SCHEMA_VERSION` goes to `mycelium/store/v4` and existing stores are recreated
under the D-016 rebuild policy — a reader meeting a v3 store refuses it rather than
reinterpreting it, which is the behaviour that surfaced during this work when the vendored
corpora had to be rebuilt.

**Prefix queries are not stemmed.** `sign*` already reaches `signs`, `signed` and
`signature`; stemming it would add candidates the caller did not ask for while removing the
precision that made them ask for a prefix.

## What it costs, and the numbers

Developed on the dev sets, gated on the release sets, no judgment touched
(`tools/measure_ranking.py` carries the family, so every row is re-runnable).

| set | ships | `porter` | **shipped** (expand + precondition) | open expansion |
|---|---:|---:|---:|---:|
| ours/dev | 0.5120 | 0.5164 | **0.5310** | 0.5540 |
| ours/release | 0.4627 | 0.5843 | **0.5077** | 0.5454 |
| uv/dev | 0.5611 | 0.5995 | **0.6530** | 0.6358 |
| uv/release | 0.4920 | 0.5768 | **0.5484** | 0.5784 |

Per slice on the release sets, against what ships today — **no slice regresses on either**:

| slice | ours before | ours after | uv before | uv after |
|---|---:|---:|---:|---:|
| `conceptual` | 0.4819 | 0.4965 | 0.7554 | 0.8784 |
| `exact` | 0.9942 | 0.9942 | 0.5000 | 0.6505 |
| `fact` | 0.4384 | 0.4602 | 0.3863 | 0.4033 |
| `relationship` | 0.1687 | 0.3461 | 0.8522 | 0.8522 |

`exact` is held or improved everywhere, which is the hypothesis the item was filed to test.
`relationship` on our own release set doubles — 4.17's case is retrieved again — and the
third corpus (`uv-docs-ingested`) reaches 0.647 with G3 enforcing and no slice regressed.

**The stem weight is not tuned to a gate.** The dev sets were swept first, and every value
from 0.05 to 0.25 clears G3 on both release sets while 0.35 and above fails it on
`conceptual` by −12 %. The dev curve is a plateau over that whole region — 1.15 to 1.22 as
a two-set sum, against 1.07 for what ships — with a nominal peak at 0.05–0.075 that 32 dev
cases cannot resolve (4.20's finding, applied to ourselves). 0.1 is an order of magnitude
below the weakest surface field, which is the *shape* of the answer, and it sits with a
3.5× margin to the measured cliff. Shipping at 0.25 would have bought a third of a percent
and stood on the edge of it.

**The precondition bounds the reach it buys.** A query *none* of whose words the corpus
spells literally gets silence — `signs` alone still misses a document that says `signed`.
That is the same situation as the watchmaking query seen from the other side, and nothing
in the index can tell the two apart: over-stemming is why one of them must be refused, and
the precondition refuses both. Measured on the judged sets the trade is clearly worth it,
and closing the gap needs something the index does not have — filed as roadmap **4.23**
rather than approximated with a heuristic here.

## Alternatives Considered

- **Swap the tokenizer to `porter`.** The one-line change, and the largest win on our own
  release set (0.5843). Rejected: fails G3 on `conceptual` (ours, −18.6 %) and on `exact`
  (uv, −18.5 %), because it deletes the surface form the `exact` slice is about. Refused
  once by ADR-0044 and re-refused here against a corpus and chunker that have both moved.
- **Expansion without the precondition.** Better than the shipped variant on three of four
  sets and it **fails gate G4**: `escapement` → `escap` answers a watchmaking query out of
  this corpus. G4 is enforced, not comparability-dependent (NFR-5), and a retriever that
  invents an answer is worse than one that misses it. The numbers are in the table above so
  the cost of the precondition is visible rather than asserted.
- **A second FTS table with the `porter` tokenizer, fused with the first.** No stemmer to
  write — SQLite does it — and no schema column changes. Rejected: fusing two BM25
  rankings is a new ranking stage with a new weight, which is the shape ADR-0031 and
  ADR-0041 have refused ten times between them. Columns in one table express the same
  trade-off through the field-weight mechanism spec 04 §3 already uses, with one BM25
  computation and nothing to tune but the weight this ADR measures.
- **A stemmer dependency (`snowballstemmer`, `PyStemmer`).** Rejected: the lexical path is
  the *default* path, so this would be a hard runtime dependency on a closure kept to four
  packages (D-013). Porter (1980) is 200 lines, and SQLite's own C implementation of the
  same algorithm is already in the process — which makes it checkable rather than merely
  written: `test_agrees_with_sqlites_own_porter_tokenizer` stems every word of the
  determinism corpus both ways and requires agreement.
- **Porter2 / Snowball English** instead of Porter (1980). Rejected: it would forfeit that
  cross-check for a stemmer whose known improvements are in areas this corpus does not
  exercise, and `escapement`/`escape` conflates under both.
- **Expand only query terms whose stem is unambiguous in the corpus** — a document-frequency
  test that would let `signs` through and stop `escapement`. Rejected: it is a new heuristic
  with a new threshold, decided on the same thin slices 4.20 is open about, and the
  precondition achieves the safety property with no parameter at all.
- **Re-bless the release baselines here.** Rejected: 4.22 owns that decision explicitly and
  says it cannot ride along with a retrieval change. The consequence is stated below rather
  than fixed in passing.

## Consequences

- **Store schema v4, and every existing store is rebuilt.** A tokenization change is not
  migratable, which is exactly the case D-016's rebuild policy exists for; a *reader* on an
  older binary refuses a v4 store and says to rebuild.
- **Two new public names**, `mycelium.store.STEM_WEIGHT` and `expanded_query`, and a new
  module `mycelium.store.stemming`. The store's own schema stays an implementation detail
  (ADR-0008): nothing outside `mycelium.store` names a column.
- **Index size grows.** The three stem columns roughly double the FTS index's term
  instances. On this repository the store went from 770 chunks indexed over three columns
  to the same chunks over six; query p95 moved from 14 ms to 16 ms against a 150 ms budget,
  so gate G5 is unmoved.
- **The run manifest records `stem_weight`**, because a number measured on one index cannot
  be compared with a number measured on another and the manifest is where a reader finds out
  which they are holding.
- **Gate G6 did not move.** The determinism golden observes chunk records, and stems live
  only in the index — so a store-schema change with a large retrieval effect re-blessed
  nothing, which is the golden observing the right things (ADR-0012).
- **The release baselines are now conservative.** They record the pre-change numbers, so G3
  has roughly ten points of headroom on the vendored sets until 4.22 decides how ours is
  re-blessed. That is a real hole — a later change could give this gain back and still pass
  — and it is 4.22's to close, now with the retriever we actually ship as its reference.
- **Roadmap 4.23 is filed**: reach for a query with no literal foothold, which the
  precondition deliberately gives up.

## References

- ROADMAP 4.19 (this item), 4.17 (where the defect was diagnosed), 4.20 (thin slices),
  4.22 (the baselines), 4.23 (filed here).
- Spec 03 §8 (the store DDL), spec 04 §3 (the lexical leg and its field weights — this
  extends the column set and keeps the tokenizer and the three surface weights it names),
  spec 04 §7 (dev/release discipline, the gates).
- `python tools/measure_ranking.py --release` — every number in this ADR, re-runnable, with
  the refused variants kept beside the shipped one.
- [ADR-0025](0025-make-lexical-evidence-the-vector-legs-precondition.md) — the precondition
  pattern this reuses.
- [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) — the diagnosis, and the
  first measurement of the swap.
