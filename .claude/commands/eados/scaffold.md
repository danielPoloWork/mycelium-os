---
description: EADOS scaffold phase — generate the governed repository from the manifest, the classic factory (role: enterprise-architect)
---

Run the governed EADOS command **`/eados scaffold`**.

This adapter is a thin pointer (ADR-0019 class 4: an adapter surfaces a command, never adds
behavior). The canonical procedure is the single source of truth — read it and follow it exactly;
do not improvise or reproduce it from memory.

- **Procedure:** `.eados-core/orchestrator/generate.md` (the five-step generation playbook — the
  one command whose procedure predates `commands/` and lives beside the interview it drives)
- **Acting role:** `enterprise-architect` (`.eados-core/orchestrator/os/authority/authority.yaml`)
- **Contract:** `AGENTS.md` — agent drafts / human merges; one PR at a time; every human gate is
  confirmed by the owner, never by you.

User arguments (may be empty): $ARGUMENTS
