# ADR-0111: A floor can reject what a preference must not choose

- **Status:** Accepted
- **Date:** 2026-09-14
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.1
- **Related:** [ADR-0102](0102-record-whether-the-passage-landed-whole-and-read-a-large-negative-with-it.md)
  (which recorded `whole` and refused to let it choose — narrowed here),
  [ADR-0039](0039-measure-what-projection-costs.md) (the carry and what it measures),
  [ADR-0104](0104-merge-what-the-projection-could-not-tell-apart-and-record-that-it-could-not.md)
  (the opposite shape: many judged units onto one chunk),
  [ADR-0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md) (why a feature
  list is graded 1), [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md)
  (the trap a query-aware carry would walk into),
  [ADR-0109](0109-print-the-grade-beside-the-share-because-a-split-anchor-is-only-half-the-reading.md)
  (the receipt column that found this); D-010; spec 04 §7.1; roadmap 5.39, 5.41

## Context

Roadmap 5.41 was found at 5.39 by reading the lowest `whole` in the carry receipt — a column
that had been signalling correctly for two milestones and had never been read.

`u-0017` (dev, query `uv venv`) grades two passages of the Markdown corpus: the section that
*documents* the command at 3, and uv's feature list, which only says
`uv venv: Create a new virtual environment.`, at 1 — ADR-0062's rule, with the reason written
into the case's own note. The carry mapped that grade-1 anchor onto
`features-html-dba4b609.md#uv-pip-compile-compile-requirements-into-a-lockfile/0`, a chunk
whose text is the `uv pip compile` / `uv pip sync` pair and which **never mentions `uv venv`**.

### Why coverage chose it

The HTML lane turns uv's feature list into **a heading per item**, so the 201-token judged
passage is shattered across five twin chunks. Coverage is over *distinct* tokens, and a
feature list's vocabulary is nearly uniform across its items — `uv`, `pip`, `environment`,
`packages`, `install`, `the documentation on … for details` — so every fragment scores
respectably and the winner is decided by which one repeats more of the scaffolding:

| twin chunk | coverage | whole | holds `uv venv`? |
|---|---:|---:|---|
| `#uv-pip-compile-compile-requirements-into-a-lockfile/0` | **0.5269** | 0.3383 | no |
| `#the-pip-interface/0` | 0.4731 | 0.2886 | **yes** |
| `#uv-pip-uninstall-uninstall-packages/0` | 0.2151 | 0.1542 | no |

`MIN_COVERAGE` sat *between* the top two and kept the one that does not answer.

### It is a shape, not a case

Five judged anchors grade a feature-list section of that document. Four are shattered the
same way, and before this change three of them were already dropped by `MIN_COVERAGE` at
0.39–0.42 — `u-0006`, `u-0018` and `u-1007`. `u-0017` was the one that cleared the floor by
accident of vocabulary. The fifth, `u-1019`, is the control: coverage lands it on the item
that reads `uv python pin: …`, which is what its query asks about and holds half the passage.

## Decision

**`MIN_WHOLE = 0.4`: an anchor is dropped when the winning chunk holds less than two fifths
of the passage's word occurrences, however well it covers its vocabulary.**

**This narrows ADR-0102 rather than reversing it, and the distinction is the whole argument.**
That ADR refused to let `whole` *choose* between candidates, because re-deciding which of two
plausible chunks best holds a passage by a second metric is how a carry starts being fitted.
Rejecting is not choosing. A floor expresses one claim — *none of these is the passage* — which
is exactly the claim `MIN_COVERAGE` already makes, on the one metric that can see a split.
`whole` still picks nothing.

**The constant sits in a basin, not on a cliff.** Over the 63 anchors that cleared
`MIN_COVERAGE`, `u-0017`'s 0.3383 is the lowest and the next is 0.5088 — a gap of 0.17, the
widest at the bottom of the range. Every value from 0.35 to 0.50 drops that one anchor and
nothing else, so the number is a decision with room on both sides rather than a threshold
tuned to an outcome. A test asserts the room is still there.

**The carry stays query-blind.** It reads the source judgement, the source passage and the twin
document, and never the query.

## Alternatives Considered

All three shapes roadmap 5.41 named were measured before any was chosen, and all three lost.

- **Prefer a same-heading-slug candidate when one exists.** Right for `u-0017` and wrong
  everywhere else, which is the worst possible combination. Measured: on `u-0003` the same-slug
  candidate scores **0.1883** against the winner's 0.7468, on `u-0020` **0.3857** against
  0.9143, on `u-1019` **0.2069** against 0.6207. The projection re-heads a document, so the
  slug that survives is usually a stub holding the section's first sentence. It also
  re-introduces the structural assumption the coverage rule exists to avoid.
- **Use `whole` as a tie-break between close candidates.** Does not even fix the case it was
  proposed for: `u-0017`'s wrong winner has `whole` **0.3383** against the right chunk's
  **0.2886**, so a tie-break on `whole` picks the wrong one too. Both fragments are fragments;
  neither is the passage, and no comparison between them can say so.
- **Require the query's own distinguishing terms to survive into the carried chunk.** The most
  direct repair, correct on this case, and the one thing this tool must not do. A carry that
  reads the query stops measuring projection and starts handing the twin a chunk that lexically
  matches what is about to be searched for — ADR-0027's trap with the evidence removed, and it
  would make every twin number incomparable to its source's. Measured as well as argued: 15 of
  the 63 mapped anchors have a winner missing one of the query's words (`live`, `clear`,
  `which`, `mean`, `before`) at coverage and `whole` of 1.0000, so the rule would also have to
  be narrowed to terms present in the judged passage — more machinery, on a signal it must not
  consult at all.
- **Drop the case rather than the anchor.** Rejected: `u-0017`'s grade-3 anchor — the section
  that documents the command — carries at coverage 1.0000, and it is what the case is about.
  Deleting the case would discard a good measurement to repair a bad anchor.
- **Re-anchor `u-0017` onto `#the-pip-interface/0` by hand.** Rejected on two grounds. Nothing
  in this repository hand-writes a carried anchor — the regeneration check exists to prove
  none is — and the chunk holds 29 % of the judged passage, so claiming it *is* that passage
  would be false in the receipt as well as in the set.
- **Lower `MIN_COVERAGE` so the other three feature-list anchors carry too.** Rejected: it
  would carry them onto fragments for the same reason `u-0017` was carried onto one, which is
  the defect, multiplied.

## Consequences

- **Exactly one anchor moves, and only on the dev set.** `uv-ingested/dev`, `mycelium`:
  **0.583450 → 0.586058**, the `symbol` slice 0.4690 → 0.4820, and `u-0017`
  **0.5788 → 0.6309**. The incumbent does not move at all (0.431194 either way), because grep
  scored the case 0.0 on both sides. `uv-ingested/release` is untouched: every case, every
  slice and both overall numbers are identical to six decimals.
- **The case improves because a wrong anchor left, not because retrieval got better.** The
  grade-1 anchor was never retrieved — rank > 50 — so its only effect was to inflate the ideal
  DCG the case is scored against. Removing it makes the ideal describe what is in the corpus.
- **No baseline is re-blessed, and the item expected otherwise.** 5.41 was filed saying it
  "re-blesses both baselines … through `cases_digest`". It does not: the mis-carry is in the
  **dev** set, the release set is byte-identical, and gate G3 reported *"same corpus, same
  boundaries, same judgements, no enforced slice regressed"* throughout. The enforcing gate
  never disarmed, so there is nothing to re-arm.
- **Gate G2's verdict is re-recorded**, because `uv-ingested/dev`'s `cases_digest` moved and
  the currency check said so by name. The decision is unchanged.
- **The coverage floor gains headroom it did not have.** Its closest mapped anchor was
  **0.5269** — the mis-carry — and is now **0.6207**; the closest on `whole` is 0.5088 against
  0.40. The receipt's own docstring said that 0.5269 was "a cliff a reviewer should be able to
  see rather than discover", and the thing standing on the cliff turned out to be the defect.
- **Four anchors of one document are now dropped for one stated reason**, and the fifth is
  carried because its answer survived the shattering in one piece. That asymmetry is the
  evidence the floor is reading the projection rather than the document.
- **The receipt records `min_whole`** beside `min_coverage`, so a set regenerated under a
  different floor is distinguishable from one regenerated under the same.
- **A limit, stated:** the floor says a passage is absent, not where it went. A judgement whose
  passage is shattered is simply not carried, so the twin's dev set is one grade-1 anchor
  smaller than its source's and that difference is a projection finding, not a scoring one.
  `tools/measure_projection_cost.py` reports the case, and the drop is printed on every run.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §7.1 (frozen sets, slices).
- Decision log: D-010 (fix the product, not the benchmark).
- The receipt: `eval/corpora/uv-docs-ingested/eval/carry.json`, and the run that writes it,
  `python tools/build_ingested_cases.py` (`--check` reproduces and compares).
- Re-runnable: `mycelium eval eval/corpora/uv-docs-ingested --set eval/dev.jsonl --against grep`.
- Tests: `tests/test_eval_ingested_corpus.py` — the arithmetic that makes coverage blind to a
  split, the basin the constant sits in, the four dropped anchors and the one kept.
