# EADOS — Enterprise Agentic Delivery Operating System

This folder is the **factory**: everything needed to stamp out a new, fully governed,
enterprise-grade software repository — in *any* language — that ships on day zero with an
AI-agent contract, ADRs, a CI quality-gate matrix, a cross-artifact consistency lint, SemVer
release governance, and opt-in i18n.

EADOS is **not** a product you run. It is the factory you point at a project idea: it
interviews you, records your answers in one manifest, and renders the new repository from
parameterized templates.

> **This is a factory bundle.** It contains the factory plus the agent contract. The README,
> SECURITY policy, and LICENSE of the *project you generate* are produced from the templates at
> render time — they are native to that project, not to this factory. (The bundle keeps
> `LICENSE` at the root because the renderer uses it as the source for each generated project's
> license.)

---

## Requirements

- **git** and an **AI coding agent** that reads `AGENTS.md` — Claude Code, Gemini Antigravity,
  or ChatGPT Codex (the usual way to drive it).
- **Python 3.12+** — only for the bundled tooling (`.eados-core/tools/render.py`,
  `.eados-core/tools/eados_lint.py`). Standard-library only; no `pip install`.

Confirm the factory is internally congruent (optional):

```bash
python .eados-core/tools/eados_lint.py
```

---

## Use it — conversational (recommended)

1. **Open this folder with your AI coding agent.** It auto-loads [`AGENTS.md`](../AGENTS.md)
   (the binding contract) and adopts the Enterprise Project Architect persona.
2. **Say what you want to build**, e.g. *"New project: a Rust token-bucket rate limiter,
   library, GitHub owner `acme`, default branch `main`."*
3. **Answer the interview.** The architect walks
   [`orchestrator/interview.md`](orchestrator/interview.md) — language(s), frameworks, tools,
   governance, and the functional spec — asking only what it cannot safely default.
4. **Review the manifest.** It writes `orchestrator/project.yaml` and shows it to you for
   confirmation before generating anything.
5. **Generate.** It follows [`orchestrator/generate.md`](orchestrator/generate.md) to render the
   new repository, runs the consistency lint, and drafts the bootstrap PR.

You never have to remember the enterprise rules — they are encoded in the templates and
enforced by the lint. You only make the project-specific decisions.

---

## Use it — deterministic (no agent)

The interview's only output is a filled manifest, so you can fill it by hand and render. With
this bundle copied into your project repo (`<your-repo>/.eados-core/`), `--in-place` generates the
project **into that repo**, next to `.eados-core/` (which the rendered `.gitignore` excludes):

```bash
cp .eados-core/orchestrator/project.yaml.template .eados-core/orchestrator/project.yaml
# edit it — see .eados-core/orchestrator/examples/reference.yaml for a worked manifest
python .eados-core/tools/render.py .eados-core/orchestrator/project.yaml --in-place
python tools/consistency_lint.py   # the generated repo's own gate (now at the repo root)
```

(To render a *separate* copy instead, use `--out <dir-outside-the-factory>`.) `render.py` is
deterministic, honors the `capabilities.*` gates, leaves GitHub Actions `${{ … }}` untouched,
and **aborts on any unresolved placeholder**.

---

## What the generated repository gets, on day zero

- **Agent contract** — `AGENTS.md` (source of truth) + `CLAUDE.md` / `GEMINI.md` adapters, bound
  to the new project's language and stack.
- **Source layout** — the Maven-style cross-language tree
  `src/{main,test,bench}/<lang>/<group-path>/<project>/`.
- **Git governance** — Conventional Commits, branch-naming, one-change-per-PR / one-PR-at-a-time,
  the agent-vs-human boundary, the PR template + metadata policy.
- **GitHub automation** — CI + release workflows, Dependabot, CODEOWNERS, issue forms, a label
  set, and a one-time `gh` setup script.
- **Documentation system** — ADRs (+ template + index), design-patterns catalogue, spec
  template, session journal, bug ledger, releases, and opt-in i18n.
- **Quality gates** — a CI workflow wired to the chosen toolchain plus the generated
  `consistency_lint.py`.
- **Versioning & comms** — SemVer policy, milestone-driven releases, post-release maintenance,
  and an opt-in announcements workflow.

---

## Go deeper

- [`docs/USAGE.md`](docs/USAGE.md) — the full capability map: what's fixed vs. what you customize.
- [`../AGENTS.md`](../AGENTS.md) — the binding contract (source of truth).
- [`orchestrator/`](orchestrator/README.md) — the engine (interview, generate, placeholders, profiles, recovery).
- [`agent/`](agent/README.md) — the composable role registry.
- [`config/`](config/README.md) · [`learning/`](learning/README.md) · [`maintenance/stay-current.md`](maintenance/stay-current.md) — customization & self-improvement.

---

## License & provenance

EADOS is MIT-licensed (see `LICENSE` at the bundle root). It is reverse-engineered from the
`pbr-cpp-memory-pool` reference project. The canonical repository, full history, and
contribution guide live at <https://github.com/danielPoloWork/pgs-eados>.
