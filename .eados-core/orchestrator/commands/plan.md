# `/eados plan` — negotiate the roadmap from the approved RFCs

The `plan` phase turns approved RFCs into a **negotiated** milestone roadmap. Owned by the
**producer** (the roadmap guardian); co-created with `product-manager` and `tech-lead`. Protocol:
[`../os/plan/negotiation-protocol.md`](../os/plan/negotiation-protocol.md); config:
[`../os/plan/plan.yaml`](../os/plan/plan.yaml).

## Preconditions

- The design phase produced ≥1 approved RFC (recorded in `delivery_state.refs.rfcs`).
- `phase_runner.py <manifest>` reports `-> plan` (or the manifest is already at `phase: plan`).

## Procedure

1. **Negotiate** — run [`negotiation-protocol.md`](../os/plan/negotiation-protocol.md) with the
   roles from [`plan.yaml`](../os/plan/plan.yaml): `product-manager` proposes priorities →
   `tech-lead` attaches T-shirt sizes (`sizing_scale`) + a **model/effort route** (tier + effort,
   the [`os/routing`](../os/routing/_schema.md) policy via
   [`route_advice.py`](../../tools/route_advice.py)) + flags tech debt → `producer` reconciles
   capacity × dates into milestones (using the domain's `milestone_vocabulary`). Each step edits a
   concrete artifact.
2. **Check authority** — before writing the roadmap, the producer confirms it may:
   ```bash
   python .eados-core/tools/authority_check.py producer ROADMAP.md
   ```
3. **Write the roadmap** — produce/update `ROADMAP.md`: milestones with pre-numbered items, each
   item referencing the RFC it implements (so the gate can trace it) and carrying its **route** —
   the tier / effort in the `os/routing` vocabulary, **tiers not model names** (a name would rot;
   the dated `catalog:` owns them). A routed item reads, for example:

   ```markdown
   - [ ] 3.2 Token-bucket rate limiter (RFC-0002) — size: M · route: standard / medium
   - [ ] 3.3 Migrate the auth schema (RFC-0002) — size: L · route: frontier-reasoning / high (decision-heavy)
   ```

   The route is advisory: it states the recommended tier + effort per step; the human keeps final
   model authority (ADR-0017). A companion route checkpoint compares a step's route against the
   session model at run time and warns on a mismatch — it never switches the model.
4. **Gate: roadmap-covers-rfcs** — every approved RFC must be addressed by ≥1 milestone:
   ```bash
   python .eados-core/tools/traceability.py ROADMAP.md $(rfc ids from delivery_state.refs.rfcs)
   ```
   Must pass before `plan → scaffold` is legal.
5. **Record the cross-links** — add the milestone ids to `delivery_state.refs.milestones` (feeds
   the traceability graph; references, not content).
   > **Who writes this:** the phase's **`state_writer`** (`enterprise-architect`), not the
   > acting role. `authority.yaml` grants `orchestrator/project.yaml` and `.eados-core/**`
   > to the architect alone, so the acting role doing it is an authority violation this
   > project's own gate catches (#346, ADR-0025). Hand off, or act as the state writer for
   > this step — `/eados status` names both roles.
6. **Propose the transition** — emit the checkpoint for `plan → scaffold` (human-gated):
   ```bash
   python .eados-core/tools/phase_runner.py <manifest> --propose scaffold
   ```
   The agent writes the emitted checkpoint + `phase: scaffold` **after** the human confirms.
7. **Record the run** — append the phase-tagged run record (the learning loop's uniform shape;
   every phase leaves the same audit trail, #250):
   ```bash
   python .eados-core/tools/record_run.py <manifest> --phase plan   # add --failure GATE=MSG on a red gate
   ```
8. **Hand off** — to [`/eados scaffold`](../generate.md): render the repository as today, now with
   the roadmap and spec already agreed.

## Boundary

The agent **drafts** the roadmap and **proposes** the transition. The human **decides scope** in
the negotiation (cuts are a human call) and **confirms** the human-gated move. No roadmap ships
that leaves an RFC uncovered; no phase advances on the agent's authority (`AGENTS.md` §6).

**Calibrate the negotiation** (`AGENTS.md` §10): sizing and priority claims carry a confidence tag
earned by evidence, and a scope disagreement uses the dissent template — position / alternative /
risk — first line, no warm-up. Once the human decides scope, the dissent is recorded, never
relitigated.
