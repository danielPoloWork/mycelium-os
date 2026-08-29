# Failure & Recovery Playbook

The generation playbook describes the happy path; this is what to do when a step fails. The
governing principle: **never silence a gate or hand-edit the generated repo to make a check
pass** — fix the cause (manifest, profile, template, or seed) and re-run. When in doubt, stop
and ask the maintainer; the agent-vs-human boundary still holds under failure.

| Symptom | Cause | Recovery |
|---|---|---|
| **No profile for the chosen language** (Step 0/2) | The language has no `profiles/<lang>.yaml`. | Stop. Adopt the [`profile-author`](../agent/profile-author.md) role, author the profile from [`profiles/_schema.md`](profiles/_schema.md) + an ADR, then resume. **Never** inline toolchain facts into a template to work around it. |
| **Render aborts: unresolved placeholder** | A template uses a `{{UPPER}}` with no manifest value, or a placeholder missing from the dictionary. | The renderer lists each one. Add the value to `project.yaml`, or (if it is a new token) define it in [`placeholders.md`](placeholders.md) and wire it. Re-render. Never emit literal `{{…}}` to disk. |
| **`consistency_lint.py` fails after render** (Step 7) | A day-zero seed is malformed (ROADMAP Spec Coverage Map, ADR index, version badge, bug/i18n schema). | Read the named check, fix the **template/seed or manifest** (not the output), re-render, re-lint. The seeds are arranged to pass on a clean run, so a failure points at a real defect. |
| **`self_review.py` reports INCOMPLETE** | A required artifact didn't render — usually a capability gate or a skipped template. | Check the manifest's `capabilities.*` and the generate.md render tables; render the missing artifact; re-run. |
| **Toolchain smoke build fails** (Step 7.3) | The skeleton can't build a trivial stub yet. | Don't block: record it as the first Milestone-1 task and note it in the hand-off report. |
| **Interrupted / partial run** | A run stopped midway. | The output dir is a sibling and uncommitted — delete it and re-render from the **confirmed** manifest. Rendering is idempotent. |
| **`eados_lint.py` fails** (working on EADOS) | placeholder/profile/registry/lessons/generate-reference drift. | The message names the failing check; fix that artifact and re-run before drafting the PR. |
| **git push / PR step fails** | Auth, protected branch, or no remote. | Never force-push, never push to the default branch. Print the suggested commands and stop for the human. |

## Escalate, don't improvise

If a failure is not covered here, or fixing it would mean dropping a governance rule or
disabling a gate, **stop and surface it** to the maintainer with the exact error. A drafted PR
that does not pass every gate is not ready; say so plainly rather than working around it.
