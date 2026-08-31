---
id: BUG-0013
title: links to files that exist but are not documents are reported as unresolved
status: fixed
severity: low
reporter: internal
discovered: 2026-08-31
affected-versions: "unreleased (introduced by PR #34, roadmap 3.4)"
fixed-in: "0.3.0"
---

# BUG-0013: links to files that exist but are not documents are reported as unresolved

## Summary

The link resolver warned for every authored link it could not turn into an edge, including
links to files that are right there and simply are not part of the corpus — `LICENSE`,
`.github/PULL_REQUEST_TEMPLATE.md`, a path under an excluded directory. Building this
repository produced about 150 such warnings, which is enough to train a reader to skip the
warning stream entirely.

## Environment

- **Affected versions:** unreleased; introduced by PR #34 (roadmap 3.4), never released.
- **Configuration:** any repository that links from its documentation to a non-Markdown
  file, which is most of them.

## Reproduction

```text
mycelium build .
  warning: README.md: unresolved markdown_link [[LICENSE]] - no document matches
  warning: AGENTS.md: unresolved markdown_link [[.github/PULL_REQUEST_TEMPLATE.md]] - …
  … ~150 lines
```

## Expected vs. actual

- **Expected:** a link to a file that exists is not broken. No edge can exist, because the
  target is not a document, and the author did nothing wrong.
- **Actual:** every such link was reported as though the target were missing, drowning the
  warnings that mean something — a link into the corpus that really does not resolve.

## Root cause

ADR-0018 decided that "an unresolvable *or ambiguous* link is a build warning naming the
candidates, never a guess", and the resolver implemented that against the *corpus index*
alone. From the index's point of view a link to `LICENSE` and a link to a deleted document
look identical; only the filesystem can tell them apart, and the resolver never consulted it.

## Impact

Low in mechanism, real in effect: no edge is wrong and no document is affected, but a
warning stream nobody reads is a diagnostic that has stopped working. It also made the CI
evaluation job's output unreadable, which is where it was noticed (roadmap 3.7).

## Fix / workaround

The resolver takes the repository root and, before warning, asks whether the link target
exists on disk relative to the linking document or the root. If it does, no edge and no
warning; if it does not, the warning stands. The test is existence rather than extension:
a Markdown file the corpus excludes is as legitimately unlinked as a PNG.

This repository's build went from ~150 warnings to 3, and the 3 are real — the README
links to explicit `<a id="…">` anchors that a heading-based resolver cannot see.

## References

- Fixing PR: #37 (roadmap 3.7)
- Introduced by: #34 (roadmap 3.4)
- Related: [ADR-0018](../../../adr/0018-build-the-graph-from-authored-links.md)
