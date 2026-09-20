# 2026-09-20 — the cloners were us (roadmap 6.12)

- **Session scope:** roadmap 6.12 — the Phase-3 adoption gate M5 carried into M6 at zero:
  read it, decide whether ten is the wrong number, record the re-cut rather than assume it.
- **PR:** #172 (`feat/re-cut-the-adoption-gate`). Follows #171, merged as `a034bb9`.
- **Milestone 6:** 6.12 closed. 6.18, 6.24 and 6.25 remain open.
- **Decisions it records:** D-030 (owner decision, taken in session) and
  [ADR-0138](../../../adr/0138-recut-the-adoption-gates-onto-acts-we-can-observe.md).

## The number was not the first problem

The item asked one question — *is ten the wrong number for a pre-1.0 tool nobody has heard
of?* — and the honest answer is that the number is the third thing wrong with the gate.

**It is not observable.** There is no telemetry and there will be none (D-016), so a
repository that installs this, compiles its documentation and never says so cannot be
counted. A gate that admits only *assert it* or *carry it* is not a gate, and 5.43 was right
to carry rather than assert.

**The one number that looked like adoption was ours.** GitHub reports 3 988 clones from 340
unique cloners in the fortnight to 2026-09-19 — beside 225 page views from **one** unique
visitor, the owner. Fourteen jobs a CI run, one `actions/checkout` each, 12–28 runs a day.
The proof is the two days inside the window when no workflow ran at all, 2026-09-06 and
2026-09-16: **8 clones and 14**. Reaching for the 340 would have closed the gate by counting
this repository, which the item forbids in exactly those words. It is now excluded *by name*
and structurally: the field that would carry its verdict is `None`.

**And Phase 4's plugin count contradicts D-029.** *≥ 5 community plugins* before 1.0 asks
five strangers to publish out-of-tree plugins, which is the thing the topology decision
reserves for after the freeze. That one was not in the item's scope and was re-cut in the
same record, because a gate nobody is permitted to satisfy is worse than a gate nobody
reaches.

## What asking found that reading could not

The item was written against *"1 star, 0 forks, and every merged pull request authored by
the owner or Dependabot."* Two forks now. And on 2026-09-15 somebody took a reserved
`good first issue` — #149, the settings survey — built it, pushed it to their fork, and
reported that GitHub would not let them open the pull request. The maintainer reviewed the
commit in the thread and asked them to wait for M6 and the hardening baseline; they agreed.

So the contribution ladder ADR-0117 built **worked**, on its second week, and the first
external contribution this repository has ever received is finished, reviewed, and unmerged
by decision. Reopening intake is not housekeeping. It is the gate.

## The instrument corrected itself twice, and that is the finding

Neither correction came from thinking about the problem. Both came from running the thing.

1. Comparing each fork's **default branch** reported the one genuine contributor as a
   bookmark: they had done the work on `fix/repo-settings-checks` and kept `main` in sync,
   which is precisely what `CONTRIBUTING.md` asks for. *A contributor who follows the branch
   rule is invisible to a default-branch comparison.*
2. Comparing every branch then reported a second contributor **three commits ahead** — and
   the three commits were ours, sitting on `ci/declared-mode`, an upstream branch that
   outlived its squash merge and was copied wholesale when the fork was taken. A fork
   reflecting our own undeleted branches back at us is the purest available form of the
   mistake this gate exists to forbid.

Only commits an external account *authored* count now, and `external_commits` is a function
of its own with a test that names both mistakes, because the rule that decides a gate is the
rule that gets tested.

## Standing, and who moves it

`python tools/adoption_report.py`, 2026-09-20: **1 of 3** engaged actors, **0 of 3**
recurring contributors, and `mycelium-os` resolves on neither PyPI nor TestPyPI. Three owner
actions precede anything else and none is an agent's — publish to an index, enable Pages,
reopen outside pull requests — and they are collected in `docs/workflow/adoption.md` instead
of being rediscovered a fourth time.

The report is deliberately not in `verify.py` and not on a schedule. This is a property of
the world, not of a diff, and a scheduled caller would need the long-lived token the supply
chain is built to avoid (the ADR-0118 boundary). It runs at a milestone exit and before a
release, beside `check_repo_settings.py`.

No code closes this item. What code can do is make the answer checkable instead of
arguable, and that is what shipped.
