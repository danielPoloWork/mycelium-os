# Adoption: the gate nobody's code can close

Two of this project's phase-exit gates are not statements about the software. Spec 06 asks
Phase 3 for **external adoption** and Phase 4 for **external contribution**, and no change
to this repository can produce either. D-030 re-cut both onto acts this project can
actually observe (ADR-0138); this page is the operating side of that decision — how the
count is taken, and what is left for a human.

Everything about *what* counts and *why* lives in
[ADR-0138](../adr/0138-recut-the-adoption-gates-onto-acts-we-can-observe.md). Nothing here
restates it.

## Taking the count

```bash
python tools/adoption_report.py
```

Needs `gh`, authenticated. It takes about two minutes, because it compares every branch of
every fork. `--json` for a machine, `--no-network` to skip the index lookups (they are then
reported *unreadable*, not absent), `--repo owner/name` to point it elsewhere.

Exit **0** when nothing in scope is failing, **1** when a condition is not met or a deferred
decision's trigger has fired (below), **2** when GitHub could not be asked.

It is **not** in `tools/verify.py` and not on a schedule, for ADR-0118's reason: this is a
property of the world rather than of a diff, and an unattended caller would need a
long-lived token — the one thing the supply-chain design exists to avoid. Read it at a
**milestone exit** and before a **release**, beside `tools/check_repo_settings.py`.

Reading clone traffic needs push rights. Without them that section says so and nothing
else changes; the traffic figure never carries a verdict in any case.

## What is left for a human

The report can only ever say *not yet* while these three are outstanding. None of them is
an agent's to do, and two of them are the last inch of work that is otherwise finished.

| # | Action | Where it is written down | Why the gate waits on it |
|---|---|---|---|
| 1 | **Publish to an index.** Rehearse on TestPyPI, create the `pypi` environment with a required reviewer, add the pending publisher, run `publish.yml`. | [`packaging.md`](packaging.md) § *Turning the publish on* | `pip install mycelium-os` 404s on PyPI **and** TestPyPI today. Nothing can dogfood what nothing can install (roadmap 6.11, ADR-0116). |
| 2 | **Enable GitHub Pages.** Settings → Pages → Build and deployment → Source: **GitHub Actions**. | [`github-setup.md`](github-setup.md) | `pages.yml` runs on every push to `main`, checks the endpoint, prints *"Pages not enabled"* and skips the deploy. The tutorial, the four how-tos and the plugin-author guide have no reader (roadmap 6.14, ADR-0127). |
| 3 | **Reopen outside pull requests** once M6 closes and the hardening baseline is in. | the maintainer's reply on issue #149, 2026-09-16 | This is the gate's own blocker, and it is a deliberate one. See below. |

Then, and only then, outreach — which is the maintainer's, not an agent's, and which this
repository deliberately holds no plan for.

## The contribution that is finished and cannot be delivered

On 2026-09-15 **`blamevlan`** took issue #149 — a `good first issue`, held open for a human
by the rule [AGENTS.md §6.1](../../AGENTS.md) writes down and ADR-0117 argued for — built
it, pushed it to `fix/repo-settings-checks` in their fork, and reported that GitHub would
not let them open the pull request. The maintainer reviewed the commit in the issue thread
and asked them to wait until Milestone 6 closes, because the repository-hardening baseline
is not yet in place. They agreed to wait.

That is the ladder working and the gate stuck at the same time, and both halves are worth
saying plainly:

- the reservation rule did its job — an outside human found a first move and took it;
- the first external contribution this repository has ever received is **complete,
  reviewed and unmerged by decision**, and the Phase-3 gate cannot pass until intake
  reopens. Action 3 above is therefore not housekeeping: it is the gate.

No interaction limit or ruleset is active as of 2026-09-20, and branch protection on `main`
is still absent (`check_repo_settings.py` has reported that since roadmap 6.6). Whatever
blocked the pull request on 2026-09-15 is not visible in today's settings, so **verify
before announcing anything**: the cheapest check is to ask the contributor to try again.

## The deferred decision it also watches

Spec 06 §3 defers the **remote build cache** (roadmap 7.1) until *"≥ 1 team dogfooding with
measured duplicate-build pain"*. Until roadmap 7.4 that trigger was the same kind of
sentence the adoption gates were before D-030: nothing could measure the pain, so nothing
could ever say it had fired. It has an instrument now, and the report above reads it
([ADR-0154](../adr/0154-price-the-remote-cache-before-its-trigger-and-give-the-trigger-a-reading.md)).

**If you are a team building one corpus and cold builds cost you**, measure it on your own
repository — nothing inside it is written; the documents are copied into scratch:

```bash
python tools/measure_cache_ceiling.py --corpus /path/to/your/repo --out /tmp/ceiling \
    --people 5 --cold-builds-per-week 40 --rounds 1
```

It prints a fenced JSON block. Paste it, fence and all, into an issue on this repository.
`--people` and `--cold-builds-per-week` are your own figures; the tool cannot know them and
does not guess. The report carries numbers only — no path, no document name.

What the report does with it, and what it does not:

- **It fires on one report** from an external login (not the owner, not a bot) on a corpus
  **two or more people** build, whose saving is **outside the measurement's own noise** —
  every seeded build faster than every cold one. *≥ 1 team* is the spec's number, unmoved;
  7.4 gave its words a reading.
- **A fired trigger is a decision owed, not a decision taken.** How much pain justifies an L-sized
  feature with a new trust boundary is the call the trigger defers, and it is the owner's.
  The report exits non-zero while a trigger has fired, and the trigger leaves the tool in
  the change that records the decision — ADR-0118's shape for a deferral.
- **To withdraw a report** — fabricated, mistaken, or retracted by its author — close its
  issue as *not planned*. The trigger reads GitHub's own record of that, so no code
  changes.

## When the numbers move

A signal that passes is recorded where the gate is, not here:

1. re-run the report and keep its output in the milestone-exit review;
2. tick the condition in spec 06 §3 against the run that showed it;
3. if a bar itself has to move, that is an owner decision and a new `D-0NN` beside D-030 —
   never an edit in passing. The bars live in one place in code
   (`ENGAGED_ACTORS_BAR` and its siblings) and `tests/test_adoption_report.py` fails if one
   changes without the decision changing with it.
