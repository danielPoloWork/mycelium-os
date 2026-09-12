# ADR-0097: A twin case that outscores its source is the defect, not the fall that corrects it

- **Status:** Accepted
- **Date:** 2026-09-12
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.1
- **Related:** [ADR-0039](0039-measure-what-projection-costs.md) (the twin, the carry, and
  the comparison this reads), [ADR-0095](0095-read-the-corpus-in-the-dialect-it-is-written-in.md)
  (the repair that moved the number), [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md)
  (judgements frozen before the corpus existed), [ADR-0029](0029-let-a-judgment-name-a-section.md)
  (what a judgement names), [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md)
  (the precedent: read the cases, not the mean), [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md)
  (per-case scores, which made this readable), [ADR-0091](0091-a-symbols-defined-in-names-where-it-is-named.md)
  (a refusal with measurements behind it); D-010; roadmap 5.24, 5.26

## Context

Roadmap 5.24 re-rendered the ingested twin in the dialect the corpus is written in
(ADR-0095), repairing 21 of 81 documents whose headings the old rendering had swallowed into
code blocks. The `exact` slice on `uv-ingested/release` fell **0.7893 → 0.7602**, and 5.26 was
filed to read the one case that moved before anything was adjusted:

> The question is whether the new anchor is the *right* one and the old score was inflated by
> a chunk that had swallowed its neighbours, or whether the carry picked a worse chunk among
> several good ones; read the document and the two chunks before deciding.

Both alternatives assume the carried anchor moved. It did not, and the measurements say so
without ambiguity.

**The judged chunk is the same chunk, before and after.** `u-1003` (query `tool.uv.index`,
slice `exact`) carries onto `knowledge/evidence/indexes-pdf-*.md#/0`. In both renderings that
anchor is lines 8–51 of the projection, 535 tokens, and it covers the judged passage at
**1.0000** — every distinct word token of the Markdown original's preamble is in it. Its text
differs by exactly one character pair: `“default”` became `"default"`, because pandoc's
`markdown` dialect applies smart quotes and `gfm` does not. The store's `unicode61` tokenizer
indexes neither, so **the chunk's alphanumeric tokens are identical**. Its BM25 score against
this query cannot have changed, and did not.

**What moved is a rival, and the rival is a repaired document.** `u-1003` fell from rank 2 to
rank 3 because `dependencies-docx-*.md#dependency-sources/index/0` rose from rank 6 to rank 2.
That chunk did not exist before: `docs/concepts/projects/dependencies.md` is one of the nine
documents 5.24 named, its `### Index` heading was inside a code block, and the section's text
sat inside a 626-token `#dependency-sources/0` block with four of its siblings. The repaired
twin cuts that document into 28 chunks where it cut 23, and its `dependency-sources` sections
are now the **same nine sections, with the same names and token counts within four**, as the
Markdown corpus it was projected from.

**And the Markdown corpus agrees with the repaired twin about the order.** On `uv/release`,
where the same frozen judgement is applied to the documents a human wrote:

| | judged passage (`indexes` preamble) | the rival (`dependencies` → Index) |
|---|---:|---:|
| `uv/release` — the Markdown source | rank **6** | rank **3** |
| `uv-ingested/release` — before the repair | rank **2** | rank **6** |
| `uv-ingested/release` — after the repair | rank **3** | rank **2** |

The broken twin ranked them in the opposite order from its own source. The repaired twin
ranks them in the source's order. The fall is the twin agreeing with the corpus it is a twin
of.

**The number that should have raised the question was never the fall.** `u-1003` scores
**0.3562** on `uv/release` and **0.6309** on the twin before the repair — the ingested copy
outscoring the Markdown it was projected from by +0.27, for three milestones. A twin cannot
be easier than its source; where it is, something upstream of the measurement is wrong. The
comparison that would have said so is reported per format (ADR-0039) and nothing printed a
case, so a standing +0.27 was invisible and the −0.13 that partly corrected it arrived
looking like a regression.

## Decision

**`u-1003`'s carried anchor stands, and nothing about the case is adjusted.** No judgement,
no grade, no anchor, no baseline, no floor. The carry did what ADR-0039 specifies: it found
the chunk of the twin document that covers the passage the frozen judgement already picked,
at the maximum coverage the metric admits. The score it now earns is the more honest of the
two, and 0.7602 is the `exact` slice's correct reading.

**`tools/measure_projection_cost.py` prints every shared case, widest gap first, and names
the cases that score above their source.** No threshold and no verdict: a gap is evidence
about the corpus, and which way it points depends on the case. An ingested score *below* its
source is projection costing something, which is what this tool exists to measure; an
ingested score *above* its source is the twin being easier than the document it was made
from, which is not a result at all. Naming a cut-off would turn that reading into arithmetic,
which is the fitted parameter this project has refused every time it has been offered.

**And the first run of it says `u-1003` was never the interesting case.** Three of the
twenty-five shared release cases score above their source, all three PDFs — and reading them
separates one mechanism into two, of which only the milder is the one this ADR started with:

| case | what the source judgement names | what the twin carries | Markdown | twin |
|---|---|---|---:|---:|
| `u-1006` | a **section**, `#requesting-a-version/`, over several chunks | one chunk, `#/0` | 0.431 | **1.000** |
| `u-1001` | **two** anchors — a section at grade 3 *and* a chunk at grade 2 | one chunk, `#/0`, listed **twice** | 0.676 | **1.000** |
| `u-1003` | one **chunk**, `#/0` | one chunk, `#/0` | 0.356 | 0.500 |

**`u-1003` is the size effect**, and it is the small one: the same single unit on both sides,
535 tokens against 64. The mechanism is printed one table above it — a PDF carries no
headings, so its chunks are packed to the token budget and the carried target averages **602
tokens against the Markdown chunk's 128, a factor of 4.7**. A bigger target is easier to rank
highly.

**The two large ones are collapse, which is a different and worse thing.** A headingless PDF
gives the carry one chunk where the judgement named several units, so a case that asked for
*more than one thing* becomes a case that asks for one. `u-1006`'s source judgement is
section-scoped (ADR-0029) precisely because the answer is spread across the section; on the
twin that section is a single block, retrieved at rank 1, and the case is complete. `u-1001`
is the same collapse made literal: its two distinct source anchors both carry onto `#/0`, so
the twin's set lists that anchor **twice** — `run_evaluation` builds `{anchor: grade}`, the
duplicate silently dedupes to the survivor's grade 2, and a case that required a section and
a chunk in the right order becomes one chunk at rank 1. Neither
`tools/build_ingested_cases.py` nor `validate_judged_set` says a word about it: the
validator's three lints are anchor-exists, unanswerable-is-unanswerable, and
grade-3-carries-the-answer. Filed as roadmap 5.33.

The `pdf` row's apparent **+0.093 nDCG@10 gain** is these three, net of `u-1004`'s −0.387. It
is not a gain and has never been one. `docx` (1.1×) and `html` (1.0×) show no case above its
source.

**The dev set confirms it independently, and it is the clearer picture of the two.** Over its
twenty-two shared cases the twin is **worse overall** — −0.032 nDCG@10, which is what
projection costing something looks like — with `docx` at −0.037 and `html` at −0.108. The one
format that rises is `pdf`, **+0.111**, and it has exactly one case above its source
(`u-0011`, 0.000 → 0.333) on targets averaging 2.4×. Two sets, judged and frozen separately,
agree: every apparent ingestion *gain* this project has reported is a PDF case whose judged
target the projection enlarged or collapsed, and every format whose structure survives loses a
little.

## Alternatives Considered

- **Re-anchor `u-1003` to a different twin chunk.** The option 5.26 offered second. Rejected
  on the measurement: `#/0` covers the judged passage at 1.0000 and no other chunk of the
  document exceeds 0.7097, so there is no "several good ones" to have chosen badly among. The
  carry had one candidate and took it.
- **Re-judge the source case, so the twin's anchor follows.** The judged passage is the
  64-token preamble that names `[[tool.uv.index]]` once, and three sections the corpus devotes
  to the key — *Defining an index*, *Pinning a package to an index*, `--index-url and
  --extra-index-url` — outrank it on the Markdown corpus. There is a real question there.
  Rejected here, twice over: `uv/release` is a **frozen, held-out** set judged before this
  corpus existed (ADR-0027), and re-judging it inside the change that reads a corpus repair is
  the conjunction `tools/check_frozen_release_sets.py` refuses. It is filed as roadmap 5.30,
  where it can be argued from the documents and nothing else.
- **Treat 0.7602 as a regression and find retrieval work to recover it.** Rejected outright,
  and it is the reason this item was filed before anything was touched: the previous number
  was produced by a corpus defect, and tuning to restore it would be fitting the ranker to a
  rendering bug. D-010 says fix the product, not the benchmark; this is the same rule pointed
  at the instrument.
- **Re-bless the baseline to the pre-repair numbers.** Rejected: the baseline already carries
  0.7602, blessed with the repair in PR #122 where the corpus moved. Nothing here moves a
  corpus, so nothing here re-blesses.
- **Gate the "above its source" condition** — fail the build when a twin case outscores its
  Markdown. Rejected: three cases do it today for a reason this ADR states and does not
  propose to fix (a PDF has no headings; that is what a PDF is), so the gate would be red on
  arrival and would have to be granted exceptions, which is a threshold by another name. The
  report names them; a reader decides.
- **Add a per-case column to the committed baselines instead.** They already have one
  (ADR-0052), which is how the two halves of this were read — but a baseline records one
  corpus, and the fact that matters here is a *difference between two corpora*. It has to be
  printed where the pairing happens.

## Consequences

- **`uv-ingested/release`'s `exact` slice is correct at 0.7602** and its fall from 0.7893 is
  recorded as a repair, not a regression. Two cases moved, not one as 5.26 estimated:
  `u-1003` 0.63093 → 0.50000 (rank 2 → 3) and `u-1021` 0.315465 → 0.30103 (rank 8 → 9),
  which is 90 % and 10 % of the slice's 0.0291. `u-1021` is judged in the same repaired
  `dependencies` document and moved one rank as its own siblings became competitors — the
  same mechanism, on the other side of the ledger, and its source scores 0.3333 at rank 7.
- **The instrument now shows what the averages average away**, and it changes a reading that
  has stood since roadmap 4.10: the `pdf` row's ranking advantage is three cases carried on
  4.7× targets, not a property of ingestion. `eval/README.md`'s projection-cost table is
  refreshed with the current run — it still described the 14-case corpus of 4.10 and a 10.6×
  ratio, both superseded.
- **A standing gap is now as visible as a moving one.** The defect this item found was three
  milestones old and only became legible when something disturbed it. The per-case block is
  the cheapest thing that makes the standing state readable on every run.
- **No code in `src/` changes**, no judged set is edited, no baseline is re-blessed and no
  gate moves. `tools/check_frozen_release_sets.py`'s conjunction is not merely satisfied, it
  is irrelevant — the shape roadmap 4.12 established for a judgement question.
- **Filed rather than absorbed:** roadmap 5.30 — whether `u-1003`'s source judgement names
  the right section; roadmap 5.31 — `u-1004`, the PDF case that scores **0.000** on the twin
  against 0.387 on its source, in the same document whose neighbour gains, which is the `pdf`
  row's other half and is not explained by target size; and roadmap 5.33 — the carry
  collapsing several judged units onto one twin chunk, including the duplicate anchor it
  wrote into `u-1001` and nothing reports.
- **This ADR does not fix the collapse**, because fixing it edits the carried set and
  re-blesses the twin's baselines, which is the one thing an item that reads a corpus repair
  must not do in the same change (`tools/check_frozen_release_sets.py`; the shape roadmap
  4.12 established). What it does is make the condition visible on every run.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §7.1 (frozen sets, slices), §7.3
  (reported versus gated).
- Decision log: D-010 (fix the product, not the benchmark).
- Re-runnable: `python tools/measure_projection_cost.py --set release.jsonl`; the ranks above
  from `mycelium search "tool.uv.index" --path eval/corpora/uv-docs --explain` and the same
  against `eval/corpora/uv-docs-ingested`.
- The carry receipt: `eval/corpora/uv-docs-ingested/eval/carry.json`, where this anchor is
  recorded at coverage 1.0.
- [ADR-0039](0039-measure-what-projection-costs.md), [ADR-0095](0095-read-the-corpus-in-the-dialect-it-is-written-in.md).
