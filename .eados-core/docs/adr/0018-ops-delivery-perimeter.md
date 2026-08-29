# ADR-0018: Ops & deployment perimeter — documents in scope, live infrastructure a non-goal

## Status

Accepted (2026-07-10)

## Context

EADOS governs a repository up to CI/CD: it renders pinned workflows (ADR-0009), release
pipelines, and the delivery machinery around them — but **deployment architecture,
container/orchestration setup, monitoring/logging strategy, and IaC were never decided**: neither
a phase, nor a design fold, nor a recorded non-goal. The 2026-07-09 prompt-pack review (issue
#261) exposed the silence — and a silent boundary reads as an accident, not a decision (the
ADR-0009 §3 lesson: apparent gaps get re-litigated until the design intent is written down).

The boundary was already implicit in three places: the security posture runs its gates
**offline** (no network in the gate path); RFC-0001 N1 declines a runtime kernel; and the M15/M16
plans already accept ops *documents* into scope (the #248 production-readiness checklist
enrichment, the #249 observability budgets).

## Decision

1. **Ops documents are in scope.** Deployment architecture, monitoring/observability strategy,
   and the production-readiness checklist are legitimate EADOS surface — **manifest-driven,
   rendered, reviewable documents**, gate-checked for existence and shape like every other
   design-fold artifact (#240 pattern). They land through the already-planned issues (#248
   checklist, #249 budgets) and, if demand grows, an `ops` design fold — no new machinery is
   minted by this ADR.

2. **Live infrastructure is a recorded non-goal.** EADOS never provisions, deploys, or operates
   infrastructure: no Docker/K8s execution, no cloud credentials, no `kubectl`/terraform apply,
   no monitoring agents. The generated project owns its runtime; EADOS's job ends at the governed
   repository. This keeps the gate path offline (Security posture), the factory dependency-free,
   and the human-in-the-loop model intact — a deploy is the *most* irreversible step a delivery
   makes, and EADOS's contract already reserves irreversible steps for the human.

3. **A `deploy` phase is deferred, not declined.** If real demand materializes (users asking the
   pipeline to gate an actual deployment), option C of #261 — a phase with entry gates (audit
   green, budgets met) and a deployment-checklist gate — gets its own milestone and a fresh ADR;
   it touches `workflow.yaml` and must not be smuggled in through a fold.

## Consequences

- The README FAQ states the boundary in one line (EN + zh-Hans + ja, i18n hash refreshed).
- #248's checklist enrichment now points at a ratified perimeter instead of an open question;
  #249's observability budgets are confirmed in scope as *documents*.
- Viral-prompt-11 requests ("set up Docker/K8s, configure monitoring") get a principled answer:
  EADOS will *design and document* the ops story; executing it stays with the project's own
  tooling — the same split ADR-0009 §3 drew between factory-pinned and consumer-managed CI.
- Nothing in the phase machine changes today; `init → design → plan → scaffold → audit →
  refactor` stands.

## References

- Issue #261 (the decision request; prompt-pack review 2026-07-09); RFC-0001 N1 (no runtime
  kernel); ADR-0009 §3 (trust-domain split precedent); #240 (design folds), #248 (enterprise
  posture + readiness checklist), #249 (NFR budgets); README "Security posture" (offline gates).
