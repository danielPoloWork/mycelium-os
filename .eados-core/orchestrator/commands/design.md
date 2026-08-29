# `/eados design` — author and gate an RFC

The first governance phase. An RFC is written *before* the code, reviewed, approved, and gated;
only then is `design → plan` legal. Owned by the **tech-lead** (or **product-manager** for a
product-facing RFC). Protocol: [`../os/rfc/review-protocol.md`](../os/rfc/review-protocol.md).

## Preconditions

- The manifest exists with `delivery_state.phase: init` (from [`/eados init`](init.md)).
  `phase_runner.py <manifest>` reports `-> design` as the default legal move (the adoption
  edges it also lists stay NOT READY without an `adoption:` block, #247).

## Procedure

1. **Check authority** — before drafting, the acting role confirms it may write the RFC path:
   ```bash
   python .eados-core/tools/authority_check.py tech-lead docs/rfc/NNNN-<slug>.md
   ```
2. **Author the RFC** — copy [`../os/rfc/template.md`](../os/rfc/template.md) to
   `docs/rfc/NNNN-<slug>.md` and fill **Context, Decision, Alternatives, Consequences**. Push for
   measurable phrasing and a concrete rejection reason per alternative. The Decision section carries
   the **design folds** (ADR-0019 §2 — the `systemdesign`/`api`/`database`/`scalability`/`pseudocode`
   sub-modes): the **API contract** checklist (endpoints/payloads/error model/versioning, aligned
   with spec §5), a **Data & schema** subsection when the change owns state (within ADR-0004's
   secondary-SQL frame), the **numeric scalability budgets** per hard NFR axis (interview Q5.3 →
   spec §3), and an optional language-free **algorithm sketch** (spec §4). Fill the folds that
   apply; omit those that do not, never leaving one hollow. A `service`/`web` API surface may seed a
   `docs/api/` stub via `capabilities.api_spec`.
3. **Review** — `reviewer` peers (and the `enterprise-architect` when the change is cross-cutting)
   return **structured findings**; the author resolves each. No prose hand-waving.
4. **Approve** — when findings are resolved, the **approver** (`tech-lead`) adds the record:
   ```
   approved-by: tech-lead (YYYY-MM-DD)
   ```
5. **Verify the gate** — the `rfc-approved` gate is mechanical:
   ```bash
   python .eados-core/tools/rfc_check.py docs/rfc/NNNN-<slug>.md      # must pass
   ```
6. **Record the cross-link** — add the RFC id to `delivery_state.refs.rfcs` (feeds the
   traceability graph, M3/M4) — references, not content.
   > **Who writes this:** the phase's **`state_writer`** (`enterprise-architect`), not the
   > acting role. `authority.yaml` grants `orchestrator/project.yaml` and `.eados-core/**`
   > to the architect alone, so the acting role doing it is an authority violation this
   > project's own gate catches (#346, ADR-0025). Hand off, or act as the state writer for
   > this step — `/eados status` names both roles.
7. **Propose the transition** — emit the checkpoint for `design → plan` (human-gated):
   ```bash
   python .eados-core/tools/phase_runner.py <manifest> --propose plan
   ```
   The agent writes the emitted checkpoint + `phase: plan` to the manifest **after** the human
   confirms; the runner never advances state itself.
8. **Record the run** — append the phase-tagged run record (the learning loop's uniform shape;
   every phase leaves the same audit trail, #250):
   ```bash
   python .eados-core/tools/record_run.py <manifest> --phase design   # add --failure GATE=MSG on a red gate
   ```
9. **Hand off** — to [`/eados plan`](../commands/README.md) (lands in M3): the producer turns the
   approved RFCs into a negotiated milestone roadmap.

## Boundary

The agent **drafts** the RFC, runs the checks, and **proposes** the transition. A human **approves**
the RFC (the approval encodes a human decision) and **confirms** the human-gated move. No RFC
self-approves; no phase advances on the agent's authority (`AGENTS.md` §6).

**Calibrate the review** (`AGENTS.md` §10): structured findings and the approval recommendation carry
a confidence tag earned by evidence (cite the spec §, the file, or the check), and a disagreement on
a design choice leads with the dissent template — position / alternative / risk — not prose
hand-waving.
