# Learning — the factory's memory

EADOS's agents do not retrain a model; they improve through **structured, versioned memory**.
This folder is that memory. It is read at the start of work and appended after it, and every
change is a reviewable diff — auditable self-improvement, never an opaque black box.

## Contents

| Path | Role |
|---|---|
| [`lessons.yaml`](lessons.yaml) | The lessons ledger — generalizable rules learned from past runs and corrections. |
| [`scope-examples.yaml`](scope-examples.yaml) | Worked examples (#224) for the **apply-vs-skip** call — WHEN a lesson's `scope` matches the run. Shape-checked by `eados_lint` (`examples`); a companion to the ledger, which stays a pure list. |
| [`runs/`](runs/README.md) | One record per generation run (the final manifest + outcome), the input the auto-tuner mines. |

## The loop

1. **Read first.** At the start of a generation run (or a task on EADOS), the agent reads
   `lessons.yaml` and applies every lesson whose `scope` matches (global, the chosen language,
   or the project kind).
2. **Act.** Generate / review / release as usual.
3. **Record after.** When the maintainer corrects the agent, or a run reveals a generalizable
   improvement, the agent **drafts** a new lesson (human approves it in the PR). Record the
   *rule*, not the one-off incident.

## Lesson schema

Each entry (validated by `tools/eados_lint.py`'s `lessons` check):

```yaml
- id: L-NNNN              # unique, monotonic
  date: YYYY-MM-DD        # when learned
  scope: global           # global | lang:<lang> | kind:<library|service|cli|app>
  context: <one line — the situation that triggered the lesson>
  rule: <one line — the durable, generalizable rule to apply next time>
  source: <optional — PR/commit/run that produced it>
```

Keep `context` and `rule` to one line each; a lesson that needs a paragraph is really an ADR.
Lessons are **advisory guidance**, not hard gates — the lint checks their *shape*, not that the
agent obeyed them (that is the reviewer's job). A lesson is the **lowest-precedence** layer: it
never overrides a gate, a spec, or the human terminal gate (see the *Precedence* section of
[`orchestrator/os/README.md`](../orchestrator/os/README.md)).
