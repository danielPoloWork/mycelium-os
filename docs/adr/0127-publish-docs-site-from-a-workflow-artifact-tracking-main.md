# ADR-0127: Publish docs-site from a workflow artifact, tracking `main`

- **Status:** Accepted
- **Date:** 2026-09-18
- **Deciders:** tech-lead (EADOS delivery agent)
- **Related:** [ADR-0115](0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-of-duplicating.md)
  (built and checked the site this ADR publishes; filed this item as a residual cost),
  [ADR-0126](0126-measure-the-docs-site-before-deciding-whether-it-joins-the-corpus.md)
  (the sibling decision 6.14 explicitly must not land in the same PR as),
  [ADR-0117](0117-sign-and-inventory-the-artifact-and-reserve-the-rung-a-newcomer-stands-on.md)
  (the "reports, never installs" boundary this ADR extends to Pages, and the
  OIDC-over-secrets attestation posture `release.yml` already follows), D-029;
  roadmap 6.2, 6.6, 6.11, 6.14

## Context

6.2 built `docs-site/` and CI checks it on every push (`mkdocs build --strict`), but
nothing serves it: GitHub Pages is not configured for this repository, and no workflow
deploys the built site anywhere. The content is real and the reader of it does not
exist. Two loose ends already pointed at a URL that has to become true —
`pyproject.toml`'s `Documentation` link named the site's *sources* with a comment
saying it moves "in the change that starts publishing it," and `mkdocs.yml` carries a
`site_url` nothing serves — and one contribution-ladder rung is blocked by it:
`CONTRIBUTING.md` rung 2 asks a newcomer to fix documentation they were reading, and
today reading it means cloning the repository or browsing raw Markdown mkdocs was
meant to render.

Three things needed deciding, not merely building.

## Decision

**Artifact-based deploy, never a `gh-pages` branch.** `.github/workflows/pages.yml`
builds the site with `mkdocs build --strict` (the same command the existing `docs` CI
job already runs), uploads it with `actions/upload-pages-artifact`, and deploys with
`actions/deploy-pages`. The built site is never committed anywhere, which matches
every other derived artifact this repository already treats as disposable
(`.mycelium/`, and `site/` itself, both gitignored) — a `gh-pages` branch would be a
second copy of build output living in version control for no reason ADR-0072's own
restatement argument would accept.

**Deployed on every push to `main`, never gated on a release tag.** The site links out
to canonical content pinned at `main` rather than duplicating it (ADR-0115, D-029), so
it is a live view onto the default branch, not a release artifact — gating it on a tag
would leave it lagging between releases, which the item itself names as "its own
defect." It is also the more direct fix for the blocked rung: a merged documentation
correction has to be visible without waiting for the next cut, or rung 2's promise
("a PR that corrects a step that did not run is merged on sight") is kept in the
repository and not for the reader it was written for. The workflow's `paths:` filter
(`docs-site/**`, `mkdocs.yml`, `src/mycelium/**` for the mkdocstrings reference,
the workflow file itself) keeps an unrelated push from triggering a deploy that
changes nothing.

**Not versioned.** Pre-1.0 there is exactly one build, tracking `main`, matching the
choice `docs-site/project.md`'s own links already made. The one place an older reader
needs a stable answer — what is still guaranteed to work — is the compatibility
promise, and it already lives at a permanent path (`docs/compatibility.md`) linked to
from the site rather than rendered inside it. A versioned build (`mike`, most commonly)
is real complexity to carry for a reader who has not appeared yet; it is deferred to
the day one does, on this project's standing refusal to design an interface from a
sample of nobody.

**Enabling Pages is reported, never executed.** This repeats the boundary
`tools/check_repo_settings.py` already draws for branch protection and private
vulnerability reporting: a repository setting under the owner's account is theirs to
flip. The `probe` job reads the repository's own public Pages metadata — an
unauthenticated `GET /repos/{owner}/{repo}/pages` on a public repository returns 404
when unconfigured rather than 401/403, verified before writing this, so no token and
no added permission is needed to ask. Absent, the `build` and `deploy` jobs do not run
at all, and the run prints the one owner action that unblocks them. `check_pages()`
joins the same survey `check_repo_settings.py` already runs, so the finding is
discoverable outside a workflow log too, and it checks more than presence:
`build_type` must read `workflow`, because a repository already Pages-enabled the
legacy way (a branch source) would report as configured while `upload-pages-artifact`
still fails against it — a false green is worse than an absent one.

**The one-time enable step is a web-UI click, not a `gh api` call.** GitHub's REST
documentation for "create a Pages site" does not consistently state whether `source`
is required alongside `build_type=workflow`, and this repository's convention for
security- or scope-relevant settings is to test the exact command before printing it
as a remedy (every other `check_repo_settings.py` remedy is a verified, idempotent
`gh api` invocation). A guessed command against a public-facing setting risks a
confusing failure for a one-click alternative that cannot fail the same way; the
remedy printed here is the Settings page instead.

**Two links move with this PR**, because this is the change ADR-0115's own comment
and roadmap 6.11's own precedent both name as the moment to move them: `pyproject.toml`'s
`Documentation` URL now names the Pages URL rather than the sources tree, and the
README's own document table gains it beside the existing local-preview instruction.
Neither is visible on a live package index yet — `publish.yml` is `workflow_dispatch`
-only and has not been run — so there is no dead link on an index page in the
meantime, only a link that resolves the moment the owner's one Settings step lands.

## Alternatives Considered

- **Serve from a `gh-pages` branch built by `peaceiris/actions-gh-pages` or
  equivalent.** Rejected on the reasoning above: it commits build output, which this
  repository does not do for any other derived artifact, and it is a third-party
  action with write access to a branch where `actions/deploy-pages` needs none of that
  — the artifact upload/deploy split has no branch to push to and nothing to force-push
  over on a re-run.
- **Deploy on the release tag, alongside `release.yml`.** Considered because it would
  give the site a version to match the package's; rejected because the site is
  explicitly *not* a release artifact under D-029/ADR-0115's design (canonical content
  linked at `main`, never duplicated or pinned to a tag), and the item itself names the
  lag this would introduce as a defect.
- **Enable Pages from this workflow with `gh api -X POST .../pages -f
  build_type=workflow` on first run, using a token with `administration: write`.**
  Rejected twice over: it would need a permission scope no other workflow in this
  repository holds (widening the supply-chain surface ADR-0116/ADR-0117 have been
  narrowing), and it would be an agent flipping a public-facing repository setting
  the owner never asked for in this session — the same line `check_repo_settings.py`
  already refuses to cross for branch protection and vulnerability reporting.
- **Version the site with `mike` now, pre-emptively.** Rejected for the reason named
  in the decision: nobody has asked to read an older version, and building the seam
  before it is needed is exactly what ADR-0086 and ADR-0114 both refused for the
  module-facing surface and the plugin protocols, for the same underlying reason — a
  design taken from no real consumer is a guess wearing infrastructure.
- **Gate the deploy job on the corpus decision (6.13) landing first, in case docs-site
  joining the corpus changed the site's content.** Unnecessary: 6.13 (ADR-0126) changed
  what the compiler indexes, not what mkdocs renders, and it merged as its own PR
  before this one started, exactly as the item asked — the two never needed to touch.

## Consequences

- **The contribution ladder's second rung is unblocked** once the owner's one Settings
  step lands: a reader reaches rendered documentation instead of raw Markdown, and a
  merged fix to it is live within one workflow run of merging.
- **A new workflow, gated cleanly.** `.github/workflows/pages.yml` adds one new
  concurrency group (`pages`) and one new environment (`github-pages`); neither
  collides with `release-${{ ... }}` or `publish-${{ ... }}`. Dependabot's existing
  `github-actions` group (`.github/dependabot.yml`) picks up the three newly pinned
  actions on its normal weekly cadence — nothing added there.
- **`tools/check_repo_settings.py` gains one more documented step**, following the
  established pattern exactly: three-valued `installed`, a verified remedy or an
  honest admission that a remedy is not worth guessing, and no change to what the
  tool is permitted to do (report, never install).
- **A residual, named cost.** Until the owner's one click, `.github/workflows/pages.yml`
  runs on every qualifying push and does nothing beyond the `probe` job's cheap,
  unauthenticated check — a few seconds of runner time reporting the same finding
  `check_repo_settings.py` already reports. This is accepted rather than avoided: the
  alternative is a workflow that silently does not exist until someone remembers to
  add it, which is the exact failure `github-setup.md`'s own audit (ADR-0117) found
  three times already.

## References

- The workflow: `.github/workflows/pages.yml`. The check: `check_pages()` in
  `tools/check_repo_settings.py`. The one-time step: `docs/workflow/github-setup.md`
  §4.
- Verified before writing: `curl -s -o /dev/null -w '%{http_code}' https://api.github.com/repos/danielPoloWork/mycelium-os/pages`
  → `404` (Pages absent) both authenticated and not, confirming the probe needs no
  token; the pinned commit SHAs for `actions/configure-pages@v6.0.0`,
  `actions/upload-pages-artifact@v5.0.0` and `actions/deploy-pages@v5.0.1` were each
  resolved from that project's own tags API and confirmed reachable via
  `GET /repos/{action}/commits/{sha}` before being written into the workflow.
- [ADR-0115](0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-of-duplicating.md)
  — the site's own design (link out, do not duplicate), which is most of why this ADR
  can decide "not versioned" without a real cost.
