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

If a tag was pushed before a fix to this workflow (or the drafting step failed after the
build), re-run it from the default branch rather than moving the tag:
`gh workflow run release.yml --ref main -f tag=v<X.Y.Z>`. Re-running the original run
would replay the workflow file *as it existed at that tag* (BUG-0006).


## Boundary

| Action | Who |
|---|---|
| Re-bless `ours/release` (its own PR, both arms) | Agent |
| Bump version, roll changelog, draft notes | Agent |
| Open / merge the release PR | **Human** |
| Create & push the annotated tag, then the **draft** release (CI drafts it on tag-push) | Agent |
| Publish the GitHub Release (click **Publish**) | **Human** |
| Build & attach artifacts | CI |


Agents never publish releases, never amend or delete published tags, and only delete-and-
repush an *unpublished* tag whose release run visibly failed.
