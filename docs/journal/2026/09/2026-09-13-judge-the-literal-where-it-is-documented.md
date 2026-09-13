# 2026-09-13 — judge the literal where it is documented (roadmap 5.30)

- **Session scope:** roadmap 5.30 — whether `u-1003`, which asks the literal `tool.uv.index`,
  is judged on the passage that *documents* the key or on the one that merely names it
  (spec 04 §7.1; ADR-0027/0029/0062/0097).
- **PR:** #129 (`fix/judge-u1003-from-the-documents`). Follows #128, merged as `f690e18`.
- **Milestone 5:** 5.30 done; 5.37 and 5.38 filed.
- **ADR:** [ADR-0101](../../../adr/0101-let-the-exact-slice-name-the-section-that-documents-the-literal.md).
  **Bug:** [BUG-0026](../../../bugs/2026/09/BUG-0026-the-uv-judged-sets-do-not-reproduce-from-their-generator.md).

## The question was whether a rule reaches, and the answer was that it had already arrived

The item asked whether ADR-0062's rule for the `symbol` slice — *a judgement names the section
that documents the named thing* — reaches `exact`, where the query is a literal string and the
mentioning passage genuinely contains it. It framed that as an extension to argue for.

It is not. Reading the other five `exact` cases before touching anything, four of them were
already judged on exactly that rule and say so in their own notes: `u-1018` (*"appears in four
documents and is **explained** in one, which is the discrimination an exact query has to
make"*), `u-1021` (*"only one says what it **is**"*), `u-0013` (*"the section that documents
it"*), and `u-0014`, which grades its document's root mention **1** for the reason `u-1019`
gives. `u-1003`'s whole note reads *"A literal configuration key."* — the only note in the
slice that names no discriminator, attached to the only judgement that contradicts the rest.

The evidence the item did not have came from reading the document rather than the slice.
`u-1001` — a different query, the same document — already grades `#defining-an-index/` at 3 and
the preamble at 2. Two cases, two passages, opposite gradings, sitting in the same file for
three milestones. Once that is on the page there is no interesting question left: the
judgement changed to `#defining-an-index/` at 3 and the preamble at 2, section-scoped to match
its neighbour, and the six sections that use the key to document *something else* — pinning,
search strategy, seven authentication options, flat indexes, the legacy flags — stay ungraded,
which is ADR-0062's refusal of "right neighbourhood" applied where it was written to apply.

## The honesty check, which is the part worth keeping

The item said to distrust the direction that would flatter us, and named the current
judgement as the one we score worst on. Both halves turned out to be true and they point
opposite ways.

Under the old judgement grep scored **0.0000** on this case — not badly, *zero* — because its
distinct-terms-then-occurrences ranking will never put a 64-token passage with one mention of
the key in a top ten drawn from 568 chunks. The judgement being replaced was one only we
could win. Under the new one:

| set / retriever | `u-1003` | `exact` | overall |
|---|---:|---:|---:|
| uv/release, mycelium | 0.3562 → 0.4247 | 0.7379 → 0.7516 | 0.6109 → 0.6138 |
| uv/release, grep | 0.0000 → 0.3390 | 0.5528 → 0.6206 | 0.5173 → 0.5321 |

The incumbent gains five times what we do and our reported lead on the held-out set narrows,
+0.0936 → +0.0817. A judgement written to flatter the product does not do that.

## The twin did not move, and that was the prediction

Both new anchors carry onto the same chunk — `indexes-pdf-d37689d3.md#/0`, coverage 1.0000 for
each — because the PDF projection has no headings and its first chunk holds the preamble *and*
the whole of `## Defining an index`. So the twin's score is byte-identical, and the +0.27
anomaly ADR-0097 measured but could not explain now has its explanation: the twin was easier
precisely where its chunk accidentally contained the section this judgement should have named.
`tools/measure_projection_cost.py` now reports the gap at **+0.075** rather than +0.144, fifth
widest rather than second. It does not close, and it should not — a page-sized chunk cannot be
asked to tell framing from documentation, and that residue is what projection costs.

## Found by running it: ten judged cases, one command from deletion

Regenerating the sets printed `wrote 12 dev and 25 release cases` and `git diff --stat` showed
`dev.jsonl | 12 +-----------`. The generator held twelve dev cases; the committed set holds
twenty-two. PRs #88 and #90 had edited `dev.jsonl` directly — re-judging `u-0006` under
ADR-0065, and adding `u-0013`…`u-0022` so that a field-weight question could have an interior
optimum — and neither edit reached `tools/build_uv_docs_cases.py`, which rewrites the file
from its own tuples. Running it deletes them, silently.

The shape of it is almost a controlled experiment. `build_eval_cases.py` is checked by a test;
`build_ingested_cases.py` has had `--check` in CI since [BUG-0018]; `build_uv_docs_cases.py`
was checked by nothing. The unchecked one is the one that drifted. And the carry kept
reproducing perfectly the whole time, because a carry copies whatever it is given — checking
the derivation while the source goes unchecked is the weaker half of a pair.

Repaired by transcribing the ten cases back **from `dev.jsonl` itself**, by script rather than
by hand, and proving it by regenerating and byte-comparing: `dev.jsonl` is untouched in the
commit. Then the missing `--check`, wired into `tools/verify.py` at `code` and into CI beside
the carry check. Its message says what to do rather than what happened, because the trap here
is that regenerating *looks* like the fix.

One small thing worth admitting: demonstrating the failure by stashing the fix and re-running
the old generator clobbered the working tree, because the old file ignores `--check` and
writes. Recovered with `git checkout -- eval/` and `git stash pop`. The demonstration that
belonged in the record was the case count, which does not need the tool to be run at all.

## Two things filed rather than absorbed

Both were found on the way and neither could ride here. `u-1001` and now `u-1003` each hold
one twin anchor twice with two grades, and the harness builds its ground truth as a dict — so
the last entry wins and a grade-3 anchor is scored as grade 2. It moves no number today only
because nDCG is scale-invariant when a case has one distinct anchor; a case with three anchors
of which two collapse would score wrong in silence (5.37). And `encode_cases` now exists in
two tools, each with a docstring explaining that it must not disagree with `write_cases` —
an argument for one function, made twice. It belongs in `mycelium.eval.cases`, which is a
tuning path, which a change re-judging a frozen release set may not touch (5.38). The guard
refusing that is the guard working.

## Lesson

Before extending a rule to a new slice, read what that slice already does. The convention was
not missing, it was unwritten and unevenly applied, and the case that looked like the question
was the single exception to an answer four of its siblings had already given.
