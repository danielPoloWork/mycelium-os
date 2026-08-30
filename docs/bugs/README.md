# Bug Ledger

The **source of truth** for defects in `mycelium-os`. One Markdown file per defect,
`BUG-NNNN-<slug>.md`, under a discovery-date tree `docs/bugs/<YYYY>/<MM>/`. `NNNN` is a
globally-monotonic id, never reused or renumbered. Template: [`template.md`](template.md).

A record is created only for a **verified, reproducible** defect. A third-party report is
reproduced and root-caused first; an unsubstantiated report is still recorded — as
`cannot-reproduce` / `rejected` / `duplicate` — so the triage trail is preserved. When a fix
lands, flip the record to `status: fixed`, set `fixed-in`, link the PR, and add the
`CHANGELOG` `Fixed` line in the same PR.

Structural integrity (frontmatter keys, the `status`/`severity`/`reporter` vocabularies,
filename↔`id` and path↔`discovered` agreement, monotonic ids, the index bijection, and that
a `fixed` record names its `fixed-in`) is enforced by the consistency lint's `bugs` check.

## Index

| Bug | Title | Severity | Status | Fixed in |
|-----|-------|----------|--------|----------|
| [BUG-0001](2026/08/BUG-0001-release-workflow-matrix-context.md) | release workflow references matrix context in a matrix-less job | low | fixed | 0.1.0 |
| [BUG-0002](2026/08/BUG-0002-ci-tools-not-on-path.md) | CI invokes hatch/pytest/ruff/mypy bare, but uv sync never puts .venv on PATH | high | fixed | 0.1.0 |
| [BUG-0003](2026/08/BUG-0003-bootstrap-probe-too-coarse.md) | bootstrap guard probes only the build manifest, activating toolchain jobs too early | medium | fixed | 0.1.0 |
| [BUG-0004](2026/08/BUG-0004-ulid-pattern-admits-overflow.md) | the Ulid record pattern admits 26-character strings that overflow 128 bits | medium | fixed | 0.2.0 |
| [BUG-0005](2026/08/BUG-0005-fts-and-semantics-zeroes-queries.md) | one unmatched word returns no results, because FTS5 combines terms with implicit AND | high | fixed | 0.2.0 |
