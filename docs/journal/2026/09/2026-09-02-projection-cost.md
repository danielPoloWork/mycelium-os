# 2026-09-02 — judging the same document twice (roadmap 4.10)

- **Session scope:** roadmap 4.10 — an ingestion-heavy corpus joins the eval set, the third
  and last clause of the M4 exit gate (spec 04 §7, D-010).
- **PR:** #58 (`feat/ingestion-heavy-eval-corpus`). Follows #57 (4.7), merged as `b0f6b1e`.
- **Milestone 4:** 4.1–4.7 and 4.10 done; 4.8 and 4.9 open. 5.7 filed here.

## The item asked for judgements, and the project had already banned writing them

"A corpus of ingested PDF/DOCX/HTML with relevance judgements" is the roadmap line. The
trouble is in the last two words: ADR-0027 exists because the agent that builds the
retriever should not also decide what the right answer is, and here the same agent had just
written the parsers as well. Hand-judging a new corpus of ingested documents would have been
the same mistake with one more conflict of interest stacked on it.

The way out is to notice that the *interesting* question is paired. Ingestion's promise is
that an evidence document projected from a PDF is usable knowledge; nothing had tested
whether it is **retrievable**. And a paired question needs no new judgements at all: take the
corpus that is already judged, render it into DOCX, HTML and PDF, put it back through
`mycelium ingest`, and score the same queries with the same grades against what came out.

So the third corpus is the second corpus. Only the anchor is computed — the chunk of the
twin document that best covers the passage the original judgement already picked — and every
anchor that will not carry is dropped by name, because a silent drop is the one way the
comparison could quietly make the ingested side easier.

## What it measured

Release set, the same 14 cases on both sides:

```text
                    nDCG@10          MRR             R@10           R@50      target
overall   14   0.327 → 0.385   0.266 → 0.387   0.583 → 0.583   0.958 → 0.958
docx       2   0.587 → 0.587   0.600 → 0.600   0.750 → 0.750   1.000 → 1.000    1.0x
html       3   0.167 → 0.167   0.135 → 0.136   0.333 → 0.333   1.000 → 1.000    1.0x
pdf        5   0.379 → 0.517   0.260 → 0.550   0.800 → 0.800   1.000 → 1.000   10.6x
```

**Recall does not move.** Not in any format, not in either set. The passages that answer a
question come back whether they arrived as Markdown or as a rendered DOCX.

**Where structure survives, projection changes nothing** — DOCX and HTML are not close, they
are *identical* to three decimals. That is a stronger result than I expected to be able to
report, and it is the one sentence worth carrying out of this item: the evidence document a
DOCX becomes is, for retrieval, the document.

**The PDF gain is refused.** +0.138 nDCG@10 looks like ingestion improving retrieval, which
should have been the first thing to distrust. The last column is why: a PDF has no headings,
so its chunks are page-sized, and the carried anchor is 10.6× the tokens of the Markdown
chunk it came from. A bigger target is easier to rank highly. I added that column
specifically so the number could not be quoted without its confound attached.

## Two things fell out sideways

**The graph does not survive projection.** 229 edges become 10. A relative link between two
documents is read fine by the parsers and written fine by the projector, and then resolves
against nothing, because the evidence tree is flat and the source tree was not. So an
ingested corpus is a set of isolated documents — `mycelium_neighbors` has nothing to say
about any of them, and 5.3's graph expansion would have nothing to expand over. Filed as 5.7,
where the resolution question belongs.

**The PDF arm is an accidental experiment for ADR-0031.** That ADR diagnosed our ranking
failure as BM25 length normalisation over wildly heterogeneous chunks, and named "score at
the section level so length normalisation compares comparable units" as the next hypothesis.
The PDF arm has uniformly page-sized chunks, and ranking went up. It is confounded and proves
nothing alone — but it is the first evidence in that hypothesis's favour, and 4.8 is where it
should be read.

## The defect committing a corpus surfaced

Evidence documents had never been committed before. The moment they were, the frontmatter
said:

```yaml
source: "file:///C:/Users/Polo/AppData/Local/Temp/.../sources/cache.pdf"
```

An absolute path, naming the ingesting machine, in a file that goes into Git. Two people
ingesting the same source produce two different documents, and a local directory layout —
username included — is published to everyone who can read the repository.
[BUG-0017](../../../bugs/2026/09/BUG-0017-evidence-frontmatter-carries-an-absolute-path.md),
fixed in the connector, where the roots are known.

It had survived two milestones because the URI was *right* for both of its earlier
consumers — an error message and an in-`.mycelium/` lookup key — and the third consumer
arrived in a different PR with nobody re-asking the question. Fixing it also broke
`--forget` for the length of one test run, because the quarantine key was rebuilt by a second
copy of the same rule. Both now go through the connector.

## One measurement decided the corpus's shape

I had intended to generate the rendered binaries rather than commit them, to keep ~1.2 MB out
of the tree. Then typst turned out to embed a build identifier: the same markup compiles to
different bytes on consecutive runs, and `SOURCE_DATE_EPOCH` does not fix it. Inputs that
cannot be re-derived have to be kept, so `--render` became a one-time provenance act and the
drift guard moved to where it is exact — `--check` re-ingests the *committed* bytes, and any
difference is a change in ingestion rather than in pandoc's version number.
