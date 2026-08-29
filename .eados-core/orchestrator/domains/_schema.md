# `domains/<domain>.yaml` — schema

The **domain / target axis**: a second dimension of genericity, *parallel to* the language
profiles and authored the same way — **knowledge as data, not code**. Where a language profile
answers "what toolchain?", a domain profile answers "what kind of thing are we building?"
(software · web · game · mobile · …) and adapts the delivery pipeline accordingly: which roles are
active, which artifacts it uses (GDD vs PRD), which NFR axes are hard budgets, the milestone
vocabulary, the non-engineering (asset-pipeline) dependencies, and which `workflow.yaml`
overlay applies. Designed in [RFC-0001](../../docs/rfc/0001-eados-delivery-os.md) §3–4.

`eados_lint` (`domain-completeness`) requires every `domains/<domain>.yaml` to define every
top-level key below. Underscore-prefixed files (`_template.yaml`) are scaffolds, not domains, and
are not checked — exactly like the language-profile convention.

## Required structure

```yaml
domain:                # id (software | web | game | mobile | …); matches the filename stem
display_name:          # human-readable name
roles:                 # canonical authority.yaml role ids active in this domain
role_labels:           # domain vocabulary: canonical role id -> domain-specific label
artifacts:             # design artifacts: product_spec (PRD/GDD), design_doc, test_strategy
nfr_axes:              # the NFR axes that matter, each {axis, hard_budget}
milestone_vocabulary:  # semver | alpha-beta-rc — the milestone naming scheme
cross_discipline_deps: # non-engineering dependencies (asset pipeline, localization, …) or []
workflow_overlay:      # the workflow.yaml `domain_overlays` key this domain maps to
```

## Item shapes (runtime-enforced as the axis is wired in, M1-C / M2)

- **`roles`** — a list of canonical role ids defined in
  [`../os/authority/authority.yaml`](../os/authority/authority.yaml). A domain activates a
  subset; it does not invent roles.
- **`role_labels`** — `canonical-role → label` (e.g. `product-manager → game-designer`). Captures
  the domain's vocabulary without changing role shape; whether a label becomes its own role is
  **OQ4**, resolved in M2.
- **`artifacts`** — `{ product_spec, design_doc, test_strategy }`. `product_spec` is `PRD` for
  software/mobile, `GDD` for a game.
- **`nfr_axes[]`** — `{ axis, hard_budget, unit?, direction?, seed?, scale?, metrics? }`.
  `hard_budget: true` marks a *fixed* constraint (a game's RAM/GPU/framerate, a mobile app's
  size) the spec must treat as non-negotiable — and a hard axis is **typed** (#249): `unit`
  (fps, MB, s, …) + `direction` (`min` | `max`) make the budget checkable; `seed` is the
  suggested target Q5.3 offers (data, never a comment). A level axis (web accessibility)
  declares a `scale` (`"A|AA|AAA"`) its target is drawn from; a composite axis (Core Web
  Vitals) declares `metrics` (`"LCP|INP|CLS"`) — one `spec.nfr_budgets` entry per metric. The
  recorded budgets are enforced by the `nfr-budgets` audit-overlay gate (workflow.yaml,
  evaluated in-process by `eados.py`): a hard axis with no recorded number — or a recorded
  measurement that violates it — FAILs. A soft axis (`hard_budget: false`) stays untyped.
- **`milestone_vocabulary`** — `semver` (version-driven, pre-1.0 milestone-driven) or
  `alpha-beta-rc` (Alpha / Beta / Release Candidate / Gold, as in game production).
- **`cross_discipline_deps`** — the non-engineering pipeline a feature depends on (a game's
  `[art, animation, sound]`); `[]` for engineering-only domains.
- **`workflow_overlay`** — the key under `workflow.yaml` `domain_overlays` (e.g. `game` inserts
  `asset-pipeline-review` + a `hardware-budget` gate; `mobile` adds `store-compliance`).

## Invariants

- Every `roles[]` entry and every `role_labels` key is a canonical role id in `authority.yaml`.
- `workflow_overlay` is a key present in `workflow.yaml` `domain_overlays`.
- `domain` matches the filename stem (`game.yaml` → `domain: game`).
