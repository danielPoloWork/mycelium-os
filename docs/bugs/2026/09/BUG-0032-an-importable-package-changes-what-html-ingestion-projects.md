---
id: BUG-0032
title: what HTML ingestion projects depends on which unrelated packages happen to be importable
status: fixed
severity: medium
reporter: internal
discovered: 2026-09-14
affected-versions: ">=0.4.0"
fixed-in: "0.6.0"
---

# BUG-0032: what HTML ingestion projects depends on which unrelated packages happen to be importable

## Summary

The HTML lane parses through docling's declarative backend, which builds a
`BeautifulSoup(raw, "html.parser")` over the document's raw bytes. BeautifulSoup decides
what encoding those bytes are in, and for a document that declares none it asks an
**encoding detector it binds at import time** from the first of `cchardet`, `chardet` and
`charset-normalizer` it can import (`bs4.dammit.chardet_module`).

Nothing in this repository says which of the three that is. So installing a package that
has nothing to do with ingestion — or resolving a dependency to a different minor version —
can change what an ingestion projects, silently, on a corpus whose evidence documents are
committed.

## Environment

- **Affected versions:** every release with the docling parser in it (roadmap 4.1, v0.4.0).
- **Toolchain / platform:** any. The binding is BeautifulSoup's, on every platform.
- **Configuration:** any configuration whose `[ingest] parsers` dispatches `text/html` to
  `docling`, which is every configuration that ingests HTML at all.

## Reproduction

Found at roadmap 6.6, by the ladder rather than by a test. Adding a `sbom` dependency group
for the SBOM generator pulled `chardet` into the environment; `python
tools/build_ingested_corpus.py --check` then failed, and uninstalling that one package
turned it green again (ADR-0117).

Replayed at roadmap 6.15 without installing anything: `chardet`'s answers for the 62 HTML
sources of `eval/corpora/uv-docs-ingested` were captured in a throwaway environment, bound
to `bs4.dammit.chardet_module` as a lookup table, and the corpus check re-run.

```text
7 of 81 evidence documents differ from a fresh ingestion:
  azure-html-fd66ed92.md      environments-html-8c414191.md   layout-html-ca5b0a5f.md
  coiled-html-88fa9813.md     help-html-3ab4dd91.md
  docker-html-27ce52d7.md     install-python-html-105d4878.md
```

**The count is a property of the detector's version, not of this repository.** Every
`chardet` from 3.0.4 to 6.0.0 reads those seven as `Windows-1252` at confidence 0.73;
7.6.0 reads none of them that way, and `charset-normalizer` 3.5.1 reads none of them that
way either. The seven are the only sources whose non-ASCII content is a single character —
an em dash, or one `✓` — which is too little signal for the detectors that guess wrong and
enough for the ones that do not.

| detector | sources read as windows-1252 | evidence documents that move |
|---|---|---|
| charset-normalizer 3.5.1 (installed today) | 0 | 0 |
| chardet 3.0.4 / 4.0.0 / 5.0.0 / 5.1.0 / 5.2.0 / 6.0.0 | 7 | 7 |
| chardet 7.6.0 | 0 | 0 |

The figure recorded at 6.6 was five. Seven is what the replay produces against the corpus
as committed; the discrepancy is not reconciled and does not need to be, because it is the
finding restated — the number is not this repository's to know.

## Expected vs. actual

- **Expected:** two contributors with the same sources and the same `mycelium-os` produce
  the same evidence documents.
- **Actual:** they produce the same evidence documents if, and only if, they happen to have
  the same encoding detector importable at the same version.

## Root cause

`bs4/dammit.py` binds its detector at import:

```python
chardet_module: Optional[ModuleType] = None
try:
    import cchardet
    chardet_module = cchardet
except ImportError:
    try:
        import chardet
        chardet_module = chardet
    except ImportError:
        try:
            import charset_normalizer
            chardet_module = charset_normalizer
        except ImportError:
            pass
```

`EncodingDetector.encodings` then yields candidates in order — a byte-order mark, a
declaration inside the document, **the detector's guess**, then UTF-8, then windows-1252 —
and the first that decodes wins. None of the 62 HTML sources in the vendored corpus declares
a charset (pandoc's html5 writer emits a bare fragment without `--standalone`), so the
detector's guess is consulted for every one of them, ahead of UTF-8.

Two things this is *not*. It is not a hole in NFR-1: ingestion is authoring-time, and the
build remains a pure function of tiers 1–2. And it is not something `--check` could have
prevented — it detects the divergence after the fact, and cannot tell an environment
difference from a parser change, which is what made the 6.6 failure a puzzle rather than a
report.

## Impact

- The reproducibility of a **committed artifact**. `eval/corpora/uv-docs-ingested` is
  vendored evidence that two people must be able to regenerate identically.
- Any consumer ingesting HTML. A document read as windows-1252 instead of UTF-8 reaches the
  index as mojibake — `’` becomes three characters — so it is indexed, chunked, embedded
  and cited in that state.
- The defect is **invisible on today's resolution**: with `charset-normalizer` 3.5.1 or
  `chardet` 7.6.0 nothing moves. It returns with a dependency resolution nobody reviews.

## Fix

**Fixed at roadmap 6.15 (ADR-0134): the detector is removed from the path rather than
pinned.** `mycelium.ingest.encoding` decodes HTML by a rule this repository owns — a
byte-order mark, then an encoding the document declares, then UTF-8, then windows-1252 —
and the docling adapter hands the backend the decoded text re-encoded as UTF-8 **with a
byte-order mark**, which BeautifulSoup takes as definite. The detector is not agreed with;
it is not asked.

Verified on the corpus, both ways round:

```text
plain:                81 evidence documents match a fresh ingestion   (exit 0)
chardet 5.2.0 replayed: 81 evidence documents match a fresh ingestion (exit 0)
                        fake detector consulted: 0 hits
```

The committed corpus did not move a byte, because every one of its sources is valid UTF-8
and declares nothing, so the rule's third step decides exactly what the detectors that
agree with it decided.

Pinning a detector instead was considered and refused: `beautifulsoup4[charset-normalizer]`
makes one *present*, not *chosen* — bs4 prefers `cchardet` and `chardet` over it — and the
table above shows the answer moving between versions of one detector, which no dependency
pin can hold.

## References

- `src/mycelium/ingest/encoding.py` — the rule; `src/mycelium/ingest/parsers/docling.py` —
  the one call site; `tests/test_ingest_encoding.py` — the rule step by step, and the guard
  that binds a hostile detector and asserts it changes nothing.
- [ADR-0134](../../../adr/0134-own-the-decode-and-stop-asking-whatever-is-importable.md);
  [ADR-0117](../../../adr/0117-sign-and-inventory-the-artifact-and-reserve-the-rung-a-newcomer-stands-on.md),
  where the incident was first recorded and the rule *a tool that is not part of this
  product must not be resolvable alongside it* came from.
- Roadmap 6.6 (found), 6.15 (fixed).
- Sibling in kind: [BUG-0025](BUG-0025-the-corpus-renderer-reads-a-dialect-the-corpus-is-not-written-in.md) —
  the other defect in this corpus where a reader's assumption, not its content, decided what
  the documents said.
