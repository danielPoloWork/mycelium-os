---
description: EADOS upgrade — read-only advisory: what changed upstream since a generated repo was created (cross-cutting, any phase)
---

Run the governed EADOS command **`/eados upgrade`**.

This adapter is a thin pointer (ADR-0019 class 4: an adapter surfaces a command, never adds
behavior). The canonical procedure is the single source of truth — read it and follow it exactly;
do not improvise or reproduce it from memory.

- **Procedure:** `.eados-core/orchestrator/commands/upgrade.md`
- **Class:** cross-cutting (ADR-0019 class 3) — advisory and non-state-advancing; **read-only**. It
  reports what changed upstream and **never** rewrites the generated repository: no patches, no
  merges, no `git` operations, no manifest edits (ADR-0003, 2026-07-27 addendum).
- **Contract:** `AGENTS.md`.

User arguments (may be empty): $ARGUMENTS
