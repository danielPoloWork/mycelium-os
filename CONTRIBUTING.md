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
- For anything non-trivial, open an issue first to agree on scope before writing code.
  A question that is not a bug or a proposal belongs in
  [Discussions](https://github.com/danielPoloWork/mycelium-os/discussions).
- **What is open and what is not is written down** — see *The ladder* below. Pre-1.0 the
  core is planned through `ROADMAP.md` and an unsolicited feature inside it is unlikely to
  be merged; bug reports, documentation fixes, reserved issues and **plugins** are the four
  places outside work is wanted, and the last of those needs no core change at all.

## The ladder

Five rungs, lowest first. Each is a real way in, and the list is deliberately specific
because "contributions welcome" is not information (roadmap 6.6, ADR-0117).

**1. Use it and say what broke.** The most valuable thing anyone outside this repository
can do right now. Open a
[bug report](https://github.com/danielPoloWork/mycelium-os/issues/new?template=bug_report.yml)
with a minimal
reproduction; a maintainer reproduces and root-causes it before a `docs/bugs/` record
exists, so the reproduction is the contribution. No code required, and nothing here has
been installed by a stranger yet — which means the first person to try it will find
something.

**2. Fix the documentation you were reading when it was wrong.** The tutorial, the how-to
guides and the plugin-author guide under `docs-site/` were written by the people who built
the thing, which is the worst possible position from which to judge whether they work. A PR
that corrects a step that did not run is merged on sight. `docs`-only changes run a
narrower gate (`python tools/verify.py` derives it), so the loop is fast.

**3. Take an issue labelled [`good first issue`](https://github.com/danielPoloWork/mycelium-os/labels/good%20first%20issue).**
These are **reserved**: `AGENTS.md` §6.1 forbids the agent pipeline from taking one, so it
is still there when you arrive. That rule exists because this repository closed 43 roadmap
items in five days during Milestone 5 — without the reservation the label would be an
invitation withdrawn before anyone could accept it. Say on the issue that you are taking it;
nobody else will.

**4. Write a plugin.** The contribution that needs no permission and no core change, and
the one the architecture exists for. A `Connector`, a `Parser`, a `Synthesizer` or a whole
`Module` is its own distribution, resolved through an entry point, held to the plugin API
generation it declares. Start from the cookiecutter and the guide in
[`docs-site/plugin-author-guide.md`](docs-site/plugin-author-guide.md); the contracts it
builds on are frozen and the terms are in [`docs/compatibility.md`](docs/compatibility.md).
A plugin that proves useful can be adopted into `contrib/` (spec 05 §4.3).

**5. Change the core.** Open an issue first. Substantial features become a `ROADMAP.md`
item and usually an ADR before any code, and a change to one of the **five stable
contracts** — identity, KIR, snapshot manifest, MCP tools, plugin protocols — needs an RFC
under `docs/rfc/` (spec 06 §4). This rung is narrow on purpose and the ones below it are not.

Whichever rung you are on: the quality bar in `AGENTS.md` §10 applies to the change, not to
the contributor. A first PR that misses a gate gets told which one.

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
uv run python tools/verify.py
```

`tools/verify.py` is the gate: it reads your diff, derives which checks it implicates —
`docs`, `code`, `retrieval` or `full` — runs them cheapest first, and prints the mode it
chose and why. CI derives the mode with the same script, so a green run locally is the run CI
will make (ADR-0055). The individual commands it wraps, for a tighter loop while you work:

```bash
uv run ruff format --check src tests tools contrib
uv run ruff check src tests tools contrib
uv run mypy --strict src tools contrib/chats/src tests contrib/chats/tests
uv run pytest -q
uv run python tools/consistency_lint.py
```

CI re-runs them on Linux, Windows and macOS.

### When a property test fails intermittently

Property tests run under the `mycelium` hypothesis profile registered in
`tests/conftest.py`: a declared 200 ms per-example deadline, and `print_blob`, so a failure
prints a `@reproduce_failure(...)` line you can paste onto the test as a decorator to replay
the exact example. If a property test fails once and passes on re-run, keep that line — it
is the only durable record of the example. Then:

```bash
HYPOTHESIS_PROFILE=debug uv run pytest tests/test_markdown_adapter.py --hypothesis-show-statistics
```

The `debug` profile drops the deadline, turns on verbose output, and runs 1000 examples
instead of 100. In CI the same evidence is already collected: the build matrix shows
hypothesis statistics, and a red run uploads the example database as an artifact
(ADR-0060).

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
5. Open the PR against `main`, from a branch in your fork. **Anyone may open a pull
   request; only the named reviewers may review and merge** — the owners `.github/CODEOWNERS`
   lists, today the maintainer alone. A reviewer requests changes if needed and merges
   (squash-only). Your first pull request's CI waits for a maintainer to approve its
   workflows — GitHub holds a first-time contributor's runs by design, and the checks start
   once someone looks.

## Code of Conduct

Participation in this project is governed by the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Reporting a security issue

Do not open a public issue. See [`SECURITY.md`](SECURITY.md) for the private disclosure
channel.
