# `plan.yaml` — schema

The **roadmap-negotiation protocol** as data: who proposes, who sizes, who reconciles, the
estimation scale, and what feeds and falls out of the `plan` phase. The roadmap is a *collaborative
artifact* (delivery-roles guide §3): Product proposes priorities, Engineering sizes, Delivery
reconciles against capacity. The `/eados plan` command reads this; the human-readable protocol is
[`negotiation-protocol.md`](negotiation-protocol.md); the output is gated by
[`../../../tools/traceability.py`](../../../tools/traceability.py) (`roadmap-covers-rfcs`).

`eados_lint` (`os-spec-completeness`) requires the instance to define every top-level key below.

## Required structure

```yaml
version:        # integer schema version
roles:          # the negotiation participants — { proposes, sizes, reconciles } (authority roles)
sizing_scale:   # the macroscopic ("T-shirt") estimate vocabulary engineering uses
inputs:         # what feeds the negotiation (the approved RFCs from the design phase)
output:         # the artifact produced (the single-source roadmap)
gate:           # the workflow gate the plan phase satisfies
```

## Item shapes

- **`roles`** — `{ proposes, sizes, reconciles }`, each an authority role id:
  `product-manager` proposes the wishlist + business priorities; `tech-lead` gives the T-shirt
  sizing and flags tech debt; `producer` reconciles estimates × capacity × dates into milestones.
- **`sizing_scale`** — an ordered list of macroscopic sizes (e.g. `[XS, S, M, L, XL]`), **not**
  story points — the negotiation is about scope and capacity, not precision.
- **`inputs`** — the artifact kinds that feed planning (the approved RFCs, `refs.rfcs`).
- **`output`** — the roadmap file (`ROADMAP.md`).
- **`gate`** — the workflow gate id the phase output must clear (`roadmap-covers-rfcs`).

## Invariants

- Every `roles` value and `gate` is declared (in [`../authority/authority.yaml`](../authority/authority.yaml)
  and [`../workflow/workflow.yaml`](../workflow/workflow.yaml) respectively).
- The negotiation is **anchored to artifacts** — each step produces or edits a concrete document
  (the wishlist, the sizing, the roadmap diff). No outcome rests on prose alone (no "theatre").
