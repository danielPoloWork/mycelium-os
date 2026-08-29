# ADR-0001: Three-layer genericity model (profiles, manifest, templates)

- **Status:** Accepted
- **Date:** 2026-06-15
- **Deciders:** Maintainer, Enterprise Project Architect
- **Related:** `AGENTS.md` §3, `orchestrator/placeholders.md`

## Context

EADOS must reproduce the `pbr-cpp-memory-pool` enterprise system for *any* language and
toolchain. The naïve approach — fork the reference repo and hand-edit per project — does not
scale and lets the structure drift. We need a way to vary three independent dimensions
without entangling them: the **language/toolchain**, the **project's facts** (name, owner,
spec), and the **invariant enterprise structure** (governance, docs system, gates).

## Decision

We separate genericity into **three layers**, each with one responsibility:

1. **Language profiles** (`orchestrator/profiles/<lang>.yaml`) — toolchain knowledge as
   data: build tool, test framework, formatter, linter, sanitizers, CI matrix, namespace
   idiom, version-constant location, and the CI setup/extra-job YAML snippets.
2. **Project manifest** (`orchestrator/project.yaml`) — the maintainer's answers from the
   intake interview, merged with the chosen profile. One source of truth for every
   placeholder.
3. **Templates** (`templates/**`) — the reference artifacts with all project- and
   language-specific facts replaced by `{{PLACEHOLDERS}}`. Templates know only *roles*
   (build tool, test runner), never specific tools.

Rendering is a dumb Mustache-subset substitution; all intelligence lives in the manifest.
Adding a language is adding a profile, never editing a template.

## Alternatives Considered

- **Fork-and-edit per project.** Rejected — does not scale; structure drifts; no single
  place encodes "the enterprise system".
- **Templates with embedded conditionals per language** (`{{#IF_RUST}}…`). Rejected — turns
  templates into per-language spaghetti and couples the invariant structure to the language
  set. The profile layer keeps that knowledge out of the templates.
- **A code generator in one language emitting all repos.** Rejected — heavier than needed;
  the agent is the renderer, and a data+template model stays inspectable and diff-able.

## Consequences

- New languages are cheap and isolated: one `profiles/<lang>.yaml` + an ADR.
- Templates stay readable and review-able as ordinary enterprise artifacts.
- The placeholder dictionary (`orchestrator/placeholders.md`) becomes a contract between
  templates and the manifest; an undefined placeholder is a hard render error.
- A risk: profile/template parity must be maintained — a template referencing a placeholder
  no profile provides breaks generation. The quality bar (`AGENTS.md` §8) guards this.

## References

- `AGENTS.md` §3, §8; `orchestrator/generate.md`; `orchestrator/placeholders.md`.
