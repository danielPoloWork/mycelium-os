---
description: EADOS adopt — brownfield intake for an existing repo; gap map → goal menu → manifest with adoption block → a legal, human-gated route into design/audit/migrate (role: enterprise-architect)
---

Run the governed EADOS command **`/eados adopt`**.

This adapter is a thin pointer (ADR-0019 class 4: an adapter surfaces a command, never adds
behavior). The canonical procedure is the single source of truth — read it and follow it exactly;
do not improvise or reproduce it from memory.

- **Procedure:** `.eados-core/orchestrator/commands/adopt.md`
- **Class:** phase intake (ADR-0019 §1) — `init`'s brownfield sibling, **not** a new phase: the
  manifest lands at `delivery_state.phase: init`, and the chosen goal routes through the
  `init → audit` / `init → migrate` workflow edges ADR-0021 made legal by data (gated on
  `manifest-valid` + the in-process `adoption-recorded`).
- **Acting role:** `enterprise-architect` (`.eados-core/orchestrator/os/authority/authority.yaml`;
  owns the `init` and `migrate` phases).
- **Intake:** read-only gap map (`brownfield.py`) captured beside the manifest → the goal menu
  (`governance-docs` / `retro-design` / `audit` / `migrate` / `bugfix` — the closed ADR-0021
  vocabulary) → the manifest's `adoption:` block (goals + gap_map_ref + provenance).
- **Contract:** `AGENTS.md` — interview in the maintainer's language, manifest in English (§2);
  the agent drafts and **proposes**; the human confirms every human-gated route. A greenfield
  target is refused and routed to `/eados init`; an already-governed repo to `/eados status`.

User arguments (may be empty): $ARGUMENTS
