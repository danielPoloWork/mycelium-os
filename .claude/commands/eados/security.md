---
description: EADOS security — the audit threat-modeling sub-mode (STRIDE → docs/security/threat-model.md; role: security-auditor). Alias of /eados audit.
---

Run the governed EADOS command **`/eados security`** — an **alias** into the **threat-modeling
sub-mode of `/eados audit`** (ADR-0019 §2: `security` is a sub-mode, not a phase or a new command;
this adapter routes, it never adds behavior).

The canonical procedure is the single source of truth — read it and follow it exactly; do not
improvise or reproduce it from memory. Enter at its **"Threat-modeling sub-mode"** section.

- **Procedure:** `.eados-core/orchestrator/commands/audit.md` (the `security` sub-mode section)
- **Acting role:** `security-auditor` (`.eados-core/orchestrator/os/authority/authority.yaml`;
  owns `docs/security/**`)
- **Artifact:** the project's `docs/security/threat-model.md` — a STRIDE pass per trust boundary
  (artifact/method/owner are data: `os/risk/risk.yaml` `threat_model:`)
- **Contract:** `AGENTS.md` — defensive assessment only; findings feed the risk register; a
  vulnerability becomes a **draft** advisory the human publishes, never the agent.

User arguments (may be empty): $ARGUMENTS
