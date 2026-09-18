# 2026-09-18 — the guard cost more than the leg (roadmap 6.21)

- **Session scope:** roadmap 6.21 — measure the vector path at the reference profile, which
  6.4 built the corpus for and deliberately did not measure.
- **PR:** `feat/measure-the-hybrid-path`. Follows #164, merged as `767965c`.
- **Milestone 6:** 6.21 closed, 6.27 filed.
- **Decision it records:** [ADR-0130](../../../adr/0130-measure-the-vector-path-and-retire-three-disagreeing-extrapolations.md).

## The item understated the problem

It said the project makes *one* extrapolation about the vector path at 10⁵. It makes **three**,
in three files, and they disagree:

- the benchmark: **~70 ms** on a fresh process, citing ADR-0026;
- `search_vectors`'s own docstring: **~31 ms**, citing ADR-0030;
- `measure_vector_index.py`: 10⁵ is *"where the exact scan misses the budget"* — which ADR-0030
  had disproved.

ADR-0030 did this work in August and its finding is precise: ~71 ms is the *re-map-per-query*
pattern BUG-0015 found no code path has, and the first query in a process costs ~31 ms. The
benchmark never received that correction. It still prints the harness number, under the label
the ADR took away from it, sourced to the ADR the same ADR corrected. Five milestones.

Measured through `search_vectors` rather than over a bare matrix: **43.2 ms** fresh, **12.1 ms**
warm. Both inside spec 04 §1's 60 ms budget. Both previous numbers wrong, in opposite
directions — and the warm one is the larger error, twelve times rather than one, because a
`numpy` memmap skips the pack resolution, the SQL filters and the hydration of fifty results
that the method performs.

## What the run was not looking for

`search` decides whether to run the vector leg by asking `store.vector_counts()`. That is a
`GROUP BY` over the whole `vectors` table, **once per hybrid query**, and at 10⁵ rows it costs
**129.9 ms** — three times the leg it guards, eleven times the warm leg, 87 % of NFR-2's whole
budget, to answer *does this snapshot hold vectors for this model*. Filed as 6.27; fixing it
inside the item that measured it is how a measurement stops being trustworthy.

It is the same shape 6.18 took off the configuration path and 6.25 still owns on the import
path: a per-call cost paying for a fact that does not change between calls.

## Two obstacles and two instrument defects

**Every chunk in the reference profile shared one `chunk_digest`.** Harmless while the profile
was lexical — `chunks_fts` does not carry the column — and fatal here, because vectors are
keyed on it: the profile would have held one vector for a hundred thousand chunks. The digest
now derives from the anchor, outside the generator's rng stream, so the prose stays
byte-identical and no published lexical figure moves.

**And two defects in my own instrument, both caught before they produced a number**, both of
BUG-0015's family — a harness measuring something the product does not do:

1. It read which legs ran off the **last** query and reported `lexical` for a pass in which the
   vector leg had run on 34 of 39. The hybrid figure is now split by whether the leg actually
   ran, with counts, because ADR-0025 withholds it where the lexical leg found nothing and
   those queries cost 1.9 ms rather than 1 288.
2. The stand-in embedder drew 384 gaussians in Python **inside the timed region**, so the
   harness's own cost was being charged to retrieval. Query vectors are precomputed now, and
   the real model's `embed_query` is timed separately at 9.7 ms and excluded on purpose.

The second would have inflated the headline by milliseconds on a one-second measurement — small
enough to publish without noticing, which is exactly why it is worth writing down.

## Lesson

A correction is not applied until every copy of the number is found. ADR-0030 corrected the
cost model and two files kept the old figure, one of them still citing the superseded ADR — so
the project carried three disagreeing answers to a question it had already settled. Grep for
the number, not just for the decision.
