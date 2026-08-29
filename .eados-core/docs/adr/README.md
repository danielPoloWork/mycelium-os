# Architecture Decision Records — EADOS

Decisions governing the orchestrator's own design (not the projects it generates — those
get their own `docs/adr/` from the templates). Lightweight Michael Nygard format; numbering
is sequential and never reused. Template: the generated
[`templates/docs/adr/template.md`](../../templates/docs/adr/template.md).

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-templating-and-genericity-model.md) | Three-layer genericity model (profiles, manifest, templates) | Accepted |
| [0002](0002-interview-driven-intake.md) | Interview-driven intake before generation | Accepted |
| [0003](0003-generated-repos-are-self-governing.md) | Generated repositories are self-governing | Accepted |
| [0004](0004-seed-language-profiles.md) | Seed profiles for C, C#, VB.NET, JS, PHP, Lua (SQL/CSS/HTML stay secondary) | Accepted |
| [0005](0005-seed-modern-and-legacy-profiles.md) | Seed Scala/Kotlin/Swift/Dart/Ruby + legacy COBOL/Pascal (QBasic deferred) | Accepted |
| [0006](0006-manifest-loader-and-emitted-yaml-validation.md) | Spec-correct manifest loader + real-parser gate for emitted YAML | Accepted |
| [0008](0008-loader-scalar-fidelity-and-differential-gate.md) | Loader scalar fidelity (quote escaping, chomping) + PyYAML differential gate | Accepted |
| [0009](0009-ci-supply-chain-pinning.md) | CI supply-chain pinning (SHA-pin EADOS-authored workflows, kill @latest, pin+hash PyYAML) | Accepted |
| [0007](0007-renderer-write-guards-and-validation-independence.md) | Renderer write-containment, required-field validation, independent CI-YAML gate | Accepted |
| [0010](0010-content-hash-i18n-freshness.md) | Content-hash i18n freshness (squash-merge-proof) | Accepted |
| [0011](0011-eados-phase-based-delivery-operating-system.md) | EADOS — phase-based agentic delivery operating system (the pivot) | Accepted |
| [0012](0012-project-rename-to-eados.md) | Rename EAAO → EADOS: repo, path, and bundle migration | Accepted |
| [0013](0013-dependabot-action-pin-auto-remediation.md) | Dependabot action-pin auto-remediation (`workflow_run` template re-sync) | Accepted |
| [0014](0014-inbound-contribution-trust-model.md) | Inbound-contribution trust model (verify the change, never merge non-owner commits, adopt via co-author) | Accepted |
| [0015](0015-web-domain-and-enterprise-posture.md) | Web domain (shipped) + enterprise as an orthogonal posture flag, not a domain | Accepted |
| [0016](0016-authoring-language-model.md) | Authoring-language model: confirmed doc/comment-language defaults, non-English choices as recorded exceptions | Accepted |
| [0017](0017-model-effort-routing.md) | Model & effort routing: advisory-first, capability tiers not model names, dated per-host catalog | Accepted |
| [0018](0018-ops-delivery-perimeter.md) | Ops & deployment perimeter: ops documents in scope, live infrastructure a recorded non-goal, `deploy` phase deferred | Accepted |
| [0019](0019-command-surface-taxonomy.md) | Command-surface taxonomy: phases closed, design/audit sub-modes, bounded cross-cutting class, adapters+aliases; manifest required | Accepted |
| [0020](0020-rename-refactor-phase-to-migrate.md) | Rename the brownfield phase `refactor` → `migrate` (naming honesty; frees `refactor` for the code-quality command); `phase: refactor` a deprecated alias for one minor | Accepted |
| [0021](0021-brownfield-adoption-route.md) | Brownfield adoption route: `/eados adopt` as init's sibling intake; `adoption:` manifest block; `init → audit`/`init → migrate` legal by data, gated on in-process `adoption-recorded` | Accepted |
| [0022](0022-interaction-policy-as-data.md) | Interaction policy as data (`os/interaction/`, ninth spec): confidence tags with evidence criteria, sycophancy denylist as config-overridable data, structured dissent, pushback splits claims-vs-decisions; enforcement ceiling instruct/verify/re-ground | Accepted |
| [0023](0023-scaffold-routing-surface.md) | Scaffold routing surface: manifest items declare signals (never tiers), the renderer derives each item's advisory route through `route_advice`, the ROADMAP opens with a dated-catalog legend; plain-string items render unchanged | Accepted |
| [0024](0024-provider-agnostic-capability-routing.md) | Provider-agnostic capability routing (extends 0017): two-level provider/host catalog, resolution by capability not name, cost may only choose above the earned floor and never lower it, host identity from evidence with a loud unknown (never model self-report), `extra` effort level, enforceable catalog freshness | Accepted |
| [0025](0025-phase-state-writer.md) | The phase state writer: a workflow state declares who RECORDS its outcome (`delivery_state` + the run record) as distinct from who AUTHORS its artifact; held honest by the `state-writer-authority` gate | Accepted |
