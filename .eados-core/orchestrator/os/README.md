# EADOS — machine-readable OS specs

The machine-readable specs that turn EADOS's delivery governance from prose conventions into
**declarative, gate-enforced contracts**. Each spec is *data*, validated by
[`eados_lint`](../../tools/eados_lint.py) (the `os-spec-completeness` check) and elaborated in
[`docs/rfc/0001-eados-delivery-os.md`](../../docs/rfc/0001-eados-delivery-os.md).

The design principle is the same one the language profiles already follow: **knowledge is
data, not code**. Adding a workflow, a role, or a gate is editing a YAML file the lint
validates against a schema — never a special case in a tool.

| Spec | What it governs | Schema + instance |
|------|------------------|-------------------|
| **workflow** | The phase state machine: states, gated transitions, the gate registry, per-domain overlays | [`workflow/_schema.md`](workflow/_schema.md) · [`workflow/workflow.yaml`](workflow/workflow.yaml) |
| **authority** | Roles (separate from persona), the path→role ownership map, the escalation ladder | [`authority/_schema.md`](authority/_schema.md) · [`authority/authority.yaml`](authority/authority.yaml) |
| **git** | Branch/commit/PR/release policy and the PR↔RFC↔milestone cross-link requirement | [`git/_schema.md`](git/_schema.md) · [`git/git.yaml`](git/git.yaml) |
| **rfc** | The RFC review protocol: required sections, author/reviewer/approver roles, the `rfc-approved` gate | [`rfc/_schema.md`](rfc/_schema.md) · [`rfc/rfc.yaml`](rfc/rfc.yaml) (+ [`template.md`](rfc/template.md) · [`review-protocol.md`](rfc/review-protocol.md)) |
| **plan** | The roadmap-negotiation protocol: who proposes/sizes/reconciles, the T-shirt sizing scale, the `roadmap-covers-rfcs` gate | [`plan/_schema.md`](plan/_schema.md) · [`plan/plan.yaml`](plan/plan.yaml) (+ [`negotiation-protocol.md`](plan/negotiation-protocol.md)) |
| **risk** | The audit risk model: security-surface globs, size buckets, levels, the per-domain mandatory-gate threshold | [`risk/_schema.md`](risk/_schema.md) · [`risk/risk.yaml`](risk/risk.yaml) |
| **contribution** | The inbound-PR trust model: contributor tiers, the never-merge-non-owner-commits courtesy policy, the `contribution-review` gate, the escalation ladder | [`contribution/_schema.md`](contribution/_schema.md) · [`contribution/contribution.yaml`](contribution/contribution.yaml) |
| **routing** | Model & effort routing (advisory-first): work signals → capability tier + effort, the dated per-host model catalog (tiers-not-names, ADR-0017) | [`routing/_schema.md`](routing/_schema.md) · [`routing/routing.yaml`](routing/routing.yaml) |
| **interaction** | The conversation contract (instruct-verify-re-ground): confidence tags with evidence criteria, the sycophancy denylist (config-overridable), structured dissent, the pushback protocol — claims follow evidence, decisions follow the human (transformed adoption, ADR-0022) | [`interaction/_schema.md`](interaction/_schema.md) · [`interaction/interaction.yaml`](interaction/interaction.yaml) |

The **traceability graph** (requirement → RFC → milestone → PR → commit → release) and its lint
are *described* here and in the RFC but are **built in M3/M4** — derived from the cross-links the
`git` spec mandates, not stored as a separate file. The `rfc` protocol is enforced by
[`../../tools/rfc_check.py`](../../tools/rfc_check.py).

> **Status:** these are the **reference instances** that encode the design (RFC-0001). Their
> runtime wiring lands across milestones M2–M8 (see RFC §12). A reference to a role persona or
> a gate runner that does not exist yet is intentional — its milestone adds it. Each instance
> validates today: it parses and defines every key its schema declares.

## Invariants (all instances)

- **English on disk.** Every value is English (`AGENTS.md` §2).
- **Human holds the terminal gate.** Any `human_gate: true` transition and any
  `*_by: human` action is never crossed by an agent (`AGENTS.md` §6).
- **Versioned.** Every instance carries a top-level `version:` so the schema can evolve with
  backward compatibility (the persistent manifest references a spec version).

## Precedence — which layer wins

EADOS resolves knowledge from several overlapping sources: a human decision, the `os/` specs and
their gates, the project manifest, language-profile defaults, and advisory lessons. They rarely
conflict *by construction* — a spec constrains what a manifest may say, a profile only fills gaps a
manifest left, a lesson only advises — but when two disagree, this is the **canonical total order**,
highest wins:

1. **A human decision.** Any `human_gate: true` transition or `*_by: human` action; the escalation
   ladder terminates at `human-owner` ([`authority`](authority/authority.yaml), `AGENTS.md` §6). Never
   overridden by anything below.
2. **A blocking gate / spec.** The `os/` specs are the governance contracts; a `blocking: true` gate
   ([`workflow`](workflow/workflow.yaml)) validates or rejects everything under it. A spec is never
   relaxed by a lower layer — it is the ceiling the manifest must fit inside.
3. **The project manifest** (`orchestrator/project.yaml`) — the maintainer's committed answers, the
   single source of truth for every placeholder, *within* what the specs allow.
4. **A profile default** (`profiles/<lang>.yaml`) — applied only where the manifest is silent; an
   explicit manifest value always wins over a profile default.
5. **An advisory lesson** ([`learning/lessons.yaml`](../../learning/README.md)) — guidance applied
   when nothing above decides. A lesson never overrides a gate or the human terminal gate; the lint
   checks its *shape*, not obedience.

**Domain overlays only add, never relax.** `domain_overlays` ([`workflow`](workflow/workflow.yaml))
may insert states and add gates for a target domain; they never remove or loosen a base gate. The
base machine is the floor — an overlay raises the bar for its domain, it never lowers it
(`phase_runner.apply_overlay` only appends). So a domain never becomes *less* governed than the base.

This order is the tie-breaker, not a routing table: it exists to make the rare disagreement
unambiguous, so no layer silently wins by accident.
