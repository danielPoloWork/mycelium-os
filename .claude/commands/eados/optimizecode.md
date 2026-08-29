---
description: EADOS optimizecode — alias of /eados optimize (measure-first performance work against a numeric NFR budget). Routes to the optimize command.
---

Run the governed EADOS command **`/eados optimize`** — the maintainer's `optimizecode` wishlist
verb is an **alias** that routes to it (ADR-0019 class 4: an alias routes, it never adds behavior;
this is the second alias adapter after `/eados:security`, #244).

The canonical procedure is the single source of truth — read it and follow it exactly; do not
improvise or reproduce it from memory.

- **Procedure:** `.eados-core/orchestrator/commands/optimize.md` (the `/eados optimize` command)
- **Acting roles:** `tech-lead` authors the change + the benchmark record; the `reviewer` judges
  the readability/complexity cost.
- **Guarantee:** measure-first — a numeric NFR target, a recorded baseline, one profiled change,
  and a re-measure toward budget with the suite green.
- **Contract:** `AGENTS.md` — the agent drafts; the human opens and merges.

User arguments (may be empty): $ARGUMENTS
