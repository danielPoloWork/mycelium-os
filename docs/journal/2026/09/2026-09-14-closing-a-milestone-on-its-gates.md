# 2026-09-14 — closing a milestone on its gates (roadmap 5.43)

- **Session scope:** the Milestone 5 exit review the maintainer asked for before cutting the
  release, and the corrections it turned up.
- **PR:** #142 (`docs/close-m5-and-correct-the-labels`). Follows #141, merged as `631b9d7`.
- **Milestone 5:** 5.43 done, and M5 closes. 6.11 and 6.12 filed to carry the unmet gate.
- **ADR:** [ADR-0113](../../../adr/0113-close-a-milestone-on-its-gates-and-carry-an-unmet-one-by-name.md).

## The list was empty and that was not the question

M5 closed its last item, which is where M4's review said a milestone must *not* be judged from.
The question is which exit gates hold, and the two objects had quietly come apart: three of the
four gates in `.draft-specs/06` §Phase 3 are met, and the roadmap's own copy of that list was
wrong in both directions. It carried *≥ 200 judged cases*, which the spec puts under Scope, and
omitted *stale-anchor handling*, which is a gate. The unlisted one is met; the mis-listed one is
not.

That is worth more than the tidy-up it looks like. A gate that can be lost by paraphrase is not
a gate, and this one had been lost for a milestone without anyone noticing.

## What the review found under the gate that failed

The dogfooding gate stands at zero: public repository, one star, no forks, every merged pull
request by the owner or Dependabot. Forty-three M5 items could not have moved it, because it is
adoption and not engineering.

But the reason is a step earlier than adoption, and nothing in the roadmap had named it. **The
package is not published anywhere.** `release.yml` builds the wheel and the sdist, refuses a
build whose version disagrees with the tag, attaches both to a draft GitHub Release, and stops.
No registry appears anywhere in `.github/`. Meanwhile `docs/workflow/packaging.md` described the
flow in the present tense — *"A human approves the publish step; CI pushes to the registry"* —
and the README tells a reader to `pip install mycelium-os[embeddings]`.

Nothing can dogfood what nothing can install. That is 6.11, and 6.12 owns the gate itself, with
the order it actually needs written into it: publish, then the docs site, then the contribution
ladder, then outreach, which is the maintainer's.

## The labels would have mis-cut the release

The roadmap called M5 *v0.3*, which is what the spec's phase numbering calls Phase 3. M1 and M2
shipped v0.1.0 and v0.2.0, which that numbering does not count, so every label since has been two
behind: M3 released v0.3.0 under the label *v0.1*, M4 released v0.4.0 under *v0.2*. M5 cuts
**v0.5.0**.

The maintainer caught this before I did — the review's own recommendation said "cut v0.5.0" only
because the mismatch was visible in the changelog directory, and the roadmap heading still said
otherwise. Fixed in both places, with M6 keeping v1.0.0 because there the phase name and the
release agree.

## Why this is its own PR and not part of the release

The release PR rewrites the README status table and the changelog index, which is exactly where
the wrong labels live. Fixing them there would mean cutting a release whose own notes carry the
mistake, with the correction invisible among a dozen other edits. And ADR-0112, written two days
ago, puts the `ours/release` re-bless *before* the version bump — so the order is corrections,
then bless, then release, each step moving the corpus and the baseline describing the corpus the
release is cut from.

## Trajectory, for the record

43 items closed against 7 planned at the plan phase: 84 % self-filed, the same ratio M4 ran at,
across 44 pull requests in five days. The one real difference from M4 is that the open count
reached zero rather than oscillating between two and eight.

And what M5 built for retrieval mostly ships off: hybrid and graph expansion disabled because
the ablation refused them, symbol lookup on because at 5.25 it finally earned it after three
refusals. That is the gates working, not three failures.

## Lesson

A milestone has two lists: the items, which the team writes, and the gates, which the spec
writes. Only the second is a contract, and it is the one nobody re-reads — so it drifts by
restatement, and the drift is invisible precisely because the restatement is the thing everyone
looks at. Read the gates from the spec at every exit review, not from the roadmap's copy of them.
