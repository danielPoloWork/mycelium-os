---
id: BUG-0027
title: nine lines of YAML aliases in a document's frontmatter stall the build indefinitely
status: fixed
severity: medium
reporter: internal
discovered: 2026-09-17
affected-versions: ">=0.2.0,<0.6.0"
fixed-in: 0.6.0
---

# BUG-0027: nine lines of YAML aliases in a document's frontmatter stall the build indefinitely

## Summary

A Markdown document whose frontmatter uses YAML anchors and aliases to describe a large
structure in a few lines — `a0: &a0 [x, x, x, x, x, x, x, x, x]`, then eight levels each
referencing the previous nine times — makes `mycelium build` run without returning. The
build does not fail, quarantine the document, or report anything; it consumes the CPU
until it is killed.

## Environment

- **Affected versions:** every release with the frontmatter parser (roadmap 2.4, v0.2.0)
  up to but not including 0.6.0
- **Toolchain / platform:** any; measured on CPython 3.12.10, Windows 11, PyYAML 6
- **Configuration:** defaults; the document may sit anywhere the build reads, and the
  same block reaches the ingest lane through the Markdown parser plugin

## Reproduction

Found by the 6.3 security review's probes; pinned by
`tests/test_security_controls.py::test_a_yaml_alias_bomb_is_refused_by_name_in_milliseconds`
and, at fixture size, by `tests/fixtures/injection/knowledge/candidate/yaml-alias-bomb.md`.

```text
---
a0: &a0 [x, x, x, x, x, x, x, x, x]
a1: &a1 [*a0, *a0, *a0, *a0, *a0, *a0, *a0, *a0, *a0]
...                                   (through a8)
tags: *a8
---
# Bomb
```

`mycelium build` on a two-document corpus containing that file: no output after 90 s.

## Expected vs. actual

- **Expected:** the document is refused by name and quarantined, and the build finishes
  in the time the other document takes.
- **Actual:** the build never finishes.

## Root cause

`yaml.safe_load` builds the aliased structure in six milliseconds as *shared references*
— nine lists each holding the same nine children — so the parse is cheap. Everything
downstream walks the structure as a tree: pydantic's validation of the `properties`
mapping the non-contract keys land in, and the canonical JSON a digest is taken over
(`canonical_json`), both of which recurse into every reference and therefore into
9⁹ ≈ 387 million leaves. Neither the block's size nor the parse time gave any warning,
because the cost was in the expansion, not the text.

## Impact

Denial of service of the compiler by one authored or ingested Markdown file. No data is
damaged and nothing is written; the build has to be killed and the file found by hand,
because no quarantine record names it. Medium: the failure is total for the build but
local to one machine and one corpus, and D-017 already declares the user's own documents
untrusted content.

## Fix / workaround

Fixed at roadmap 6.3 (ADR-0119): frontmatter is loaded with a `SafeLoader` subclass that
refuses YAML aliases outright — the profile has no use for them — and a block over
`MAX_FRONTMATTER_BYTES` (64 KiB) is refused before it is parsed. Both are a
`FrontmatterError`, which the build and the ingest lane quarantine per document.
Workaround before 0.6.0: remove the offending file; a build never modifies it, so it can
be found by bisecting the tree.

## References

- Fixing PR: #154 (roadmap 6.3, `feat/security-review-pass`)
- `CHANGELOG` entry: `[Unreleased]` → *Security*
- Related: ADR-0119; `docs/security/audit-2026-09-17-review-pass.md` finding F6;
  ADR-0033 (the ingest lane's own cost bounds, which the authored lane now shares)
