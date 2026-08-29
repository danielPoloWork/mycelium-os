# Roadmap-negotiation protocol

How the `plan` phase turns approved RFCs into a **negotiated** milestone roadmap. The roadmap is a
collaborative artifact (delivery-roles guide §3) — it fails when Product imposes dates without
Engineering's estimates, or Engineering ignores market windows. Machine-readable config:
[`plan.yaml`](plan.yaml); the output gate is
[`../../../tools/traceability.py`](../../../tools/traceability.py) (`roadmap-covers-rfcs`).

## Participants (authority is data — `../authority/authority.yaml`)

| Step | Role | Contributes | Artifact |
|------|------|-------------|----------|
| **Propose** | `product-manager` | the wishlist + business priorities ("Multiplayer by Christmas") | the prioritized RFC/feature list |
| **Size & route** | `tech-lead` | macroscopic **T-shirt** sizing (`XS…XL`), a **model/effort route** (tier + effort), + the tech debt to pay | sizing + route notes on each item |
| **Reconcile** | `producer` | estimates × capacity × dates → milestones (Alpha/Beta/RC or SemVer) | the **roadmap diff** |

## The flow

1. **Propose** — the `product-manager` brings the wishlist and business priorities, ranked. Each
   item references an approved RFC (`refs.rfcs`) — no roadmap item without a design behind it.
2. **Size & route** — the `tech-lead` attaches a T-shirt size (`plan.yaml` `sizing_scale`) to each
   item, flags tech debt that must be paid first, and attaches a **model/effort route**: a
   capability tier (`fast` / `standard` / `frontier-reasoning`) + an effort (`low`–`max`) from the
   [`os/routing`](../routing/_schema.md) policy (ADR-0017), resolved with
   [`route_advice.py`](../../../tools/route_advice.py) where the item's signals are already known
   and a tech-lead judgment otherwise — a roadmap item carries no tracker labels yet, so the route
   is asserted from severity + the derived flags now and firms up when the item is filed as an
   issue (the M11 seeding flow). **Tiers, not model names**: concrete names live only in the dated
   `catalog:` and would rot in a roadmap. Advisory — it recommends the model; the human keeps final
   model authority.
3. **Reconcile** — the `producer` crosses estimates with real capacity (people, leave, budget) and
   the market window, cuts or defers scope **with** product + engineering, and writes the roadmap:
   milestones (per the domain's `milestone_vocabulary`) with pre-numbered items.
4. **Gate** — `roadmap-covers-rfcs` (`traceability.py`) verifies **every RFC is addressed by ≥1
   milestone**; only then is `plan → scaffold` legal (human-gated).
5. **Hand off** — to [`/eados scaffold`](../../generate.md) (today's factory) once the roadmap is
   agreed.

## Anti-theatre

Every step **produces or edits a concrete artifact** — the prioritized list, the sizing notes, the
roadmap diff. A negotiation outcome never rests on prose alone; a disagreement follows the
authority `escalation` ladder, ending at the human owner (`AGENTS.md` §6). The agent drafts and
proposes; the human decides scope and confirms the phase move.
