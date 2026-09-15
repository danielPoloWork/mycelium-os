# Release Process

The mechanical step-by-step for cutting a release of `mycelium-os`. The governance
(which SemVer level, how a fix flows, deprecation/security) is in
[`maintenance.md`](maintenance.md); the agent-vs-human boundary is
[`AGENTS.md`](../../AGENTS.md) §11.

## Versioning

**Semantic Versioning 2.0.0**, annotated tags `vMAJOR.MINOR.PATCH`. Start point:
pre-1.0 milestone-driven.

- Pre-1.0: `MINOR` bumps on each completed roadmap milestone; `PATCH` for hotfixes.
- Post-1.0: `MAJOR` for incompatible changes, `MINOR` for additions, `PATCH` for fixes.

## Cutting a release (the steps)

0. **Re-bless `ours/release`, as its own PR, before anything below** (ADR-0112). Our own
   corpus grows with every merge, so the baseline G3 *reports* against goes stale between
   releases and its delta starts reading as a regression when what it records is the incumbent
   diluting — measured at 5.42: over one bless interval our score moved −0.0029 and grep's
   −0.0376. Dating it to a release is what keeps that delta meaningful. Two runs, because
   `write_baseline` writes only the arm it was given:

   ```bash
   mycelium eval . --set eval/release.jsonl --bless
   mycelium eval . --set eval/release.jsonl --retriever grep --bless
   ```

   Carry the per-slice diff in the PR body, and never let this ride with a change under
   `TUNING_PATHS` — a bless beside a retrieval change is the one conjunction that can fit the
   retriever to the set (ADR-0056). To attribute a move rather than merely report it, use
   `python tools/measure_slice_decay.py <ref> [--retriever grep]`.
0b. **Check the repository's own settings and the register's deferrals** (roadmap 6.16,
   [ADR-0118](../adr/0118-make-a-deferral-name-the-condition-that-ends-it.md)):

   ```bash
   python tools/check_repo_settings.py
   ```

   It reports which of [`github-setup.md`](github-setup.md)'s one-time steps are installed and
   whether any accepted risk now rests on a premise that has become void. It **changes
   nothing** — every remedy is a repository setting under the owner's account.

   Here rather than in CI because reading these settings unattended would need a long-lived
   token, and a release is the one moment a maintainer with their own `gh` is already in the
   loop. A non-zero exit does not block the cut on its own: read it, act or record why not,
   and carry the verdict in the release PR body.

1. **Bump the version constant** (__version__ = 'X.Y.Z') in `__about__.py`; update any
   version-check test.
2. **Roll the changelog** — move the `[Unreleased]` entries into a new per-version file
   `docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and add an index row to `CHANGELOG.md`.
3. **Refresh the README** status badge (and milestone table on a MINOR that closes a
   milestone).
4. **Draft release notes** under `docs/releases/v<X.Y.Z>.md`.
5. **Run the consistency lint** (`python tools/consistency_lint.py`) — version lockstep must
   pass.
6. **Open the release PR** — *the maintainer does this*. The agent prepares it.
7. **Merge** — *the maintainer*.
8. **Tag + draft (carry-through)** — the agent runs `git tag -a v<X.Y.Z> -m "<headline>"` and
   `git push origin v<X.Y.Z>` immediately after merge; the tag push lets CI open the GitHub Release
   as a **draft**. The agent always carries the release this far — only **Publish** is the human's.
9. **Publish** the GitHub Release — *the maintainer* (the deliberate human checkpoint).
10. **CI builds & attaches artifacts** on the tag push — the wheel and sdist are uploaded
    to the draft, and the build is refused if the artifact version does not equal the tag.
11. **Publish to the index** — *the maintainer*, by running the **`publish` workflow** by hand
    with the tag and the index (roadmap 6.11). It fires on `workflow_dispatch` and nothing
    else, so no tag push can trigger it; it defaults to **TestPyPI**; and it runs inside a
    GitHub Environment where required reviewers gate the run. Before it uploads it re-checks
    that the tag equals the declared version and runs `tools/check_distribution.py`, because
    a published version is immutable. The index-side setup is in
    [`packaging.md`](packaging.md) § *Turning the publish on*; until that is done, step 11 has
    nothing to publish to and the release stops at step 10.

If a tag was pushed before a fix to this workflow (or the drafting step failed after the
build), re-run it from the default branch rather than moving the tag:
`gh workflow run release.yml --ref main -f tag=v<X.Y.Z>`. Re-running the original run
would replay the workflow file *as it existed at that tag* (BUG-0006).


## Boundary

| Action | Who |
|---|---|
| Re-bless `ours/release` (its own PR, both arms) | Agent |
| Run `check_repo_settings.py` and carry its verdict into the release PR | Agent |
| Install any setting it reports absent | **Human** (repository settings) |
| Bump version, roll changelog, draft notes | Agent |
| Open / merge the release PR | **Human** |
| Create & push the annotated tag, then the **draft** release (CI drafts it on tag-push) | Agent |
| Publish the GitHub Release (click **Publish**) | **Human** |
| Build & attach artifacts | CI |
| Run the `publish` workflow, and approve its environment | **Human** |


Agents never publish releases, never amend or delete published tags, never run the `publish`
workflow, and only delete-and-repush an *unpublished* tag whose release run visibly failed.
An upload to an index is the one act in this process that cannot be undone: a version is
immutable and a name is claimed by its first upload.
