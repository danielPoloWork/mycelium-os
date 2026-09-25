# 2026-09-25 — the middle had citations (roadmap 7.10)

- **Session scope:** roadmap 7.10 — bring the reader-facing documents to the standard a
  first-tier engineering organisation publishes, and draft the repository's *About* box.
- **PR:** #N (`docs/front-door-standard`). Follows #201, merged as `d18f5c0`.
- **Milestone 7:** 7.10 closed.
- **Decision it records:**
  [ADR-0159](../../../adr/0159-keep-the-front-door-to-what-a-first-reader-needs-and-move-the-rest-with-its-citations.md).

## The editing job that was not one

The README had eighteen good sections in the wrong place, and moving them looked like an hour
of prose. It was not, because this repository's documentation is its own judged corpus: 45
cases cite the README, 28 anchors sit in exactly the sections that had to go. Moving them
without the cases breaks the citations; moving the cases without saying so re-writes the
frozen release set in passing. The maintainer was asked before anything moved, with three
courses, and chose to move and re-point in one change.

## Make the move provably a move

The rule was mechanical once one fact was checked — a document's H1 is not part of an anchor,
so `README.md#what-makes-it-different/<section>/<n>` becomes `docs/how-it-works.md#<section>/<n>`
with the sections promoted from H3 to H2. What made it trustworthy was refusing to edit while
moving: the sections went verbatim, links re-rooted, one sentence adjusted. Then every judged
anchor was chunked before and after with the build's own chunker — 25 of 26 identical up to
link targets, the 26th being the table that stays. The generator, which builds the corpus and
refuses a dangling anchor, then wrote sets identical to the textual substitution.

One small trap on the way: a heading demoter that treats every line opening with backticks as
a fence meets a line that opens with an inline code span. CommonMark says a backtick fence's
info string has no backtick in it, and that rule fixed it.

## Two things the front door said that were not true

The README said the docs site is published on every push to `main`; the address answers 404,
because enabling Pages is still an owner step. `CONTRIBUTING.md`'s setup ran ruff and mypy on
`src` alone, while the gate runs them on `src tests tools contrib`. Both are corrected, and
contributing now leads with `tools/verify.py`, which is what CI runs.

## A guard that read the wrong half of its own bar

The ladder stopped at *result rules*: a heading-depth boost "now earns a default" on this
repository's corpus, +0.23 %. The move had promoted eighteen sections to H2, so the depths
had changed, and a runner built to notice exactly that had noticed. What it had not done was
apply its own bar — the same run printed that arm at −19 % and −21 % on the two vendored
release sets, and the bar says *no overall regression on any set*. The check tested each
release set alone. That is BUG-0037, fixed here because the gate could not pass without it,
and it is the unsafe direction for a guard: the same code would have waved through a
one-corpus gain as a mandate.

## What the next session should know

- **The owner's two About commands** are in `docs/workflow/github-setup.md` §7, and
  `tools/check_repo_settings.py` reports the box absent until they run. The *Website* field
  waits for Pages.
- **`docs/how-it-works.md`'s headings are citations.** Rename one and the cases pointing at it
  stop resolving; `tools/build_eval_cases.py` refuses to write such a set.
- **Re-recording G2 was part of this change**, because the verdict digests the judged cases;
  it was recorded in a worktree at the commit, per the route 6.33 used.
