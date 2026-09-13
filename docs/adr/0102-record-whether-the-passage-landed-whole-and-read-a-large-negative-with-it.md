# ADR-0102: Record whether the carried passage landed whole, and read a large negative with it

- **Status:** Accepted
- **Date:** 2026-09-13
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.1
- **Related:** [ADR-0039](0039-measure-what-projection-costs.md) (the carry, the coverage
  rule, and the comparison this reads), [ADR-0097](0097-a-twin-case-that-outscores-its-source-is-the-defect-not-the-fall.md)
  (the per-case block that found this case, and the sibling gain in the same document),
  [ADR-0029](0029-let-a-judgment-name-a-section.md) (section scope, which a headingless
  projection cannot carry), [ADR-0101](0101-let-the-exact-slice-name-the-section-that-documents-the-literal.md)
  (the neighbouring case, re-judged one item earlier),
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) (what a handful of cases
  may and may not conclude); [BUG-0018](../bugs/2026/09/BUG-0018-carried-ingested-cases-do-not-reproduce.md)
  (why the receipt exists at all); D-010; roadmap 5.26, 5.31

## Context

`u-1004` — *"how do I pin one package to a specific index"*, slice `fact` — scores **0.387**
on the Markdown corpus and **0.000** on its ingested twin. It is the largest negative in
`tools/measure_projection_cost.py`'s per-case block, and it sits in the same projected PDF
that carries `u-1003` and `u-1001`, both of which score *above* their source. One document
holds the format's largest gain and its largest loss, which rules out the 4.7× target-size
explanation that covers the gainers: a bigger target cannot make one case easier and another
impossible.

Roadmap 5.31 asked the question in the right order: **is the carried anchor the passage, or
is this the case where the coverage rule picks wrong?** — and said to read the receipt first,
since anchors mapping near the 0.50 floor would settle it immediately.

**The receipt says the carry did well.** `docs/concepts/indexes.md#pinning-a-package-to-an-index/`
maps at coverage **0.9533**, the best of the document's six chunks by a wide margin (the
runner-up is 0.6355) and nowhere near the floor. The item's premise that *"three anchors
already map between 0.42 and 0.49"* does not hold either: the closest mapped anchor is at
0.5269, and the three at 0.39–0.42 are anchors the floor **dropped**, which are printed and
never enter the receipt.

So neither hypothesis was right, and the answer is in a third place. `coverage` is over
**distinct** tokens — *are the passage's words here* — and a section's vocabulary repeats
across its examples while its topic sentence occurs once. Measured over the same passage by
word *occurrences* instead:

| twin chunk | distinct coverage | occurrence share | holds |
|---|---:|---:|---|
| `indexes-pdf-…#/0` | 0.6355 | 0.6716 | the section heading, its opening sentence, its first example |
| `indexes-pdf-…#/1` | **0.9533** | **0.8955** | the platform-marker variation, `explicit = true`, the closing rules |

**A PDF page boundary fell inside the section.** The twin's `#/1` begins mid-sentence-flow at
*"Similarly, to pull from a different index based on the platform…"*; the sentence that
answers the query — *"A package can be **pinned** to a **specific** index by specifying the
index in its `tool.uv.sources` entry"* — is in `#/0`. Four of the query's five content words
are in `#/0`; `#/1` has three and is missing `specific` entirely.

The rankings follow exactly. On the twin, the judged `#/1` is **outside the top ten** for this
product and **10th** for grep, while the unjudged `#/0` — which does hold the answer — is
**7th** and **1st**. On the source the judged section is 5th and 2nd. A twin reader asking this
question is served; the score says they were not.

## Decision

**Nothing about `u-1004` is adjusted — no judgement, no grade, no anchor, no baseline — and
`whole` is recorded so the next case like it is legible from the receipt.**

**The carried anchor stands.** It is the chunk the carry's rule selects, by both measures, and
selecting the other one would require knowing the query. The carry is query-blind on purpose
(ADR-0039: *"the judgement is fixed and retrieval is the only thing that varies"*), and a
carry that consulted the query to choose between two halves of a split passage would be
fitting the anchor to the question asked of it. That is the line this repository has refused
every time it has been offered.

**The 0.000 is the measured cost of the projection, and the mechanism is named.** It is not
the 4.7× chunk size the `pdf` row is otherwise about. It is that **a page boundary does not
know where a section ends**: on `u-1003` the same boundary *merged* the document's framing
with the section that documents the key, and the case gained; on `u-1004` it *split* a section
and the case lost everything. One document, one mechanism, both signs — which is the puzzle
5.31 opened with, answered.

**`tools/build_ingested_cases.py` records `whole` beside `coverage`** for every mapped anchor:
the share of the judged passage's word *occurrences* the chosen chunk accounts for. 1.0 means
the passage is in that chunk entire; below it, part of the passage is in a neighbour that
nothing credits. The receipt is `mycelium/eval-carry/v1`.

**It is recorded, not acted on.** `whole` does not choose an anchor and carries no floor.
Which chunk best holds a passage is a question about the projection, and re-deciding it by a
second metric — or dropping an anchor for being split — is how a carry starts being fitted;
`MIN_COVERAGE` is deliberately the only threshold here. The generator prints the share and
appends *"part of the passage is elsewhere"* as a fact rather than a verdict, because 0.985
and 0.509 are both below 1.0 and do not mean the same thing.

**`tools/measure_projection_cost.py` marks the cases.** The per-case block gains a `whole`
column, read from the committed receipt rather than recomputed so the two cannot disagree, and
a line naming how many cases carry a split passage. That is the step that turns *"why is this
case zero"* from a session's work into a column.

## Alternatives Considered

- **Re-anchor `u-1004` to `#/0`, which holds the answer.** The tempting one, and it would
  raise the case. Rejected: `#/0` is chosen only by looking at the query, so the twin's
  anchors would become a function of the questions asked of them — the exact property
  ADR-0039 built the carry to avoid. It would also be picking the chunk with *less* of the
  passage (0.6716 against 0.8955) on the grounds that it scores better, which is the shape of
  every fitted parameter this project has refused.
- **Carry both chunks, since the passage is in both.** Query-blind, and defensible on its
  face. Rejected on the arithmetic: two anchors make nDCG's ideal gain larger, so the change
  would move cases that are not split, and on the twin it would raise scores generally — the
  twin becoming easier than its source is what ADR-0097 named as the defect to avoid, not a
  repair to adopt.
- **Preserve section scope through the carry** (ADR-0029's trailing slash), so any chunk of
  the section counts, as it does on the source. This is the structurally appealing fix — the
  source judgement *is* section-scoped and the carry narrows it to one chunk. Rejected on a
  measurement: **a headingless projection has no sections.** Fifteen of the 54 carried anchors
  are section-scoped, and the five whose twin "section" holds more than one chunk are all
  PDFs, where the section is the *whole document* — so preserving scope would credit all six
  chunks of `indexes-pdf-…`, and the twin would be trivially easy. The asymmetry is real and
  has no fix that survives the format that causes it.
- **Lower `MIN_COVERAGE`, or add a floor on `whole` that drops a split anchor.** Rejected
  both ways: 0.9533 is nowhere near the floor so lowering it changes nothing here, and
  dropping split anchors would silently shrink the set that measures projection cost by
  removing exactly the cases where projection costs something.
- **Use occurrence share to choose the anchor instead of coverage.** Rejected because it
  chooses the same chunk here (0.8955 against 0.6716) and would be a re-tuning of the carry
  justified by one case — with, as far as this receipt can say, no case it would decide
  differently.

## Consequences

- **No score moves.** The carried sets are byte-identical; only `eval/carry.json` changes, by
  gaining a field per anchor and a schema version. Both `--check` reproductions pass.
- **43 of 54 anchors land whole; 11 do not**, and the eleven are now visible. Among scored
  release cases the two largest negatives are the two lowest shares — `u-1004` at 0.895 and
  `u-1019` at 0.509 — which is what makes the number worth recording.
- **And it is a reading aid, not a predictor, which the data itself insists on.** The largest
  *gain* in the table, `u-1006` at +0.569, is also a split passage (0.911). Split passages
  average −0.030 against +0.017 for whole ones, on six cases and seventeen: suggestive, and
  far too thin to be a rule (ADR-0044's discipline). Anyone quoting those means has to quote
  the counts with them.
- **`u-1019` is now readable and unread**, so it is filed as roadmap 5.39: −0.314, `whole`
  0.509, the lowest share of any scored case, on an anchor the judgement grades **1**. Whether
  a grade-1 anchor splitting matters at all is its own question.
- **One stale sentence corrected on the way.** `build_ingested_cases.py` claimed *"three
  anchors currently map between 0.42 and 0.49 against a 0.50 floor"*. They do not map — they
  are dropped by the floor and never reach the receipt, which is why 5.31 sent a reader to
  look for them there. The closest mapped anchor is 0.5269.
- **The receipt is `v1`.** It is a derived artifact regenerated byte-exactly and validated by
  `--check`, not one of the record contracts in `mycelium.sdk.types`, so the bump costs
  nothing and says plainly that an older receipt has no `whole` key. The projection-cost tool
  treats a missing key as "no marks" rather than inventing them.

## References

- Spec 04 §7.1 (frozen sets, the twin's judgements), §7.2 (metrics).
- `eval/corpora/uv-docs/docs/concepts/indexes.md` §*Pinning a package to an index* and
  `eval/corpora/uv-docs-ingested/knowledge/evidence/indexes-pdf-d37689d3.md` chunks `#/0` and
  `#/1` — the two halves of the passage.
- Re-runnable: `python tools/build_ingested_cases.py --check` for the receipt,
  `python tools/measure_projection_cost.py` for the per-case block, and
  `mycelium search "how do I pin one package to a specific index" --path eval/corpora/uv-docs-ingested`
  for the ranking that shows `#/0` served and `#/1` did not.
