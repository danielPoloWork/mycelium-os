# ADR-0040: Refuse the PDF layout pipeline on its merits, not on its constraints

- **Status:** Accepted
- **Date:** 2026-09-02
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.9; RFC-0001; spec 02 §5; NFR-1, NFR-3, NFR-6; D-007, D-013, D-017;
  [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md),
  [ADR-0031](0031-refuse-three-rerankings.md),
  [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md),
  [ADR-0039](0039-measure-what-projection-costs.md)

## Context

v1 reads a PDF's text layer and nothing else: characters, page numbers, no headings, no
tables, nothing from a scanned page ([ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md)).
The structure lives in docling's ML pipeline, and 4.1 declined it on three grounds it had
measured only partly. Roadmap 4.9 was filed to settle it, and was explicit that those three
grounds were **acceptance criteria, not obstacles**:

- **(a) the closure** — `pip install docling` resolves sixty-odd packages including `torch`,
  and downgrades this project's own `typer` pin;
- **(b) NFR-6** — the weights are fetched from HuggingFace on first use, which is an
  unconfigured network call, so it needs the `allow_download` / `artifacts_path` consent
  shape [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) established for
  the embedder;
- **(c) NFR-1** — float inference is not promised byte-identical across the CI matrix, so the
  stage must either prove reproducibility or declare `deterministic = false` and stay out of
  the G6 golden.

Measuring them changed the picture, and not in the direction the earlier ADR expected: **all
three turn out to be satisfiable.** Which meant the decision could no longer rest on them,
and had to be taken on whether the feature is worth having.

Roadmap 4.10 had just built the apparatus that makes that answerable. The ingested corpus is
a twin of a Markdown one, so the *true* structure of every PDF is known rather than guessed,
and the frozen judgements can be carried onto a third variant and scored against a control.

## The measurements

Every number below is reproduced by `tools/measure_pdf_structure.py`, which ships with this
ADR for the reason [ADR-0031](0031-refuse-three-rerankings.md)'s harness did: a refusal that
cannot be re-run is an opinion with a date on it.

**(a) The closure.** ~1.0 GB of Python packages, 121 top-level distributions, against a
runtime closure of four and an embeddings extra of ~20. The weights are a further **1 372 MB**.
**~2.4 GB** to read a PDF's headings.

**Cost per document.** ~35 s of one-time model loading, then **2–3.5 s per page** on CPU,
across two runs on the same machine.
A two-hundred-page manual is ten minutes. NFR-3 budgets a single-document *rebuild* at 2 s.

**(b) The network.** Satisfiable, with a caveat worth writing down. Pointing
`PdfPipelineOptions.artifacts_path` at a pre-fetched model set makes the whole pipeline
silent, verified under `HF_HUB_OFFLINE=1`. But out of the box — no `artifacts_path` —
converting a PDF fetches OCR weights from **`modelscope.cn`** at conversion time, and
`HF_HUB_OFFLINE=1` does **not** stop it: that downloader belongs to a transitive dependency
and does not read HuggingFace's switch. So the offline posture D-017 requires is available
here only because *we* would have fetched everything in advance — not because the library
honours a flag. That is a guarantee with a version number on it, not a contract.

**(c) Determinism.** The same PDF, converted twice by two freshly constructed converters,
produced **byte-identical KIR**. Same machine, same versions — which is necessary and not
sufficient, and is exactly the position ADR-0017 took for ONNX inference. A shipped parser
would still declare `deterministic = False` and stay out of the G6 golden. The objection
survives as a *declaration* rather than as a defect.

**What it recovers.** Over the five PDF documents of the ingested corpus, against the
Markdown originals they were rendered from:

| | ML pipeline | true | text layer |
|---|---:|---:|---:|
| headings | **50** | 61 | 0 |
| code blocks | **39** | 90 | 0 |

82 % of headings and 43 % of code blocks, against a text layer that recovers none of either.
It also fills `src.page` **and `src.bbox`**, so a citation can name a region of a page, and
anchors stop being ordinals: `#/0` becomes `#platform-support/0`, `#package-indexes/0`,
`#managed-and-system-python-installations/0`.

**What it buys in retrieval.** The frozen judgements carried onto an ML-parsed variant and
scored beside the text-layer arm and the Markdown control, on the cases whose answer lives in
a PDF-rendered document:

| release set (4 cases) | nDCG@10 | MRR | R@10 | R@50 | judged passage |
|---|---|---|---|---|---|
| markdown (control) | 0.398 | 0.298 | 0.750 | 1.000 | 66 |
| text layer | 0.396 | 0.438 | 0.750 | 1.000 | 714 |
| **ML layout** | **0.327** | 0.388 | **0.500** | 1.000 | 112 |

Dev set (2 cases): all three arms at nDCG@10 0.500 and R@10 0.500.

The control is what makes this readable. ADR-0039 showed the text-layer arm's numbers are
inflated by a target ten times too big, so "worse than the text layer" would mean nothing.
Worse than **Markdown** is the claim, and the confound is gone with it: the ML arm's judged
passage is 112 tokens against the control's 66, not 714.

So restoring structure imperfectly retrieves **worse** than not restoring it at all, and
worse than the document it came from. The mechanism is visible in the output: the pipeline
recovers section boundaries but degrades their contents — list items arrive as `·`-joined
prose, and more than half the code blocks are gone. Section-sized chunks whose text is worse
is the losing combination, and it is the one this produces.

## Decision

**v1 does not read PDF structure.** The `pdf` parser stays as it is — PDFium's text layer,
page-scoped, with a warning on every document saying what it cannot see — and docling's ML
pipeline is not shipped, not as a default and not as an extra.

The refusal is **on the merits, not on the constraints**. All three of 4.9's acceptance
criteria are satisfiable: the closure is opt-in, the network can be made silent, and the
determinism objection reduces to a declaration this project already makes elsewhere. What
does not hold up is the case *for* it: ~2.4 GB and three seconds a page buy a measured
retrieval regression against the Markdown control, on the one thing the product exists to do.

That is the same standard [ADR-0031](0031-refuse-three-rerankings.md) applied when it refused
three ranking changes, one of which had already been implemented. A change that cannot show a
benefit does not ship because it is interesting.

**What would change the answer is named, not hand-waved.** The pipeline delivers one benefit
that is real and that no number above captures: an ingested PDF stops being cited by ordinal
and starts being cited by section, with a bounding box. The evaluation cannot score that —
every metric here ranks *chunks*, and none of them asks whether the anchor a reader is handed
names the right thing. Filed as **roadmap 6.7**: score citation precision, not only rank. With
that in place the trade becomes decidable on evidence, and this ADR is the thing to revisit.

## Alternatives Considered

- **Ship it as an optional, off-by-default parser** — the outcome 4.9 itself called
  defensible, and the one I expected to reach. Rejected once the retrieval numbers came in:
  an opt-in extra still has to be worth opting into, and this one asks 2.4 GB and 3 s/page for
  a regression. The secondary cost is real too — CI cannot install it, so it would ship
  unexercised and rot between releases, which the quality bar (AGENTS §10) does not allow for
  a supported surface.
- **Ship it with `allow_download`, mirroring `[embedding]`.** Rejected on a difference that
  matters: `mycelium.embedding.models` pins every file by URL, size and SHA-256 and verifies
  the bytes before installing them, because fetching a model is a supply-chain event.
  docling's downloader offers no such pin, and one of its dependencies fetches from a third
  host entirely. Offering a consent we cannot make safe to the standard we already set would
  be worse than offering none.
- **Ship the ML pipeline only for `src.bbox`, keeping the text layer's chunking.** A real
  option: take the layout model's coordinates and none of its structure. Rejected as
  unmotivated — nothing consumes `bbox` today, and building a second parse path to populate a
  field no reader uses is speculative work by definition.
- **Wait for a lighter engine.** Not an alternative, a hope. Recorded instead as the trigger:
  6.7 makes the benefit measurable, and this decision is re-taken then, on the same harness.
- **Improve the pipeline's output ourselves** — re-join the `·`-joined lists, recover the
  missing code blocks. Rejected on D-007: Mycelium OS owns the representation, not the
  parsing research. Post-processing another engine's mistakes is how you end up maintaining a
  parser you did not write.

## Consequences

- **PDF ingestion stays thin, and says so.** The `pdf` parser's per-document warning now names
  this ADR beside ADR-0032, so an operator meeting "no headings, no tables" is one link from
  the numbers and the harness rather than from a decision they have to take on trust.
- **No new dependency, no new extra, no new configuration.** `mycelium-os[ingest]` stays at
  ~24 packages with no `torch`, and the default profile stays offline.
- **`tools/measure_pdf_structure.py` ships and cannot run in CI**, by nature: it needs ~2.4 GB
  that no runner should carry. It states its requirements and refuses cleanly without them,
  and it is the artifact that makes this decision re-checkable when docling changes.
- **A finding that outlives the decision.** The docling adapter written at 4.1 for DOCX and
  HTML mapped the ML pipeline's output with **no changes at all** — the ML pipeline produces
  the same `DoclingDocument` type. Whatever a future engine is, the cost of adopting it is the
  engine, not the adapter. That is the KIR boundary (D-007) paying for itself in the one place
  it is hard to arrange deliberately.
- **A second finding, for 4.8.** ADR-0039 noticed that the text-layer arm's page-sized chunks
  scored *well* because the target was large. This item's control isolates that further: the
  ML arm's section-sized chunks score like Markdown's, and the text layer's page-sized ones
  score higher than both. Chunk size is doing more work in our ranking than chunk *quality* —
  which is ADR-0031's diagnosis, arriving from a third direction.

## References

- Measured this session, all reproducible with `tools/measure_pdf_structure.py --artifacts <dir>`:
  closure 121 distributions / ~1.0 GB; weights 1 372 MB; 2-3.5 s per page after a ~35 s model
  load; byte-identical KIR on repeat conversion; 50/61 headings and 39/90 code blocks; the
  retrieval table above.
- Spec 02 §5 (the evidence lane); NFR-1 (determinism), NFR-3 (incremental budget), NFR-6 (no
  unconfigured network call).
- [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) — the consent shape and
  the `deterministic` rule this reuses.
- [ADR-0031](0031-refuse-three-rerankings.md) — the standard for refusing a change that does
  not measure.
- [ADR-0039](0039-measure-what-projection-costs.md) — the corpus, the control, and the
  target-size confound that makes this table readable.
