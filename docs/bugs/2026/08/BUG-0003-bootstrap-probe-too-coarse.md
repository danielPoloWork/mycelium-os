---
id: BUG-0003
title: bootstrap guard probes only the build manifest, activating toolchain jobs too early
status: fixed
severity: medium
reporter: internal
discovered: 2026-08-29
affected-versions: "unreleased (bootstrap scaffold, pre-0.1.0)"
fixed-in: "0.1.0"
---

# BUG-0003: bootstrap guard probes only the build manifest, activating toolchain jobs too early

## Summary

`.github/workflows/ci.yml`'s `bootstrap` job gates every toolchain job on a single probe —
`compgen -G "pyproject.toml"`. But the jobs it guards need far more than a build manifest:
they invoke `hatch`, `pytest`, `ruff` and `mypy`, which exist on the runner only once a dev
dependency group is declared **and** locked. Roadmap item 1.1 lands `pyproject.toml` with no
dev toolchain at all, so the guard flipped to `ready=true` several roadmap items early and
the jobs failed instead of skipping.

## Environment

- **Affected versions:** unreleased — introduced by the bootstrap scaffold (PR #2), before
  any tagged release
- **Toolchain / platform:** GitHub Actions, `bootstrap` job (ubuntu-24.04)
- **Configuration:** default

## Reproduction

On PR #5 (roadmap 1.1 + 1.5 — build system and version constant only, no test framework,
no linter configs, no dev dependencies):

```text
bootstrap / is the build system in place?   pass    → ready=true
build / ubuntu-24.04  / python-3.12 / test  fail
build / ubuntu-24.04  / python-3.13 / test  fail
build / windows-2022  / python-3.12 / test  fail
build / macos-14      / python-3.12 / test  fail
lint  / ruff + mypy                         fail
benchmark / reproducible perf               fail
```

## Expected vs. actual

- **Expected:** the toolchain jobs stay skipped until the toolchain they invoke is
  installable, then activate by themselves with no edit to the workflow or the profile.
- **Actual:** they activated as soon as the build manifest appeared, three roadmap items
  early, and produced exactly the wall of red the guard was written to prevent.

## Root cause

The probe was derived from `orchestrator/project.yaml`'s `ci.build_manifest` field, which
answers "is there a build system?" — a strictly narrower question than "can these jobs
install and run their tools?". The guard's own comment encoded the wrong assumption: *"The
moment `pyproject.toml` exists every job below runs for real."* That holds only if the
manifest arrives complete with its dev toolchain; the roadmap deliberately splits those
across items 1.1 (build system), 1.2 (pytest) and 1.3 (ruff + mypy configs).

The failures the early activation exposed are catalogued separately as
[BUG-0002](BUG-0002-ci-tools-not-on-path.md) — a real defect that this guard was
inadvertently hiding, and that would otherwise have surfaced at roadmap 1.2.

## Impact

Medium. No production or release-path effect; the damage is to the signal itself. Red CI on
a correct PR trains maintainers to read red as normal, which is precisely the failure mode
the guard exists to prevent — and it blocks the roadmap's own one-item-per-PR cadence
(AGENTS.md §6) by forcing items 1.2 and 1.3 to be dragged into 1.1's PR.

## Fix / workaround

Fixed in the PR #5 CI-repair commit: the probe now requires **both** the build manifest and
a committed `uv.lock`, the definitive signal that the dev toolchain is declared and
resolvable. `pyproject.toml` alone (item 1.1) keeps the jobs skipped; committing `uv.lock`
alongside the dev group (items 1.2 + 1.3) flips them on automatically, preserving the
guard's no-edit-required property. The stale comment and the `::notice` text are corrected
to match, and `ci.build_manifest` in `orchestrator/project.yaml` records the two-signal
semantics so a regeneration cannot silently revert them.

ROADMAP items 1.2 and 1.3 carry a note that the dev group must cover `hatch`, `pytest`,
`pytest-benchmark`, `ruff` and `mypy` before `uv.lock` is committed — otherwise the guard
opens onto a toolchain that is still incomplete.

## References

- Fixing PR: [#5](https://github.com/danielPoloWork/mycelium-os/pull/5)
- Related: [BUG-0002](BUG-0002-ci-tools-not-on-path.md) (the defect this guard was masking),
  ROADMAP items 1.2, 1.3, 1.4
