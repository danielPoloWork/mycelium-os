# ADR-0013: Dependabot action-pin auto-remediation

## Status

Accepted

## Context

[ADR-0009](0009-ci-supply-chain-pinning.md) SHA-pins the EADOS-authored workflow surfaces and adds
the `action-pins` lockstep gate: a SHA-pinned action shared by the factory CI
(`.github/workflows/ci.yml`) and the rendered templates (`templates/.github/workflows/*.tmpl`) must
pin the same commit. Its 2026-06-27 addendum added `tools/sync_action_pins.py` so the re-pin is one
deterministic command. But a command is still a manual step: Dependabot's `github-actions` ecosystem
only edits real workflow files, never the `.tmpl` copies, so **every** shared-pin bump drifts the
templates and the gate blocks the PR until a human runs the fix.

Removing that last manual step means CI must run `--fix` and commit the result back onto the
Dependabot PR. Two GitHub Actions facts constrain how:

- **Dependabot PRs run with a read-only `GITHUB_TOKEN`** (a 2021 hardening) — a `pull_request`-
  triggered job cannot push back.
- **`pull_request_target`** grants a write token *and* secrets but is a well-known privilege-
  escalation footgun if it checks out and executes PR-authored code.

## Decision

Add `.github/workflows/dependabot-pin-sync.yml`, triggered by **`workflow_run`** on completion of
`eados-ci` — **not** `pull_request_target`. It:

1. Runs the workflow definition from the **default branch** (trusted; a PR cannot alter what runs),
   with `permissions: contents: write` and nothing else.
2. Is gated to **genuine Dependabot, in-repo PRs that failed CI**:
   `workflow_run.event == 'pull_request'` && `conclusion == 'failure'` &&
   `actor.login == 'dependabot[bot]'` (an actor login cannot be forged) &&
   `head_repository.full_name == github.repository` (excludes forks).
3. Checks out the PR head branch, runs the repo's own deterministic `sync_action_pins.py --fix`
   (which only copies a SHA the factory CI already trusts — it never resolves a tag itself), and
   pushes the result back **only if the templates drifted**.

Token: a **GitHub App** when configured, else `GITHUB_TOKEN`. When the repo secrets `SYNC_APP_ID` +
`SYNC_APP_PRIVATE_KEY` are present, the job mints a short-lived installation token
(`actions/create-github-app-token`) and pushes with it — an App-token push **does** re-trigger CI, so
the failed check goes green with no human action. With the secrets absent it falls back to
`GITHUB_TOKEN`: the fix still lands, but a `GITHUB_TOKEN` push does **not** re-trigger CI (GitHub's
recursion guard), so the check refreshes on the next event or a manual re-run. The App is the owner's
choice — not required for the fix to land. (A repo-scoped PAT works too by swapping the token source;
the App is preferred — not person-bound, and its tokens are short-lived.)

## Consequences

- A Dependabot `github-actions` bump that drifts the templates is **self-healed** — the lockstep
  gate's fix is committed automatically, with no manual companion edit (the goal of #76).
- **No loop, no privilege escalation.** The job is idempotent (no drift → no commit → no push), so a
  `GITHUB_TOKEN` push that does not re-trigger CI cannot loop, and an optional-token push that does
  re-trigger ends when the next run finds the templates already in lockstep (`conclusion == 'success'`
  fails the `failure` guard). `workflow_run` never executes PR-authored code with the write token; the
  unforgeable `actor` + in-repo guards keep non-Dependabot actors (incl. a collaborator pushing to a
  Dependabot branch — which shows as *their* actor) out of the privileged job.
- **Factory-only.** Generated repos render no `.tmpl` files, so they have no template drift and do
  not need this workflow; it lives in the factory's own `.github/workflows/`, not in the templates.
- With the App configured, the check goes **green by itself**; without it the `GITHUB_TOKEN` fallback
  still lands the fix but leaves the stale check until re-run. Full green-by-itself is opt-in via the
  App secrets ([setup guide](../../maintenance/dependabot-sync-token.md)) — no mandatory credential setup.

This supersedes the "tracked separately, its own reviewed PR" note in ADR-0009's 2026-06-27
addendum: the auto-remediation shipped together with the tool. See
[`maintenance/stay-current.md`](../../maintenance/stay-current.md) for the resulting maintainer flow.

## Addendum (2026-06-27)

The optional re-trigger token is wired as a **GitHub App** (owner-configured), preferred over a PAT —
not person-bound, and its installation tokens are short-lived. The shipped workflow mints one via
`actions/create-github-app-token` (SHA-pinned per ADR-0009) when `SYNC_APP_ID` + `SYNC_APP_PRIVATE_KEY`
are set, and otherwise falls back to `GITHUB_TOKEN` (the fix still lands; the check re-runs on the next
event). A PAT remains a swap-in alternative. Setup:
[`maintenance/dependabot-sync-token.md`](../../maintenance/dependabot-sync-token.md).
