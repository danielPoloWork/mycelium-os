# ADR-0101: Let the `exact` slice name the section that documents the literal, because four of its five cases already do

- **Status:** Accepted
- **Date:** 2026-09-13
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.1
- **Related:** [ADR-0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md) (the
  rule this extends, written for `symbol`), [ADR-0065](0065-one-section-cannot-document-two-commands.md)
  (which narrowed it), [ADR-0029](0029-let-a-judgment-name-a-section.md) (chunk-or-section
  notation), [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md)
  (the frozen held-out set this moves), [ADR-0097](0097-a-twin-case-that-outscores-its-source-is-the-defect-not-the-fall.md)
  (which measured this case and deferred the judgement question to here),
  [ADR-0039](0039-measure-what-projection-costs.md) (the carry),
  [ADR-0091](0091-widen-the-heading-rule-and-refuse-to-guess-which-section-documents-a-name.md)
  (a refusal in the other direction, and why this one is different); D-010; roadmap 5.26, 5.30

## Context

`u-1003` asks `tool.uv.index` — a literal configuration key, slice `exact` — and its single
grade-3 anchor is `docs/concepts/indexes.md#/0`: the document's 64-token preamble, which names
the key once, in a subordinate clause, while saying what the document is about.

The same document gives the key a section of its own. `## Defining an index` (392 tokens) says
what an entry *is*, which fields it takes (`name`, `url`, `default`), how indexes are
prioritised, what an index name may contain, and what the command-line and environment
equivalents are. Six further sections use the key to document something else: pinning,
search strategy, seven authentication options, flat indexes, and the pip-style legacy flags.
The document names the key twenty-six times.

Roadmap 5.26 found this while reading `u-1003` for a different reason and deliberately left
it (ADR-0097). Roadmap 5.30 asks the question it deferred: **does ADR-0062's rule — *a
judgment names the section that documents the named thing, and a page that merely names it is
a lesser grade or none* — reach `exact`, where the query is a literal string and the preamble
does contain it?**

**It already does, and this ADR is mostly a report of that.** Four of the slice's five other
cases were judged on exactly that rule, and their notes say so in their own words:

| case | query | judged on | its note |
|---|---|---|---|
| `u-1018` | `--no-sources` | the section that explains it | *"It appears in four documents and is **explained** in one, which is the discrimination an exact query has to make."* |
| `u-1021` | `PEP 508` | the section that defines it | *"cited in four documents. Only one says what it **is**, and the others link it in passing — so a hit anywhere is not an answer."* |
| `u-0013` | `UV_PREVIEW` | the section that documents it | *"The section that documents it names it four times."* |
| `u-0014` | `--bare` | the section that documents it, **at 3** — and the document's own root mention **at 1** | *"the document's own root mentions it once, which is grade 1 … it answers only that the flag exists."* |
| `u-1003` | `tool.uv.index` | the document's root preamble, at 3 | *"A literal configuration key."* |

`u-1003`'s note is the only one in the slice that names no discriminator at all, and its
judgement is the only one that contradicts the other four. `u-0014` is the same shape in the
same slice with the opposite grades.

**And a second case in this very document already disagrees with it.** `u-1001` (*"how do I
add a package index other than PyPI"*, slice `fact`) grades
`docs/concepts/indexes.md#defining-an-index/` at **3** and the preamble at **2**. Two cases,
one document, the same two passages, opposite gradings.

The measurements say the same thing from the other side. On the Markdown corpus the judged
preamble sits at rank **6** of 568 chunks for the mycelium retriever and outside the top ten
for grep, while `#defining-an-index/0` sits at **5** and **4**. And on the ingested twin the
case scores **1.0000 for grep and 0.5000 for us** — because the PDF projection has no headings,
so its first chunk holds the preamble *and* the whole of `## Defining an index`. The twin is
easier precisely where its chunk accidentally contains the section this judgement should have
named, which is the +0.27 anomaly ADR-0097 could measure but not explain.

## Decision

**`u-1003` is re-judged from the documents**, and the rule ADR-0062 wrote for `symbol` is
stated for `exact` as well: **an `exact` judgment names the section that documents the
literal.** Containing the string is the floor for being judgeable at all, not the criterion —
in this corpus twenty-six passages contain it. A passage that frames the literal, or names it
in passing, is a lesser grade or none:

| anchor | grade | why |
|---|---|---|
| `docs/concepts/indexes.md#defining-an-index/` | 3 | the entry's documentation: what it is, its fields, the priority rule, what a name may contain, the command-line and environment forms |
| `docs/concepts/indexes.md#/0` | 2 | frames it in one clause — that uv can be configured to use other indexes *via* this option — which is more than "it exists" and less than its documentation. `u-1001`'s grade for the same passage, now agreed |

**Section-scoped, to match `u-1001` and for ADR-0029's stated reason.** The section is one
392-token chunk today, so the notation costs nothing; it is written as a section because the
answer is spread across the whole of it — two configuration examples and four rules — and
because the neighbouring case already names it that way. Two cases naming one passage two ways
would be a difference that means nothing.

**No code changes.** Not one line under `src/`, so the conjunction
`tools/check_frozen_release_sets.py` refuses is not merely satisfied but irrelevant — the
shape roadmap 4.12 established and ADR-0062 followed. The derived twin is re-carried by its own
generator and byte-checked in CI, and all four baselines are re-blessed in this change, because
a bless rides with the judgement change that occasions it and never with a retrieval change
(ADR-0056 narrowing ADR-0053).

## Alternatives Considered

- **Leave it: in `exact` the query is a literal, and the preamble contains it.** The
  counter-argument the roadmap item asked to weigh, and the only one with real force.
  Rejected on the slice's own precedent: `u-1018` and `u-1021` were written specifically to
  refuse "a hit anywhere is an answer", and if containing the literal were the criterion then
  twenty-six passages of this document are relevant and the case measures nothing. A slice
  that cannot discriminate is not a slice.
- **Re-anchor to `#defining-an-index/` alone, dropping the preamble.** Rejected: the preamble
  *is* relevant and the original judge was right that it is — what it was wrong about is the
  grade. Dropping a true relevance to sharpen a score is re-fitting in the direction nobody
  inspects, and it would also contradict `u-1001` from the other side.
- **Grade `#index-url-and-extra-index-url/0` as well.** It explains what the key is in terms
  of the legacy flags, ends on *"`--index-url` and `--extra-index-url` can be thought of as
  unnamed `[[tool.uv.index]]` entries"*, and it outranks the judged preamble on both
  retrievers. Rejected: its subject is the legacy options, and the key is the reference point
  it explains them against. Crediting it is ADR-0062's "right neighbourhood" generosity with
  the direction reversed.
- **Grade `#pinning-a-package-to-an-index/0`.** Rejected for a sharper reason: it is
  `u-1004`'s own grade-3 anchor, for the question it does document. A section that documents
  pinning is not a second home for the key, and grading it here would blur two cases into one.
- **Grade the seven authentication subsections, `#flat-indexes/0` and
  `#searching-across-multiple-indexes/0`.** Each documents one *field* of the entry. Rejected
  as aspects, verbatim the refusal ADR-0062 made for `uv tool install`'s neighbourhood.
- **Fix the twin's `u-1003` instead.** The anomaly is on the twin, so the twin looks like the
  place to act. Rejected: ADR-0097 already established that the carry is faithful at coverage
  1.0000 and that the carried anchor is the passage. The twin was never the defect; it was the
  symptom that made the source judgement legible.

## Consequences

- **Exactly one case moves, and the incumbent gains five times what we do.** Every other case
  on all four (corpus × retriever) combinations is identical to within 1e-6:

  | set | retriever | `u-1003` | `exact` | overall |
  |---|---|---:|---:|---:|
  | uv/release | mycelium | 0.3562 → **0.4247** | 0.7379 → 0.7516 | 0.6109 → **0.6138** |
  | uv/release | grep | 0.0000 → **0.3390** | 0.5528 → 0.6206 | 0.5173 → **0.5321** |
  | uv-ingested/release | mycelium | 0.5000 → 0.5000 | 0.7602 → 0.7602 | 0.6187 → 0.6187 |
  | uv-ingested/release | grep | 1.0000 → 1.0000 | 0.7492 → 0.7492 | 0.5754 → 0.5754 |

- **Our reported lead on the held-out set narrows, +0.0936 → +0.0817.** The roadmap item said
  to distrust the direction that would flatter us; this is the other one. Under the old
  judgement the incumbent could not score the case *at all* — 0.0000, because its
  distinct-terms-then-occurrences ranking will not put a 64-token passage with one mention in
  the top ten — so the judgement we are replacing was one only we could win.
- **The twin is byte-identical, and that is the prediction holding.** Both anchors carry onto
  the same page-sized chunk (`indexes-pdf-d37689d3.md#/0`, coverage 1.0000 for both), so the
  twin's score cannot move. What does move is the comparison: `u-1003`'s twin-minus-source gap
  falls from **+0.144 to +0.075** and from second-widest to fifth in
  `tools/measure_projection_cost.py`'s report. It does not close, and it should not — a
  headingless PDF page holds the framing and the documentation in one chunk, so a query that
  has to tell them apart on the source cannot fail on the twin. That residue is what
  projection costs, measured, which is the tool's purpose.
- **Gate G2's verdict is re-recorded in this change**, because a judged set is a ranking input
  and ADR-0068 makes the re-record part of the change that stales it rather than a follow-up.
  The default stays `lexical`. The check that this was a judgement move and not a retrieval one
  is in the diff: `uv/dev` and `uv-ingested/dev` reproduce **byte-identically**,
  `uv-ingested/release` moves only its `cases_digest`, `uv/release` moves its lexical arm by the
  +0.0030 measured above, and `ours/*` drifts only by the documents this change adds to a
  self-hosting corpus (reported, never gated — ADR-0053).
- **Gate G3 disarmed itself on both corpora and said so**, in the words roadmap 4.24 gave it:
  *"the judgements changed since the baseline was taken, so these numbers are means over
  different case populations — reported, not enforced."* Both baselines were then re-blessed
  deliberately, both arms each, and the arming is visible in the diff.
- **A trap was found by triggering it, and is now closed.** Regenerating the judged sets
  revealed that `tools/build_uv_docs_cases.py` had drifted ten dev cases and one re-judgement
  behind the committed `dev.jsonl` — PRs #88 and #90 edited the set directly — so running it
  deletes them. Recorded as [BUG-0026](../bugs/2026/09/BUG-0026-the-uv-judged-sets-do-not-reproduce-from-their-generator.md),
  fixed by transcribing the cases back from the committed file mechanically and by giving the
  generator the `--check` its two siblings already had. No judgement changed in that repair:
  `dev.jsonl` is byte-identical.
- **The `exact` slice's convention is now written down**, as ADR-0062 wrote `symbol`'s, so the
  next literal-query case has a rule to follow rather than four examples to infer one from.
- **What this does not decide.** ADR-0091 refused to let a *symbol's* `defined_in` claim which
  section documents a name, because a stage seeing one document at a time cannot read an
  editorial fact about a corpus. Nothing here contradicts that: a judgement is written by a
  reader who has read the whole document, and the claim it makes is about this document's own
  structure — one section defines the key, the rest use it. The refusal stands for the
  compiler; the rule applies to the judge.

## References

- Spec 04 §7.1 (slices, frozen sets), §7.2 (metrics), §7.4 (the incumbent).
- `eval/corpora/uv-docs/docs/concepts/indexes.md` — the document the judgement was written
  from; `eval/corpora/uv-docs-ingested/knowledge/evidence/indexes-pdf-d37689d3.md` — the twin
  whose first chunk holds both passages.
- Re-runnable: `mycelium search "tool.uv.index" --path eval/corpora/uv-docs --explain`, then
  `mycelium eval eval/corpora/uv-docs --set eval/release.jsonl --against grep`, and
  `python tools/measure_projection_cost.py` for the twin comparison.
- [ADR-0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md) — the rule; this
  ADR extends its reach and adds the evidence that `exact` was already following it.
