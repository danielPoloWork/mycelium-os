---
id: BUG-0011
title: a quoted YAML key makes frontmatter parse as prose
status: fixed
severity: medium
reporter: internal
discovered: 2026-08-31
affected-versions: "0.1.0, 0.2.0 (introduced by PR #17, roadmap 2.4)"
fixed-in: "0.3.0"
---

# BUG-0011: a quoted YAML key makes frontmatter parse as prose

## Summary

The discriminator that separates a frontmatter block from a document opening with a
thematic break required the block's first line to be a *bare* YAML key. A quoted key —
`'off': idle` — failed the test, so the whole block was compiled as body: the document's
title, tags, and identity were ignored and its metadata was indexed as prose.

Quoted keys are not exotic. YAML 1.1 reads `on`, `off`, `yes`, and `no` as booleans, so
PyYAML *emits* them quoted, and any vault with such a property round-trips into this shape.

## Environment

- **Affected versions:** since PR #17 (roadmap 2.4). Present in v0.1.0 and v0.2.0.
- **Configuration:** none — the behaviour was unconditional.

## Reproduction

```text
---
'off': idle
title: Bussola
---

# Bussola
```

parsed to `Frontmatter()` with `body_line_offset == 0`: no title, no tags, and the three
metadata lines indexed as text.

## Expected vs. actual

- **Expected:** a quoted key is a YAML key. The block declares itself frontmatter and is
  read as frontmatter.
- **Actual:** it read as `---` / prose / `---`, which CommonMark calls two thematic breaks,
  and the document lost its metadata.

## Root cause

`_MAPPING_KEY` was `^[A-Za-z_][A-Za-z0-9_.-]*\s*:(\s|$)`. The discriminator exists to run
*before* YAML does, so that Markdown between two rules is never diagnosed as broken YAML
(ADR-0006) — the design is right, the character class was too narrow.

It was found by a property test: `test_any_yaml_written_frontmatter_round_trips` generates
arbitrary vault properties, and hypothesis eventually drew the key `off`. The test had been
in the suite since 2.4 and passed for months, which is what property tests are for.

## Impact

Medium. Affected documents keep their content but lose their authored metadata — title,
tags, collection, trust — and gain a chunk of YAML in the search index. Identity is
unaffected in practice, because a document with a quoted *first* key and a `mycelium_id`
later in the block would still be re-pinned rather than mis-identified.

## Fix / workaround

The pattern accepts a single- or double-quoted key alongside the bare form. A regression
test pins both, and the thematic-break cases that motivated the discriminator still parse
as body.

Workaround before the fix: put a bare key first in the block.

## References

- Fixing PR: #37 (roadmap 3.7)
- Introduced by: #17 (roadmap 2.4)
- Related: [ADR-0006](../../../adr/0006-adopt-markdown-it-adapter-and-kir-node-fields.md),
  D-022 (a vault's own properties are preserved, never interpreted)
