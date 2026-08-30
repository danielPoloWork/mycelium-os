---
id: BUG-0008
title: a UTF-8 byte-order mark hides frontmatter, so identity and metadata compile as prose
status: fixed
severity: medium
reporter: internal
discovered: 2026-08-30
affected-versions: "0.1.0, 0.2.0 (introduced by PR #17, roadmap 2.4)"
fixed-in: "0.3.0"
---

# BUG-0008: a UTF-8 byte-order mark hides frontmatter, so identity and metadata compile as prose

## Summary

`split_frontmatter` recognised a frontmatter block only when `---` was at position zero.
A UTF-8 byte-order mark puts it at position three, so a BOM-prefixed document was compiled
as if it had no frontmatter at all: its `title`, `tags`, `collection`, and provenance were
ignored, and the block itself — `mycelium_id` included — became indexed prose that came back
as a search result.

Windows editors emit UTF-8 with a BOM routinely (PowerShell 5.1's `Set-Content -Encoding
utf8`, Notepad, VS Code when configured that way), and Windows is a supported platform.

## Environment

- **Affected versions:** since PR #17 (roadmap 2.4) wrote the frontmatter contract. Present
  in v0.1.0 and v0.2.0.
- **Toolchain / platform:** any; the input is what varies, and BOMs are produced by default
  by common Windows tooling.
- **Configuration:** none — the behaviour was unconditional.

## Reproduction

Found while exercising the real binary in a Windows terminal for roadmap 3.3:

```powershell
Set-Content knowledge\bus.md -Value "# Event Bus`n`nThe bus routes messages." -Encoding utf8
mycelium build .            # pins a mycelium_id, writing the frontmatter block
mycelium search "..." --hybrid
```

```text
3. Retries - ---
mycelium_id: 01M19VGRDZDFY4TSKVY4HGGMRA  (0.015873)
   mycelium://…#mycelium-id-01m19vgrdzdfy4tskvy4hggmra/0?lines=1-3
   --- mycelium_id: 01M19VGRDZDFY4TSKVY4HGGMRA
```

The document's own identity is returned as a passage, under a heading slugged from it.

## Expected vs. actual

- **Expected:** a byte-order mark is an encoding artefact, not content. The fence is on the
  first line either way, and the block is metadata.
- **Actual:** the fence was not at index 0, so the block was body. Two chunks per document
  instead of one, metadata silently ignored, and identity text in the search index.

## Root cause

`split_frontmatter` opened with `if not text.startswith(DELIMITER): return None, text, 0`.
The *identity* path had the BOM handled already — `_ensure_identity` in the orchestrator
strips it before parsing and restores it when writing, which is why pinning stayed correct
and a second build did not re-pin — so the failure was confined to the content pipeline,
where nothing had a reason to look at byte three.

It survived the test suite because every fixture was written by `Path.write_text` /
`str` literals, which never produce a BOM. It survived CI for the same reason. It was found
by running the shipped binary against files a Windows shell had written — the same class of
gap ADR-0010 recorded for console encoding, and the reason that note says to run the real
binary in a real terminal.

## Impact

Medium. No data is lost or corrupted and identity is unaffected, so rebuilds and citations
stayed correct. What degrades is *quality*: affected documents lose their authored metadata
(title, tags, collection, trust), their chunk counts inflate, and retrieval can return a
frontmatter block as evidence — which for a product whose contract is "verbatim cited
passages" is a visible defect. It affects only documents whose files carry a BOM; no file in
this repository's own corpus does (the single BOM-prefixed file lives under a dot-directory
that discovery never enters), so no published measurement is affected.

## Fix / workaround

`split_frontmatter` strips a leading BOM before testing for the fence, and does not return
it with the body — it carries no content, and `normalize_text` removes it from every digest
anyway, so no digest changes. Regression tests cover both a BOM'd frontmatter block and a
BOM'd document that legitimately opens with prose.

Workaround before the fix: save documents as UTF-8 without a BOM.

## References

- Fixing PR: #33 (roadmap 3.3 — found while verifying the CLI by hand)
- Introduced by: #17 (roadmap 2.4)
- `CHANGELOG` entry: `[Unreleased]` → Fixed
- Related: [ADR-0006](../../../adr/0006-adopt-markdown-it-adapter-and-kir-node-fields.md)
  (the frontmatter contract), [ADR-0010](../../../adr/0010-adopt-cli-output-conventions.md)
  (the standing note that Windows behaviour must be checked with the real binary)
