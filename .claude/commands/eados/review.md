---
description: EADOS review — evaluate an inbound PR against the contribution policy; recommends, never merges (role: contribution-reviewer)
argument-hint: <PR#>
---

Run the governed EADOS command **`/eados review`**.

This adapter is a thin pointer (ADR-0019 class 4: an adapter surfaces a command, never adds
behavior). The canonical procedure is the single source of truth — read it and follow it exactly;
do not improvise or reproduce it from memory.

- **Procedure:** `.eados-core/orchestrator/commands/review.md`
- **Acting role:** `contribution-reviewer` (`.eados-core/orchestrator/os/authority/authority.yaml`)
- **Class:** cross-cutting (ADR-0019 class 3) — advisory and non-state-advancing; it drafts a
  recommended disposition, and the human disposes (ADR-0014: verify the change, never merge a
  non-owner's commits, always thank).
- **Contract:** `AGENTS.md`.

User arguments (the PR number; may be empty): $ARGUMENTS
