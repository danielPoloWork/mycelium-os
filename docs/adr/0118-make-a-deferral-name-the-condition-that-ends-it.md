# ADR-0118: Make a deferral name the condition that ends it, in code

- **Status:** Accepted
- **Date:** 2026-09-15
- **Deciders:** tech-lead (EADOS delivery agent) with the maintainer, per RFC-0001 / spec 06 §4
- **Related:** [ADR-0117](0117-sign-and-inventory-the-artifact-and-reserve-the-rung-a-newcomer-stands-on.md)
  (the survey that found the settings absent, and the tool this extends),
  [ADR-0116](0116-publish-under-a-name-already-decided-and-let-the-artifact-be-a-defined-thing.md)
  (why no long-lived credential exists to run this unattended),
  [ADR-0113](0113-close-a-milestone-on-its-gates-and-carry-an-unmet-one-by-name.md) (an unmet
  gate is carried by name, never waived quietly — the same failure one level up),
  [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md) (a gate that
  fires on everything selects for being ignored); `docs/security/audit-2026-08-29-bootstrap.md`
  F2/F3; `docs/security/threat-model.md` B1; spec 06 §4; AGENTS.md §7; roadmap 1.8, 3.7, 6.6, 6.16

## Context

Roadmap 6.6 surveyed the repository's own settings and reported three documented steps that had
never been installed. The obvious response was to file three corrective roadmap items. The
maintainer asked whether that made sense, and looking for the answer produced a better question.

**Two of the three were never oversights.** They are risks that were *formally accepted*, on
2026-08-29, in the bootstrap audit's risk register, each with a severity, an owner and an
explicit condition for revisiting:

| record | accepted because | revisit when | status as written |
|---|---|---|---|
| F2 (medium) | branch protection is unavailable on a private free-plan repository (API 403 verified) | *"at public/Pro"* | `half-resolved — protection pending public/Pro` |
| F3 (low) | *"today there are no external reporters (private repo), so exposure is nil; at public launch a reporter would find a dead door"* | *"the day the repo goes public, before any announcement"* | `open — deferred with trigger` |

Both conditions came true. The repository is public. The first external fork appeared on
**2026-09-14T20:17:33Z**. F3's recorded impact — *exposure is nil* — had been void for weeks,
and the "dead door at public launch" it predicted is the door that is there now.

Nothing observed either. The reasons are worth naming because they are structural rather than
careless:

- **A risk register is a document, and nobody re-reads a document.** The register was written
  once, at bootstrap, and referenced twice since — both times by things pointing *into* it.
- **The roadmap item that carried F3's trigger was ticked and closed.** Item 1.8's own text says
  *"activate the repo feature at public launch — register F3"*. It shipped at v0.1.0 with the
  trigger inside it, and a closed item is not a place anyone looks.
- **The threat model recorded the premise as an assumption and never moved.** Boundary B1 read
  *"repo currently private (no external contributors yet)"*, which AGENTS.md §7 obliges to move
  with a trust boundary. Going public was such a change.

So three independent records each held a piece of a condition, and none of them could tell
whether it had fired.

## Decision

**A deferral must name the condition that ends it in a form a machine can evaluate. One that
cannot be written that way has no expiry, and is not granted.**

`tools/check_repo_settings.py` gains `DEFERRALS`: the register's **open** deferrals, each with
the premise it rested on, the condition that voids it, and the setting that closes it. The tool
evaluates every condition against what GitHub reports and names the ones whose premise is void.

**The two halves are separated by what they cost to ask**, and this is the design's load-bearing
part rather than an optimisation:

- **Evaluating a condition** reads only `repos/{owner}/{repo}` — visibility, plan, merge methods
  — which any token can fetch. This is the half that was missing, and it is the half that
  matters: *a deferral whose premise is void is a finding again whether or not anyone can
  verify the remedy.*
- **Verifying a remedy** reads branch protection and the vulnerability-reporting setting, which
  need administrative rights. `Finding.installed` is therefore **three-valued**, and a caller
  without those rights is told the remedy is *unverifiable* rather than absent.

`--triggers-only` runs the first half alone. `Expiry.unremedied` counts an unverifiable remedy
as unremedied, on the rule that in a security record *"I could not check"* is not a pass.

**The list is self-limiting.** It holds what the register still calls deferred, so the owner
installs the remedy, the register records the closure, and the row leaves `DEFERRALS` in the
same change. That is why a fired condition is reported as a failure even in `--triggers-only`,
where the remedy is unknown: the thing being asked for is not the setting, it is *the register
entry closed by someone who looked*.

**It runs in the release procedure, not in CI, and that is a decision about credentials.**
Reading these settings unattended would need either `administration: read` on the workflow token
— unverified, and it would still not cover every endpoint — or a long-lived personal token,
which is the one thing ADR-0116 and ADR-0117 removed from every other part of this supply chain.
A release is the one moment a maintainer with their own authenticated `gh` is already in the
loop, so `release.md` gains it as step 0b. The cheap half stays available to any caller that
wants it.

**The three records are brought current in the same change**, because a re-assessment that
lands later is the failure repeating:

- **F3 is re-rated `low` → `medium`.** Its severity was conditional on a premise that is false.
- **F2 keeps `medium` and its deferral is marked expired.** The plan constraint is gone; the
  protection API now answers *404 not protected* rather than *403 unavailable*.
- **Threat model B1's assumption line is corrected** and the fork recorded. The controls it
  lists still hold and are the right ones for a public repository; what is gone is the comfort
  the line offered, and two accepted risks rested on it.

**The three settings themselves get no roadmap items.** They are owner actions in a web UI or
one `gh` call; an item no pull request can close is roadmap pollution, and this repository
already declines that shape — 6.11's three index-side steps are a runbook in `packaging.md`, not
items. They are tracked where they already were, in the register, which now has a watcher.

## Alternatives Considered

- **File three corrective roadmap items, one per finding.** The question that started this, and
  it is wrong three times over: it would be a third copy of a record that already exists twice,
  it would put the roadmap in charge of something no PR can close, and it would treat findings
  of three different severities with one mechanism. It also fixes nothing — the next deferral
  would be granted the same way and lost the same way.
- **Do nothing; the survey already found them.** The survey was manual and happened to be run
  for another item. Repeating it depends on somebody deciding to, which is precisely the
  property that failed.
- **A scheduled workflow polling GitHub.** The mechanism that most looks like the answer.
  Rejected on the credential: unattended reads of protection settings need a long-lived token,
  and introducing one here would undo the argument every other part of this supply chain is
  built on. Named rather than hand-waved, and the cheap half is available to a scheduled caller
  that wants only the conditions.
- **Add the check to `tools/consistency_lint.py`**, which already runs on every PR. Rejected:
  the lint asserts *cross-artifact congruence within this repository* and makes no network call.
  Giving it one would change what a red lint means, and a lint that needs the internet fails for
  reasons that have nothing to do with the change under review.
- **Parse the conditions out of the register's prose.** Tempting, since the register already
  states them in words. Rejected: it would make the security record's formatting load-bearing,
  and a prose condition like *"at public/Pro"* has no single reading a parser could be trusted
  with. A short executable list beside the prose is honest about being a second statement, and a
  test holds the two together.
- **Re-rate F3 and stop there.** Rejected: the re-rating is the symptom. The finding is that a
  condition fired with nothing watching, and fixing the instance without the mechanism is what
  6.6 did for `chardet` and explicitly filed 6.15 not to repeat.
- **Treat the dead disclosure channel as a bug-ledger record.** Genuinely arguable — the ledger
  covers CI and repository plumbing defects (BUG-0001, BUG-0006), and a published policy that
  does not work is a defect. Rejected because the ledger's own rule is *verified, reproducible
  defect in `mycelium-os`*, and this is an unperformed configuration step whose record already
  exists in the register. Duplicating it would give one finding two homes and two statuses.

## Consequences

- **`python tools/check_repo_settings.py` now exits non-zero for two reasons**, and says which:
  a documented step is not installed, or an accepted risk rests on a void premise. Today it
  reports both — F2 and F3 are expired and unremedied, pending the owner.
- **A future deferral costs a row in `DEFERRALS`.** If its condition cannot be expressed against
  what GitHub reports, the deferral is refused. That is the whole behavioural change, and it is
  a constraint on how risk is accepted rather than a new capability.
- **The release procedure gains step 0b** and a boundary row: the agent runs the check and
  carries its verdict into the release PR; installing anything it reports absent is the
  maintainer's.
- **Three security records are current** for the first time since the repository went public,
  and each says when and why it changed.
- **A limitation, and it is the honest one.** This watches the conditions the register *has
  written down*. A risk accepted in conversation, or one whose condition nobody thought to
  state, is still invisible — `DEFERRALS` cannot find what the register never recorded. What it
  does remove is the class where the condition *was* stated and no one was holding it.
- **A second limitation.** The trigger is evaluated only when someone runs the tool. Release
  time is a real cadence and a much shorter one than seventeen days, but it is not continuous,
  and the ADR states that rather than implying otherwise.

## References

- `docs/security/audit-2026-08-29-bootstrap.md` — F2 and F3, with their 2026-09-15 re-assessment.
- `docs/security/threat-model.md` — B1's corrected assumptions, the Spoofing row, and §3's rule.
- `docs/workflow/release.md` step 0b; `docs/workflow/github-setup.md` §0.
- Re-runnable: `python tools/check_repo_settings.py`,
  `python tools/check_repo_settings.py --triggers-only --json`.
