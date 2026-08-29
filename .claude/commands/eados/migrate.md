---
description: EADOS migrate phase — bring an existing repo up to the standard via gated, sandboxed, additive PRs (role: enterprise-architect)
---

Run the governed EADOS command **`/eados migrate`**.

This adapter is a thin pointer (ADR-0019 class 4: an adapter surfaces a command, never adds
behavior). The canonical procedure is the single source of truth — read it and follow it exactly;
do not improvise or reproduce it from memory.

- **Procedure:** `.eados-core/orchestrator/commands/migrate.md`
- **Acting role:** `enterprise-architect` (`.eados-core/orchestrator/os/authority/authority.yaml`)
- **Contract:** `AGENTS.md` — agent drafts / human merges; one PR at a time; every human gate is
  confirmed by the owner, never by you. Every write goes through the sandbox — additive only.

User arguments (may be empty): $ARGUMENTS
