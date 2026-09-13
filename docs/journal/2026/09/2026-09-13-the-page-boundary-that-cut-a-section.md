# 2026-09-13 — the page boundary that cut a section (roadmap 5.31)

- **Session scope:** roadmap 5.31 — why `u-1004` scores 0.000 on the ingested twin and 0.387
  on its source, in the same projected PDF whose other two cases score *above* theirs
  (spec 04 §7.1; ADR-0039/0097).
- **PR:** #130 (`fix/u1004-twin-anchor`). Follows #129 (5.30), merged as `b4bc729`.
- **Milestone 5:** 5.31 done; 5.39 filed.
- **ADR:** [ADR-0102](../../../adr/0102-record-whether-the-passage-landed-whole-and-read-a-large-negative-with-it.md).

## Two hypotheses, and the answer was in neither

The item offered a clean fork — the carried anchor is the passage, or the coverage rule picks
wrong — and told me to read `carry.json` first, because an anchor near the 0.50 floor would
settle it in one line. That instruction was right and its premise was not.

The anchor maps at coverage **0.9533**, the best of the document's six chunks by a wide
margin, nowhere near the floor. And the item's supporting claim — *"three anchors already map
between 0.42 and 0.49"* — is a sentence the generator's own docstring has been carrying for
milestones, and it is wrong twice over: anchors below the floor are **dropped**, so they never
enter the receipt, and the closest one that does map sits at 0.5269. The three at 0.39–0.42
are drops. I corrected the docstring, since it is what sent a reader looking in the receipt
for rows that cannot be in it.

So the coverage rule did not pick a marginal chunk. It picked the best one available, and the
case still scores zero.

## What coverage cannot see

`coverage` counts **distinct** tokens: are the passage's words here. A section's vocabulary
repeats across its examples while its topic sentence occurs once — so the chunk holding the
examples can score 0.95 while the sentence that states the rule went next door. Counting word
*occurrences* instead makes the split visible immediately:

| twin chunk | distinct | occurrences | holds |
|---|---:|---:|---|
| `#/0` | 0.6355 | 0.6716 | the heading, the opening sentence, the first example |
| `#/1` | **0.9533** | **0.8955** | the platform-marker variation, `explicit = true`, the closing rules |

A PDF page boundary fell inside `## Pinning a package to an index`. The judged `#/1` opens
mid-flow at *"Similarly, to pull from a different index based on the platform…"*. The sentence
that answers the query — *"A package can be **pinned** to a **specific** index by specifying
the index in its `tool.uv.sources` entry"* — is in `#/0`. `#/1` does not contain the word
`specific` at all; four of the query's five content words are in `#/0` and three in `#/1`.

The rankings say the rest. On the twin the judged chunk is outside this product's top ten and
10th for grep, while the unjudged `#/0` is **7th** and **1st**. A reader asking that question
of the twin is served; the score records that they were not.

## One document, one mechanism, both signs

This is the part worth keeping. The item's puzzle was that a single projected PDF holds the
format's largest gain and its largest loss, which rules out the 4.7× target-size story. It
does — and the real mechanism explains both at once. **A page boundary does not know where a
section ends.** In `u-1003` it *merged* the document's framing with the section that documents
the key, and the case gained (+0.075 after 5.30 re-judged it). In `u-1004` it *split* a
section, and the case lost everything. Same rule, same page, opposite signs.

## What I refused, and the measurement that killed the best idea

Re-anchoring to `#/0` would raise the case and requires knowing the query, which would make
the twin's anchors a function of the questions asked of them — the property ADR-0039 built the
carry to avoid. Carrying both halves enlarges nDCG's ideal gain and makes the twin easier,
which is the defect ADR-0097 named rather than a repair.

The idea I expected to adopt was preserving **section scope**: the source judgement is
section-scoped, any chunk of the section counts there, and the carry narrows it to one chunk —
a real asymmetry, and the twin is judged more strictly than its source because of it. Then I
measured it. Fifteen of the 54 carried anchors are section-scoped, and the five whose twin
"section" holds more than one chunk are **all PDFs, where the section is the whole document**.
Preserving scope would credit all six chunks of `indexes-pdf-…` for a single judgement. A
headingless projection has no sections to preserve, so the asymmetry is real and has no fix
that survives the format that causes it. That is now written down so the next person does not
spend the same hour on it.

## What ships instead

Visibility, not a decision. `eval/carry.json` records `whole` beside `coverage` for every
mapped anchor, the receipt is `v1`, and `measure_projection_cost.py` gains a `whole` column
read from the committed receipt so the two cannot disagree. 43 of 54 anchors land whole. No
score moves; the carried sets are byte-identical.

The discipline that matters here is what `whole` is *not*. It selects nothing, it has no
floor, and the generator prints "part of the passage is elsewhere" as a fact rather than a
verdict — because 0.985 and 0.509 are both below 1.0 and mean different things. The data
insists on the same caution: among scored release cases the two largest negatives are the two
lowest shares, which is why the number is worth recording, and the largest *gain* is a split
passage too, which is why it is not a predictor. Six split cases against seventeen whole ones
average −0.030 against +0.017. That is suggestive and far too thin to be a rule.

## Filed rather than absorbed

`u-1019` is the other large negative (−0.314) and now carries the lowest `whole` of any scored
case, 0.509 — but on an anchor its own judgement grades **1**, the feature-list entry that
"answers only that the command exists". Whether a split on a grade-1 anchor moves a case at
all is a narrower question than this one and deserves its own read (5.39), together with
`features.md#the-pip-interface/0` at 0.338, lower still, on a dev case nobody has read.

## Lesson

When a metric is a proxy, ask what it cannot see before asking whether it chose wrong. Coverage
was doing its job perfectly and reporting a number that could not distinguish "the passage is
here" from "the passage's words are here" — and the case it could not describe had been sitting
in the table for milestones, looking like a retrieval failure.
