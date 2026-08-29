# Dependabot pin-sync — the re-trigger token (optional, for green-by-itself)

This guide is for whoever **operates the EADOS factory repository** (the maintainer of `pgs-eados`,
or anyone who forks/vendors EADOS and runs its CI). It is **factory-only** — generated repositories
render no workflow templates, so they have no pin-drift and do not need this.

## What this is for

The [`dependabot-pin-sync`](../../.github/workflows/dependabot-pin-sync.yml) workflow
([ADR-0013](../docs/adr/0013-dependabot-action-pin-auto-remediation.md)) auto-commits the action-pin
re-sync onto a Dependabot `github-actions` PR (see the
[`action-pins` lockstep](../docs/adr/0009-ci-supply-chain-pinning.md) and
[`tools/sync_action_pins.py`](../tools/sync_action_pins.py)).

The catch: a commit pushed with the default **`GITHUB_TOKEN` does not re-trigger CI** (GitHub's
recursion guard). So with no extra setup the fix *lands on the PR* but the failed `action-pins` check
stays red until the next event or a manual re-run. Pushing that commit with a token that is **not**
`GITHUB_TOKEN` (a GitHub App token, or a PAT) makes CI re-run, so the check goes **green by itself**.

**This is optional.** Without it the auto-fix still lands; you just re-run the check (or merge, since
the templates are now correct). The shipped workflow uses the App token **when its secrets are
present and falls back to `GITHUB_TOKEN` when they are not** — so a fork that configures neither still
gets the fix committed (just not the auto-re-run). Set this up only if you want zero-touch green
checks — most useful once branch protection requires status checks (when the repo is public).

> ⚠️ **Never paste a token or a private key into a chat, an issue, a commit, or a log.** Set secrets
> only via the hidden-input paths below. Treat them like passwords.

---

## Which to choose

| | GitHub App (Option A) | Fine-grained PAT (Option B) |
|---|---|---|
| Works with the shipped workflow | **Yes — already wired** (set two secrets) | Needs a one-line workflow edit |
| Tied to a person | **No** (survives team changes) | **Yes** (breaks if they lose access) |
| Token lifetime | Short-lived (minted per run) | Long-lived (≤ 1 year), **you must rotate** |
| Counts as | The App (a bot identity) | The user's actions |
| Best for | The default — orgs and longevity | A quick personal stop-gap |

**Recommendation:** the **GitHub App** — it is what the shipped workflow uses, and it is not tied to a
person. Use the PAT only if you cannot create an App.

---

## Option A — GitHub App (the shipped path, no workflow edit)

The workflow already mints an App token (`actions/create-github-app-token`) when `SYNC_APP_ID` +
`SYNC_APP_PRIVATE_KEY` are set. You only create the App and store the two secrets.

1. **Create the App.** github.com → *Settings → Developer settings → GitHub Apps → New GitHub App*.
   - Homepage URL: anything (e.g. the repo URL). **Uncheck "Active" under Webhook** (not needed).
   - **Repository permissions → Contents → Read and write** — the *only* permission needed. (The sync
     edits `templates/.github/workflows/*.tmpl` — `.tmpl` files, **not** the repo's real
     `.github/workflows/*.yml` — so the *Workflows* permission is **not** required.)
   - **Where can this App be installed:** *Only on this account*.
2. **Generate a private key** (App settings → *Private keys → Generate*) and download the `.pem`.
   Note the **App ID**.
3. **Install the App** on `pgs-eados` (App settings → *Install App* → select the repo).
4. **Store the two repo secrets** (UI: *Settings → Secrets and variables → Actions*, or `gh`):
   ```bash
   gh secret set SYNC_APP_ID --repo danielPoloWork/pgs-eados                      # paste the App ID
   gh secret set SYNC_APP_PRIVATE_KEY --repo danielPoloWork/pgs-eados < app.pem   # the full .pem
   rm app.pem    # don't leave the private key on disk
   ```
   `SYNC_APP_PRIVATE_KEY` must hold the **full** PEM, including the `-----BEGIN/END …-----` lines.

Done — no workflow edit. The next drifting Dependabot PR re-syncs and goes green by itself.

---

## Option B — Fine-grained PAT (fallback; one workflow edit)

If you cannot create an App, a PAT works — but the shipped workflow prefers the App, so you swap the
token source.

1. **Create the token.** github.com → *Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token*.
   - **Resource owner:** the account/org that owns `pgs-eados`.
   - **Repository access:** *Only select repositories* → **`pgs-eados`**.
   - **Repository permissions → Contents → Read and write** (only this; same *Workflows* note as above).
   - **Expiration:** the shortest you'll tolerate re-issuing (≤ 1 year) — set a rotation reminder; an
     expired token silently drops you back to the `GITHUB_TOKEN` (no auto-re-run) path.
2. **Store it** as a repo secret:
   ```bash
   gh secret set DEPENDABOT_SYNC_TOKEN --repo danielPoloWork/pgs-eados   # paste at the hidden prompt
   ```
3. **Point the workflow at it.** In `.github/workflows/dependabot-pin-sync.yml` set the checkout
   `token:` to the PAT (instead of the App-token output) and drop the App-token step + `HAS_APP` env:
   ```yaml
             token: ${{ secrets.DEPENDABOT_SYNC_TOKEN || github.token }}
   ```

---

## Verify it works

Exercised by the **next Dependabot `github-actions` PR that drifts a shared pin** — no artificial
trigger is reliable for the actions ecosystem. When that PR opens:

1. `eados-ci` runs and the `self-lint` job fails on `[action-pins]`.
2. The `dependabot-pin-sync` workflow fires (Actions tab → it runs only for `dependabot[bot]` PRs),
   runs `sync_action_pins.py --fix`, and pushes the re-sync commit.
3. **With the App/PAT:** that push re-triggers `eados-ci`, which now passes — green with no human
   action. **Without either:** the fix is committed but you re-run the check (or merge, since the
   templates are correct).

Confirm the secrets exist (names only, never values):
```bash
gh secret list --repo danielPoloWork/pgs-eados   # expect SYNC_APP_ID + SYNC_APP_PRIVATE_KEY
```

## Security notes

- **Least privilege:** Contents-write only, scoped to this one repo. Nothing else.
- The token is consumed **only** by the `dependabot-pin-sync` workflow, which is gated to genuine
  in-repo Dependabot PRs (`actor == dependabot[bot]`) and runs from the trusted default branch
  (`workflow_run`, not `pull_request_target`) — see ADR-0013.
- Prefer the **App** (short-lived tokens, not person-bound); **rotate** a PAT before expiry.
- Revoke immediately if leaked: App → regenerate its private key (and re-set `SYNC_APP_PRIVATE_KEY`);
  PAT → delete it in *Developer settings*, then re-issue and re-set the secret.
