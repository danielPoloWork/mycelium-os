# ADR-0023: Scaffold routing surface — render advisory routes into the generated ROADMAP

## Status

Accepted (2026-07-16)

## Context

ADR-0017 made model & effort routing a first-class OS policy (`os/routing/routing.yaml`,
`tools/route_advice.py`) and M18 attached routes to the *plan phase*'s roadmap items
(negotiation-protocol, #300). But the classic **scaffold** path — the factory rendering
`templates/ROADMAP.md.tmpl` — surfaced none of it: the generated repository's planning artifact
carried no legend and no per-item route, and the generated `AGENTS.md` never referenced the
policy. The gap was found in the field (scaffold run `egl-utils-js`, 2026-07-16, #306): the
maintainer's first post-hand-off question was *"which model and effort do I use for each
milestone step?"*, and the answer had to be hand-annotated into the rendered `ROADMAP.md` —
exactly the kind of derivable annotation the factory exists to render. This violates the quality
bar's *template parity* principle extended to OS policy layers: a delivery surface the OS governs
was invisible in the artifact the maintainer plans from (field lesson; upstreamed as L-0007).

Per the L-0004 discipline we checked whether ADR-0017 had deliberately scoped routing to
per-issue delivery advice only: it had not — 18.1 explicitly began pushing routes into consumer
roadmaps via the plan phase; the template path was simply never given the same treatment. This is
a gap, not a rediscovered trade-off.

## Decision

1. **The manifest declares signals, never tiers.** A roadmap item in `spec.milestones[].items`
   (and `spec.milestone1_items`) may take an object form — `{text, signals[]}` — where `signals`
   is drawn from the `os/routing` vocabulary the policy already speaks: the labels its rules
   reference (`security`, `adr`, `severity:medium|high`, …) plus its declared asserted flags
   (`sets-pattern`, `decision-heavy`). The signal→route mapping stays in `routing.yaml` alone;
   a manifest that named tiers would duplicate the policy and rot with it.

2. **The renderer derives the route through the one existing evaluator.** `render.py` resolves
   each object item via `route_advice`'s `signals_for` + `advise` (lazy import — the same
   render↔tool cycle-break as `phase_runner`), so the only-raise resolution has exactly one
   implementation. The rendered item reads `<text> — route: <tier> / <effort> (<signals>)` — the
   plan phase's own notation (#300): tiers, never model names.

3. **Opting in renders an explicit route; staying out renders nothing new.** An object item with
   no signals still renders the explicit floor route (opting into the object form is opting into
   a visible route); a plain-string item — every legacy manifest — renders byte-identical under
   the legend's floor clause. Backward compatibility is a rendering guarantee, not a migration.

4. **The ROADMAP opens with a routing legend; the generated AGENTS.md restates the boundary.**
   Five derived placeholders — `ROUTE_TIERS`, `ROUTE_EFFORTS`, `ROUTE_FLOOR`, `ROUTE_CATALOG`,
   `ROUTE_CATALOG_AS_OF` — are computed from `routing.yaml` at render time (the dated catalog
   snapshot is the only place model names surface; its `as_of` date is the staleness cue, per
   ADR-0017). The generated `AGENTS.md` §6.1 tells the maintainer to pick the session model per
   item and restates advisory-first: the human keeps final model authority.

5. **Failure is loud at every layer.** `validate_manifest` rejects a malformed object item
   (unknown key, empty text, non-list signals) and — the new class — an **inert signal**: one
   that matches no routing rule and no declared flag, which would otherwise silently route to
   the floor (`set-pattern` for `sets-pattern` is the canonical typo). If `routing.yaml` itself
   is unreadable, legacy manifests validate and render exactly as before (no new dependency),
   while a manifest with object items fails validation naming the real cause, and the legend's
   unresolved placeholders independently abort any render that skipped validation.

## Consequences

- A repo scaffolded from a signal-bearing manifest answers "which model and effort per step?"
  on day zero; a legacy manifest re-rendered today gains only the legend.
- A catalog refresh (`as_of` + names) changes the *next* render's output — no template, policy,
  or code edit. Already-rendered repos keep their snapshot; the printed `as_of` date is the
  review cue, and the authoritative per-issue call remains `route_advice.py` where
  `.eados-core/` is vendored.
- The interview (Q5.7) gains an optional routing-signal follow-up; the questionnaire, manifest
  template, and placeholder dictionary document the object form; `reference.yaml` exercises both
  forms so render-smoke covers them.
- The signal vocabulary is derived from `routing.yaml` (rules ∪ flags), so adding a routing rule
  automatically widens what manifests may declare — no renderer change.
- `seed_milestones.py` and the generated `consistency_lint.py` are unaffected by construction:
  the route suffix follows the item text, and the legend section is neither a milestone header
  nor a checkbox line.

## References

- Issue #306 (field report, `egl-utils-js` scaffold run 2026-07-16); ADR-0017 (advisory-first,
  tiers-not-names, dated catalog); #300 (M18 18.1 — plan-phase item routes, the notation this
  ADR reuses); L-0004 (check-the-ADR-first discipline, applied in #306's triage); lessons ledger
  L-0007 (this gap, upstreamed from the field run's local L-0008).
