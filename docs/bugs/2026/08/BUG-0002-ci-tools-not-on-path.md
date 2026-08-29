---
id: BUG-0002
title: CI invokes hatch/pytest/ruff/mypy bare, but uv sync never puts .venv on PATH
status: fixed
severity: high
reporter: internal
discovered: 2026-08-29
affected-versions: "unreleased (bootstrap scaffold, pre-0.1.0)"
fixed-in: "0.1.0"
---

# BUG-0002: CI invokes hatch/pytest/ruff/mypy bare, but uv sync never puts .venv on PATH

## Summary

Every toolchain step in `.github/workflows/ci.yml` and `.github/workflows/release.yml`
installs dependencies with `uv sync --all-extras --dev` and then invokes the tool by bare
name — `hatch build`, `pytest -q`, `ruff format --check .`, `mypy --strict src`. `uv sync`
provisions a project virtualenv at `.venv/` but does **not** activate it or prepend
`.venv/bin` (`.venv\Scripts` on Windows) to `PATH`, and `astral-sh/setup-uv` does not do it
either. Every such step therefore exits `127`.

## Environment

- **Affected versions:** unreleased — introduced by the bootstrap scaffold (PR #2), before
  any tagged release
- **Toolchain / platform:** GitHub Actions, all matrix cells (ubuntu-24.04, windows-2022,
  macos-14) — platform-independent, `PATH` is wrong on all of them
- **Configuration:** default

## Reproduction

Land any commit that satisfies the bootstrap guard, so the toolchain jobs stop skipping.
PR #5 did exactly that by adding `pyproject.toml`; all six toolchain jobs failed:

```text
/home/runner/work/_temp/....sh: line 1: ruff: command not found
/home/runner/work/_temp/....sh: line 1: hatch: command not found
/home/runner/work/_temp/....sh: line 1: pytest: command not found
##[error]Process completed with exit code 127.
```

Locally: `uv sync` in a clean checkout, then `command -v ruff` — no hit outside `.venv`.

## Expected vs. actual

- **Expected:** each quality gate runs the tool that `uv sync` just installed.
- **Actual:** every gate dies with `command not found` (exit 127) before running. The
  failure is indistinguishable, at a glance, from a genuine lint/test failure.

## Root cause

The workflow templates were written against a `pip install`-into-the-system-interpreter
model, where installed console scripts land on `PATH`. `uv` deliberately isolates into a
project venv instead; reaching its entry points requires `uv run <tool>` (or an explicit
`PATH` export). The defect is in the generator source too — `orchestrator/project.yaml`
`ci.extra_jobs` carries the same bare `ruff … && mypy …` line — so regenerating the
workflow would have reintroduced it.

## Impact

High. This is not a cosmetic defect: it disables **every** automated quality gate the
repository has — build, test, format, lint, benchmark — while presenting as red CI rather
than as absent CI. On the release path (`release.yml`) it breaks the tag build at the worst
possible moment, the same latent-breakage class as [BUG-0001](BUG-0001-release-workflow-matrix-context.md).

## Fix / workaround

Fixed in the PR #5 CI-repair commit: every bare tool invocation is routed through
`uv run` in `.github/workflows/ci.yml` (build, test, lint, benchmark),
`.github/workflows/release.yml` (tag build), and the `ci.extra_jobs` generator block in
`orchestrator/project.yaml`. `CHANGELOG.md` `Fixed` entry added in the same PR.
`fixed-in: 0.1.0` = the first tagged release that will contain the fix (merged pre-release).

The declared commands in `project.yaml` `toolchain.commands` are deliberately left bare —
they are the project's canonical, runner-agnostic commands; `uv run` is the CI-side
invocation wrapper, not part of the command's identity.

## References

- Fixing PR: [#5](https://github.com/danielPoloWork/mycelium-os/pull/5)
- Related: [BUG-0001](BUG-0001-release-workflow-matrix-context.md) (same workflow, same
  latent-breakage class), [BUG-0003](BUG-0003-bootstrap-probe-too-coarse.md) (the guard
  that should have kept these jobs skipped until the toolchain existed)
