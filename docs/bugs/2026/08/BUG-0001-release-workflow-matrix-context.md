---
id: BUG-0001
title: release workflow references matrix context in a matrix-less job
status: fixed
severity: low
reporter: internal
discovered: 2026-08-29
affected-versions: "unreleased (bootstrap scaffold, pre-0.1.0)"
fixed-in: "0.1.0"
---

# BUG-0001: release workflow references matrix context in a matrix-less job

## Summary

`.github/workflows/release.yml`'s `draft-release` job sets
`python-version: ${{ matrix.toolchain == 'python-3.13' && '3.13' || '3.12' }}` but the job
declares no `strategy.matrix` — `matrix.toolchain` is an undefined context there.

## Environment

- **Affected versions:** unreleased — introduced by the bootstrap scaffold (PR #2), before
  any tagged release
- **Toolchain / platform:** GitHub Actions, `draft-release` job
- **Configuration:** default

## Reproduction

Statically verifiable: the expression references `matrix.*` in a job with no matrix
(actionlint-class finding). At run time the undefined context compares false and the
expression happens to resolve to `'3.12'`.

## Expected vs. actual

- **Expected:** the release job pins its interpreter explicitly.
- **Actual:** it resolves to `3.12` only through an undefined-context comparison —
  correct by accident, brittle under any future edit or stricter workflow linting.

## Root cause

The manifest's shared `ci.setup_steps` block was written for `ci.yml`'s build matrix
(3.12/3.13 cells) and the release template injects the same `{{CI_SETUP_STEPS}}` block
into a matrix-less job. Factory-level gap (shared placeholder, two contexts) — lesson
drafted for the EADOS ledger; found by the 2026-08-29 bootstrap audit (register F1).

## Impact

Low: today's behavior is correct (3.12). The risk is latent breakage of the release path
at tag time — the worst moment to discover it — under future edits or lint hardening.

## Fix / workaround

Fixed in the audit PR: literal `python-version: '3.12'` in `draft-release`. `CHANGELOG.md`
`Fixed` entry added in the same PR. `fixed-in: 0.1.0` = the first tagged release that
will contain the fix (merged pre-release).

## References

- Fixing PR: the bootstrap-audit PR (#4)
- Register: [`docs/security/audit-2026-08-29-bootstrap.md`](../../../security/audit-2026-08-29-bootstrap.md) F1
- Related: factory ADR-0009 §3 (profile-injected steps), EADOS lesson L-0015 (drafted)
