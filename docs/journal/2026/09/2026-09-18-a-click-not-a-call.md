# 2026-09-18 — a click, not a call (roadmap 6.14)

- **Session scope:** roadmap 6.14 — publish `docs-site/` to GitHub Pages, following
  6.13's corpus decision (#161, merged) as its own PR, per the item's own instruction
  not to combine them.
- **PR:** `feat/publish-docs-site`, following M6 through #161.
- **Decision it records:** [ADR-0127](../../../adr/0127-publish-docs-site-from-a-workflow-artifact-tracking-main.md).

## Three decisions, made once each

Artifact-based deploy, not a `gh-pages` branch — the built site joins every other
derived artifact this repository already treats as disposable rather than committed.
Deployed on every push to `main` that touches the site, never on a release tag,
because the site links canonical content pinned at `main` and a tag-gated deploy
would leave it lagging exactly the way the item warned against. Not versioned,
because nobody has asked to read an older build and building that seam ahead of a
real reader is the same mistake this project has refused for the module-facing
surface and the plugin protocols.

## The pins had to be real

Three GitHub Actions needed pinning by commit SHA, per this repository's own
supply-chain posture (threat model B2). I do not have a memorized table of current
action SHAs, and writing a plausible-looking hex string would be a broken workflow
wearing a real one's clothes. Fetched each action's tags from the GitHub REST API
directly, took the SHA behind the newest release tag, and confirmed each one
resolves with a second call before writing it into the workflow. All three came back
`200`.

## Enabling Pages is not this session's to do

`tools/check_repo_settings.py`'s own docstring settled this before I had to decide
it: three settings already documented in `github-setup.md` are reported and never
installed, because each is a repository setting under the owner's account. GitHub
Pages belongs in the same section of that document (§4, next to Discussions and
vulnerability reporting) as the two settings already held to that boundary, so it
gets the same treatment — a `probe` job that reads the repository's own public
`/pages` endpoint with no token at all (confirmed: an unauthenticated call 404s when
Pages is off, not 401 or 403, so nothing needed granting), and does nothing further
while it is off.

That left one more decision smaller sessions might skip past: what command to print
as the remedy. GitHub's REST reference for "create a Pages site" does not say plainly
whether `source` is required alongside `build_type=workflow`, and I was not willing to
print a `gh api` call I could not verify against a setting that is public-facing the
moment it works. The remedy is the Settings page instead — one click, unambiguous,
and the thing `check_pages()` reports afterward is stricter than "does something
exist": it checks that `build_type` actually reads `workflow`, because a repository
already Pages-enabled the legacy branch way would look configured while the deploy
job's upload step failed against it anyway.

## Two links moved, because the comment said this was the change

`pyproject.toml`'s `Documentation` field and the README's own document table both
still pointed at the site's *sources*, with a comment on the first naming exactly
this moment as the one to move them. Neither is visible on a live package index
yet — the publish workflow is dispatch-only and has not been run — so moving them
now costs nothing and saves a future session from re-deriving that the comment was
talking about this PR.

## Lesson

A workflow that depends on a setting nobody has flipped yet should say so in its own
run, not fail silently or fail loud forever. The `probe` → `if: needs.probe...` shape
already existed in this repository's own `ci.yml` for exactly this reason (the
toolchain-not-installed-yet case at Milestone 1) — reusing it here was cheaper than
inventing a new way to be quiet about the same kind of gap.
