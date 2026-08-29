---
description: EADOS audit phase — risk scoring, traceability lint, and the risk register (role: security-auditor)
---

Run the governed EADOS command **`/eados audit`**.

This adapter is a thin pointer (ADR-0019 class 4: an adapter surfaces a command, never adds
behavior). The canonical procedure is the single source of truth — read it and follow it exactly;
do not improvise or reproduce it from memory.

- **Procedure:** `.eados-core/orchestrator/commands/audit.md`
- **Acting role:** `security-auditor` (`.eados-core/orchestrator/os/authority/authority.yaml`)
- **Contract:** `AGENTS.md` — agent drafts / human merges; one PR at a time; every human gate is
  confirmed by the owner, never by you.

User arguments (may be empty): $ARGUMENTS
