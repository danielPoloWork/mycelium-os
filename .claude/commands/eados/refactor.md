---
description: EADOS refactor — behavior-preserving code-quality refactoring (readability/modularity/idiom, pattern-guided; cross-cutting, any phase; roles: tech-lead + reviewer)
---

Run the governed EADOS command **`/eados refactor`**.

This adapter is a thin pointer (ADR-0019 class 4: an adapter surfaces a command, never adds
behavior). The canonical procedure is the single source of truth — read it and follow it exactly;
do not improvise or reproduce it from memory.

- **Procedure:** `.eados-core/orchestrator/commands/refactor.md`
- **Class:** cross-cutting (ADR-0019 class 3) — advisory and non-state-advancing; it never writes
  `delivery_state.phase` and never proposes a transition. **Manifest required** (ADR-0019
  boundary): pasted/standalone code is refused and routed to `/eados init` / `/eados adopt`.
- **Acting roles:** `tech-lead` authors the restructure + the catalogue row
  (`.eados-core/orchestrator/os/authority/authority.yaml`; owns `src/**`, drafts `docs/patterns/**`);
  the `reviewer` holds the quality-bar verdict (`AGENTS.md` §10).
- **Guarantee:** **behavior-preserving** — a green test suite on both sides of the change
  (characterization tests added where coverage is missing before restructuring); guided by the
  committed architecture style + the patterns catalogue; a structural pattern introduction earns
  its ADR (`AGENTS.md` §8).
- **Contract:** `AGENTS.md` — the agent scopes, proves, restructures, and **drafts** the PR; the
  human opens and merges. No behavior change, no optimization, no public-API break without the
  SemVer/ADR path.

User arguments (may be empty): $ARGUMENTS
