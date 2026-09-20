# ADR-0138: Re-cut the adoption gates onto acts we can observe, and count nobody twice

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** the maintainer (D-030) with the tech-lead (EADOS delivery agent), per
  RFC-0001 / spec 06 §§3, 4
- **Related:**
  [ADR-0116](0116-publish-under-a-name-already-decided-and-let-the-artifact-be-a-defined-thing.md)
  (the publish pipeline this gate waits on),
  [ADR-0117](0117-sign-and-inventory-the-artifact-and-reserve-the-rung-a-newcomer-stands-on.md)
  (the contribution ladder, and the `good first issue` reservation the one real contributor
  arrived through),
  [ADR-0118](0118-make-a-deferral-name-the-condition-that-ends-it.md) (the three-valued
  *unreadable* this report inherits, and why a scheduled token is refused),
  [ADR-0127](0127-publish-docs-site-from-a-workflow-artifact-tracking-main.md) (the docs
  site, published nowhere until one owner action),
  [ADR-0114](0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md)
  (the 1.0 promise Phase 4 exits on);
  D-016 (no telemetry), D-024 (the distribution name), D-029 (repository topology, which
  decides what a *community plugin* can be before the freeze); spec 06 §3 Phase 3 / Phase 4;
  roadmap 5.43, 6.11, 6.12, 6.14

## Context

Spec 06 gives Phase 3 the exit gate **"≥ 10 external repos dogfooding"** and Phase 4
**"≥ 3 recurring external contributors and ≥ 5 community plugins"**. Roadmap 5.43 found the
first unmet at **zero** and carried it into M6 rather than waiving it, on the stopping rule
that item exists for: *a milestone closes on its exit gates, not on an empty list*. Roadmap
6.12 is where the gate was finally read rather than counted, and three things were wrong
with it. Only one of them is the number.

### 1. It is not observable, so it can only be asserted

There is no telemetry and there will not be (D-016). A repository that installs this
package, compiles its documentation and never says so is invisible from here. "Dogfooding"
names something real and names nothing we can ever count, so the gate admits exactly two
outcomes: assert it, or carry it forever. 5.43 chose to carry it, correctly, and that is a
holding position rather than an answer.

### 2. The one number that looks like adoption is manufactured by this repository

GitHub reports, for the fortnight to 2026-09-19:

| signal | value |
|---|---:|
| clones | **3 988** |
| unique cloners | **340** |
| page views | 225 |
| unique visitors | **1** (the owner) |

Three hundred and forty unique cloners against one unique visitor is not adoption; it is
CI. Every workflow run checks the repository out **fourteen times**, once per matrix job,
and this repository ran 12–28 runs a day across that window. The proof is in the two days
inside it when no workflow ran at all — **2026-09-06 and 2026-09-16**, on which clones were
**8** and **14**.

Quoting the 340 would have closed the gate by counting ourselves, which the roadmap item
forbids in those words.

### 3. Phase 4's plugin count asks for something our own topology forbids

D-029 decided that pre-1.0 external contribution happens **in-repo, through the contrib
tier**, and that plugins spin out to their own repositories only **after the freeze** —
because before it the plugin API may break at any minor, and an out-of-tree plugin would
chase a moving target. Phase 4 *is* the 1.0 exit. So "≥ 5 community plugins" as a condition
for reaching 1.0 asks five strangers to do, before the freeze, the thing D-029 says nobody
should do before the freeze. The gate and the decision cannot both be satisfied.

### What is actually out there

Asking, rather than assuming, found **one engaged actor, and a finished contribution that
cannot be merged**:

- **`blamevlan`** took issue #149 — a `good first issue`, held open for a human by the rule
  ADR-0117 wrote — implemented it on `fix/repo-settings-checks` in their fork, and reported
  on 2026-09-15 that *"GitHub won't let me open the PR because pull request creation is
  limited to collaborators"*. The maintainer reviewed the commit in the issue thread and
  asked them to wait until M6 closes and the hardening baseline is in. So the first real
  external contribution this repository has ever received is **complete, reviewed, and
  unmerged by decision**.
- **`Voyagerroc-Lab`** forked on 2026-09-14 and has no commit of their own.

Roadmap 6.12 was written against *"1 star, 0 forks, and every merged pull request authored
by the owner or Dependabot"*. The star and the merge list still hold; the forks do not, and
the sentence had no slot at all for the thing that matters most — somebody turned up, did
the work, and could not hand it over. Nothing was watching for any of it.

## Decision

**Re-cut both gates onto acts that cost the actor something and that GitHub reports to us,
and build the instrument that counts them** (D-030, owner decision, 2026-09-20).

An **engaged actor** is a GitHub login that is neither the owner nor a bot and that has:

- opened an issue, or
- opened a pull request, or
- commented on an issue, a pull request or a discussion, or opened a discussion, or
- pushed **a commit of their own** to a fork.

| gate | was | is |
|---|---|---|
| Phase 3 exit | ≥ 10 external repos dogfooding | **≥ 3 engaged actors**, and the package resolves on an index |
| Phase 4 exit | ≥ 3 recurring external contributors | **≥ 3 external authors of ≥ 2 merged pull requests each** |
| Phase 4 exit | ≥ 5 community plugins | **≥ 1 `contrib/` plugin or module authored outside the maintainer** |

Ten becomes three because three is the smallest number that cannot be one enthusiast having
an interesting week, and because a bar nobody can reach stops being a gate and becomes a
sentence. Ten survives as the 1.0-and-after ambition in the product strategy, not as an exit
condition on a pre-1.0 phase. *Recurring* is spelled **two merged pull requests**: one merge
cannot show that somebody came back. Five community plugins becomes one in the tier D-029
permits, and the five move behind the freeze with the topology that allows them.

**Three exclusions are part of the decision**, because a gate is as much what it refuses:

- **clone traffic** — reported by `tools/adoption_report.py` and never summed into a bar,
  always printed beside the count of workflow runs that produced it;
- **stars, watches and forks with no commit** — one click each. One of this repository's
  two forks is exactly this, and the star is the owner's own;
- **anything a reader could only assert.** If the tool cannot read it, it prints
  *unreadable* and the bar stays open.

`tools/adoption_report.py` is the instrument and `docs/workflow/adoption.md` is the page
that says what is left for a human. Neither is wired into `tools/verify.py`: this is not a
property of a diff, it is a property of the world, and it is read at a milestone exit and a
release — the boundary ADR-0118 drew around `check_repo_settings.py`, for the same reason
(a scheduled caller would need a long-lived token, and the supply chain is built to not have
one).

## Consequences

**Positive.** The gate can now be evaluated by a command instead of an argument, and it
reports **1 of 3** rather than the *zero* the roadmap believed — and it names them. Every
number it prints carries the actor and the act behind it, so a later reader can audit the
verdict rather than trust it. The exclusions are executable rather than advisory: clone
traffic cannot pass a bar, because the field that would carry a verdict is `None`.

**Negative, and accepted.** Three is a judgement, not a derivation; it is recorded here so
that moving it is an edit to a decision rather than a drift. The instrument counts *visible*
acts only, so a real adopter who never opens GitHub still does not exist to it — the gate is
now honest about what it measures, not complete. And the report costs about two minutes of
API calls, because a fork's every branch is compared; that is why it runs at a milestone
exit and not in CI.

**What the instrument found by being run.** Two corrections, both from reality and neither
from reasoning:

1. The first draft compared each fork's **default branch** only, and reported `blamevlan` —
   the one genuine contributor — as a bookmark, because they had done the work on a feature
   branch and left `main` in sync, which is exactly what `CONTRIBUTING.md` asks for. *A
   contributor who follows the branch rule is invisible to a default-branch comparison.*
2. The second draft then reported `Voyagerroc-Lab` as three commits ahead — and the three
   were **ours**, sitting on `ci/declared-mode`, an upstream branch that outlived its squash
   merge and was copied wholesale when the fork was taken. A fork reflecting this
   repository's own undeleted branches back at it is the purest available form of the
   mistake the gate forbids. Only commits an external account **authored** count now
   (`external_commits`), and `tests/test_adoption_report.py` pins it.

**What no code can do.** Every remaining condition moves only when somebody outside this
repository acts, and three owner actions have to precede that: publishing to an index
(nothing resolves on PyPI or TestPyPI today, ADR-0116's last inch), enabling Pages so the
tutorial has a reader (ADR-0127's last inch), and reopening outside pull requests after M6,
which is the maintainer's stated plan in issue #149 and the thing currently standing between
this repository and its first external merge. `docs/workflow/adoption.md` holds them in one
place. This ADR does not make the gate pass; it makes it possible to tell whether it has.
