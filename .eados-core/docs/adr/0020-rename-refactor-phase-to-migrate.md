# ADR-0020: Rename the brownfield phase `refactor` → `migrate`

## Status

Accepted (2026-07-10)

## Context

The last phase of the pipeline — `init → design → plan → scaffold → audit → refactor` — is a
**false friend**. Named `refactor`, it does not restructure application code for quality; it
**migrates an existing repository toward the EADOS standard** by rendering missing governance
artifacts through the write-contained sandbox (`brownfield.py` → `migration_planner.py` →
`render_artifact.py` + `sandbox.py`). Its tooling was already named for migration; only the phase
carried the misleading name. "Refactor" universally means behavior-preserving code
restructuring, so the name misleads users and — decisively — **blocks shipping a true
code-quality `/eados refactor` command**, which ADR-0019 ratified as a cross-cutting member of the
command surface (#243).

The owner ratified the rename on 2026-07-09 (M15 Wave 0, drafted as issue 0014 / #236). ADR-0019
already anticipated it, phrasing the pipeline as "…→ `refactor` (→ `migrate` once the #236 rename
lands)".

## Decision

1. **Rename the phase `refactor` → `migrate`** across the live machine and its governed docs, in
   one PR: the `workflow.yaml` state / transition / gate `required_for`, `authority.yaml` role
   phases, `eados.PHASES` + `record_run.PHASES`, `project.yaml.template`, the command procedure
   (`commands/refactor.md` → `commands/migrate.md`) and the `commands/README.md` row, the tools'
   prose (`render.py`, `render_artifact.py`, `sandbox.py`, `migration_planner.py`), and the
   user-facing prose (README + zh-Hans/ja translations, AGENTS.md §3, RFC-0001, the walkthrough,
   the flow diagram, `learning/runs/README.md`). Behavior is unchanged — this is a name, not a
   new capability.

2. **Back-compat for one minor version.** An existing manifest that still records
   `delivery_state.phase: refactor` (or a checkpoint into it) is accepted: `phase_runner`
   canonicalizes the alias (`PHASE_ALIASES = {"refactor": "migrate"}`) in `current_phase` and
   `checkpoint_chain_problems`, and prints a one-line **deprecation warning** at the CLI boundary.
   A legacy manifest keeps working; the warning tells the owner to update it.

3. **History is not rewritten.** The CHANGELOG, the prior ADRs (0007, 0011, 0018), and the
   completed-milestone records in `ROADMAP.md` (M5 shipped *as* `refactor`) keep the old name —
   they record what was true when written. `refactor` also legitimately remains as the
   Conventional-Commits type (`git.yaml`, branch naming) and as the **future code-quality command**
   (`/eados refactor`, ADR-0019 / #243) — this ADR frees exactly that name.

## Consequences

- `/eados migrate` behaves exactly as the old `/eados refactor`; the end-to-end phase smoke test
  passes against the renamed state.
- The name `refactor` is now free for the code-quality command (#243), unblocking M15 Wave 2.
- A grep for the old phase name in governed docs returns only history (CHANGELOG / ADR / ROADMAP
  milestone records), the commit-type usages, the `#243` code-quality references, and the
  deprecation-alias note — never a live pipeline reference.
- README changed, so its i18n source hash is refreshed (`2007aeb5fd9d` → `d18e3e9d5228`) and both
  translations updated in lockstep; the `i18n-freshness` gate stays green.
- The deprecation alias is scheduled for removal in the next minor after one release carries it.

## References

- Issue [#236](https://github.com/danielPoloWork/pgs-eados/issues/236) (draft 0014) — the decision
  request; owner ratification 2026-07-09 (`.issues/M15-command-surface-milestone.md`).
- ADR-0019 (command-surface taxonomy — the cross-cutting `refactor` command this frees, #243);
  ADR-0011 (the phase-machine pivot that introduced the `refactor` phase); ADR-0007 (the shared
  write-containment sandbox the phase uses).
- RFC-0001 §3 (the phase state machine), §9 (the phase edits real user code, sandboxed + last).
