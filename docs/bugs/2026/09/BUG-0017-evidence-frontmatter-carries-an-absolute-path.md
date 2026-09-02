---
id: BUG-0017
title: a projected evidence document records the absolute path of the machine that ingested it
status: fixed
severity: medium
reporter: internal
discovered: 2026-09-02
affected-versions: "0.3.0 (introduced by PR #51, roadmap 4.1)"
fixed-in: "0.4.0"
---

# BUG-0017: a projected evidence document records the absolute path of the machine that ingested it

## Summary

`mycelium ingest` writes an evidence document into `knowledge/evidence/` — the authored
tree, which is Git-tracked and committed (D-021). Its provenance frontmatter carries
`source:`, copied from the URI the file connector produced, and that URI was
`path.as_uri()`: an absolute `file:///…` path naming the ingesting machine's directory
layout.

Three consequences, in increasing order of seriousness:

1. **The document is not portable.** A reader who clones the repository sees a path that
   does not exist on their machine, naming a directory that is nobody's business.
2. **The same source ingested by two people produces two different documents**, so the
   content digest differs, the build sees a change that is not one, and a corpus of
   evidence documents cannot be committed and re-derived.
3. **It leaks.** `file:///C:/Users/<name>/…` is a username and a local layout, published to
   whoever can read the repository — precisely what D-017's "no telemetry" posture is about,
   arriving through a door nobody was watching.

## Environment

- **Affected versions:** since PR #51 (roadmap 4.1), which introduced the file connector.
  Present in v0.3.0. Visible in a committed artifact only from PR #53 (roadmap 4.3), which
  is what started writing evidence documents.
- **Configuration:** any ingestion of a local file, which is every ingestion v1 supports.

## Reproduction

```bash
mycelium ingest sources/cache.pdf
head -5 knowledge/evidence/cache-pdf-6ca97856.md
```

```yaml
---
title: cache.pdf
origin: ingested
source: "file:///C:/Users/Polo/AppData/Local/Temp/.../spike/sources/cache.pdf"
source_digest: "sha256:6ca9785679d598e440836e8ca6dc081a1c9337add22440ba0f1d67b2922ad791"
---
```

## Root cause

`FileConnector.acquire` built the blob's `source_uri` with `Path.as_uri()`, which is
absolute by definition. Nothing downstream reinterpreted it: the pipeline copies the blob's
URI into the projection's provenance verbatim, which is correct — the projector should not
be inventing provenance — so the only place that could have known better is the connector,
which is the component that knows the roots.

The reason it survived review at 4.1 is that the URI had two consumers at the time — error
messages and quarantine keys — and an absolute path is the *right* answer for both. The
third consumer, a committed document, arrived two items later, and nobody re-asked the
question.

## Fix

`FileConnector` gains a `base` (defaulting to the first declared root, which is the
repository root in every construction) and emits a **relative-path URI reference** —
`file:sources/cache.pdf`, which RFC 3986 permits — for any source inside it. A source
outside `base` keeps the absolute form, because a relative name for it would be a lie
rather than a shorter truth.

The normalisation is exposed as `FileConnector.uri_of` rather than kept private, because it
is also the *lookup* key: quarantine records are filed under the URI acquisition produced,
so `mycelium ingest --forget` has to ask the same question the same way. It previously
rebuilt the key itself with `as_uri()`, and the second copy of the rule is what turned this
fix into a second defect for the length of one test run — `--forget` stopped finding any
record. Both now go through the connector.

## Verification

`tests/test_ingest_connector.py`:

- an acquired URI is relative, and does not contain the root's path;
- it is written against `base`, not against whichever declared root happens to match;
- a source outside `base` keeps `file:///`;
- an acquired URI round-trips: handing it back to the connector acquires the same bytes;
- a space in a filename is percent-encoded, and still round-trips.

`tests/test_ingest_pipeline.py` pins the URI a quarantine record is keyed by, and
`tests/test_cli.py` covers `--forget` finding it.

## Lesson

A field's correct value depends on who reads it, and the readers change. This one was right
for an error message, right for an in-`.mycelium/` lookup key, and wrong the moment the same
string was written into a file that gets committed — with nothing in between to notice,
because each consumer arrived in a different PR.
