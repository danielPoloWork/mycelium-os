# RFC-NNNN: <title>

- **Status:** Draft → In review → Accepted
- **Author:** <author role/name> · **Reviewers:** <peers + architect> · **Approver:** tech-lead
- **Date:** <YYYY-MM-DD>
- **Related:** <links to specs, ADRs, the milestone this feeds>

> Written *before* the code. Propose a solution, explore the alternatives (and why they were
> rejected), and state the impact. The `rfc-approved` gate ([`rfc.yaml`](rfc.yaml)) checks this
> file has every required section and a valid Approval record before `design → plan`.

## Context

The problem, the user/business need, and the constraints. What forces a decision now?

## Decision

The proposed solution and the sequence that realizes it. Fill the folds below that apply — they are
the design-phase deepenings of the wishlist verbs (ADR-0019 §2: `systemdesign` / `api` / `database`
/ `scalability` / `pseudocode` are **sub-modes of `design`**, not commands). Omit a fold that does
not apply (a library has no HTTP API; a stateless tool has no schema); never leave one hollow.

### API contract (`api` / `systemdesign`)

The public surface consumers depend on — aligned with spec §5. A checklist, not prose:

- **Endpoints / functions** — the operations, each with its verb/route or signature.
- **Payloads** — request/response shapes (or parameter/return types), with the required vs optional split.
- **Error model** — the failure taxonomy consumers must handle (status codes / error types), not just the happy path.
- **Versioning** — the compatibility contract and the SemVer surface: what a MAJOR bump would be.

For a `service`/`web` project, consider `capabilities.api_spec` to seed a `docs/api/` OpenAPI/IDL
stub (Q5.5); the RFC states the contract, the stub is where it is written down.

### Data & schema (`database`)

Only if the change owns persistent state. Within **ADR-0004's frame** — SQL/data stores are a
**secondary** component declared at interview Q1.2, never a primary language profile, and no
`database` command exists without a superseding ADR:

- **Entities & relations** — the core records and how they relate.
- **Normalization** — the normal form the design targets, and any deliberate denormalization (with its reason).
- **Migration policy** — how the schema evolves without data loss (forward-only? reversible? the tooling).

### Scalability budgets (`scalability`)

The **numeric** non-functional targets this change must hold — a value per hard axis (p99 latency,
throughput, memory ceiling, target FPS, cold-start budget), not an adjective. These come from the
domain's hard `nfr_axes` (interview Q5.3) and land in spec §3. *(Enforcing them as evaluated audit
gates is tracked separately in #249; this fold states the numbers the audit will check.)*

### Algorithm sketch (`pseudocode`) — optional

For a non-obvious core algorithm, a short **language-free** pseudocode sketch (the control flow /
invariants), mirrored into spec §4. Skip it when the approach is standard.

### Cross-cutting

Security & performance considerations; for a game, memory/GPU/framerate budgets and the
asset-pipeline deps; for `web`, the UI-architecture checklist (loading/empty/error states,
responsive breakpoints, the accessibility conformance level, component reusability + props/API
conventions).

## Alternatives

The options considered and **why each was rejected** — not on taste, on a concrete reason.

## Consequences

What this makes easy, what it makes harder, the migration path, and the follow-up roadmap items.

## Approval

Filled by the approver **after** review (this is the `rfc-approved` gate's record):

```
approved-by: tech-lead (YYYY-MM-DD)
```

Reviewers (structured findings addressed): <reviewer> — <resolved/▢>.

## References

<links>
