# 2026-09-02 — the objection dissolved, and the answer was still no (roadmap 4.9)

- **Session scope:** roadmap 4.9 — read PDF structure, or record why v1 does not
  (NFR-1/NFR-3/NFR-6; D-007/D-013/D-017).
- **PR:** #59 (`feat/pdf-structure-or-why-not`). Follows #58 (4.10), merged as `57af66e`.
- **Milestone 4:** 4.1–4.7, 4.9 and 4.10 done; 4.8 open. 6.7 filed here.

## I expected to confirm ADR-0032 and confirmed almost none of it

4.1 refused docling's ML PDF pipeline on three grounds, and 4.9 existed to test them properly
— the item was explicit that they were "acceptance criteria, not obstacles". Measuring them
one at a time:

**The network objection is satisfiable, and the real problem is a different one.** Pointing
`artifacts_path` at pre-fetched weights makes the pipeline completely silent, verified under
`HF_HUB_OFFLINE=1`. What I found instead is that the *out-of-the-box* path — no
`artifacts_path` — fetches OCR weights from `modelscope.cn` at conversion time, and
`HF_HUB_OFFLINE=1` does not stop it, because that downloader belongs to a transitive
dependency and does not read HuggingFace's switch. I nearly wrote that up as "cannot be made
offline", which would have been wrong, and then nearly as "downloads at construction time",
which was also wrong. It took four runs with the model cache cleared between them to get the
sentence right: it downloads *at conversion*, *with OCR on*, *when nothing was pre-fetched*.
A claim that decides an item deserves to be re-run until it is exact.

**The determinism objection is weaker than 4.1 assumed.** The same PDF, converted twice by
two freshly constructed converters, produced byte-identical KIR. That is only this machine and
these versions — necessary, not sufficient — so a shipped parser would still declare
`deterministic = False` under ADR-0017's rule. But "not reproducible" was not true, and I had
been carrying it as though it were.

**The closure objection is real and unchanged:** ~1.0 GB of packages, 121 distributions, plus
1 372 MB of weights. ~2.4 GB to read a PDF's headings, at 3 s a page.

So the three reasons for saying no had turned into one cost and two declarations, and the
decision had to be taken on whether the thing is worth having.

## Which 4.10 had just made answerable

The ingested corpus is a twin of a Markdown one, so every PDF's *true* structure is known
rather than guessed, and the frozen judgements can be carried onto a third variant. The
pipeline recovers **50 of 61 headings** (82 %) and **39 of 90 code blocks** (43 %), against a
text layer that recovers none of either, and it fills `src.bbox` so a citation can name a
region of a page.

Then the retrieval numbers, on the four release cases whose answer lives in a PDF:

```text
  arm           nDCG@10      MRR     R@10     R@50   target
  markdown        0.398    0.298    0.750    1.000       66
  text layer      0.396    0.438    0.750    1.000      714
  ML layout       0.327    0.388    0.500    1.000      112
```

The Markdown row is what makes this readable, and adding it was the most useful thing I did
today. Without it the result reads "ML layout is worse than the text layer", which would be a
meaningless comparison — ADR-0039 had already shown the text layer's numbers are inflated by
a target ten times too big. Against the *control*, with the confound gone (112 tokens, not
714), the ML arm is simply worse than the document it came from.

The mechanism is in the output: the pipeline gets the section boundaries back and degrades
what is inside them — lists arrive as `·`-joined prose, more than half the code blocks are
gone. Section-sized chunks with worse text is the losing combination, and it is the one this
produces. **Restoring structure imperfectly retrieves worse than not restoring it at all.**

## The decision, and the thing that would change it

No. Not as a default and not as an extra: ~2.4 GB and three seconds a page for a measured
regression on the one thing the product is for. That is ADR-0031's standard, applied to a
feature I had been assuming we would eventually want.

What I am careful not to claim is that it has no value. It has exactly one, and it is real:
an ingested PDF stops being cited by ordinal and starts being cited by section. Nothing in
the harness can score that — every metric ranks chunks, and none asks whether the anchor a
reader is handed names the right thing. So the refusal rests partly on a benefit being
*unscoreable* rather than absent, which is not a comfortable place to leave it. Filed as 6.7,
which also happens to be something 1.0 needs anyway: NFR-5 gates citation *coverage* and says
nothing about citation *precision*.

## One thing worth keeping from a session that shipped no feature

The docling adapter written at 4.1 for DOCX and HTML mapped the ML pipeline's output with **no
changes at all** — same `DoclingDocument` type, same walk, headings and bboxes and all. The
whole cost of this feature is the engine; the adapter was free. That is the KIR boundary
(D-007) paying for itself in the one situation you cannot arrange on purpose: a completely
different parsing strategy arriving and finding the seam already the right shape.
