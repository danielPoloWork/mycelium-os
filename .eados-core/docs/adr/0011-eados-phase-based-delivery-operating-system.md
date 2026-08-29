# ADR-0011: EADOS — phase-based agentic delivery operating system

- **Status:** Accepted
- **Date:** 2026-06-21
- **Deciders:** Owner (`@danielPoloWork`), Enterprise Project Architect
- **Related:** `docs/rfc/0001-eados-delivery-os.md` (forthcoming, the detailed design),
  ADR-0001 (three-layer genericity), ADR-0003 (generated repos self-govern), ADR-0012
  (the rename), `AGENTS.md` §3/§7

## Context

EADOS (then EAAO) is a **one-shot factory**: it interviews a maintainer, renders a governed
repository, and hands off (`AGENTS.md` §3 — "EADOS steps back"). The owner wants to extend it
across the **full delivery lifecycle** of an enterprise project — design (RFC/Design Docs),
planning (roadmap/milestones), scaffolding, audit/risk, and refactor of existing code — with
agents that reason as distinct professional figures (Product / Engineering / Delivery).

Two framings were on the table: a monolithic "360° orchestrator", or stripping roadmap/
milestone out and shipping loose, unconnected modules. A structured architectural review (12
areas: role routing, persona-vs-authority, workflow engine, ownership, Git/PR/CI, review,
release, manifest evolution, orchestration, traceability, extensibility) concluded that both
framings are wrong: the system should be **data + mechanical gates, state-driven**, reusing the
factory's existing strengths (data-driven profiles, composable role registry, manifest as single
source of truth) rather than rewriting them.

## Decision

Evolve the factory into a **phase-based delivery operating system**. Generation becomes *one*
phase of an N-phase pipeline; the data-driven core is unchanged.

1. **Phase pipeline.** `init → design (RFC) → plan (roadmap) → scaffold (generate) → audit
   (risk) → refactor (brownfield)`. Each phase is **opt-in, resumable, role-owned, and gated**.
   Roadmap/milestone stays as the `plan` phase — it is the delivery backbone, not removed.
   "Modular in invocation, integrated in data."
2. **Resident as a capability.** The generated `AGENTS.md` stays the source of truth; EADOS
   phases are commands the contract invokes. The generated repo keeps working without EADOS.
   The "two contracts, don't mix them" model is preserved.
3. **Persistent, reference-based manifest.** `project.yaml` is promoted from one-shot render
   input to an evolving delivery-state store that holds **references** (RFC ids, milestone ids,
   PR/commit refs) — not copies of content. Git stays the source of truth for content, so the
   manifest never duplicates (and drifts from) the repository.
4. **Domain/target axis.** `orchestrator/domains/{software,game,mobile}.yaml`, parallel to the
   language profiles and authored the same way (data, not code): it selects the active roles,
   artifacts (GDD vs PRD), NFR axes (e.g. RAM/GPU/framerate budgets for games), and milestone
   vocabulary (Alpha/Beta/RC vs SemVer).
5. **State-driven orchestration, deterministic routing.** The system is state-driven (the
   persistent manifest is the state; a thin deterministic checker computes legal transitions),
   not prompt-driven or event-driven. Routing is **phase-as-router** (explicit commands + an
   ownership map), never fuzzy intent classification. Agents are stateless executors; humans
   hold the terminal gates.
6. **Four machine-readable OS artifacts**, schema-first under `orchestrator/os/`: `workflow.yaml`
   (the state machine), `authority.yaml` (the ownership/authority map, generalizing CODEOWNERS),
   `git.yaml` (branch/commit/PR/release policy), and a **traceability graph + lint** (requirement
   → RFC → milestone → PR → commit → release). Each ships `_schema.md` + instance + an
   `eados_lint` gate + CI parse/validate — mirroring how language profiles already work.

## Alternatives Considered

- **Monolithic 360° orchestrator.** Rejected — risks boil-the-ocean delivery and erodes the
  data-driven genericity that makes the factory reusable.
- **Strip roadmap, ship loose modules.** Rejected — loses end-to-end delivery and the
  traceability backbone; the modules would re-implement shared state badly.
- **Manifest as a total state store.** Rejected — a god-file that duplicates Git and reintroduces
  the exact drift the factory's "one source of truth per fact" rule fights.
- **Intent-classification routing / event-driven runtime.** Rejected — non-deterministic,
  unauditable, and over-engineered for a human-gated, turn-based system.

## Consequences

- Full lifecycle with maximal reuse of the existing core; every phase is opt-in, so the factory
  keeps working unchanged throughout the rollout.
- The audit trail becomes the repository history itself (state + cross-links + ADRs + gates are
  all versioned, machine-readable artifacts) — a strong compliance story.
- The manifest schema must be **versioned** for backward compatibility; the domain axis is a new
  surface to keep complete (an `eados_lint` gate prevents fragmentation).
- The `refactor` (brownfield) phase touches *real user code*, not templates — the highest-risk
  surface (cf. ADR-0007 renderer write guards); it is sequenced **last (M5)** and sandboxed.
- The detailed design, the enterprise lens (security/trust boundary, determinism, auditability,
  failure&recovery, backward-compat, human authority), and the milestone sequencing M1–M5 live
  in **RFC-0001**; this ADR ratifies the direction. The rename that the new name implies is
  ADR-0012.

## References

- `docs/rfc/0001-eados-delivery-os.md` (forthcoming), ADR-0001, ADR-0003, ADR-0007, ADR-0012,
  `AGENTS.md` §3/§7, and the enterprise delivery-roles guide that motivated the role model.
