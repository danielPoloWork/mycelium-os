# First project, phase by phase — an end-to-end walkthrough

This is a **follow-along** run of the EADOS phase pipeline —
`init → design → plan → scaffold → audit → migrate` — with the exact commands, the real console
output, what **you** confirm at each human-gated step, and how the manifest's `delivery_state`
evolves. It complements the per-phase reference docs in
[`orchestrator/commands/`](../orchestrator/commands/README.md): those say *what* each phase is; this
shows *what it feels like* to run them in sequence.

> **Read this if** you want to see the whole pipeline once before driving it for real. Everything
> here runs against a tiny worked example you create below — no agent required (the agent automates
> exactly these steps; here you run them by hand to see the gates).

**Prerequisites:** Python 3.12+ and the factory in your repo (`.eados-core/`) — see the
[README "Getting started"](../../README.md) / [`USAGE.md`](USAGE.md). Run everything from your repo
root.

---

## 0. The worked example

The phase tools read a **manifest** (`project.yaml`) plus a few project artifacts. Create them:

```bash
# a full, valid manifest — start from the shipped reference and park it at phase `init`
cp .eados-core/orchestrator/examples/reference.yaml project.yaml
cat >> project.yaml <<'YAML'

delivery_state:
  phase: init
  refs:
    rfcs:
      - RFC-0001
    milestones:
      - "1"
YAML

mkdir -p docs/rfc
cat > docs/rfc/0001-sample.md <<'MD'
# RFC-0001 — Sample feature
## Context
Why the change is needed.
## Decision
We will implement the sample feature.
## Alternatives
Doing nothing; an off-the-shelf option.
## Consequences
A small maintenance cost; a clearer pipeline.
## Approval
approved-by: tech-lead (2026-06-27)
MD

cat > ROADMAP.md <<'MD'
# Roadmap — sample project
## Milestone 1 — Bootstrap
- [ ] 1.1 implement the sample feature per RFC-0001
MD

cat > links.yaml <<'YAML'
links:
  - pr: 12
    rfc: RFC-0001
    milestone: "1"
    commit: abc123
    release: v0.1.0
YAML
```

> `delivery_state` is the persistent spine: `phase` is where you are, `refs` are the cross-link ids
> (RFCs, milestones) the gates trace. The tools **report and check** — they never advance the phase;
> **you** write the next `phase` after confirming a human-gated move (`AGENTS.md` §6).

**At a glance** — the doctor ([`/eados status`](../orchestrator/commands/status.md)) summarizes
where you are and whether the lineage is whole:

```text
$ python .eados-core/tools/eados.py status project.yaml
EADOS status - project.yaml
  phase: init   (role: enterprise-architect; produces: manifest)
  legal next transitions:
    -> design   (gates: manifest-valid)  [human-gated]
    -> audit    (gates: manifest-valid, adoption-recorded)  [human-gated]
    -> migrate  (gates: manifest-valid, adoption-recorded)  [human-gated]
  refs: rfcs=['RFC-0001']; milestones=['1']
  roadmap-covers-rfcs: OK (RFC-0001 -> M1)
  traceability-lint: OK - the graph is whole
```

(The `-> audit` / `-> migrate` rows are the brownfield adoption edges, #247/ADR-0021 — listed
everywhere, NOT READY for this greenfield project since its manifest has no `adoption:` block.)

---

## 1. `init → design` — author the RFC

The deterministic checker reports the legal next move (it reads `delivery_state.phase` +
`workflow.yaml`):

```text
$ python .eados-core/tools/phase_runner.py project.yaml
current phase: init
legal next transitions:
  -> design   (gates: manifest-valid)  [human-gated — the owner confirms]
  -> audit    (gates: manifest-valid, adoption-recorded)  [human-gated — the owner confirms]
  -> migrate  (gates: manifest-valid, adoption-recorded)  [human-gated — the owner confirms]
```

In `design` you (or the agent) author the RFC from the template, then the **`rfc-approved`** gate
verifies it carries the required sections + a `tech-lead` approval record:

```text
$ python .eados-core/tools/rfc_check.py docs/rfc/0001-sample.md
rfc-check: OK — docs/rfc/0001-sample.md satisfies the rfc-approved gate.
```

Propose the transition. The runner validates it and **emits the checkpoint to write** — it does not
write state. With `--rfc` / `--roadmap` it evaluates the transition's deterministic gates **live**
and records the marks in the checkpoint's `gate_results` (#213), so the checkpoint is the phase's
own audit record — its own observation, not a copy of `workflow.yaml`:

```text
$ python .eados-core/tools/phase_runner.py project.yaml --propose plan --rfc docs/rfc/0001-sample.md
proposed transition: design -> plan  (read at manifest_rev 0)
  LEGAL — gates to satisfy: rfc-approved; human-gated: yes
  gate results (live): rfc-approved=OK
  emit — append to delivery_state.checkpoints, then set delivery_state.phase:
    - { from: design, to: plan, gates: ['rfc-approved'], at: 2026-07-06, confirmed_by: <owner>, gate_results: { rfc-approved: OK } }
    phase: plan
    (top-level) manifest_rev: 1   # bump the optimistic-concurrency counter, and re-run with --expect-rev 0 before writing to catch a concurrent edit (#214)
    (human-gated — replace <owner> in confirmed_by with who approved the move)
```

A gate that is not `OK`/`manual` (e.g. `rfc-approved=needs-input` when `--rfc` is omitted) prints a
**NOT READY** line — `checkpoint_chain_problems` rejects a recorded checkpoint whose `gate_results`
are not all `OK`/`manual`, so a transition can't be logged as taken over a gate that did not pass.

> **Human gate.** You confirm the move by editing the manifest: append that checkpoint under
> `delivery_state.checkpoints`, set `delivery_state.phase: plan`, and bump `manifest_rev` to `1`.
> Before writing, re-run the propose with `--expect-rev 0` (#214): if another session moved the rev
> in the meantime it refuses with a `CONFLICT`, so a parallel edit fails loud instead of silently
> losing one. Nothing advanced on its own.

---

## 2. `plan → scaffold` — negotiate the roadmap

In `plan` the roadmap is co-created from the approved RFCs; the **`roadmap-covers-rfcs`** gate fails
if any RFC is addressed by no milestone:

```text
$ python .eados-core/tools/traceability.py ROADMAP.md RFC-0001
roadmap: 1 milestone(s); RFCs to cover: 1
  RFC-0001 -> M1
roadmap-covers-rfcs: OK — every RFC is addressed by a milestone.
```

```text
$ python .eados-core/tools/phase_runner.py project.yaml --propose scaffold
proposed transition: plan -> scaffold
  LEGAL — gates to satisfy: roadmap-covers-rfcs; human-gated: yes
  emit — append to delivery_state.checkpoints, then set delivery_state.phase:
    - { from: plan, to: scaffold, gates: ['roadmap-covers-rfcs'], at: 2026-07-06, confirmed_by: <owner>, gate_results: { roadmap-covers-rfcs: OK } }
    phase: scaffold
```

Confirm as before (write the checkpoint + `phase: scaffold`). Since #250 the recorded
`gate_results` are **required** on every human-gated checkpoint — a direction-changing move
must carry the evidence of what its gates said, not just who confirmed it.

---

## 3. `scaffold` — generate the repository (the classic factory)

`scaffold` is the deterministic renderer — today's factory, unchanged. It substitutes every
`{{PLACEHOLDER}}` from the manifest and lays down the repo:

```text
$ python .eados-core/tools/render.py project.yaml --out rendered
Render: OK — 40 template(s) -> rendered
```

> Use `--in-place` to generate into the repo that holds `.eados-core/`, or `--out <dir>` for a
> separate copy (as here). This is the same step you'd run on its own as `/eados scaffold` —
> see [`USAGE.md`](USAGE.md) §3.

`scaffold → audit` is the **one automatic transition** (gates `consistency-lint` + `self-review`,
run on the rendered repo) — no human confirmation needed to enter `audit`.

---

## 4. `audit` — risk + traceability

Audit verifies the Git-side lineage is whole (**`traceability-lint`**) and scores the change's risk:

```text
$ python .eados-core/tools/traceability.py ROADMAP.md RFC-0001 --links links.yaml
traceability-lint: OK -- the RFC->milestone->PR->commit->release graph is whole.

$ python .eados-core/tools/risk_score.py tools/render.py --lines 120
risk: high  (factors: security-surface, medium-change)
security-auditor gate: REQUIRED
```

> At/above the (per-domain) threshold the **`security-auditor` gate is REQUIRED** before proposing
> the next move. The agent runs the deep audit and drafts a **risk register**; you resolve findings.

```text
$ python .eados-core/tools/phase_runner.py project.yaml --propose migrate
proposed transition: audit -> migrate
  LEGAL — gates to satisfy: risk-register-present, traceability-lint; human-gated: yes
  emit — append to delivery_state.checkpoints, then set delivery_state.phase:
    - { from: audit, to: migrate, gates: ['risk-register-present', 'traceability-lint'], at: 2026-07-06, confirmed_by: <owner>, gate_results: { risk-register-present: manual, traceability-lint: OK } }
    phase: migrate
```

`migrate` (brownfield) is the terminal phase — bring an existing repo up to the standard via
gated, sandboxed PRs; see [`migrate.md`](../orchestrator/commands/migrate.md).

---

## Shortcut — run a phase's gates in one shot

Instead of running each gate by hand, the thin orchestrator runs a phase's deterministic gates and
reports the legal next moves (it never writes or advances — see
[`eados.py`](../tools/eados.py)):

```text
$ python .eados-core/tools/eados.py plan project.yaml
EADOS plan - project.yaml
  gates to leave 'plan':
    [OK] roadmap-covers-rfcs
    [OK] manifest-valid
  legal next transitions:
    -> scaffold   (gates: roadmap-covers-rfcs)  [human-gated]
    -> design   (gates: manifest-valid)
  next: orchestrator/commands/plan.md — the authoring + human-gated steps.
```

`python .eados-core/tools/eados.py status project.yaml` is the read-only doctor (§0).

---

## How `delivery_state.phase` evolved

| After you confirmed | `delivery_state.phase` | Gate that guarded the move |
|---|---|---|
| (start) | `init` | — |
| `init → design` | `design` | `manifest-valid` |
| `design → plan` | `plan` | `rfc-approved` |
| `plan → scaffold` | `scaffold` | `roadmap-covers-rfcs` |
| `scaffold → audit` | `audit` | `consistency-lint` + `self-review` (automatic) |
| `audit → migrate` | `migrate` | `risk-register-present` |

Every move is **gated**; every move that changes committed direction is **human-confirmed**. The
tools compute what is legal and check the gates; you decide and write the state. For the authoring
and negotiation behind each phase, read its command doc under
[`orchestrator/commands/`](../orchestrator/commands/README.md).
