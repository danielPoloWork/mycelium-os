# ADR-0025: The phase state writer — who records a phase's outcome

## Status

Accepted (2026-07-27)

## Context

Every phase command names **one** acting role. But every phase has to do two things beyond
producing its artifact:

1. update the manifest's `delivery_state` — the refs cross-links and the transition checkpoint, and
2. append a run record under `learning/runs/` (`record_run.py`, instructed by *every* phase
   procedure — #250's uniform audit trail).

`authority.yaml` grants both paths to the **architect alone**: `orchestrator/project.yaml` is
covered by no other role's `may_draft`, and `.eados-core/**` is in the architect's `owns`. So three
of the six procedures instructed the acting role to write paths the authority gate denies it:

| Procedure | Acting role | Instruction | Verdict |
|---|---|---|---|
| `design.md` step 6, 8 | `tech-lead` | write `delivery_state.refs.rfcs`; `record_run.py` | DENIED |
| `plan.md` step 5, 7 | `producer` | write `delivery_state.refs.milestones`; `record_run.py` | DENIED |
| `audit.md` step 5 | `security-auditor` | note the audit in `delivery_state`; `record_run.py` | DENIED |

**The gate was right; the procedures were wrong.** Which phases are affected follows directly from
`workflow.yaml`'s role column — the three unaffected ones (`init`, `scaffold`, `migrate`) are
exactly the three the architect already owns, which is why the classic one-shot `init → scaffold`
path never hit it. It surfaced only when a consumer ran the full pipeline end to end
(`egl-utils-java`, 2026-07-27, #346).

The consequences were worse than an inconvenience. Following the procedure literally is an
authority violation the project's own gate catches. Following it *correctly* required undocumented
behaviour — an unstated role switch mid-procedure, or splitting a phase's output across two PRs,
which the reporter did three times with nothing in the procedures saying to. So the correct
behaviour was **folklore**, which is the precise opposite of the knowledge-as-data posture the
`os/` specs exist for. And because `record_run.py` is instructed by every phase, #250's "every
phase leaves the same audit trail" was unreachable for `design`, `plan` and `audit` as specified.

## Decision

**A workflow state declares its `state_writer`: the role that records the phase's outcome.**

```yaml
states:
  - id: design
    role: tech-lead                      # AUTHORS the artifact
    state_writer: enterprise-architect   # RECORDS delivery_state + the run record
    produces: [rfc]
```

`role` and `state_writer` are the same for the phases the architect already owns, and deliberately
different for `design`, `plan` and `audit`. The procedures for those three now say so at the step
where it matters, and `/eados status` names both roles — when they differ, it says which write the
acting role may not make.

The declaration is held honest by a new **`state-writer-authority`** self-lint: every state must
name a `state_writer` that is a declared role *and* that `authority.yaml` actually authorizes for
the state-recording paths. A declared writer the authority denies is the original defect with an
extra step, so it fails in the factory rather than at a consumer's keyboard.

Nothing about the authority model changes. No role gains a path; no new authorization axis is
introduced. What changes is that a handoff which was already required — and already implicit in
`authority.yaml` — becomes **stated in data** instead of inferred.

### Alternatives considered

**Widen `may_draft`** — add `orchestrator/project.yaml` and `learning/runs/**` to every phase
role's grants. *Rejected:* it dissolves the separation the spec exists to enforce, handing the
manifest to five roles to solve a problem in two paths. It also makes the gate quieter without
making the procedures truer.

**Model it as a capability** — a `may_record: [delivery_state, learning]` grant, decoupling "may
write the phase ledger" from "owns these globs". *Rejected as disproportionate:* it is the most
expressive option and introduces a second authorization axis alongside `may_draft` / `may_approve` /
`owns`. Worth revisiting if a third such cross-cutting write appears; two paths do not justify a
new model.

**Document `--root`-style workarounds in the procedures** — tell each procedure to switch roles ad
hoc. *Rejected:* it writes the folklore down without removing it, and leaves the data unable to
answer "who records this phase?".

## Consequences

- A phase with a different author and recorder is now legible from the data alone; `/eados status`
  states the handoff rather than leaving it to be discovered by a denial.
- `design`, `plan` and `audit` become completable as specified — #250's uniform audit trail is
  reachable for all six phases for the first time.
- Adding a phase now requires answering "who records its outcome?", and the gate refuses a state
  that does not.
- A future phase whose recorder is genuinely not the architect is a one-field change, with the
  authority check proving it is allowed.
- **Still open, deliberately out of scope:** in a consumer repo whose `.gitignore` excludes the
  vendored `/.eados-core/` — the shipped default from `templates/gitignore.tmpl` — run records are
  written but never committed, so the audit trail does not survive a clone. Same procedure step,
  different cause; tracked separately.

## References

- #346 (the report, from an end-to-end consumer run); #250 (the uniform run-record audit trail).
- `orchestrator/os/workflow/workflow.yaml` + `_schema.md`; `orchestrator/os/authority/authority.yaml`;
  `tools/authority_check.py`; `eados_lint` check `state-writer-authority`.
- `orchestrator/commands/{design,plan,audit}.md` — the three procedures corrected.
- ADR-0011 (the delivery OS and its role authority); ADR-0019 (command-surface taxonomy).
