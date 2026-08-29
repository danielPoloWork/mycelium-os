---
description: EADOS status — read-only doctor; current phase, legal moves, traceability coverage (cross-cutting, any phase)
---

Run the governed EADOS command **`/eados status`**.

This adapter is a thin pointer (ADR-0019 class 4: an adapter surfaces a command, never adds
behavior). The canonical procedure is the single source of truth — read it and follow it exactly;
do not improvise or reproduce it from memory.

- **Procedure:** `.eados-core/orchestrator/commands/status.md`
- **Class:** cross-cutting (ADR-0019 class 3) — advisory and non-state-advancing; a read-only
  doctor that never writes `delivery_state`, proposes no transition, and drafts nothing.
- **Contract:** `AGENTS.md`.

User arguments (may be empty): $ARGUMENTS
