# Domain / target profiles

The **second axis of genericity**, parallel to the [language profiles](../profiles/_schema.md).
A language profile says *what toolchain*; a **domain profile** says *what kind of thing we are
building* (software · web · game · mobile · …) and adapts the delivery pipeline to it — as **data**.
Designed in [RFC-0001](../../docs/rfc/0001-eados-delivery-os.md) §3–4; introduced in roadmap M1.

| Domain | What changes |
|--------|--------------|
| [`software`](software.yaml) | Baseline: engineering-only, SemVer, no hard hardware budgets. |
| [`web`](web.yaml) | Website / web app / web service; **hard** accessibility + Core Web Vitals budgets; UX-design + content dependencies; an accessibility-review + web-vitals-budget overlay. |
| [`game`](game.yaml) | GDD instead of PRD; Alpha/Beta/RC; **hard** RAM/GPU/framerate budgets; the Art/Animation/Sound asset pipeline; Producer as roadmap guardian. |
| [`mobile`](mobile.yaml) | Hard app-size/cold-start budgets; a store-compliance gate; UX-design + localization dependencies. |

## Adding a domain

Copy [`_template.yaml`](_template.yaml) to `<domain>.yaml` and fill every key (schema:
[`_schema.md`](_schema.md)). The `domain-completeness` gate in
[`eados_lint`](../../tools/eados_lint.py) validates it. **Never** add a domain by special-casing
a tool — it is always data validated against the schema (anti-fragmentation, RFC §12).

> The shipped four are **seeds**, not the allowed set — there is no "unsupported domain", only
> "not yet profiled", exactly as with languages.

## How it is used (as the axis is wired in)

- **M1-C** — the interview's `Q0.4 — development target` loads the chosen domain profile; the
  manifest records `domain`.
- **M2+** — the active `roles` (relabelled via `role_labels`), the `artifacts` (PRD/GDD), the
  `nfr_axes` (hard budgets), the `milestone_vocabulary`, and the `workflow_overlay` adapt the
  `design` / `plan` / `scaffold` phases per domain.
