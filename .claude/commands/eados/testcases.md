---
description: EADOS testcases — governed unit/integration test generation against spec §6 (QA-owned; a green suite or an xfail with a linked defect; cross-cutting, any phase; role: qa-engineer)
---

Run the governed EADOS command **`/eados testcases`**.

This adapter is a thin pointer (ADR-0019 class 4: an adapter surfaces a command, never adds
behavior). The canonical procedure is the single source of truth — read it and follow it exactly;
do not improvise or reproduce it from memory.

- **Procedure:** `.eados-core/orchestrator/commands/testcases.md`
- **Class:** cross-cutting (ADR-0019 class 3) — advisory and non-state-advancing; it never writes
  `delivery_state.phase` and never proposes a transition. **Manifest required** (ADR-0019
  boundary): pasted/standalone code is refused and routed to `/eados init` / `/eados adopt`.
- **Acting role:** `qa-engineer` (`.eados-core/orchestrator/os/authority/authority.yaml`; owns
  `src/test/**`) — the first code command owned by QA rather than the tech-lead; the `reviewer`
  enforces the coverage bar the new tests move.
- **Guarantee:** tests **prove a requirement** — generated against the spec's §6 verification
  strategy using the project profile's test toolchain, landing under `src/test/**`, and either
  running **green** or marked **`xfail`** with a defect handed to `/eados debug` (a genuine failure
  is never enshrined as an expected pass).
- **Contract:** `AGENTS.md` — the agent intakes, generates, verifies, and **drafts** the PR; the
  human opens and merges. No test generation without a testable target; the code under test is
  never fixed here.

User arguments (may be empty): $ARGUMENTS
