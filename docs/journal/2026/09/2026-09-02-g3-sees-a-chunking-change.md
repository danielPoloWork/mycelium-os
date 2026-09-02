# 2026-09-02 — the gate that could not see the change it was for (roadmap 4.13)

- **Session scope:** roadmap 4.13 — gate G3's comparability test conflated *what the corpus
  says* with *where its boundaries fall*, so the gate meant to catch a bad chunking change
  was blind to chunking changes by construction.
- **PR:** #65 (`fix/gate-g3-sees-a-chunking-change`). Follows #64 (4.17), merged as `4995c96`.
- **Milestone 4:** 4.13 done; 4.8, 4.14, 4.15, 4.18–4.21 open.

## The shape of the bug is worth stating precisely

G3 enforces the 2 % per-slice rule only when the corpus is the one its baseline was taken
on, and reports otherwise. That conditional is right and [BUG-0014] earned it: this
repository's documentation *is* its corpus, so adding an ADR moves every slice, and a gate
that fails on documentation teaches everyone to re-bless on red.

The fingerprint it tested was the fold of chunk digests. Which means: **any** change to
chunk boundaries makes the two runs "not comparable", and G3 abstains. `pack_atomic`
(4.11) moves every boundary in every corpus. So the one change class G3 is best placed to
judge — one that moves the retrieval unit, deletes anchors, and cannot be read off a diff —
was the only one it could never see. 4.15 was scheduled to land with, in its own words, "no
gate G3 verdict to lean on".

## The first option had a trap in it

4.13 offered three routes. The obvious one — digest the documents instead of the chunks —
looks like a one-liner, because `Document.content_digest` is right there. It is a digest of
the file's text **including its frontmatter**, and frontmatter is where the build pins
`mycelium_id`. Keying on it reproduces BUG-0014's root cause exactly one field along: on an
unpinned corpus every build mints fresh ULIDs, so the fingerprint never matches, and the
gate would silently stop enforcing forever — in CI first, which is the only place it
matters.

So the content fingerprint is built from chunk *text*, which carries no identity: per
document, whitespace collapsed and concatenated in document order, folded over documents
sorted by path. Two questions, two folds, and G3 enforces on the first while reporting the
second.

One detail cost a re-read of the store API. `chunks_of()` returns rows ordered by *anchor*,
and anchors sort lexicographically — `…/10` before `…/2`. Concatenating in that order would
make the result depend on how many chunks a section has, which is precisely what the
content fold must not be able to see. It sorts on each chunk's line span instead.

## Measured, on every corpus that has a baseline

`pack_atomic` off, then on, same documents:

| corpus | chunks | chunk fold | content fold |
|---|---|---|---|
| this repository | 932 → 731 | moved | **identical** |
| uv-docs | 2244 → 568 | moved | **identical** |
| uv-docs-ingested | 2073 → 624 | moved | **identical** |

The uv number reproduces ADR-0042's exactly, which is the check that the measurement is of
the thing 4.15 will actually do. The same property is a test on a synthetic corpus, so a
future change to the chunker or to the fingerprint that breaks the relationship fails in CI
rather than in someone's memory.

## Stamping is not re-blessing, and the difference is the whole point

The three committed baselines had no content fingerprint, so G3 would have fallen back to
comparing boundaries and abstained — exactly the abstention 4.15 needs not to happen. The
temptation is to re-bless. That defeats the purpose: **a baseline re-blessed from the change
under test cannot gate that change.**

So `tools/stamp_baseline_fingerprints.py` adds the field and moves no number, and it earns
that by refusing. Before writing, it rebuilds each corpus and compares the *chunk* fold
against what the baseline already recorded. If that has drifted, the recorded scores
describe a different corpus and a content fingerprint taken today would attach today's
corpus to yesterday's numbers — so it refuses and says re-bless deliberately. A migration
that cannot tell itself apart from a re-bless is a re-bless.

**It refused on our own corpus on the first run**, which was the useful part of writing the
check. Our documentation grows with every PR, so that baseline has been stale — and G3
correctly abstaining on it — since long before this session. Nothing here can fix that:
stamping it would attach today's corpus to numbers taken on a corpus that no longer exists,
and re-blessing it moves numbers, which 4.13 may not do. The two vendored corpora stamped
cleanly, so uv/release is the gate 4.15 has to clear; ours stays a reported delta, and the
decision behind it — on a self-hosting corpus G3's comparability test is *structurally* never
satisfied, so what is a committed baseline for? — is filed as **4.22**.

## The other half, and what it was

4.15's text said the frozen-set guard "would not actually catch this pairing" because
`src/mycelium/config.py` was missing from `TUNING_PATHS`, and named 4.13 as the item to
close it. It was already closed — PR #61 added the path when it put `pack_atomic`'s default
in `ChunkingConfig`. What was missing was any test, so the entry could be removed again by
someone reading `config.py` as configuration plumbing rather than as the retriever's shipped
defaults. `tests/test_frozen_release_sets.py` covers the pairing, and asserts that every
guarded path still exists — a guard naming a file that has moved guards nothing, silently,
and its failure mode is that the conjunction it exists to refuse sails through.

Both of 4.15's claims about its own preconditions are corrected in the roadmap rather than
left to be discovered by whoever picks it up.

## What is deliberately not in this change

No retrieval change, no chunker change, no judgment change, and no per-slice number moved.
The flip itself is 4.15's, and it now has a line to be measured against.
