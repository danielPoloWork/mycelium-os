# ADR-0047: Flip the packed chunker on, and let the gate say so

- **Status:** Accepted
- **Date:** 2026-09-03
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.15; RFC-0001; spec 03 §5, spec 04 §7.1, §7.3;
  [ADR-0007](0007-adopt-structure-first-chunking.md),
  [ADR-0029](0029-let-a-judgment-name-a-section.md),
  [ADR-0031](0031-refuse-three-rerankings.md),
  [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md),
  [ADR-0042](0042-let-an-atomic-block-share-its-chunk.md) (which this completes),
  [ADR-0045](0045-ask-the-documents-whether-two-runs-are-comparable.md);
  [BUG-0019](../bugs/2026/09/BUG-0019-pack-atomic-does-not-invalidate-the-chunk-cache.md);
  D-008, D-010

## Context

ADR-0042 measured `[chunking] pack_atomic` and shipped it **off**, on a rule rather than a
doubt: flipping a default moves chunk boundaries, moving a boundary deletes an anchor, and
re-judging the cases that lose one is a change to the judgments. One change may move the
retriever or the judgments, not both (spec 04 §7.1, ADR-0027). So it named the sequence —
4.12 re-anchors, 4.15 flips — and closed with the reason 4.15 would have nothing to clear:

> the gate meant to catch a bad chunking change is blind to chunking changes by
> construction.

Both preconditions have since landed. Roadmap 4.12 re-anchored the six judgments a moved
boundary invalidated, from the documents rather than from a ranking. Roadmap 4.13
(ADR-0045) split the corpus fingerprint in two — `content`, what the corpus says, and
`chunks`, how it was cut — so gate G3 enforces across a re-cut corpus instead of excusing
it. This item is the flip, and it is the first change either of those was built for.

## Decision

**`pack_atomic` is on by default**, in `ChunkingConfig` (the shipped default) and in
`ChunkingPolicy` (the chunker's own), because a policy whose default differs from what ships
is a trap for the next caller. `pack_atomic = false` still produces exactly the boundaries
ADR-0007 shipped: this is a default, not a removal.

The verdict was read **before** anything was re-blessed, which is the order that makes the
gate mean something. On both vendored corpora G3 reported *"the same documents cut
differently — a chunking change, enforced rather than excused (ADR-0045), no slice
regressed"*. Only then were their baselines re-blessed. This repository's own baseline is
**not** re-blessed here: it predates several corpus changes, could not be stamped at 4.13,
and deciding what to do about it is roadmap 4.22 — so ours stays a reported delta.

## What it measures

Release sets, `mycelium` retriever, before → after:

| corpus | nDCG@10 | R@10 | MRR | chunks | G3 |
|---|---|---|---|---:|---|
| ours/release | 0.450 → **0.463** | 0.667 → 0.667 | 0.442 → 0.492 | 946 → 745 | reported (stale baseline, 4.22) |
| uv/release | 0.306 → **0.492** | 0.536 → 0.714 | 0.238 → 0.438 | 2244 → 568 | **enforced**, no slice regressed |
| uv-ingested/release | 0.385 → **0.647** | 0.583 → 0.833 | 0.386 → 0.645 | 2073 → 624 | **enforced**, no slice regressed |

Per slice, nothing regresses on any release set. The largest movements are `relationship`
(uv 0.571 → 0.852, ingested 0.571 → 0.852), `conceptual` (uv 0.495 → 0.755, ingested
0.333 → 0.687) and `exact` (uv 0.000 → 0.500, ingested 0.250 → 0.815). `symbol` and
`unanswerable` are flat at 0.000 on both.

**Against the incumbent (D-010).** The grep baseline moves too — it maps its hits onto the
same chunks — so the comparison has to be re-taken rather than assumed:

| corpus | mycelium | grep | verdict |
|---|---:|---:|---|
| ours/release | 0.463 | 0.271 | mycelium ahead, +71 % |
| uv/release | 0.492 | 0.519 | **still behind, −5.2 %** (was −35 %) |
| uv-ingested/release | 0.647 | 0.610 | mycelium ahead, +6.1 % |

Roadmap **4.8 stays open**. On the corpus that item is about, the product still loses; what
changed is the size of the loss, from 35 % to 5 %. Reporting that as a win because two other
corpora improved is exactly the move D-010 exists to forbid.

**Against ADR-0042's own predictions.** It expected uv/release 0.280 → 0.451 and ours/release
0.472 → 0.473. The measured `off` figures are now 0.306 and 0.450, because 4.12's
re-anchoring and this repository's own growth moved the pre-flip line between then and now.
The direction and the shape hold; the magnitudes do not transfer, and the numbers above are
the ones to reproduce.

**Dev sets** — reported, and the one place a loss appears: ours/dev 0.535 → 0.512, uv/dev
0.403 → 0.561, uv-ingested/dev 0.409 → 0.501. The ours/dev regression is **not** bookkeeping:
every judged anchor in both `ours` sets survives the flip (checked directly against the
published chunks), so a dev set that tuning is allowed to see got genuinely worse while the
frozen set it must not see got better. That is the honest asymmetry, recorded rather than
smoothed.

One anchor does not survive, and it is in a derived set: `u-0012` in
`uv-docs-ingested/eval/dev.jsonl` names an ordinal the packed chunker deletes, so one of its
twelve cases scores zero for bookkeeping. Those sets are *generated* (ADR-0039, BUG-0018), so
the fix is to re-run their generator — which is a judgment change, and this change moves the
retriever. Filed as roadmap 4.23.

## Alternatives Considered

- **Re-anchor `u-0012` here**, since dev sets are not frozen and the guard would allow it.
  Rejected for the reason ADR-0042 rejected the same offer for the four `ours/dev` cases: the
  guard covers release sets because that is what a machine can check, not because dev
  judgments are fair game. One change moves the retriever or the judgments.
- **Re-bless this repository's own baseline while re-blessing the others.** Rejected: it
  cannot be stamped (4.13 established that), so re-blessing it would silently answer 4.22's
  question — *should ours be gated at all, on a corpus that grows every PR* — in the middle of
  a chunking change.
- **Flip only `ChunkingConfig` and leave `ChunkingPolicy` at `False`**, on the reading that
  the shipped default lives in the config. Rejected: `chunk_document` takes `policy=None`, so
  a direct caller would then get boundaries no build produces. Two defaults for one behaviour
  is a defect waiting for a caller.
- **Ship the flip without fixing the cache key.** Not really an alternative once
  [BUG-0019](../bugs/2026/09/BUG-0019-pack-atomic-does-not-invalidate-the-chunk-cache.md) was
  found: `pack_atomic` was absent from the chunk stage's config slice, so every existing
  installation would have upgraded into the new default and kept the old boundaries, with a
  build that reported success. The flip is the operation the defect suppresses.
- **Weaken the golden's coverage assertion** from `{prose, table, code}` to `{prose, table}`,
  since packing removes the corpus's only `code` chunk. Rejected — that assertion exists
  precisely to stop a change from quietly narrowing the gate. The fixture corpus gains a
  section whose only content is a block instead, which also puts ADR-0007's preserved
  constraint into the golden.

## Consequences

- **Every corpus is re-chunked once** on the next build after upgrading. Anchors that name a
  section are unaffected; anchors that name an ordinal inside a multi-chunk section may move,
  which is what 4.12 re-anchored the judged sets for. A consumer holding stored
  `mycelium://…#section/2` citations should expect `ANCHOR_GONE` and re-resolve — the case
  ADR-0010 built that error for.
- **A citation is larger.** On the second corpus the median chunk goes 27 → 136 tokens, so a
  reader handed one is handed roughly five times more text. ADR-0042 recorded this as the
  cost side of the trade and roadmap 6.7 is where it becomes measurable; nothing here settles
  it.
- **The determinism golden moves**: 24 lines changed, 21 chunks (20 after packing, plus the
  new solitary-block section). Smaller than 4.15's own forecast of "every chunk moves",
  because the six-document fixture corpus has few atomic blocks — the forecast was written
  from the vendored corpora, where the effect is 2244 → 568.
- **Spec 03 §5's wording is updated in this change**, not merely deviated from: tables and
  code blocks are never *split*, and may now *share*. ADR-0042 kept the sentence literally
  true by shipping off; that is no longer available, so the sentence changed (AGENTS.md §7).
- **`BuildEnv.chunk_slice` gained a member**, so the environment digest moves for every
  repository and the first build after upgrading recompiles the corpus. Correct rather than
  unfortunate: it needed re-chunking anyway.

## References

- ROADMAP 4.15 (this item), 4.11 (the measurement), 4.12 (the re-anchoring), 4.13 (the gate),
  4.8 (the incumbent gap this narrows and does not close), 4.22 and 4.23 (what it defers).
- Spec 03 §5 (chunking policy), spec 04 §7.1 (frozen release sets), §7.3 (the gates).
- Measured this session on three corpora, `--no-pin` builds throughout (ADR-0046), with the
  G3 verdict read before any baseline was re-blessed.
