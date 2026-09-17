# ADR-0122: Score what a citation names, and read it from the chunk rather than the anchor

- **Status:** Accepted
- **Date:** 2026-09-17
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.2
- **Related:** [ADR-0040](0040-refuse-the-pdf-layout-pipeline-on-its-merits.md) (which filed
  this item, and which this makes re-decidable),
  [ADR-0029](0029-let-a-judgment-name-a-section.md) (the section-vs-chunk rule the item
  named as its seed), [ADR-0007](0007-adopt-structure-first-chunking.md) (the title-heading
  convention that nearly made this metric wrong),
  [ADR-0039](0039-measure-what-projection-costs.md) (where passage size was first found
  deciding results), [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)
  (a gate that fires on everything selects for being ignored),
  [ADR-0013](0013-adopt-the-evaluation-harness.md); D-010; NFR-5; spec 04 §§7.2, 7.3;
  roadmap 4.9, 6.7

## Context

Roadmap 6.7, filed by ADR-0040 in its own words: *"every metric here ranks chunks, and none
of them asks whether the anchor a reader is handed names the right thing."*

That gap decided roadmap 4.9 in the negative. docling's ML pipeline recovers 82 % of an
ingested PDF's headings, which turns `#/0` into `#platform-support/0` — the difference
between a citation a reader can find and one only this product can resolve. ADR-0040 refused
the pipeline on measured retrieval regressions and recorded that it was refusing a benefit it
could not score, naming this item as the thing that would make the trade decidable.

The gap is also 1.0's on its own terms. NFR-5 makes citation **coverage** a gate — G1, every
anchor resolves, no exceptions — and says nothing about citation **precision**, which is the
property an agent actually depends on when it hands evidence to a human who will check it.
A run can be perfect on G1 and hand back ten anchors that name nothing.

## What the item predicted, and what the measurement said

The item predicted the metric would need *"a judged notion of the correct anchor granularity
per case"*, with ADR-0029's section-vs-chunk rule as the seed. **It does not, and the seed is
what says so.**

Whether an anchor names a place in its document is a fact about the anchor and the snapshot,
readable without any opinion about the query — and the one question a judgement could add
here, ADR-0029 has already answered. A judgement that names a *section* has declared that any
chunk under it is an acceptable answer; citing one chunk of a judged section is therefore not
a citation failure by the judge's own standard. There is nothing left for a new judged input
to decide, and adding a subjective one to a decidable question would have made the
measurement weaker and the 133 committed cases re-judgeable for no gain.

The evidence is that the metric discriminates sharply with no judgement at all. Over every
chunk of the three corpora the gates run on, by the lane each document came through
(`tools/measure_citation_precision.py`):

| corpus | lane | chunks | located | median tokens | mean tokens |
|---|---|---:|---:|---:|---:|
| this repository | authored | 1 461 | **0.999** | 197 | 318 |
| `uv-docs` | authored | 568 | **0.998** | 134 | 187 |
| `uv-docs-ingested` | docx | 126 | **1.000** | 146 | 193 |
| `uv-docs-ingested` | html | 429 | **0.998** | 90 | 148 |
| `uv-docs-ingested` | **pdf** | 37 | **0.000** | **501** | **512** |

Three lanes keep headings and one loses all of them, and the lane that loses them also
returns passages three to five times the size — so the reader of a PDF citation is told to
find an unnamed position and then scan half a page. That is ADR-0040's unscoreable benefit,
scored, and it is not a ranking problem: no rank metric moves when a passage keeps its text
and loses its name.

## The finding nobody filed this item for

Reported per run, against the incumbent D-010 says is the real competitor, the metric says
something the item did not anticipate and no existing number could show:

| corpus | set | arm | nDCG@10 | coverage | located | cited tokens |
|---|---|---|---:|---:|---:|---:|
| ours | dev | mycelium | 0.474 | 1.000 | 1.000 | **650** |
| ours | dev | grep | 0.220 | 1.000 | 1.000 | **6 453** |
| ours | release | mycelium | 0.501 | 1.000 | 1.000 | **254** |
| ours | release | grep | 0.222 | 1.000 | 1.000 | **7 289** |
| uv-docs | release | mycelium | 0.614 | 1.000 | 1.000 | 217 |
| uv-docs | release | grep | 0.532 | 1.000 | 1.000 | 421 |
| uv-ingested | release | mycelium | 0.614 | 1.000 | **0.876** | 244 |
| uv-ingested | release | grep | 0.575 | 1.000 | **0.716** | 468 |

**The product's citations are between two and twenty-nine times smaller than the
incumbent's**, and on the ingested corpus they are also better located. Both effects have the
same cause, and it is grep's ranking rather than bad luck: a passage is scored by how many
query terms it contains, so the longest chunks win, and the longest chunks are the ones whose
citation costs a reader most. On the ingested corpus the longest chunks are the PDF lane's
unlocated pages, so the incumbent surfaces precisely the passages that cite worst.

One case makes it concrete. For *"how do I report a security vulnerability"* on this
repository, the product's first citation is `SECURITY.md#reporting-a-vulnerability/0` — 218
tokens, named after the question. The incumbent's first is
`ROADMAP.md#milestone-6-v0-6-0-stable-spec-phase-4/1` — **10 798 tokens** — and it reaches
`SECURITY.md` fourth.

D-010's standing instruction is *"if Mycelium OS does not visibly beat grep, fix the product,
not the benchmark."* On this dimension it visibly does, by a wide margin, and until this item
there was no way to say so.

## The mistake this ADR is named for

The first implementation read locatedness out of the **anchor string** — does
`<doc>#<heading-slug-path>/<ordinal>` carry a non-empty path — which is the obvious reading
and is wrong. An anchor omits the document's single level-1 heading, because the document is
already identified by its path and repeating its title in every anchor is noise (ADR-0007).
So a passage sitting under a real title and before the first `##` is spelled
`docs/patterns/README.md#/0` — character for character what chunk 0 of a structureless
document looks like.

Measured rather than reasoned about: parsing the anchor calls **193 of this repository's
1 461 chunks** unstructured, when exactly one of them is. It reports 0.867 where the truth is
0.999, and — worse for the decision it exists to support — it would have credited the PDF lane
with the same defect the authored lane "has", flattening the one distinction the metric is
for.

Locatedness is therefore read from `Chunk.heading_path`, supplied to the metric as a set
built from the snapshot, exactly as gate G1's resolvable-anchor set is.

## Decision

**`mycelium eval` reports two new numbers per case and per slice, beside citation coverage.**

- **`citation_precision`** — the share of the top-ten returned anchors whose passage sits
  under at least one heading. Ten because that is the window a reader is handed:
  `CaseResult.retrieved` already records ten *"because the manifest records what a reader
  would see"*, and `mycelium_search` defaults to eight.
- **`cited_tokens`** — the mean size of those passages, the companion reading without which
  the share is half a picture. ADR-0039 and ADR-0040 both found this quantity deciding
  results and could only name it a confound; reported beside the share, it becomes a reading.

**Computed over every returned anchor, not only the ones that answered.** Scoring only
credited hits sounds more targeted and is worse twice over: it couples a citation-quality
number to ranking quality, and it measures two arms of a comparison on different sample
sizes. A reader is handed all ten.

**Reported, not gated, and the condition that would arm it is named.** Today the aggregate on
the ingested corpus is dominated by one lane reading 0.000 for a reason already decided
(ADR-0040), so a threshold picked now would encode that decision rather than measure
anything — which is how a gate becomes decoration (ADR-0053). What arms it is the ADR-0040
re-take that this metric makes possible. The premise is pinned by a test rather than left in
prose: `tests/test_eval_ingested_corpus.py` asserts that the PDF lane is unlocated, so the day
anyone ships PDF structure, a failing test points at this paragraph.

**`tools/measure_pdf_structure.py` carries the two columns**, so ADR-0040's re-take is one
command rather than a new piece of work. It is the one thing this item could not finish: the
ML arm needs ~2.4 GB of packages and weights that this environment does not carry and that
ADR-0040 already established CI must not. What the prize is worth is now quantified — the
text-layer arm reads 0.000 against a Markdown control at 0.998 — and what it costs was
measured in ADR-0040. The trade is on the table; taking it needs the download, and it stays
the maintainer's.

## Alternatives Considered

- **A judged per-case granularity, as the item specified.** Rejected on the argument above:
  ADR-0029 already answers the only question it would add, and the metric discriminates
  without it. Recorded here because the item asked for it by name and a silent omission would
  read as an oversight.
- **Score only the citations that satisfied a judgement.** Rejected: it makes a
  citation-quality number depend on ranking quality, and compares arms on unequal samples.
- **Parse locatedness out of the anchor string.** Implemented first, measured, rejected —
  the section above is the whole argument.
- **Grade locatedness by heading depth** (`#usage/install/0` scoring above `#usage/0`).
  Rejected as unnormalisable: a flat document affords depth 1 and a nested one depth 3, so a
  depth score would grade the corpus's structure rather than the citation's quality, and
  normalising against "the deepest path available at that point" is circular — that path is
  the chunk's own.
- **Express precision as judged-answer tokens over cited tokens**, the classic reading of the
  word. Rejected: when a judgement names a section, nothing records how much of it is the
  answer, so the ratio is undefined for exactly the cases it would matter on — and defining
  it would need the re-judging the paragraph above rejects.
- **Gate it now at a threshold today's corpora pass.** Rejected: that is fitting a bar to the
  present, and on the corpus that matters it would encode ADR-0040's refusal as a number.
- **Leave it in `tools/` as a study rather than in the harness.** Rejected: ADR-0040 could
  not weigh a benefit because it was not in the run manifest, and a number that lives only in
  a tool nobody runs at review time is the same failure with a different shape.

## Consequences

- **`CaseResult` and `MetricSummary` each gain two fields**, both defaulted, so a manifest
  written before this validates unchanged. They are evaluation records, which
  `docs/compatibility.md` explicitly places outside the five frozen contracts — the freeze
  covers KIR and the snapshot manifest, not the harness's own assets (ADR-0114, ADR-0022).
- **No committed number moves.** The baselines store `overall_ndcg_at_10`, per-slice means
  and per-case nDCG; none of them is touched, so no re-bless is needed and gate G3 is
  unaffected. `retrieval_identity()` reads constants out of `retrieval.py`, which this does
  not touch, so `eval/g2-verdict.json` stays current.
- **`mycelium eval` prints one more line**, beside the coverage line it belongs with.
- **`citation_precision` is near-silent on the authored corpora, and `cited_tokens` is not.**
  Both of this project's Markdown corpora read 1.000 located, which is the right outcome for
  documents that have headings — nobody should read that quiet as the metric failing to work.
  The size half speaks everywhere, and it is where the incumbent comparison lives.
- **The grep comparison gains a dimension, and it is the product's strongest.** A 29× gap in
  what a reader must scan is a bigger claim than any nDCG margin this project has ever
  reported, and it was invisible for six milestones. Roadmap 6.4 quantifies the agent-task
  verdict's rule ahead of arming it at 1.0; this belongs in that argument, and 6.4's report is
  where it should be published next.
- **A limitation, stated.** Locatedness is binary: it asks whether a passage sits under a
  heading, not whether the heading is a *good* name for it. A document whose sections are all
  called "Notes" scores 1.000. That is a judgement about writing, and no measurement here
  claims to make it.

## References

- Re-runnable: `python tools/measure_citation_precision.py` (the table above);
  `mycelium eval . --set eval/release.jsonl --against grep` (the per-run numbers);
  `python tools/measure_pdf_structure.py --artifacts <dir>` (the ADR-0040 re-take, with the
  two columns added).
- Spec 04 §7.2 (amended here), §7.3 (the gate table this deliberately does not join); NFR-5.
- [ADR-0040](0040-refuse-the-pdf-layout-pipeline-on-its-merits.md) — *"Filed as roadmap 6.7:
  score citation precision, not only rank."*
