---
id: BUG-0023
title: the docling adapter spells a relative hyperlink with the ingesting machine's path separator, so a projection differs between Windows and Linux
status: fixed
severity: low
reporter: internal
discovered: 2026-09-11
affected-versions: "0.4.0 (introduced by PR #50, roadmap 4.1)"
fixed-in: "0.5.0"
---

# BUG-0023: the docling adapter spells a relative hyperlink with the ingesting machine's path separator, so a projection differs between Windows and Linux

## Summary

docling types a relative `href` as a `pathlib.Path`, and the adapter turned every hyperlink
into a string with `str()`. On Windows that spells `../../guides/integration/bazel.md` as
`..\..\guides\integration\bazel.md`: the separator of the machine that ran the parser, not
the one the source was written with. The KIR — tier 1, custody-stored, never committed —
therefore differed between platforms for the same bytes.

Noted at roadmap 5.7 (ADR-0079) as changing no output, because the projector rendered no
reference nodes and resolution normalised separators anyway. Roadmap 5.18 makes the
projector write link targets into `knowledge/evidence/`, which is committed, and the
vendored ingested corpus is regenerated on the maintainer's Windows machine and reproduced
by CI on Linux (`tools/build_ingested_corpus.py --check`). With this defect in place the
check would have failed on 159 of the corpus's 507 links.

## Environment

- **Affected versions:** since PR #50 (roadmap 4.1), which introduced the docling adapter.
  Present in v0.4.0. Output-affecting only from roadmap 5.18.
- **Configuration:** any HTML or DOCX source with a relative hyperlink, ingested on Windows.

## Reproduction

On Windows, with the vendored ingested corpus's sources:

```python
from mycelium.ingest import Registry
registry = Registry.resolve(parsers=["docling"], connectors=["file"], roots=["eval/corpora/uv-docs-ingested"])
blob = registry.acquire("eval/corpora/uv-docs-ingested/sources/guides/integration/bazel.html")
kir = registry.parse(blob, doc_id="01J1ZC8Q4R6XKQ3F0V9T8B2M7N")
print([node.target for node in kir.nodes if node.kind.value == "link" and node.target and "\\" in node.target][:3])
```

Measured on 2026-09-12 across all 81 sources: 159 link targets carried a backslash. On
Linux the same sources produce none.

## Root cause

`_links` in `src/mycelium/ingest/parsers/docling.py` called `str(target)` on
`item.hyperlink`, which docling declares as `AnyUrl | Path`. A relative `href` is a `Path`,
and a `Path`'s string form is platform-native. The adapter's job is to hand back what the
source said; `str()` handed back what the operating system would say.

## Fix

`_href()` renders a `PurePath` with `as_posix()` and anything else with `str()`. A URL is
untouched; a relative path is spelled the way the source spelled it on every platform.

## Verification

`tests/test_ingest_parsers.py::test_docling_spells_a_relative_hyperlink_as_the_source_did`
hands the adapter a `PureWindowsPath` hyperlink and asserts the POSIX form comes out. The
corpus-level check is `tools/build_ingested_corpus.py --check`, which CI runs on Linux
against the corpus regenerated here.

## Lesson

A parser artifact that "changes no output today" is one feature away from changing committed
output. The note at 5.7 was right to name it; the right time to fix it was then.
