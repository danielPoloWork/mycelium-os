---
id: BUG-0010
title: a build indexes the export bundle it just wrote, quarantining the copies as duplicates
status: fixed
severity: low
reporter: internal
discovered: 2026-08-31
affected-versions: "unreleased (introduced by PR #36, roadmap 3.6)"
fixed-in: "0.3.0"
---

# BUG-0010: a build indexes the export bundle it just wrote, quarantining the copies as duplicates

## Summary

`mycelium export --with-markdown` writes verbatim copies of the corpus into
`export/<snapshot-id>/markdown/`. In a repository with no `knowledge/` directory the whole
tree is the corpus (spec 02 §3), so the next `mycelium build` discovered those copies and
compiled them. Because a copy carries the same pinned `mycelium_id` as its original, the
duplicate-identity guard quarantined it — correctly — and every subsequent build reported a
warning about a file the operator never wrote.

## Environment

- **Affected versions:** unreleased; introduced by PR #36 (roadmap 3.6), never released.
- **Configuration:** repositories whose documents live at the root, which is the layout the
  spec explicitly supports for a plain docs repository.

## Reproduction

```text
mycelium build .                      # 1 document
mycelium export . --with-markdown
mycelium build . --json               # 1 document, 1 quarantined
  document quarantined: export/01M…/markdown/a.md (duplicate mycelium_id 01M…)
```

## Expected vs. actual

- **Expected:** a tool never reads what it writes. `.mycelium/` is excluded by the
  dot-prefix rule; `export/` is the same kind of directory, in plain sight because spec
  03 §9 puts bundles where a human can find them.
- **Actual:** the copies were discovered, compiled, and then rejected by the identity
  guard — a correct outcome reached expensively, and a standing warning that trains the
  reader to ignore warnings.

## Root cause

Discovery excluded dot-prefixed directories and nothing else, and `export/` deliberately
is not one. Nothing had previously written Markdown into the repository, so "never index
your own output" had not needed to be a rule; roadmap 3.6 made it one.

## Impact

Low: nothing is corrupted, no document is lost, and the identity guard contains the damage
by design. What it costs is a permanent false warning on every build after an export, in a
tool whose other warnings are worth reading.

## Fix / workaround

`mycelium.corpus` — the single rule discovery and watch mode now share — excludes the
directories the tool itself writes into, alongside the dot-prefix rule. The exclusion is
structural rather than configurable: indexing your own output is never what anyone means.

## References

- Fixing PR: #37 (roadmap 3.7)
- Introduced by: #36 (roadmap 3.6)
- Related: [ADR-0021](../../../adr/0021-scope-the-corpus-and-gate-the-evaluation.md),
  [ADR-0020](../../../adr/0020-adopt-the-jsonl-interchange-bundle.md), spec 02 §3
