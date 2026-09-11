# 2026-09-11 — the promise that was wrong in one half (roadmap 5.13)

- **Session scope:** roadmap 5.13 — spec 03 §3.1 promises callouts compile to atomic chunks
  and the chunker never implemented it (spec 03 §§3.1, 5, doc 08 §7; ADR-0007, ADR-0077).
- **PR:** #112 (`feat/callouts-are-atomic-chunks`). Follows #111, merged as `e04c026`.
- **Milestone 5:** 5.13 done. 5.14–5.19 and 5.21 open.
- **ADR:** [ADR-0085](../../../adr/0085-let-a-callout-bound-a-chunk-rather-than-atomise-one.md).

## Two options were offered and both were wrong in the same place

The item put it as a fork: *"Either the chunker implements what the profile promises, or the
profile stops promising it."* Reading the two specifications against each other before writing
anything showed a third answer, and it is the interesting part of this change.

`atomic` for a table means **never split**, because half a table is not a table and half a
fence is not runnable. That is what ADR-0007 protects and why `_ATOMIC_KINDS` holds exactly
those two kinds. A callout is not that shape at all: it is a *container of blocks*, and the
adapter emits its paragraphs as children. Half a callout is readable prose.

And doc 08 §7 already knew it. The `chats` module's contract says the chunking unit is the
message *and* that **"oversize messages split at paragraph boundaries per the standard chunker
rules"** — the exact opposite of never-split. So implementing spec 03 §3.1 literally would
have broken doc 08 §7 by construction, and the two specifications had been disagreeing with
each other in silence.

The answer is that a callout **bounds** rather than atomises. Its blocks pack with each other
and never with anything outside it. That delivers all three things the two documents between
them asked for: two consecutive callouts are two chunks, a callout never merges with the prose
beside it, and an oversize one splits where its author put a paragraph break. Spec 03 §3.1's
cell is amended to say so — right about the merging, wrong about the splitting — which
AGENTS.md §7 permits explicitly and which is the honest disposition when the code is correct
and the sentence is not.

## The forecast cost was almost entirely absent, and I checked before building

The item forecast *"a G6 re-bless and three baseline re-blesses with the per-slice diff in the
PR body"*, and warned that `check_frozen_release_sets.py` would refuse the conjunction with any
judgment change.

Counted first: across all three judged corpora — 144 documents here, 81 in the vendored `uv`
documentation, 81 in its ingested twin — there are **zero** callout nodes. The only callout in
the repository is in the gate G6 fixture. So no baseline moved, there was no per-slice diff to
report, and the conjunction never arose.

That turns the decision around. This is the cheapest moment this change will ever have, and it
gets more expensive with every corpus that adopts the profile — which is an argument for doing
it now rather than for deferring it again.

## Widening the gate rather than merely re-blessing it

The fixture had one callout, which would have covered the syntax and not the rule: a single
callout cannot show that two consecutive ones stay apart. So `retries.md` gains a second,
consecutive callout with two paragraphs, and the golden goes 27 → 29 chunks: the prose before
them, and each callout, are three chunks where they were one. Everything else is
byte-identical, and the coverage test pins the three anchors and their line spans so a later
edit cannot narrow it — the guard ADR-0047 added for the solitary code chunk, reused.

## What I did not do

**A fourth `ChunkKind`.** `kind` describes content — a table is not prose, a fence is not
prose — and a callout's content is prose in a box. A new enum member would change one of the
five contracts that freeze at 1.0 in exchange for a distinction nothing reads.

**Remove the `chats` module's heading.** With the core implementing the promise, the
workaround is no longer load-bearing — but it had a second reason that survives: a section slug
is the only thing that gives a message a re-read-stable anchor, and without one a conversation's
messages would be told apart by ordinal, so inserting a message would move every anchor after
it. The module's docstring now says which of its two reasons is left, and records that the cost
it stated is closed. Its tests pass unchanged, because a message inside the ceiling was one
chunk before and is one chunk now.

## Lesson

When one specification's sentence cannot be implemented without breaking another's, the fork
on offer is usually a false one. The useful question is not *which document wins* but *which
half of each is right* — here, the merging half of one and the splitting half of the other,
which compose into a rule neither had written down. Reading both before writing any code cost
twenty minutes; implementing either literally would have shipped a contradiction with a test
suite proving it.
