# ADR-0021: Brownfield adoption route — `/eados adopt` as init's sibling intake

## Status

Accepted (2026-07-11)

## Context

The pieces for brownfield exist but the guided entry is missing. The installers already install
into an **existing** repository additively (`--mode existing` is the default); the `migrate` phase
(renamed from `refactor` by ADR-0020) maps gaps read-only and migrates via sandboxed PRs — but it
is formally reachable only through `audit`; `/eados init` frames a **new** project. Nothing greets
a maintainer who just installed EADOS into an existing codebase and asks what they want from it
(maintainer requirement, 2026-07-09: choose via interview whether to generate documentation,
reconstruct the design, run an audit, migrate, or fix bugs). Meanwhile ADR-0019 committed the
Wave-2 code commands to *refuse and route* an ungoverned repository to `/eados adopt` (#247) —
a route that did not yet exist.

The design question this ADR settles: **how does an adopted repository enter the phase machine
without minting a new phase** (ADR-0019 §1 keeps the state set closed) and without special-casing
adoption in any tool (the anti-fragmentation invariant: knowledge as data, applied by gates)?

## Decision

1. **`adopt` is an intake command, not a phase.** `commands/adopt.md` is `init`'s brownfield
   sibling (both owned by the `enterprise-architect`; ADR-0019 §1 already framed `interview` as
   the intake of `init` and of the then-planned brownfield front door `/eados adopt` — this ADR
   delivers that front door). It writes the same manifest with `delivery_state.phase: init`; the
   state set is unchanged.
2. **The adoption record is manifest data.** A new optional top-level `adoption:` section carries
   `goals` (non-empty, from the closed vocabulary `governance-docs | retro-design | audit |
   migrate | bugfix`), `gap_map_ref` (where the read-only `brownfield.py` report was captured),
   and its own `provenance` sub-block (`asked`/`defaulted`/`imported` per key — `imported` is the
   natural value for facts read off the existing repo). `render.validate_manifest` validates the
   block's shape; `adoption` joins `PROVENANCE_EXEMPT` because its provenance lives inside the
   block itself, like `delivery_state`'s state lives inside it.
3. **The route is legal by data.** `workflow.yaml` gains two transitions — `init → audit` and
   `init → migrate` — both `human_gate: true` (they change committed direction) and both gated on
   `entry_gates: [manifest-valid, adoption-recorded]`: one validity bar for every route out of
   `init`, plus the adoption record itself. No tool special-cases adoption; `phase_runner` and the
   checkpoint-chain validator honor the new edges exactly as they honor every other declared edge.
4. **`adoption-recorded` is wired in-process.** The gate is evaluated by `eados.py`
   (`GATE_EVALUATORS`), not marked `manual`: absent block → `skipped` (a greenfield project is
   genuinely not applicable — `eados.py init` stays green for every existing project), malformed
   block → `FAIL`, valid block → `OK`. An `external`/`manual` wiring was rejected because
   `manual` always satisfies the checkpoint validator — the gate would be decorative, re-opening
   the honor-system gap #199/#213 closed.
5. **Goals map to existing machinery; the earliest phase wins.**
   `retro-design → design` (the existing edge; reconstruct the RFC from the code as-is);
   `audit → audit`; `migrate → migrate`; `governance-docs → migrate` (rendering the missing
   documentation system *is* additive migration — the gap map orders it);
   `bugfix → /eados debug` (cross-cutting — the adopted manifest satisfies its ADR-0019
   precondition; no transition involved). With multiple goals, adopt proposes the **earliest**
   target in pipeline order (`design < audit < migrate`) — every later goal stays reachable from
   there through the normal machine, so no goal ever needs a second special route.

## Consequences

- A brownfield repository reaches `audit` or `migrate` in one human-confirmed move instead of
  being forced through `design → plan → scaffold` ceremony it may not want; the greenfield
  pipeline is untouched (both new edges are invisible without an `adoption:` block — the gate
  reads `skipped`).
- Domain-overlay gates whose `required_for` includes `audit` (web's `accessibility-review` /
  `web-vitals-budget`, game's `hardware-budget`, mobile's `store-compliance`) attach to
  `init → audit` automatically via `apply_overlay` — **intended**: an adopted web repository
  entering audit meets the same domain bar as a generated one.
- The deprecated `refactor` alias (ADR-0020) canonicalizes checkpoint targets, so a legacy
  `{from: init, to: refactor}` checkpoint becomes legal alongside `init → migrate`; the existing
  deprecation warning fires on it — acceptable for the alias's remaining one-minor lifetime.
- `manifest-valid` on the adoption edges means adopt's interview must fill the framing scalars
  (identity, ownership, language basics) — mostly `imported` from the repository itself; a
  half-framed manifest is NOT a legal adoption, by design.
- Alternatives rejected: **(a) a new `adopt` state** — breaks ADR-0019 §1's closed state set and
  adds a phase that produces nothing; **(b) entering only via `audit`** — forces an audit on a
  maintainer who asked for documentation or a design reconstruction; **(c) special-casing
  adoption in `phase_runner`/`eados.py`** — violates the anti-fragmentation invariant (routing
  must be data the lints can check); **(d) an `external`/`manual` gate** — decorative (see
  Decision 4).

## References

- Issue [#247](https://github.com/danielPoloWork/pgs-eados/issues/247) (draft
  `.issues/0015-eados-adopt-brownfield-adoption-interview.md`) — the maintainer requirement and
  acceptance.
- ADR-0019 (command-surface taxonomy: the closed phase set; `adopt` as intake; the Wave-2
  refuse-and-route contract), ADR-0020 (the `migrate` rename this route targets), ADR-0007
  (additive install posture the adoption inherits).
- RFC-0001 §3 (the phase machine), §5 (gates as data).
