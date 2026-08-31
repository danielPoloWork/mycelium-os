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
| [BUG-0006](2026/08/BUG-0006-release-drafts-carry-no-artifacts.md) | the release workflow builds the distribution and drafts the release without attaching it | low | fixed | 0.3.0 |
| [BUG-0007](2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md) | the evaluation corpus includes test fixtures, so an unanswerable case is answered and G4 fails | medium | fixed | 0.3.0 |
| [BUG-0008](2026/08/BUG-0008-bom-hides-frontmatter.md) | a UTF-8 byte-order mark hides frontmatter, so identity and metadata compile as prose | medium | fixed | 0.3.0 |
| [BUG-0009](2026/08/BUG-0009-mcp-stdio-uses-the-console-code-page.md) | the MCP server writes its protocol stream in the console code page, corrupting any non-ASCII response | high | fixed | 0.3.0 |
| [BUG-0010](2026/08/BUG-0010-build-indexes-its-own-export.md) | a build indexes the export bundle it just wrote, quarantining the copies as duplicates | low | fixed | 0.3.0 |
| [BUG-0011](2026/08/BUG-0011-quoted-yaml-key-hides-frontmatter.md) | a quoted YAML key makes frontmatter parse as prose | medium | fixed | 0.3.0 |
| [BUG-0012](2026/08/BUG-0012-a-date-property-quarantines-the-document.md) | a date in a non-contract frontmatter property quarantines the whole document | high | fixed | 0.3.0 |
| [BUG-0013](2026/08/BUG-0013-links-to-existing-files-warn-as-unresolved.md) | links to files that exist but are not documents are reported as unresolved | low | fixed | 0.3.0 |
