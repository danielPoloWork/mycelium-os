# Third judged corpus — the second one, ingested

The same 81 documents as [`../uv-docs`](../uv-docs/README.md), rendered into DOCX, HTML and
PDF and put back through `mycelium ingest`. What is scored here is
`knowledge/evidence/` — the Markdown the **projector** wrote from what the parsers read
(spec 02 §5, roadmap 4.10).

| | |
|---|---|
| Upstream | [astral-sh/uv](https://github.com/astral-sh/uv), via [`../uv-docs`](../uv-docs/README.md) at commit `7896d580c245493c88ea5be56724e6e42ee7d197` |
| Content | 81 documents — 6 DOCX, 70 HTML, 5 PDF |
| Vendored | `sources/` (1.2 MB of rendered binaries) + `knowledge/evidence/` (650 KB of projected Markdown) |
| Licence | MIT, [`LICENSE`](LICENSE) — Copyright (c) 2025 Astral Software Inc. |
| Judgements | **None written here.** Carried across from `../uv-docs` by `tools/build_ingested_cases.py` |
| Provenance | [`provenance.json`](provenance.json) — every document, its format, its source digest, and the parser that read it |

## Why a twin and not a new corpus

The M4 exit gate asks for an ingestion-heavy corpus in the eval set. The question worth
asking of one is whether **projection costs retrieval**, and that question is paired: it
needs the same documents, the same queries and the same grades on both sides, with the
format as the only variable.

Writing fresh judgements over ingested documents would have answered a different question,
and answered it with judgements written by the same agent that wrote the parsers — the trap
[ADR-0027](../../../docs/adr/0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md)
exists to name. Here nothing is judged. Every query, grade and slice is copied verbatim from
sets frozen before this corpus existed; only the *anchor* is computed, by finding the chunk
of the twin document that best covers the passage the original judgement already picked.

## How it was made

```bash
python tools/build_ingested_corpus.py --render   # renders sources/ — a one-time act
python tools/build_ingested_corpus.py            # ingests sources/ -> knowledge/evidence/
python tools/build_ingested_cases.py             # carries the judgements across
python tools/measure_projection_cost.py          # the paired comparison
```

**Format assignment is mechanical.** The documents a judgement points at, sorted by path,
take `docx`, `html`, `pdf` in rotation. Every other document is HTML: its format cannot
change a judgement — it is a distractor either way — and it makes those distractors *strong*
(their headings survive), which is the conservative choice. The rotation was fixed before
anything was measured, and `provenance.json` is how you check that.

**pandoc writes the DOCX and the HTML; PDF goes through typst** (`pip install typst`), which
is one wheel rather than a LaTeX distribution. Image references become their alt text first,
uniformly for all three: the vendored corpus is prose, so an image path points at nothing.

## Why `sources/` is committed

typst embeds a build identifier: compiling the same markup twice produces two different
PDFs, and `SOURCE_DATE_EPOCH` does not fix it. A corpus whose inputs cannot be re-derived
byte-for-byte has to *keep* its inputs — so the rendered binaries are vendored, and
rendering is a provenance act rather than a build step.

That leaves the reproducible half where it belongs. `build_ingested_corpus.py --check`
re-ingests the committed sources and compares, so a change in docling, pandoc, PDFium or the
projector shows up as a named difference. It runs in CI (`ingest / lanes`).

## What the corpus is for, and what it showed

The paired comparison over the release set, the same 14 cases on both sides:

| | n | nDCG@10 | MRR | R@10 | R@50 | judged passage |
|---|---:|---|---|---|---|---|
| overall | 14 | 0.327 → 0.385 | 0.266 → 0.387 | 0.583 → 0.583 | 0.958 → 0.958 | |
| docx | 2 | 0.587 → 0.587 | 0.600 → 0.600 | 0.750 → 0.750 | 1.000 → 1.000 | 1.0× |
| html | 3 | 0.167 → 0.167 | 0.135 → 0.136 | 0.333 → 0.333 | 1.000 → 1.000 | 1.0× |
| pdf | 5 | 0.379 → 0.517 | 0.260 → 0.550 | 0.800 → 0.800 | 1.000 → 1.000 | **10.6×** |

**Recall does not move — anywhere.** Where structure survives (DOCX, HTML) the numbers are
not merely close, they are *identical*. The one apparent gain is PDF's ranking, and the last
column is why it should not be read as one: a PDF's chunks are page-sized, so the carried
anchor is ten times the size of the Markdown chunk it came from, and a bigger target is
easier to rank highly. The reasoning is in
[ADR-0039](../../../docs/adr/0039-measure-what-projection-costs.md).

## Working with it

A `mycelium build` pins `mycelium_id` into each evidence document's frontmatter — the
documented behaviour of a first build — so building this corpus locally leaves a dirty tree.
Those ids are **not** committed: a projection carries no `mycelium_id` (the projector does
not write one, spec 03 §3), and `--check` compares against what ingestion produces.
`git checkout eval/corpora/uv-docs-ingested` before committing.

## What it is not

- **Not a claim about `uv`,** and no judgement here is a statement about that project's
  documentation. It is also not a claim about DOCX, HTML or PDF *in general*: these are
  pandoc's and typst's renderings of Markdown, which are cleaner and more regular than the
  documents a real organisation ingests.
- **Not enough cases to generalise.** Two to five per format, and the anchor-carrying rule
  is mildly favourable to the ingested side by construction. The result is a floor — "this
  did not cost recall here" — not a benchmark.
