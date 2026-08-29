# ADR-0015: Web domain (shipped) and the enterprise posture (a flag, not a domain)

## Status

Accepted (2026-07-01)

## Context

The intake interview classifies a project on two axes: the **kind** (`library / service / cli / app`,
Q0.2) and the **development target / domain** (`software / game / mobile`, Q0.4), where the domain
loads a `domains/<domain>.yaml` profile that shapes the active roles, artifacts, hard NFR budgets,
milestone vocabulary, and workflow overlay.

The 2026-06-30 interview-completeness audit (issue #149) found the domain axis too coarse for two of
the most common modern situations:

1. **Web** — a website / web app / web service has no first-class target. It collapses into
   `software → app/service`, which carries none of the web-specific NFR axes (accessibility, Core Web
   Vitals), the UX/content cross-discipline pipeline, or a web workflow overlay. `language-fit.md`
   already treats *web frontend*, *web backend*, and *enterprise LOB* as distinct concerns, but the
   domain axis did not, so that knowledge never shaped a generated repo. For the single most common
   modern project type, "author it yourself from `_template.yaml`" is the wrong default — it should
   be a shipped seed.
2. **Enterprise** — the audit asked whether "enterprise" should be its own target. It names a
   *governance/compliance posture* (a raised bar: mandatory ADRs for security-relevant decisions,
   stricter review, a compliance-docs expectation) that is **orthogonal to what you are building** —
   an enterprise web app and an enterprise back-office service are both "enterprise" yet different
   domains. Modelling it as a fourth domain would force a combinatorial `enterprise-web`,
   `enterprise-software`, … explosion and conflates two independent axes.

A hard constraint shaped the enterprise decision: `eados_lint`'s cross-spec gate requires every key
under `workflow.yaml`'s `domain_overlays` to be a **domain id**. So "enterprise" *cannot* be a
workflow overlay without also being a domain — the overlay mechanism is reserved for domains by
design.

## Decision

1. **Ship `domains/web.yaml`** as a first-class domain (website / web app / web service):
   - the baseline authority roles (a domain activates a subset; it does not invent roles), with the
     web vocabulary carried by `role_labels` (`product-owner`, `web-architect`, `full-stack-lead`);
   - web-appropriate NFR axes — **accessibility** and **Core Web Vitals** as *hard* budgets (a
     legal/measurable bar), plus security and latency;
   - `cross_discipline_deps: [design, content]` (the UX/UI + content pipeline);
   - a **`web` workflow overlay** adding `accessibility-review` + `web-vitals-budget` gates.
   `web` is added to Q0.4's choice set in `interview.md` and `questionnaire.yaml`.

2. **Model `enterprise` as an orthogonal posture flag, not a domain.** A new
   `governance.posture: standard | enterprise` manifest field (default `standard`), surfaced by a new
   **Q0.5** in the interview, raises the governance/compliance bar on *any* domain. It is
   **advisory** — it instructs the agent (per `AGENTS.md`) to hold the project to the raised bar
   (mandatory ADRs for security-relevant decisions, stricter review, an explicit compliance-docs
   expectation) — consistent with EADOS's "agent advises, human decides" model. It is deliberately
   *not* a domain and *not* a `domain_overlays` key (which the cross-spec gate reserves for domains).

## Consequences

- A web project generated end-to-end differs meaningfully from the bare `software` baseline: distinct
  roles-vocabulary, hard accessibility/Core-Web-Vitals budgets, a UX/content discipline, and two
  extra web gates.
- The enterprise posture composes cleanly with every domain (`web` + `enterprise`, `software` +
  `enterprise`, …) with no combinatorial profile growth.
- The posture starts advisory. Should hard enforcement ever be wanted (e.g. a mandatory
  security-auditor gate whenever `posture == enterprise`), it can be added later as a
  `risk.yaml`/`workflow.yaml` rule keyed on the flag — the field is the seam that makes that a
  data change, not a redesign. This deferral is intentional, keeping the change focused.
- Precedent: before flagging "enterprise should be a domain" on a future audit, recall that this ADR
  decided it is a posture — a raised bar orthogonal to the target — and why (the overlay-key-is-a-
  domain constraint + axis-orthogonality).
