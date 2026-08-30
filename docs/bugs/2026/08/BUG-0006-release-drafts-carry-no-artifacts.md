---
id: BUG-0006
title: the release workflow builds the distribution and drafts the release without attaching it
status: fixed
severity: low
reporter: internal
discovered: 2026-08-30
affected-versions: "0.1.0, 0.2.0 (both releases drafted by this workflow)"
fixed-in: "0.3.0"
---

# BUG-0006: the release workflow builds the distribution and drafts the release without attaching it

## Summary

`docs/workflow/release.md` promises *"CI builds & attaches artifacts on the tag push"*, and
assigns "Build & attach artifacts" to CI in its boundary table. The workflow built them and
then discarded them: the drafted GitHub Release carried **zero assets**, so a published
release offered no wheel or sdist to download.

## Environment

- **Affected versions:** every release drafted by `.github/workflows/release.yml` — v0.1.0
  (published) and v0.2.0 (drafted, unpublished at the time of discovery).
- **Toolchain / platform:** GitHub Actions, `softprops/action-gh-release` v3.0.2.
- **Configuration:** none — the defect is unconditional.

## Reproduction

Push an annotated `v*.*.*` tag and inspect the release the workflow drafts:

```bash
gh release view v0.2.0 --json assets --jq '[.assets[].name]'
# []
gh release view v0.1.0 --json assets --jq '[.assets[].name]'
# []
```

The run's own log shows the build succeeding (`Build (verify the tag builds clean):
success`) immediately before the drafting step, so the artifacts existed on the runner.

## Expected vs. actual

- **Expected:** the drafted release carries `mycelium_os-<version>-py3-none-any.whl` and
  `mycelium_os-<version>.tar.gz`, as `docs/workflow/release.md` step 10 states.
- **Actual:** the release is drafted with generated notes and no assets. `uv run hatch
  build` wrote `dist/` and nothing ever read it.

## Root cause

`softprops/action-gh-release` attaches only what its `files:` input names, and the step
passed none — it set `draft` and `generate_release_notes` alone. The build step's purpose
was worded as *"verify the tag builds clean"*, which is exactly what it did; nobody noticed
that verification had quietly become the whole of it. Nothing failed, so nothing drew
attention: the run was green for both releases.

## Impact

Low. Nobody is served `mycelium-os` from GitHub Releases today (PyPI publishing is not
wired), so no consumer was blocked. What the defect really costs is trust in the written
contract: a maintainer reading `release.md` would reasonably believe the artifacts were
attached and published without checking. Severity is *low* rather than *none* because the
gap survived a full release cycle unnoticed.

## Fix / workaround

Pass `files: dist/*` to the drafting step. Two things landed alongside it, because the same
gap made both necessary:

- a **`workflow_dispatch` trigger** taking an existing tag, so a tag pushed before the fix
  can be re-drafted without moving it — re-running the original run would replay the
  workflow file *as it existed at that tag*, which still lacks the fix;
- a **version-equals-tag check** over the built artifacts, so a tag pushed without a version
  bump fails loudly instead of drafting a release whose assets disagree with its name
  (the invariant in `docs/workflow/packaging.md`).

Workaround for a release already drafted without assets: dispatch the workflow with that
tag, which is how v0.2.0's draft was completed.

## References

- Fixing PR: #29
- `CHANGELOG` entry: `[Unreleased]` → Fixed
- Related: [`docs/workflow/release.md`](../../../workflow/release.md) (the promise),
  [`docs/workflow/packaging.md`](../../../workflow/packaging.md) (the version invariant),
  [BUG-0001](BUG-0001-release-workflow-matrix-context.md) and
  [BUG-0002](BUG-0002-ci-tools-not-on-path.md) — the two previous defects in this same
  workflow, both also invisible until someone read the run
