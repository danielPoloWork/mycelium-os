# 2026-09-14 — the first scheduled re-bless (release.md step 0)

- **Session scope:** step 0 of the release procedure, run for the first time as a scheduled
  step rather than because somebody noticed the baseline was stale.
- **PR:** #143 (`chore/rebless-before-v0-5-0`). Follows #142, merged as `e598dab`.
- **Milestone 5:** closed at 5.43. This is the pre-flight for the v0.5.0 cut.
- **Decision it applies:** [ADR-0112](../../../adr/0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md).

## Why there is a PR here at all

`ours/release` was re-blessed two days ago at 5.42, and two merges have landed since: #142's
milestone-exit review and its ADR, and #141's own ADR and roadmap entry. On a self-hosting
corpus that is enough to move the numbers G3 reports against, and the release is cut from the
corpus as it stands at the tag. So the baseline is taken now, against the tree the release will
describe, and not inside the release PR — which adds its own changelog row and would leave the
baseline describing a corpus one commit older than the tag.

That is ADR-0112's cadence doing what it was written for. The previous interval ran four
releases and produced a 0.038 gap on the incumbent that read as our regression; this one is two
PRs.

## What moved

Both arms, two runs, because `write_baseline` writes only the arm it is given.

The numbers are in the PR body rather than repeated here, and the shape is the one the cadence
predicts: our own arm barely moves, and what the interval records is mostly documents arriving.
Nothing in `src/` changed in this PR, so no gate's numbers moved for any reason other than the
corpus.

## The rule this PR had to observe, and the one it had to avoid

**Observe:** the maintainer's uncommitted work — an untracked `docs/analysis/` and an edit to
`docs/README.md` — is set aside before the build and restored after. A baseline blessed with it
in would describe a corpus that will not exist on `main`, which is the one thing a baseline must
not do.

**Avoid:** nothing under `TUNING_PATHS` may change in a PR that blesses (ADR-0056). This PR
touches the roadmap, the README, an ADR note, a journal entry and the two baseline arms, and
not one line of `src/` — so nothing but the corpus could have moved a number.

## The correction that arrived mid-session

While the first bless was running the maintainer edited `ROADMAP.md` in the working tree:
M6 from v1.0.0 to **v0.6.0**, M7 from v2.x to **v1.0.0**. They are right, and the mistake was
mine one PR earlier. ADR-0113 relabelled M1 to M5 by the rule in AGENTS.md §11 — `MINOR`
increments with each completed milestone pre-1.0 — and then exempted M6 on the grounds that
"the phase name and the release agree". That is the spec's *Phase 4* name reasserting itself in
the one place I had not checked it against the cadence, inside the ADR written to stop exactly
that.

Three things followed. Their edit had overwritten this PR's checkpoint pointer, because their
editor buffer predated my write by eight minutes, so that line was restored on top of their
version rather than around it. The README still carried the old labels, so the tree disagreed
with itself; it is corrected here. And ADR-0113 gets a narrowing note rather than a silent
rewrite, which is what this repository does with a merged decision that turns out to be half
wrong.

Because the roadmap and the README are both indexed, all of that had to land *before* the
baseline was taken, not after. The bless was redone on the finished tree.

## Lesson

A cadence is only worth writing down if the first scheduled run is boring, and the *bless* half
of this one was: two commands and a diff that matches what the interval contained. What was not
boring is that the tree moved underneath it. A baseline is a claim about a corpus at a moment,
so anything that edits an indexed document — including the maintainer, in their editor, while
the build runs — has to land before the bless and not after. Check the working tree again
immediately before blessing, not only at the start.
