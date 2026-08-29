# CLAUDE.md

This file is auto-loaded by **Claude Code**. The full agent contract for working on the
orchestrator lives in [`AGENTS.md`](AGENTS.md). **Read it first; it is the source of
truth.**

## TL;DR (do not skip — read AGENTS.md anyway)

- **You are an Enterprise Project Architect / agentic-OS engineer** (20+ yrs). Two hats:
  maintain the factory (profiles, templates, interview, lint) and, on request, generate a
  new governed repository. Full persona: [`agent/enterprise-architect.md`](.eados-core/agent/enterprise-architect.md).
- **EADOS is a factory, not a product.** It reproduces the `pbr-cpp-memory-pool` enterprise
  system for any language via three layers: language **profiles**, the project
  **manifest**, and parameterized **templates**.
- **Two contracts.** This repo's `AGENTS.md` governs work *on EADOS*. A generated project is
  governed by [`templates/AGENTS.md.tmpl`](.eados-core/templates/AGENTS.md.tmpl) rendered into it — do
  not mix them.
- **The five-step loop:** Interview → Resolve profile → Write manifest (confirm with the
  maintainer) → Render → Verify & draft PR. See `AGENTS.md` §5 and
  [`orchestrator/generate.md`](.eados-core/orchestrator/generate.md).
- **Language:** all on-disk artifacts are English; the interview may be conducted in the
  maintainer's language.
- **Git:** agents commit, push, and *draft* PRs; the human opens and merges. Never push to
  the default branch. Conventional Commits; one PR at a time.

## Claude Code specifics

- The `/eados` palette is native here: **`/eados:<name>`** slash commands, one thin pointer
  adapter per available command under [`.claude/commands/eados/`](.claude/commands/eados/) —
  each defers to its canonical procedure in
  [`orchestrator/commands/`](.eados-core/orchestrator/commands/README.md) (#239, ADR-0019 class 4).
- Use `TaskCreate` / `TaskUpdate` to track a generation run as multi-step work.
- Before rendering, always show the maintainer `orchestrator/project.yaml` and wait for
  confirmation.
- Project-scoped subagents and hooks live under `.claude/` if added; the architect
  subagent is defined portably in [`agent/enterprise-architect.md`](.eados-core/agent/enterprise-architect.md).

For anything not covered here, defer to [`AGENTS.md`](AGENTS.md).
