# ADR-0039: Measure what projection costs, by judging the same document twice

- **Status:** Accepted
- **Date:** 2026-09-02
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.10; RFC-0001; spec 02 §5; spec 04 §§7.1, 7.6; D-010, D-017;
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0031](0031-refuse-three-rerankings.md),
  [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md),
  [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md),
  [ADR-0038](0038-declare-the-corpus-then-compare-it.md);
  [BUG-0017](../bugs/2026/09/BUG-0017-evidence-frontmatter-carries-an-absolute-path.md)

## Context

The Milestone 4 exit gate has three clauses. Two were closed by mechanical checks: zero
silent element loss (4.7, ADR-0038) and a hostile suite that quarantines without failing a
build (4.2). The third — *an ingestion-heavy corpus joins the eval set* — is different in
kind, because a corpus only joins the eval set if it comes with **judgements**, and a
judgement is an opinion about a document.

That is a problem this project has already written an ADR about. ADR-0027 split dev from
release and vendored a corpus nobody here wrote, precisely because the agent that builds the
retriever should not also be the one deciding what the right answer is. A new corpus of
ingested documents, judged by hand, would have walked straight back into it — and worse,
because the same agent had just written the parsers being measured.

There is also a more interesting question available than "how does the product score on
these documents". Ingestion's whole promise is that an evidence document projected from a
PDF is usable knowledge (spec 02 §5). Nothing so far has tested whether it is *retrievable*.
The fidelity report cannot answer it: it counts what the parser produced against what the
parser produced, which is why 4.7 had to bring an independent inventory (ADR-0038), and a
PDF whose headings never existed as nodes is reported as 100 % represented, 0 lost.

## Decision

**The third corpus is the second corpus, ingested.** `eval/corpora/uv-docs-ingested` holds
the same 81 upstream documents as `eval/corpora/uv-docs`, rendered into DOCX, HTML and PDF
and put back through the real evidence lane. It is built, gated and reported beside the
other two.

**Nothing in it is judged.** Every query, grade and slice is copied verbatim from the frozen
`uv-docs` sets. Only the anchor is computed: `tools/build_ingested_cases.py` finds the chunk
of the twin document that best **covers** the passage the original judgement already picked
— coverage, not F1, because an ingested chunk is often larger and penalising it for that
would measure the chunker. An anchor that cannot be carried above a stated floor is dropped
by name, and a case that loses every anchor is dropped whole; both are printed, because a
silent drop is the one way this comparison could quietly make the ingested side easier.

**Format assignment is a rotation, fixed before measurement.** Judged documents, sorted by
path, take `docx`, `html`, `pdf` in turn; everything else is HTML. That removes the freedom
to choose an assignment that flatters a result, and `provenance.json` lets a reader check
the rotation rather than trust it.

**The rendered sources are vendored.** typst embeds a build identifier, so the same markup
compiles to two different PDFs — measured, and `SOURCE_DATE_EPOCH` does not fix it. Inputs
that cannot be re-derived have to be kept, so rendering is a one-time provenance act and
`--check` re-ingests the *committed bytes*, which keeps the reproducible half exactly
reproducible and puts the drift guard on ingestion rather than on pandoc's version.

**And the comparison is reported, never gated.** `tools/measure_projection_cost.py` scores
the two corpora over the cases they share and prints the difference per format, beside the
size of the judged passage on each side. It is evidence about the product, not a threshold:
nobody has the data to set one, and a constant chosen to look rigorous is worse than a
number a reviewer reads (the discipline spec 04 §7.3 asks for pre-GA).

## What it measured

Release set, the same 14 cases on both sides:

| | n | nDCG@10 | MRR | R@10 | R@50 | judged passage |
|---|---:|---|---|---|---|---|
| overall | 14 | 0.327 → 0.385 | 0.266 → 0.387 | 0.583 → 0.583 | 0.958 → 0.958 | |
| docx | 2 | 0.587 → 0.587 | 0.600 → 0.600 | 0.750 → 0.750 | 1.000 → 1.000 | 1.0× |
| html | 3 | 0.167 → 0.167 | 0.135 → 0.136 | 0.333 → 0.333 | 1.000 → 1.000 | 1.0× |
| pdf | 5 | 0.379 → 0.517 | 0.260 → 0.550 | 0.800 → 0.800 | 1.000 → 1.000 | **10.6×** |

Three readings, in decreasing order of confidence:

1. **Projection does not cost recall.** R@10 and R@50 move by 0.000 in every format and in
   both sets. The passages that answer a question come back either way.
2. **Where structure survives, projection changes nothing at all.** DOCX and HTML do not
   merely score closely — they score *identically*, to three decimals, on three of four
   metrics. The evidence document a DOCX becomes is, for retrieval, the document.
3. **PDF's apparent gain is a measurement artefact, and the last column is the proof.** A
   PDF has no headings (ADR-0032), so its chunks are page-sized, and the carried anchor is
   **10.6×** the tokens of the Markdown chunk it came from. A bigger target is easier to
   rank highly. The dev set says the same thing more quietly: a 1.9× target for +0.000
   nDCG@10.

A fourth result is not about retrieval at all. The Markdown corpus compiles **229 edges**;
its ingested twin compiles **10**. A relative link between two documents does not survive
rendering and re-projection — the target is a path that no longer exists once the documents
are flat under `evidence/`. Ingested knowledge is, today, a graph of isolated documents.

## Alternatives Considered

- **A new corpus of real-world PDFs and DOCX, judged by hand.** The obvious reading of the
  roadmap line, and it would have been a more realistic corpus — pandoc's renderings are
  cleaner than what an organisation actually ingests. Rejected because it cannot answer the
  paired question at all, and because its judgements would come from the same agent that
  wrote the parsers being scored (ADR-0027). Kept as the thing to do when judgements can
  come from someone else — spec 04 §7.6's 1.0 target.
- **Render every document to all three formats and index them together.** One corpus, three
  copies of each document, a `format` label per case. Rejected outright: three near-duplicate
  copies in one index destroy precision by construction, and the experiment would measure
  deduplication rather than projection.
- **Three sibling corpora, one per format.** The cleanest isolation of the variable, and
  rejected on cost and coherence: three more builds, three more gated sets, and eight case
  sets in a table that is already the hardest thing in `eval/README.md` to read. The rotation
  gets the per-format breakdown at a third of the weight.
- **Re-judge the ingested corpus by hand and compare judgements.** Would have removed the
  anchor-carrying bias. Rejected because it replaces a stated, mechanical, auditable bias
  with an unstated human one, and because re-judging after seeing a ranking cannot be told
  apart from fitting the set to the result — the reasoning already recorded at roadmap 3.15.
- **Regenerate the sources instead of vendoring them.** ~1.2 MB smaller, and the tool is the
  provenance. Rejected on the measurement: typst is not reproducible, so the corpus could
  not be re-derived, and a drift check would have been testing pandoc's version number
  rather than this project's ingestion.
- **Gate on the projection delta.** Tempting — "projection may not cost more than X" is a
  real property. Rejected: with two to five cases per format there is no threshold anyone
  could defend, and a gate nobody believes is a gate everyone re-blesses.

## Consequences

- **The eval set is three corpora and six sets**, and CI builds and gates all three. The
  third adds ~35 s to the eval job.
- **~1.9 MB is vendored** — 1.2 MB of rendered binaries, 650 KB of projected Markdown. The
  cost is stated in the corpus README beside the reason, the way `uv-docs` states its 700 KB.
- **A finding worth acting on, filed rather than acted on here.** Edges 229 → 10 says
  ingested documents are not linked to each other or to anything else. That is a real gap in
  what ingestion delivers, and it belongs to the graph milestone, not to this item —
  roadmap 5.7.
- **A second finding that lands on ADR-0031.** That ADR diagnosed our ranking failure as
  BM25 length normalisation over wildly heterogeneous chunks, and named "scoring at the
  section level, as an indexing change, so length normalisation compares comparable units"
  as the next hypothesis. The PDF arm is an accidental natural experiment in exactly that:
  uniform page-sized chunks, and ranking went up. It is confounded by target size and proves
  nothing on its own — but it is the first evidence in the hypothesis's favour, and it is
  recorded where 4.8 will look for it.
- **`mycelium ingest` writes portable provenance now.** Committing evidence documents for
  the first time surfaced [BUG-0017](../bugs/2026/09/BUG-0017-evidence-frontmatter-carries-an-absolute-path.md):
  the file connector stamped an absolute `file:///…` path into every projected document, so
  two people ingesting the same file produced two different documents and one machine's
  directory layout was published to whoever could read the repository. Fixed in the
  connector, where the roots are known.
- **The known limitation is the one to quote when quoting the numbers.** The anchor-carrying
  rule picks the chunk with the most word overlap with the judged passage, which is mildly
  favourable to the ingested side. Every conclusion above is stated in the direction that
  bias does *not* help: "recall did not fall", "structure-preserving formats are identical",
  "the PDF gain is an artefact".

## References

- Spec 02 §5 (the evidence lane); spec 04 §7.1 (dev/release split), §7.3 (relative
  discipline pre-GA), §7.6 (corpora nobody here wrote).
- Measured this session: typst compiles the same markup to different bytes on consecutive
  runs, with and without `SOURCE_DATE_EPOCH`; the Markdown corpus compiles 2 244 chunks and
  229 edges, its ingested twin 2 073 chunks and 10 edges.
- [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md) — why the
  judgements here are carried rather than written.
- [ADR-0031](0031-refuse-three-rerankings.md) — the ranking diagnosis the PDF arm speaks to.
- [ADR-0038](0038-declare-the-corpus-then-compare-it.md) — the other half of the exit gate,
  and the same principle: a report cannot corroborate itself.
