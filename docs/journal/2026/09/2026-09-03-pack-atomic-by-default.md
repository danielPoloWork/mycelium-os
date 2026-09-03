# 2026-09-03 — the flip, and the cache that would have swallowed it (roadmap 4.15)

- **Session scope:** roadmap 4.15 — flip `pack_atomic` on by default.
- **PR:** #67 (`feat/pack-atomic-by-default`). Follows #66 (4.14), merged as `5a8fa6a`.
- **Milestone 4:** 4.15 and 4.23 done; 4.8, 4.18–4.22 and 4.24 open.

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
| uv-ingested † | 0.385 → **0.647** | 2073 → 624 | enforced |

† on the 14-case set both sides; the set itself then changed — see below.

## The number the flip does not earn

grep moves with the chunker — it maps its hits onto the same chunks — so the D-010 comparison
had to be re-taken rather than carried over. Re-measured: grep 0.519 against our 0.492 on
`uv`'s documentation. **We are still behind on the corpus 4.8 is about**, by 5 % where it was
35 %. We lead on the other two (0.463 vs 0.271, and 0.591 vs 0.566 on the regenerated ingested set).

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
ordinal packing deletes. I filed that as 4.23 and moved on — and CI proved the deferral
impossible about twenty minutes later.

## The deferral that could not be deferred

`ingest / lanes` runs `tools/build_ingested_cases.py --check`: the derived sets must reproduce
byte-for-byte from the tree. A derived set is a function of the chunker, so a chunking change
that does not regenerate them is red — and a regeneration *without* the chunking change has
nothing to write, because before the flip the generator reproduces exactly what is committed.
No ordering of two pull requests satisfies both guards. The two changes are inseparable, which
is not a preference for bundling but a property of a derived artifact.

The other guard, `check_frozen_release_sets.py`, then refused the regeneration. That rule was a
category error rather than a rule under strain: **nothing in a derived set is judged** — every
query, grade, slice and note is copied verbatim from the frozen source, only the anchor is
computed. So it is replaced rather than relaxed. A derived set may not move in the same change
as *its source*, and reproduction is byte-checked on every run — which is a better guarantee
than "nobody edited this file", and one the old rule never gave.

Regenerating turned out to be good news: `u-1008` and `u-1013` — the two cases BUG-0018 named
as dropped — now clear the coverage floor at 0.87 and 1.00, because packing makes their twin
chunks large enough to cover the judged text. The release set grows 14 → 16.

And then G3 went red: `fact` 0.632 → 0.494. Two restored cases had joined a five-case slice.
Nothing had regressed — scored on the same build, the old 14-case set still gives exactly its
old number — but **G3 cannot see a case-set change**: its comparability test asks about the
corpus, not the judgements. The only available response was to re-bless, which is precisely
the response a gate exists to make unnecessary. Filed as 4.24, and argued by hand here in the
meantime.

## The golden nearly lost a chunk kind

`test_the_corpus_still_covers_the_profile` asserts `{prose, table, code}`, and after packing
the six-document fixture corpus had no `code` chunk left: every block had prose beside it. The
tempting fix is to relax the assertion, which is exactly what that assertion exists to prevent.
The corpus gained a section whose only content is a block instead — which also puts ADR-0007's
preserved constraint (a solitary block is still its own chunk) into the golden, where it is
checked on every run.

The golden diff is 24 lines, not the "every chunk moves" this item forecast. The forecast was
written from the vendored corpora, where the effect is 2244 → 568; the fixture corpus has few
atomic blocks.

## The generator was dirtying the tree

While chasing that, 81 evidence documents turned up modified. `build_ingested_cases.py` builds
both committed corpora, and it built them *pinning* — so every run wrote a `mycelium_id` into
81 tracked files. Harmless on CI, where the checkout is discarded; corrosive locally, and it
would have made the next `--check` fail for a reason unrelated to anything.

The fix is the flag 4.14 shipped one item ago. Four tools that build a committed corpus now
pass `pin_identity=False`. Two items in a row have now found the same shape of defect: work
that writes where it only meant to read.
