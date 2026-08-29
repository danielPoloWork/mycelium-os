# Contributing to mycelium-os

Thanks for considering a contribution. This project is pre-1.0 and single-maintainer
today (see [`.github/CODEOWNERS`](.github/CODEOWNERS)); the process below is written to
scale as more contributors join.

## Before you start

- Read [`AGENTS.md`](AGENTS.md) — it is the authoritative contract for how this repository
  is built, reviewed, and released (persona, source layout, git workflow, documentation
  rules, quality bar). It governs human and AI contributors alike.
- Check [`ROADMAP.md`](ROADMAP.md) for the current milestone and open items, and
  [`docs/bugs/`](docs/bugs/) for known issues, before opening new work.
- For anything non-trivial, open an issue first to agree on scope before writing code —
  this project accepts external contributions only through the deferred-decision triggers
  and RFC process described in the spec (`docs/specs/01_spec_mycelium.md`); wholesale
  unsolicited features are unlikely to be merged pre-1.0.

## Developer Certificate of Origin (DCO)

Every commit must be signed off, certifying you wrote it or otherwise have the right to
submit it under this project's license ([Apache-2.0](LICENSE)):

```bash
git commit -s -m "your commit message"
```

This adds a `Signed-off-by: Your Name <you@example.com>` trailer using your Git
`user.name`/`user.email`. A PR with unsigned commits will be asked to amend and force-push
before merge; see the [DCO text](https://developercertificate.org/) for what you're
certifying.

## Development setup

```bash
uv sync --all-extras --dev
uv run pytest -q
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy --strict src
python tools/consistency_lint.py
```

All five must pass before a PR is opened; CI re-runs them on Linux, Windows, and macOS.

## Making a change

1. Branch from `main`: `<type>/<short-kebab-description>` (`type ∈ {feat, fix, refactor,
   perf, docs, test, build, chore, ci}`) — see [`docs/workflow/git-workflow.md`](docs/workflow/git-workflow.md).
2. Commit with [Conventional Commits](https://www.conventionalcommits.org/), signed off
   (`-s`), one logical change per commit.
3. Update the docs that ship with your change in the same PR — `README.md`, `ROADMAP.md`
   (flip the checkbox), an ADR if you made a non-trivial design decision, `CHANGELOG.md`
   under `[Unreleased]`. See `AGENTS.md` §7.
4. Fill out `.github/PULL_REQUEST_TEMPLATE.md` in full — it is squash-merged into the
   permanent commit on `main`, so write it as it should read in `git log` forever.
5. Open the PR against `main`. A maintainer reviews, requests changes if needed, and
   merges (squash-only).

## Code of Conduct

Participation in this project is governed by the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Reporting a security issue

Do not open a public issue. See [`SECURITY.md`](SECURITY.md) for the private disclosure
channel.
