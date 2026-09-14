# GitHub Repository Setup

The one-time, repo-level configuration that cannot live as a committed file — branch
protection, rulesets, merge strategy, Discussions, Pages, labels, the first milestone. Run
these once, with admin rights, after creating the GitHub repository for `mycelium-os`.
Everything here reproduces the reference project's GitHub governance; the in-repo automation
(CI, Dependabot, issue forms, CODEOWNERS, release draft) ships as files and needs no setup.

> Prerequisites: the [`gh`](https://cli.github.com/) CLI, authenticated (`gh auth login`),
> and `OWNER=danielPoloWork` / `REPO=mycelium-os` exported.

```bash
OWNER=danielPoloWork
REPO=mycelium-os
BRANCH=main
```

## 0. Which of these is actually installed?

```bash
python tools/check_repo_settings.py
```

Asks GitHub and prints one line per step below, with the command to install the ones that
are absent. **It reports and never changes anything** — every step here is a repository
setting under the owner's account, the same boundary `publish.yml` draws around the index
side.

This tool exists because the document you are reading was, for five milestones, a list of
things somebody did once with nothing saying which (roadmap 6.6, ADR-0117). When it was
first run, on 2026-09-14, **three of the six steps had never been installed**: `main` had no
branch protection and no ruleset, private vulnerability reporting was off while `SECURITY.md`
pointed reporters at it, and two labels carried colours the manifest did not declare. The
same failure had already happened once to §2 — `fix`, `refactor` and `security` were missing
until 2026-09-11, found when `gh pr create --label fix` failed.

## 1. Merge strategy — squash only, PR title/body as the commit

```bash
gh api -X PATCH repos/$OWNER/$REPO \
  -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false \
  -F delete_branch_on_merge=true \
  -F squash_merge_commit_title=PR_TITLE -F squash_merge_commit_message=PR_BODY
```

This is why the PR title/body is written "as it should read in `git log` forever"
(AGENTS.md §6.4).

## 2. Labels (one type-label per PR)

> **Run this before the first Dependabot run.** GitHub drops a label a bot requests if it does not
> exist yet — **silently**, with no error anywhere. `.github/dependabot.yml` asks for `ci` / `build`,
> which live in `.github/labels.yml` and only exist once this import has run; until then the first
> batch of bot PRs arrives unlabelled and nothing tells you why (#350).

```bash
# Requires yq. Imports .github/labels.yml idempotently.
yq -o=json '.[]' .github/labels.yml | jq -c . | while read -r l; do
  name=$(jq -r .name <<<"$l"); color=$(jq -r .color <<<"$l"); desc=$(jq -r .description <<<"$l")
  gh label create "$name" --color "$color" --description "$desc" --force
done
```

## 3. Branch protection / ruleset for `main`

Require PRs, a green CI, linear history, and conversation resolution; block direct pushes and
force-pushes. (Agents never push to the default branch — this enforces it server-side.)

```bash
gh api -X PUT repos/$OWNER/$REPO/branches/$BRANCH/protection \
  --input - <<JSON
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["consistency / lint"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": { "required_approving_review_count": 0 },
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true,
  "restrictions": null
}
JSON
```

Add the build matrix contexts (e.g. `build / ubuntu-24.04 / …`) to `contexts` once you have
seen their exact names in the first CI run.

> **Not installed as of 2026-09-14.** `main` accepts a direct push, so AGENTS.md §6.1's
> *"agents never push directly to `main`"* is a rule an agent keeps rather than one the
> server enforces — and it has been broken once already, at roadmap 3.7, where a session's
> work landed on `main` and had to be undone with an authorised force-push. This is the one
> step here whose absence has already cost something.

## 4. Discussions, Pages, and the security policy

```bash
# Enable Discussions (questions/ideas; linked from the issue chooser).
gh api -X PATCH repos/$OWNER/$REPO -F has_discussions=true

# GitHub Pages from the docs/ folder on the default branch (optional doc site).
gh api -X POST repos/$OWNER/$REPO/pages \
  -F "source[branch]=$BRANCH" -F "source[path]=/docs" 2>/dev/null \
  || echo "Pages already configured or needs the web UI once."
```

```bash
# Private vulnerability reporting — the channel SECURITY.md and the issue chooser both
# send a reporter to. There is an API for it; the web UI equivalent is
# Settings → Code security → Private vulnerability reporting → Enable.
gh api -X PUT repos/$OWNER/$REPO/private-vulnerability-reporting

# Free on a public repository, and the control that stops a contributor — or an agent —
# pushing a credential in the first place.
gh api -X PATCH repos/$OWNER/$REPO \
  -F 'security_and_analysis[secret_scanning][status]=enabled' \
  -F 'security_and_analysis[secret_scanning_push_protection][status]=enabled'

# Branches accumulate otherwise; every PR here is squash-merged from a short-lived branch.
gh api -X PATCH repos/$OWNER/$REPO -F delete_branch_on_merge=true
```

> **Not installed as of 2026-09-14.** Private vulnerability reporting was **off**, and it is
> a defect rather than a gap: with it off, an outside reporter following `SECURITY.md`
> reaches an advisory form they cannot submit, and their remaining option is the public
> issue tracker — which is exactly what a disclosure policy exists to prevent. Secret
> scanning and push protection were off too.

## 5. Roadmap milestones — seed every `MN — name`

PRs are delivered against the **roadmap milestones** (AGENTS.md §6.4), so seed **all** of them
from [`ROADMAP.md`](../../ROADMAP.md) up front — the board is then complete before milestone-scoped
delivery begins. Each is titled `MN — <name>` (em-dash, matching the `## Milestone N — <name>`
headers) with a professional description from the milestone's Goal.

```bash
# One POST per roadmap milestone — worked example for Milestone 1:
gh api -X POST repos/$OWNER/$REPO/milestones \
  -f title="M1 — Project bootstrap & CI" -f state=open \
  -f description="The thinnest slice that compiles, tests, and ships under the full quality bar."
```

To generate the create-commands for **every** milestone straight from `ROADMAP.md`, the EADOS
factory ships a helper (available in the in-place model): `python
.eados-core/tools/seed_milestones.py ROADMAP.md` prints the exact `gh api` calls — add `--run` to
execute them. Creating a milestone that already exists returns HTTP 422, so the seeder is
safely re-runnable.

## Re-running

Every command here is idempotent or safely re-runnable. Re-run after changing labels, after a
new CI check name should become required, or when onboarding a second collaborator (then bump
`required_approving_review_count` to 1 and add reviewers to CODEOWNERS).
