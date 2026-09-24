---
id: BUG-0034
title: the reference profile harvests one of the two corpora it names, and says it harvests both
status: open
severity: low
reporter: internal
discovered: 2026-09-23
affected-versions: ">=0.6.0"
fixed-in:
---

# BUG-0034: the reference profile harvests one of the two corpora it names, and says it harvests both

## Summary

`tools/benchmark_reference_profile.py` generates the reference corpus every performance
budget is stated against from prose it *harvests*, and `SOURCE_CORPORA` names two places
to harvest from: this repository's `docs/` and `eval/corpora/uv-docs/knowledge`. The
second directory does not exist and never has — the vendored uv corpus keeps its
documents under `eval/corpora/uv-docs/docs` (`knowledge_dir = "docs"` since PR #43) — and
`harvest()` skips a missing source without a word. So every reference-profile corpus since
the tool was written has been generated from **this project's own documentation alone**,
while the docstring beside the constant says the opposite: *"Two sources rather than one
so the vocabulary is not a single project's."*

## Environment

- **Affected versions:** every reference-profile run since the tool landed (PR #155,
  roadmap 6.4) — all of `docs/benchmarks/`'s generated-corpus reports.
- **Toolchain / platform:** any; the path is wrong on every platform.
- **Configuration:** none.

## Reproduction

```text
$ ls eval/corpora/uv-docs
LICENSE  README.md  docs  eval  mycelium.toml
$ git log --oneline -- 'eval/corpora/uv-docs/knowledge/*'
(nothing: the path has never existed)
```

`harvest(ROOT)` then walks `docs/` only. Found at roadmap 7.4 by exporting the two named
sources from a clean tree before a measurement: `git archive <commit> docs
eval/corpora/uv-docs/knowledge` fails with *pathspec did not match any files*.

## Expected vs. actual

- **Expected:** prose harvested from both named corpora, or a refusal naming the one
  that is missing.
- **Actual:** prose from one corpus, silently, under a docstring that claims two.

## Root cause

A path written for a layout the uv corpus never had, and a loop that treats a missing
source as nothing to harvest — `if not directory.is_dir(): continue`. The only guard is a
floor on the *total* (fewer than 100 blocks or 20 headings is refused), and this
repository's `docs/` alone clears it by fifty times, so the floor could never notice a
source going missing.

## Impact

Low, and bounded, which is why it is recorded rather than fixed in the item that found
it. The build-time numbers in `docs/benchmarks/` measure what they say they measure — a
compile of generated documents of a stated size — and a cold build's cost is not sensitive
to whose vocabulary the prose carries. What is overstated is the *realism* of the query
measurements' term distribution, which the tool presents as not being a single project's.
Every committed report is still a correct measurement of the corpus it records; what it
cannot claim is the second source.

The fix changes every reference corpus generated afterwards, so it has to arrive with its
own re-baseline rather than inside a measurement that wants to stay comparable with the
existing series. Roadmap 7.4's measurement (ADR-0154) was taken on the corpus the tool
generates today, on purpose, and says so.

## Fix / workaround

Point `SOURCE_CORPORA` at `eval/corpora/uv-docs/docs`, and make `harvest()` refuse a
source that does not exist instead of skipping it — filed as roadmap 7.6. Until then, a
reader of any reference-profile report should take the prose to be this repository's
`docs/` at the report's commit.

## References

- Fixing PR: — (open; roadmap 7.6)
- `CHANGELOG` entry: —
- Related: roadmap 6.4 ([ADR-0120](../../../adr/0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md)),
  roadmap 7.4 ([ADR-0154](../../../adr/0154-price-the-remote-cache-before-its-trigger-and-give-the-trigger-a-reading.md)),
  `docs/benchmarks/README.md`
