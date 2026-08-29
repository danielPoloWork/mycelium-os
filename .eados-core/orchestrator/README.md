# orchestrator/ — the engine

This directory is the machinery that turns a project idea into a governed repository. It is
data and procedure; the intelligence that drives it is the
[Enterprise Project Architect](../agent/enterprise-architect.md) agent.

## Files

| File | Role |
|---|---|
| [`interview.md`](interview.md) | The human-readable intake protocol — phases, defaults, follow-up logic. |
| [`questionnaire.yaml`](questionnaire.yaml) | The machine-readable question bank backing the interview. |
| [`placeholders.md`](placeholders.md) | The canonical dictionary of every `{{PLACEHOLDER}}` the templates use. |
| [`project.yaml.template`](project.yaml.template) | The manifest skeleton — copied to `project.yaml` and filled per run. |
| [`generate.md`](generate.md) | The ordered generation playbook: resolve → render → verify → bootstrap. |
| [`profiles/`](profiles/) | Per-language toolchain knowledge (`<lang>.yaml`), plus [`_schema.md`](profiles/_schema.md). |

## The flow in one paragraph

The architect runs [`interview.md`](interview.md) (in the maintainer's language), resolves
the [`profiles/`](profiles/) for the chosen language(s), and merges both into a confirmed
[`project.yaml`](project.yaml.template). It then executes [`generate.md`](generate.md):
substitute the [`placeholders.md`](placeholders.md) into [`../templates/`](../templates/),
lay down the cross-language source tree, seed the day-zero docs, run the generated
consistency lint, and draft the bootstrap PR. The new repo is then self-governing.

## Adding a language (any language)

EADOS supports **any** programming language; the nineteen shipped profiles are seeds. A new
language is added by **data, not template edits**:

1. Copy [`profiles/_template.yaml`](profiles/_template.yaml) to `profiles/<lang>.yaml` and
   fill every field (schema: [`_schema.md`](profiles/_schema.md)). Pick the de-facto
   enterprise tool for each role.
2. Add the language's framework follow-ups to the interview (Phase 2) if it needs them.
3. Record an ADR in [`../docs/adr/`](../docs/adr/) for the addition.
4. Prove it: `python ../tools/eados_lint.py` (completeness) **and** render a manifest for the
   language whose generated `tools/consistency_lint.py` passes.

If you find yourself editing a template to support a language, stop — the missing
knowledge belongs in the profile. This is what keeps EADOS open-ended instead of capped at a
fixed list.
