# `authority.yaml` — schema

The **authority model**: who may draft, who may approve, who owns which artifacts — kept
**separate from persona**. A role's behavior/voice lives in [`agent/*.md`](../../../agent/README.md);
its *authority* lives here, as data. This separation is what lets a role exist **without**
authority over an artifact (a `reviewer` comments on an RFC but does not approve it; only the
`tech-lead` does), and what makes routing deterministic: the acting role for a change is a
function of the touched path via the **ownership map**, never of fuzzy intent.

This spec generalizes `.github/CODEOWNERS` from "who reviews" to "who may draft / approve /
owns", machine-readable and gate-enforced. `eados_lint` (`os-spec-completeness`) requires the
instance to define every top-level key below.

## Required structure

```yaml
version:            # integer schema version
roles:              # the org-chart as authority records (persona is elsewhere)
pending_personas:   # authority roles whose agent/<role>.md persona is intentionally not written yet
ownership_map:      # path glob -> owning role + permitted action; the routing substrate
escalation:         # the decision ladder for reviewer disagreement, ending at the human owner
```

## Item shapes (runtime-enforced, M2)

- **`roles[]`** — `{ name, pillar, phases[], may_draft[], may_approve[], owns[] }`.
  `pillar ∈ {product, engineering, delivery}` (the three collaborative pillars of the delivery
  guide); `phases` are the [`workflow`](../workflow/workflow.yaml) states the role operates in;
  `may_draft`/`may_approve`/`owns` are path globs. A role with empty `may_approve` can act but
  holds no approval authority.
- **`ownership_map[]`** — `{ glob, role, action }`, `action ∈ {draft, approve, review}`. The
  deterministic mapping from a changed path to its owning role. A change that touches a glob the
  acting role may not write is rejected by the authority gate —
  [`tools/authority_check.py`](../../../tools/authority_check.py) (the agent invokes it with its
  role + the changed paths before drafting).
- **`escalation[]`** — an ordered ladder `{ level, decider }`. The terminal decider is always
  `human-owner` — `AGENTS.md` §6: the owner is the sole decider.
- **`pending_personas`** — a list of role names whose `agent/<role>.md` persona has not been
  written yet (they arrive with the phase that needs them). The `authority-personas` lint
  (`eados_lint`) enforces the persona↔authority pairing: every role has a persona **or** is listed
  here, every persona maps to a role, and a `pending` role must not already have a persona.

## Invariants

- Every `roles[].name` referenced by `workflow.yaml` `states[].role` exists here.
- Every `ownership_map[].role` is a declared role `name`.
- The last `escalation[]` entry's `decider` is `human-owner` (the boundary is never removed).
- Every role has an `agent/<role>.md` persona **or** appears in `pending_personas`; the new roles
  `product-manager`, `tech-lead`, `producer` are pending until their persona lands in **M2**.
