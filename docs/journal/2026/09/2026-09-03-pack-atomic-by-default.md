# 2026-09-03 — the flip, and the cache that would have swallowed it (roadmap 4.15)

- **Session scope:** roadmap 4.15 — flip `pack_atomic` on by default.
- **PR:** #67 (`feat/pack-atomic-by-default`). Follows #66 (4.14), merged as `5a8fa6a`.
- **Milestone 4:** 4.15 done; 4.8, 4.18–4.23 open.

## The one-line change had a precondition nobody had checked

The item is a boolean. Before flipping it I wanted to see the setting work on a corpus that
already had a store — and it did not. Turning `pack_atomic` on against an existing
`.mycelium/` changes **nothing**: every document looks unchanged, every `doc_state` row is
reused, the previous boundaries are served under the new configuration, and the build
reports success.

`BuildEnv.chunk_slice` — the whole of what the chunk stage's cache identity knows about its
configuration — carried `target_tokens`, `max_tokens` and the token counter. Not
`pack_atomic`. So the environment digest and the chunk build key were identical either way,
and the two guards that exist to catch a configuration change agreed, wrongly, that none had
happened.

It stayed hidden because every measurement of the setting so far was taken on a fresh store
or with `--clean`, and because `tools/measure_chunking.py` re-chunks in memory from an
explicit policy and never consults the cache. ADR-0042's numbers are unaffected. What would
have been affected is every existing installation upgrading into the new default and keeping
the old boundaries — the flip is precisely the operation the defect suppresses.

[BUG-0019](../../../bugs/2026/09/BUG-0019-pack-atomic-does-not-invalidate-the-chunk-cache.md),
severity high, fixed here. The general shape is worth remembering: a setting was added to the
thing that *computes* (`ChunkingPolicy`) without being added to the thing that *remembers*
(the slice), and nothing forced the two to agree.

## Reading the verdict before re-blessing

4.15's own text says it: *read the verdict before re-blessing, not instead of it.* That is
the whole reason 4.13 existed, so the order mattered more than usual.

Both vendored corpora came back with **"the same documents cut differently — a chunking
change, enforced rather than excused (ADR-0045), no slice regressed"**. G3 enforcing across a
re-cut corpus is the thing ADR-0042 said 4.15 would not have, and 4.13 built one item later.
Only after reading that were the two baselines re-blessed. Ours was not: its baseline could
not be stamped at 4.13, and re-blessing it would have answered 4.22's question inside a
chunking change.

Release sets, before → after:

| corpus | nDCG@10 | chunks | G3 |
|---|---|---:|---|
| ours | 0.450 → 0.463 | 946 → 745 | reported (4.22) |
| uv | 0.306 → **0.492** | 2244 → 568 | enforced |
| uv-ingested | 0.385 → **0.647** | 2073 → 624 | enforced |

## The number the flip does not earn

grep moves with the chunker — it maps its hits onto the same chunks — so the D-010 comparison
had to be re-taken rather than carried over. Re-measured: grep 0.519 against our 0.492 on
`uv`'s documentation. **We are still behind on the corpus 4.8 is about**, by 5 % where it was
35 %. We lead on the other two (0.463 vs 0.271, 0.647 vs 0.610).

Reporting "+61 % and two corpora won" without that line would have been the exact move D-010
exists to forbid. 4.8 stays open.

## Two things the tests refused to let me get away with

**The dev regression is real.** ours/dev goes 0.535 → 0.512. My first instinct was
bookkeeping — a moved boundary deletes an anchor — so I checked every judged anchor in both
`ours` sets against the published chunks: all present. 4.12 had already covered them. So a set
tuning is allowed to see got worse while the frozen set it must not see got better. That
asymmetry is recorded rather than smoothed, because the only honest thing to do with it is
leave it visible.

**One anchor did die**, and it is in a derived set: `u-0012` in the ingested dev sets names an
ordinal packing deletes. Those sets are generated, so the fix is to re-run their generator —
a judgment change, in a change that moves the retriever. Filed as 4.23 rather than slipped in.

**The golden nearly lost a chunk kind.** `test_the_corpus_still_covers_the_profile` asserts
`{prose, table, code}`, and after packing the six-document fixture corpus had no `code` chunk
left: every block had prose beside it. The tempting fix is to relax the assertion, which is
exactly what that assertion exists to prevent. The corpus gained a section whose only content
is a block instead — which also puts ADR-0007's preserved constraint (a solitary block is
still its own chunk) into the golden, where it is checked on every run.

The golden diff is 24 lines, not the "every chunk moves" this item forecast. The forecast was
written from the vendored corpora, where the effect is 2244 → 568; the fixture corpus has few
atomic blocks.
