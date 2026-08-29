---
description: EADOS debug — governed defect investigation; reproduce → root-cause → fix + regression test → bug ledger (cross-cutting, any phase; roles: tech-lead + reviewer)
---

Run the governed EADOS command **`/eados debug`**.

This adapter is a thin pointer (ADR-0019 class 4: an adapter surfaces a command, never adds
behavior). The canonical procedure is the single source of truth — read it and follow it exactly;
do not improvise or reproduce it from memory.

- **Procedure:** `.eados-core/orchestrator/commands/debug.md`
- **Class:** cross-cutting (ADR-0019 class 3) — advisory and non-state-advancing; it never writes
  `delivery_state.phase` and never proposes a transition. **Manifest required** (ADR-0019
  boundary): pasted/standalone code is refused and routed to `/eados init` / `/eados adopt`.
- **Acting roles:** `tech-lead` authors the fix + the ledger record
  (`.eados-core/orchestrator/os/authority/authority.yaml`; owns `src/**`, drafts `docs/bugs/**`);
  the `reviewer` verifies red → green.
- **Artifacts:** a failing-then-green regression test, a one-logical-change fix, and the
  `docs/bugs/` ledger record + index row (integrity: the generated `consistency_lint.py` `bugs`
  check).
- **Contract:** `AGENTS.md` — the agent reproduces, root-causes, fixes, and **drafts** the PR;
  the human opens and merges. No fix without a red reproduction.

User arguments (may be empty): $ARGUMENTS
