# templates/ — the parameterized enterprise scaffolding

These are the `pbr-cpp-memory-pool` artifacts with every project- and language-specific fact
replaced by a `{{PLACEHOLDER}}`. The [generation playbook](../orchestrator/generate.md)
renders them into a new repository; the [placeholder dictionary](../orchestrator/placeholders.md)
defines every token; the [language profiles](../orchestrator/profiles/) supply the
toolchain-shaped values.

## Conventions

- **`.tmpl` files are rendered** — placeholders substituted, the `.tmpl` suffix stripped on
  output (`AGENTS.md.tmpl` → `AGENTS.md`).
- **Non-`.tmpl` files are copied** but still parameterized at their documented `{{...}}`
  config points (e.g. `tools/consistency_lint.py`'s `CONFIG` block, `docs/adr/template.md`,
  `docs/patterns/design-patterns.md`).
- **Path segments are expanded too** — the source tree directories come from `{{LANG}}`,
  `{{GROUP_PATH}}`, and `{{PROJECT_SLUG}}`.
- Templates reference **roles**, never specific tools — `{{LINTER}}`, not `clang-tidy`.

## What renders where

| Template area | Becomes (in the generated repo) |
|---|---|
| `AGENTS.md.tmpl`, `CLAUDE.md.tmpl`, `GEMINI.md.tmpl` | the agent contract trinity |
| `README.md.tmpl`, `ROADMAP.md.tmpl`, `CHANGELOG.md.tmpl`, `SECURITY.md.tmpl`, `gitignore.tmpl` | root governance |
| `docs/**` | ADRs (+ template + index + 2 seeds), patterns catalogue + taxonomy, spec template + instance, bug ledger, threat model (STRIDE), journal, workflow docs, dev guide |
| `.github/**` | PR + issue templates, CODEOWNERS, Dependabot, label set, CI + release workflows |
| `tools/consistency_lint.py` | the generic, profile-driven congruence checker |

## Editing rule

If you find yourself adding a language name or a specific tool to a template, **stop** — that
knowledge belongs in a [profile](../orchestrator/profiles/). Templates must hold for every
supported language. A new placeholder must be added to
[`placeholders.md`](../orchestrator/placeholders.md) in the same change.
