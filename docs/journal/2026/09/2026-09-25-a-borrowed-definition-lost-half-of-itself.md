# 2026-09-25 — a borrowed definition lost half of itself (roadmap 7.13)

- **Session scope:** roadmap 7.13 — the gap 7.11 found in ADR-0155's plugin-sandbox reading:
  reusing D-030's engaged-actor definition on a plugin's own repository excluded only that
  plugin's owner, so this repository's owner read as a stranger to every plugin and could
  fire the trigger alone.
- **PR:** #N (`fix/exclude-this-owner-from-plugin-adoption`). Follows #203, merged as
  `f19d38d`.
- **Milestone 7:** 7.13 closed.
- **Decision it records:**
  [ADR-0160](../../../adr/0160-exclude-this-repositorys-owner-from-a-plugins-own-adoption.md).

## Two exclusions, one parameter

`is_external(login, owner)` answers one question — is `login` a stranger to `owner` — and
every caller until roadmap 7.5 asked exactly that. 7.5 asked a second one at the same call
site without changing the shape of the answer: is this login a stranger to the *plugin's*
owner **and** to *ours*. Nothing failed, because the first question's answer was still
correct; the second one was silently never asked. `also_exclude` gives it a slot, threaded
through `tally`, `external_commits` and `fork_acts` to the one caller that needed it,
`engaged_actors`, defaulting to `None` everywhere else so every existing behaviour is
unchanged.

## Pinning the wiring, not just the rule

`is_external("danielPoloWork", "acme", also_exclude="danielPoloWork")` being `False` proves
the function does what it is asked. It does not prove `third_party_plugins` asks it — that
the fix reaches the one call site the bug lived at. A spy standing in for `engaged_actors`,
recording the arguments `third_party_plugins` actually calls it with, is what pins that: the
pre-fix call shape (no `also_exclude` at all) was reproduced by hand against the fix to
confirm the new test would have failed against it, before trusting that it does.

## The record said less than the code already did

ADR-0155's *exists* bullet read *"a repository that is not this one"* while
`plugin_candidates` has excluded every repository this repository's owner holds since it was
written — the stricter reading, and the one 7.13 judged intended. Corrected in place with a
`> **Corrected**` note naming ADR-0160, per `docs/workflow/documentation.md`'s amendment
mechanism, rather than silently retyped: the record's own convention is that a decision that
moved is traceable, even when moving it just means catching up to code that was already
right.

## What the next session should know

- **The plugin-sandbox trigger still reads *holding*.** Neither defect had a candidate to
  move: GitHub code search finds no repository outside this one declaring `mycelium.plugins`
  or `mycelium.modules`. The fix matters the day one exists, not today.
- **`also_exclude` is unused outside `third_party_plugins`.** A future caller with the same
  shape — a tally on somebody else's repository that must still exclude ours — has the
  parameter rather than a fifth copy of the rule; nothing today needs a set of exclusions.
- **7.12 remains open**: the maintainer's full architecture review by a panel of senior
  architects, filed 2026-09-25 alongside 7.13's own filing item, 7.11.
