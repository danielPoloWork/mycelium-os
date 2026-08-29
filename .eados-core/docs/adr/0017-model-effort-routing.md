# ADR-0017: Model & effort routing — advisory-first, tiers-not-names

## Status

Accepted (2026-07-09)

**Extended by [ADR-0024](0024-provider-agnostic-capability-routing.md) (2026-07-26)** —
provider-agnostic capability routing. Everything below remains in force; ADR-0024 adds what this
record is silent on (host identification, multi-provider catalogs, cost as a resolution input) and
replaces the flat per-host `tier → model name` catalog with a two-level provider/host catalog
resolved by capability. Read them together.

## Context

EADOS had no notion of *which class of model* or *how much effort* a unit of work deserves: the
maintainer routed by hand (the M15 issue set was assessed manually on 2026-07-09, issue by issue).
Two facts constrain any mechanization:

1. **Model names churn every few months.** A policy that says "use Fable 5" rots the day the
   catalog moves on — exactly the trap ADR-0009 avoids for action pins and the risk model avoids
   by keeping weights as data (#79).
2. **No host lets an agent switch its own top-level session model.** That is a human action (e.g.
   `/model`). The only place "automatic" selection is real is *delegated* work, where a host may
   support per-delegation model choice (e.g. an agent-spawn `model` parameter).

## Decision

1. **Advisory-first.** The OS *recommends* a route and states it at its read-points (Step-0
   triage, `/eados status`, the `.issues/` planning docs — wired in 16.3/#254). The human keeps
   final model authority; advice never overrides an explicit human choice, and nothing in the
   policy can express a top-level session model switch. Auto-application exists only for
   host-delegated subagent work (16.4/#255) and falls back to advisory-only elsewhere.

2. **Tiers, not model names.** The policy ([`os/routing/routing.yaml`](../../orchestrator/os/routing/routing.yaml))
   speaks capability tiers — `fast` / `standard` / `frontier-reasoning` — and concrete names live
   *only* in its dated `catalog:` (today, Claude Code: Sonnet 5 / Opus 4.8 / Fable 5). Model churn
   is a catalog edit with a refreshed `as_of:`; the rules and the tools never change for it.

3. **OS-neutral effort vocabulary** — `low` | `medium` | `high` | `max` — with per-host
   `effort_aliases` in the catalog (Claude Code: "ultracode" → `max`). Advice is emitted in the OS
   vocabulary; adapters translate at the edge.

4. **Resolution is monotonic escalation.** The recommendation starts at the cheapest floor
   (`defaults`) and every matched rule raises it to at least its `min_tier` / `min_effort` — the
   final answer is the max over floor and matches. Rules never lower a result, the same
   only-add-never-relax principle as the workflow's domain overlays; resolution is deterministic
   and order-independent (no model/LLM in the routing loop). Signals are what the tracker already
   carries (`severity:*`, `adr`, `security`, …) plus two asserted flags: `sets-pattern` and
   `decision-heavy`.

5. **The judgment call ships as few-shot data.** The tier decision carries a worked-example
   `examples:` block (verdicts = the tiers), registered under the `examples` gate — the M14 #224
   pattern, seeded from the maintainer-reviewed M15 assessment.

## Consequences

- `orchestrator/os/routing/` is the eighth OS spec: auto-discovered by `os-spec-completeness`,
  parse-checked by `data-file-validity`, covered by the existing `os/**` gate-coverage entry;
  the `examples` gate shape-checks its decision surface. Referential integrity (rules reference
  declared tiers/efforts/flags; every host maps every tier) is documented as invariants and
  enforced by the 16.2 evaluator's loud rejection.
- `tools/route_advice.py` (16.2/#253) can be a pure function over this file — fixture-testable
  offline, identical advice at every surface.
- Recommending a *cheaper* route stays possible without a "lowering" rule: the floor is the
  cheapest tier, so unlabeled small work (doc fixes, authoring) routes to `fast`/`low` by default.
- A future host (or a re-ranked market) is one catalog entry, not a schema change; a future tier
  (e.g. a local model class) is an append to `tiers` plus rules that reference it.
- **Application (16.4/#255) is downward only.** The advice is *applied* — not just printed — in
  exactly one place: when a governed command **delegates** a sub-task to a host with per-delegation
  model control, the adapter passes the resolved model + effort with the delegation. The contract,
  the per-host application matrix, and the worked architect → engineer → reviewer → optimizer relay
  live in [`os/routing/delegation.md`](../../orchestrator/os/routing/delegation.md); a host without
  per-delegation control degrades to advisory-only. The top-level session model is never switched
  by the agent — that boundary (invariant #1) is unchanged.

## References

- Issue #252 (M16 16.1); milestone plan `.issues/M16-model-effort-routing-milestone.md` (#256);
  RFC-0001 (human-in-the-loop); ADR-0009 (pin-rot precedent); risk-weights-as-data (#79);
  worked-example decision surfaces (#224, M14); README model ranking (#122).
