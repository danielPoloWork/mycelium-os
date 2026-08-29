# Staying Current

Profiles encode toolchain knowledge as **static data**, so they drift as ecosystems move
(new tool versions, newer CI runner images, bumped action versions, evolving best practices).
This is the routine that keeps EADOS modern. It is run by the
[`profile-author`](../agent/profile-author.md) role and, like everything else, it **drafts**;
a human reviews and merges.

## What to refresh (per profile)

For each [`orchestrator/profiles/<lang>.yaml`](../orchestrator/profiles/):

1. **Tool versions & choices.** Are the build tool, test framework, formatter, linter,
   coverage, and doc tool still the de-facto enterprise standard at a current version? If a
   better standard has emerged, switch it — and write an ADR for the change.
2. **Language standard/edition.** Is `default_standard` still a sensible modern default?
3. **CI matrix.** Bump runner images (e.g. `ubuntu-24.04`, `macos-14`, `windows-2022`) and
   pinned action versions (`actions/checkout`, `setup-python`, …) to current stable.
4. **Sanitizers / checkers.** New race/leak/type/vuln tooling worth adopting?
5. **Dependabot ecosystem.** Still correct for how the language packages?

Also refresh shared bits: the `templates/.github/workflows/*` action pins and the
`templates/tools/consistency_lint.py` Python version in CI.

### When Dependabot bumps a shared action pin

Dependabot's `github-actions` ecosystem updates only the real workflow files
(`.github/workflows/*.yml`) — never the rendered `*.tmpl` templates (ADR-0009) — so a bump drifts
the templates and the `action-pins` lockstep gate blocks the PR. This is now **auto-remediated**:
the `dependabot-pin-sync` workflow ([ADR-0013](../docs/adr/0013-dependabot-action-pin-auto-remediation.md))
re-syncs the templates and commits the fix back onto the Dependabot PR. (With the default
`GITHUB_TOKEN` the fix lands but the check re-runs on the next event / a manual re-run; set the
GitHub App secrets `SYNC_APP_ID` + `SYNC_APP_PRIVATE_KEY` for green-by-itself — see the
[setup guide](dependabot-sync-token.md).)

To do it by hand (locally, or for any non-Dependabot drift), run the same fixer the workflow uses:

```bash
python .eados-core/tools/sync_action_pins.py --fix   # rewrite the template pins to match the factory CI
```

`--check` (the default) reports drift without writing. Same lockstep the `action-pins` gate
enforces, applied as a fix.

## How to run it

1. Adopt the `profile-author` role.
2. For each profile, compare against the current ecosystem; draft the edits + any ADR.
3. Prove it: `python tools/eados_lint.py` (profile completeness) **and** a render of a manifest
   for that language whose generated `consistency_lint.py` passes (the render-smoke pattern).
4. One PR per profile (one logical change at a time), drafted for the maintainer.

## Automating it (Claude Code routine)

Schedule a recurring cloud agent with the `/schedule` skill so EADOS checks itself on a cadence
without you remembering to. A monthly routine, for example, whose prompt is:

> *"Adopt the profile-author role (`.eados-core/agent/profile-author.md`). For each
> `.eados-core/orchestrator/profiles/<lang>.yaml`, check whether its tool versions, CI runner
> images, action pins, and default standard are still current; if not, draft a one-profile-per-PR
> update with an ADR where a default tool changes. Run `.eados-core/tools/eados_lint.py` and a
> render-smoke before drafting. Draft only — do not merge."*

Pick a cadence (monthly/quarterly) and an off-hours cron (e.g. `0 9 1 * *`). The routine
inherits the same agent-vs-human boundary: it opens nothing and merges nothing.

## Cadence

Monthly is plenty for action/runner pins; quarterly for tool-choice review. Always run it
**before cutting a release** so a release never ships on a stale toolchain.
