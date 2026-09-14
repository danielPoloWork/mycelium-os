# 2026-09-14 — the drift was the incumbent's (roadmap 5.42)

- **Session scope:** roadmap 5.42 — re-bless `uv/release` after 5.40 disarmed G3 on it, and
  decide what our own drifted `ours/release` baseline is for.
- **PR:** #141 (`chore/rebless-and-date-the-baseline`). Follows #140, merged as `2124498`.
- **Milestone 5:** 5.42 done. No open follow-ups in M5 — the milestone-exit review is next.
- **ADR:** [ADR-0112](../../../adr/0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md).

## The bookkeeping half did what it was predicted to do

5.40 moved chunk text, G3 disarmed itself on `uv/release`, and ADR-0056 forbade re-blessing in
the same PR. ADR-0110 predicted the re-bless would move `corpus_digest` and
`blessed_from_snapshot` and not one number, and said that if it moved one, that was a finding
rather than a formality. It moved none: every slice and every case is byte-identical to the
values blessed at `b4bc729`, on both arms. G3 is armed again on the only set that enforces it.

## The half worth deciding needed a number nobody could produce

`ours/release` had drifted 0.5232 → 0.5206 on us and 0.2842 → 0.2466 on the incumbent, with no
change responsible. The item offered two answers — re-bless on a cadence, or keep the baseline
old because the drift is the signal — and both are defensible until you know what the drift is.

Measured against `69a433a`, the commit that last blessed it, with judgements, compiler and
scorer held at today's and only the corpus varying, 157 → 173 documents:

| arm | ours/release | recall@50 |
|---|---|---|
| mycelium | 0.5238 → **0.5209** | 0.853 → 0.824 |
| grep | 0.2842 → **0.2466** | 0.618 → 0.618 |
| lead | **+0.2396 → +0.2744** | |

**The whole of the drift is the incumbent's.** Sixteen documents diluted a term-counting
baseline by 13 % and left ours within half a percent. That is D-010's claim — out-ranking the
incumbent under dilution — arriving in G3's verdict as though *we* had regressed.

And it is not a hypothetical misreading. At 5.40 I read that same verdict, saw grep collapse
and `r-0015` go 1.0000 → 0.6309, and came within a paragraph of attributing it to the compiler
change under test. A hand-built controlled arm is what separated them. The decay instrument now
names the same two cases as corpus growth, by ref, with their ranks: `r-0015` first judged hit
1 → 2, `r-0019` 4 → 5.

## Why the cadence, and not "the drift is the signal"

The rejected reading had a real argument behind it: roadmap 4.17 found `relationship` had
halved between two blesses, and it was visible *because* the baseline was old. But the answer to
4.17 was an instrument — `measure_slice_decay.py`, ADR-0044, "the instrument G3 cannot be" — and
an instrument can target any ref on demand. A baseline records drift only since whenever the
last bless happened to be, which is an interval nobody chose. Given the tool, a merely old
baseline is a worse version of it that also makes G3's standing report unreadable.

So: re-blessed once per release, as its own PR, written into the release procedure as step 0
with the two-run rule beside it. It has a moment and an owner instead of depending on somebody
noticing — which is how it reached a 0.038 gap on the incumbent unremarked.

## The instrument could not answer the question it was built for

`measure_slice_decay.py` scored **one arm**, through a direct `store.search_chunks` call. So the
tool for "corpus or code?" was blind to the incumbent — the arm that moves four times as far and
therefore decides how the report reads. It gains `--retriever`, and both arms now go through the
same `build_retriever` the harness uses.

One sentence in that change had to be walked back before it shipped. I had written that the
default "stopped being a lexical-store proxy that agreed with no other number in the project" —
then checked, and it agreed with the harness to four decimals on every slice, because in the
shipped lexical profile the `mycelium` arm *is* a store search. What the change buys is that the
agreement is structural rather than coincidental. Shipping the first version would have been the
overstated docstring this repository keeps finding in its own past work.

## Lesson

Two answers were on the table and both sounded principled, because neither had a number. The
number took one command that did not exist yet — and building it was cheaper than the argument
would have been. When a decision rests on "is the drift signal or noise", the thing to build
first is the instrument that can tell you, not the case for either side.
