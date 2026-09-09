# 2026-09-09 — one section, two commands (roadmap 4.37)

- **Session scope:** roadmap 4.37 — `u-0006` (`uvx`) names the same section as `u-1007` did,
  and has never been served (spec 04 §7.1; ADR-0029/0043/0062).
- **PR:** #88 (`test/judge-uvx-where-it-is-documented`). Follows #87 (4.33), merged as
  `668b110`.
- **Milestone 4:** 4.37 done; 4.38, 4.39, 4.40, 4.41 open.

## The item asked the smaller question, and the bigger one was underneath it

4.37 framed itself as a question about a `symbol` case's **second** anchor, on the explicit
grounds that the grade-3 one is fine: *"that section defines `uvx`"*. ADR-0062 had said so
outright — *"grades that same section 3, correctly"* — and `eval/README.md` carried the
sentence.

It does not hold, and the reason is not a matter of taste. ADR-0062 graded
`concepts/tools.md#the-uv-tool-interface` **2** for `u-1007` (`uv tool install`) because its
subject is the *interface*, and **3** for `u-0006` (`uvx`) because it defines the alias. A
section's subject does not change with the query asked of it. Under a rule that gives grade
3 to *the section that documents the thing*, one section cannot be the documenting home of
two sibling commands — and the corpus never asked it to be. The guide has a section per
command:

| section | first sentence | subject |
|---|---|---|
| `concepts/tools.md#the-uv-tool-interface` | "uv includes a dedicated interface for interacting with tools." | the interface |
| `guides/tools.md#running-tools` | "The uvx command invokes a tool without installing it." | the command |

`#running-tools` is the direct counterpart of the `#installing-tools` that 4.34 promoted. So
the grades move: `guides/tools.md#running-tools/` at 3 (section-scoped, ADR-0043), the
framing section at 2 — the grade it already carries in `u-1007` — and
`features.md#tools/0` at 1. `guides/tools.md#/0` is removed: 25 tokens of overview that
never contains the string `uvx`, and indefensible at grade 2 under any reading.

## The change flatters us, so it is priced against the alternative

`u-0006` goes **0.0000 → 0.3726**, uv/dev 0.673 → 0.710, uv-ingested/dev 0.634 → 0.668. A
re-judging that improves our own score is exactly the shape a fit takes, so I wrote down what
the item's own proposal scores instead: keeping the old grade-3 and grading `#running-tools`
at 2 gives **0.160**. The choice between them was made on the inconsistency, not on the
0.213 — and the ADR names the priced alternative as what a maintainer who reads the two
sections the other way should revert to. It is one line of JSONL either way.

## And it makes a loss visible where a zero hid one

The number I did not expect:

| retriever | `u-0006` before | after |
|---|---:|---:|
| mycelium | 0.0000 | 0.3726 |
| grep | **0.2275** | **0.4650** |

grep was **already ahead** on this case while our judgment scored us zero, and it still is.
`symbol` on both dev sets now reports `conceded on 1 of 1 case(s): u-0006 0.373 vs 0.465`.
The mechanism is one rank: both retrievers put `#running-tools` at rank 3, and grep also
lands the framing section inside the top ten where we have it at rank 13.

We gain more than the incumbent here (+0.373 against +0.238) — the opposite of ADR-0062's
honesty note, where the incumbent gained twice what we did. Either way the direction of the
number is not the argument; recording it is.

## What did not happen

No retrieval code. No baseline blessed — dev sets carry none, so G3 reports "nothing to
regress against" as it always has on them. No frozen release set touched, which is why this
could be one PR. And no new roadmap item filed: 4.38 through 4.41 already hold the threads
this touches, and Milestone 4 does not need a forty-second entry.

The derived set followed mechanically, which is the part that should be boring:
`build_ingested_cases.py` carried the new grade-3 anchor to
`tools-docx-cf7bdde6.md#using-tools/running-tools/0` at coverage **1.00** and dropped the
feature-list anchor at 0.42 — the same anchor it already drops for `u-1007`, for the same
reason.
