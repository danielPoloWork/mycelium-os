---
description: EADOS optimize — measure-first performance optimization against a numeric NFR budget (baseline → one change → re-measure; cross-cutting, any phase; roles: tech-lead + reviewer)
---

Run the governed EADOS command **`/eados optimize`**.

This adapter is a thin pointer (ADR-0019 class 4: an adapter surfaces a command, never adds
behavior). The canonical procedure is the single source of truth — read it and follow it exactly;
do not improvise or reproduce it from memory.

- **Procedure:** `.eados-core/orchestrator/commands/optimize.md`
- **Class:** cross-cutting (ADR-0019 class 3) — advisory and non-state-advancing; it never writes
  `delivery_state.phase` and never proposes a transition. **Manifest required** (ADR-0019
  boundary): pasted/standalone code is refused and routed to `/eados init` / `/eados adopt`.
- **Acting roles:** `tech-lead` authors the change + the benchmark record
  (`.eados-core/orchestrator/os/authority/authority.yaml`; owns `src/**`, drafts
  `docs/benchmarks/**`); the `reviewer` judges the readability/complexity cost of the speed-up.
- **Guarantee:** **measure-first** — a **numeric** NFR target (spec §3 / the domain's hard
  `nfr_axes`; "make it faster" with no number is refused), a benchmark baseline recorded to the
  `docs/benchmarks/` discipline, one profiled change, and a re-measure accepted only if it moves
  toward budget with the suite green.
- **Contract:** `AGENTS.md` — the agent targets, measures, changes, re-measures, and **drafts**
  the PR; the human opens and merges. No optimization without a number; no accepted change without
  a before/after measurement.

User arguments (may be empty): $ARGUMENTS
