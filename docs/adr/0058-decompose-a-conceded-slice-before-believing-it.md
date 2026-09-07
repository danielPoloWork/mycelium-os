# ADR-0058: Decompose a conceded slice before believing what it says

- **Status:** Accepted
- **Date:** 2026-09-07
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.25 (this item), 4.8 (where it was filed), 4.26, 4.28; RFC-0001;
  spec 04 §§3, 7.1, 7.4; D-010;
  [ADR-0029](0029-let-a-judgment-name-a-section.md),
  [ADR-0031](0031-refuse-three-rerankings.md),
  [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md),
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md),
  [ADR-0049](0049-close-the-grep-gap-and-keep-the-incumbent-in-the-manifest.md),
  [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md),
  [ADR-0057](0057-drop-the-function-words-and-score-the-seam-that-ships.md)

## Context

Roadmap 4.25 was filed from one line of `mycelium eval --against grep`:

```text
still conceded: fact 0.431 vs 0.497
```

and it drew a conclusion from that line: *"The corpus is short imperative task pages —
'how do I do X' answered by two sentences and a command — which is the shape ADR-0031 first
identified."* It supported the conclusion with a second observation: the third corpus
concedes the same slice, *"which makes it a property of that documentation rather than a
quirk of one judged set."*

The item also gave the right instruction: **read the seven cases against the documents
rather than propose a ranking.** Doing that first is what this ADR is.

Both supporting claims turn out to be wrong, and the second is wrong in a way that matters
beyond this item.

**The slice is two cases, not seven.**

| case | ours | grep | gap |
|---|---:|---:|---:|
| u-1006 "which Python version formats can I request" | 0.431 | 1.000 | **−0.569** |
| u-1004 "how do I pin one package to a specific index" | 0.333 | 0.631 | **−0.298** |
| u-1010, u-1013 | tie | tie | 0.000 |
| u-1008, u-1014, u-1001 | | | +0.023, +0.044, **+0.337** |

Seven cases, five of them ties or wins, and a mean that reads as a systematic loss. Fix
u-1006 alone and the slice reads 0.512 against 0.497 — the concession is one case wide.

**The same documentation says the opposite on the set we are allowed to develop against.**
`fact` on uv/**dev**, drawn from the same corpus: **0.893 against grep's 0.752, a lead of
+0.141.** A property of the documentation cannot hold on one judged set and reverse on
another drawn from the same documents.

**And the third corpus is not a second observation.** `eval/corpora/uv-docs-ingested`'s
release set has the *same twenty-five case ids and the same twenty-five queries* as
uv/release — it is that set carried onto the ingested projection of the same documents
(roadmap 4.16), with the anchors re-pointed at their twins. Two sets that share their
queries are one observation, and "both concede `fact`" is that one observation counted
twice.

Read per case, the two projections disagree about which cases concede it:

| set | `fact` | conceded on |
|---|---:|---|
| uv/release | 0.431 vs 0.497 | u-1006 (−0.569), u-1004 (−0.298) |
| ingested/release | 0.518 vs 0.537 | u-1004 (**−0.569**), u-1008 (−0.014) |
| ours/release | 0.459 vs 0.439 | *not conceded* |

The same −0.569 appears in both, on a different case each time. That number is the
signature of one grade-3 answer at rank 4 instead of rank 1, and which case it lands on
depends on where the chunk boundaries fell in that projection — u-1006's judged anchor is a
section in one set and a whole document's lead chunk in the other. This is ADR-0044's
warning arriving in practice: a seven-case slice does not measure a retrieval property, and
the aggregate was stable while everything under it moved.

**One of the two cases is a cost this project already accepted.** ADR-0057 names u-1004
explicitly: it went 1.000 → 0.333 when the function-word stop-list reached the product,
because *"`to` and `a` were matching a **heading** at weight 2.0 and carrying the right
answer for the wrong reason"*. That is a maintainer-accepted decision on stated evidence,
and nothing measured here is new evidence against it.

So the open case is **u-1006**, and it is a real defect. The query is answered by
`Requesting a version`, which contains the sentence *"The following Python version request
formats are supported:"* and then lists them. We return its subsection
`Requesting a version / Python version files` first, which says only *"Any of the request
formats described above can be used"* — the right neighbourhood, not the answer, which is
precisely what ADR-0029 refuses to credit. The judged anchor is right and the ranking is
wrong.

## Decision

**Refuse to change ranking or indexing for this slice, and ship the instrument that would
have stopped the item being filed on an aggregate.**

Three parts.

1. **`mycelium eval --against grep` now decomposes a conceded slice into the cases it is
   made of.** The run already scores the incumbent case by case and used to throw those
   results away; they are kept in the manifest (`incumbent_results`) and reported:

   ```text
   still conceded: fact 0.431 vs 0.497
     fact is conceded on 2 of 7 case(s): u-1006 0.431 vs 1.000 (-0.569), u-1004 0.333 vs 0.631 (-0.298)
   ```

   Gate G3 has named the cases behind a slice since roadmap 4.20, for exactly this reason
   (`_attribute`). The comparison against the incumbent — the one that sends a reader off
   to hypothesise about a corpus — was the last number in the project that could not be
   decomposed. A slice conceded by every case really is a corpus property and prints no
   list; a slice conceded by one prints the case, and those two findings ask for opposite
   work.

2. **The heading hypothesis is measured and refused**, in `tools/measure_ranking.py` as the
   twelfth family. A chunk's `heading_path` is its whole ancestor chain, so a subsection's
   heading field is a strict superset of its parent's — the plausible reason a query
   matching an ancestor's heading would boost every descendant. Splitting the leaf heading
   from the ancestors **does not move u-1006 at any setting, including ancestors at zero**,
   because the child never won on that field: per-column BM25 gives the parent 0.958 on
   `heading_path` against the child's 1.573, and 7.752 on `text` against 10.075. The gap is
   in `text`, at 164 tokens against 385 — BM25's own length normalisation, whose `b` SQLite's
   `bm25()` does not expose. ADR-0031 named that mechanism and that limit three milestones
   ago; this is the first candidate to test it on the field that looked most guilty and
   exonerate it.

3. **The premise is corrected where it was written.** Roadmap 4.25 closes with the
   measurement rather than with a fix, because the finding *is* that the item's own framing
   did not survive being read case by case.

## Alternatives Considered

- **`index: expand 0.5`** — stem weight at 0.5 with no surface precondition. The only
  strategy ever measured that beats the incumbent on this slice: `fact` 0.529 against
  0.497 on uv/release, G3 pass there. Rejected twice over, both refusals pre-existing: it
  fails G3 on **ours/release** (`conceptual` −14.7 %), and open expansion answers questions
  the corpus cannot answer, which gate G4 catches and `measure_ranking.py` cannot see
  (ADR-0048).
- **`index: porter`** — `fact` 0.487 on uv/release and 0.661 on ours/release, the largest
  gains in the file. Rejected as it has been since ADR-0044: `symbol` −16 % on uv/release
  and `conceptual` −21 % on ours/release.
- **Adopt `heading 3.0/0.5` anyway.** It wins or ties on all four sets, passes G3 on both
  release sets, and shrinks rather than grows the dev/release gap. Rejected on two grounds,
  either sufficient. It **does not fix this slice** — `fact` on uv/release goes 0.431 →
  0.438, still short of 0.497, and u-1006 does not move at all — so adopting it here would
  be smuggling an unrelated gain in under this item's name. And on **uv/dev** it scores
  exactly what the baseline scores: the pair was chosen by reading the release sets, which
  is what spec 04 §7.1's split exists to refuse. The lead is real and is filed as roadmap
  4.36, where it needs dev evidence before it can be proposed.
- **Re-judge u-1006, or credit a descendant section against an ancestor's judgment.** The
  cheapest way to make the number go away, and wrong: ADR-0029 already decided that
  section scope credits the section's own chunks and not the right neighbourhood, and the
  subsection genuinely does not answer the question — it points at the answer. Changing a
  frozen release judgment to close a gap is what `tools/check_frozen_release_sets.py`
  exists to refuse.
- **Reopen ADR-0057's u-1004 cost.** Rejected: it is a maintainer-accepted decision with
  its evidence recorded, and this item produced no new evidence against it. Relitigating a
  settled decision because a different slice made it visible again is how a project loses
  the ability to decide anything.
- **Report the decomposition only in the JSON output.** Rejected: the reader who needs it
  is the one reading the terminal line that made this item, and a finding available only to
  whoever remembers to pass `--json` is a finding nobody reads.

## Consequences

- **A conceded slice is now actionable from the line that reports it.** Two ways to be
  behind by 0.066 — everywhere a little, or one case a lot — are now distinguishable
  without writing a script, on every corpus CI scores.
- **`EvalRunManifest` gains `incumbent_results`.** Optional, defaulted, and read defensively:
  a manifest written before this change renders exactly as it did, as the slice means alone.
  The eval-run record is not one of the five contracts that freeze at 1.0
  (architecture §10), and this is the same shape of addition `cases_digest` (roadmap 4.24)
  and `incumbent_per_slice` (ADR-0049) made.
- **The sentence lives on `IncumbentComparison`, not in the CLI.** `decomposition()` is
  where it is built and tested; the CLI prints its lines. The next surface that reports a
  concession reports the same decomposition rather than a second version of it.
- **The refusal count is now fourteen**, and the twelfth family is the first to be aimed at
  a *named case* rather than at a slice mean. That is the improvement in method worth
  keeping: the hypothesis was refuted by the per-column measurement in about the time it
  took to write, because there was a specific case to refute it against.
- **`fact` on uv/release stays conceded**, at 0.431 against 0.497, and this ADR is the
  reason it is allowed to. The gate that would fail on it does not exist: seven cases
  cannot carry one (ADR-0044, ADR-0052), and D-010's quantified gate arrives at roadmap 6.4
  with the set sizes spec 04 §7.6 requires.
- **What is still open is u-1006**, one case, mechanism known, lever absent. It is not
  refiled as its own item: a single case is not a roadmap item, and the honest next step is
  set size — the corpus growth roadmap 4.26 began — not another pass at BM25.

## References

- Spec 04 §7.1 (dev/release split), §7.4 (the grep incumbent), §3 (field weights).
- D-010 — "if Mycelium OS does not visibly beat grep, fix the product, not the benchmark".
- Measured this session, reproducible with
  `mycelium eval <corpus> --set eval/release.jsonl --against grep` and
  `python tools/measure_ranking.py --release`:
  `fact` per case on six judged sets; uv/dev +0.141 against the incumbent; the two
  projections conceding on different cases; u-1006 immovable across the whole heading
  family; per-column BM25 attribution of u-1006's 2.49-point gap (text 2.32, heading 1.30,
  title 0.24 — the columns are not additive, so these are one-hot readings, and the
  ordering is what they establish).
- [ADR-0031](0031-refuse-three-rerankings.md) — the length-normalisation mechanism, named
  first and still the answer.
- [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) — what a slice this
  size can and cannot say, which this item is a worked example of.
- [ADR-0057](0057-drop-the-function-words-and-score-the-seam-that-ships.md) — u-1004's
  loss, argued and accepted there.
