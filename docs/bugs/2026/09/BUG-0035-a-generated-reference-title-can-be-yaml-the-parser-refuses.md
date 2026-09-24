---
id: BUG-0035
title: a reference-profile document can carry a title YAML refuses, so the corpus compiles short of its stated size
status: fixed
severity: low
reporter: internal
discovered: 2026-09-23
affected-versions: ">=0.6.0"
fixed-in: "1.0.0"
---

# BUG-0035: a reference-profile document can carry a title YAML refuses, so the corpus compiles short of its stated size

## Summary

`tools/benchmark_reference_profile.py` writes each generated document's frontmatter as
`title: <a harvested heading>`, escaping nothing but the colon. A heading that begins with
a YAML indicator — a backtick — or with a quoted string followed by more text is not valid
YAML in that position, so the document's frontmatter does not parse, the build quarantines
it, and the corpus the budgets are stated against compiles **short of the size it names**.
Found at roadmap 7.4, whose 1 000-document corpus compiled 998.

## Environment

- **Affected versions:** the generator since it landed (PR #155, roadmap 6.4). Whether a
  given run is affected depends on which headings the harvest finds, so it moves with the
  repository's own `docs/`.
- **Toolchain / platform:** any.
- **Configuration:** reproduced at seed 20260924 over `docs/` at `9b8d8cc`.

## Reproduction

```text
$ python tools/measure_cache_ceiling.py --out <scratch> --seed 20260924 --scales 1000 \
      --rounds 1 --harvest-root <git archive 9b8d8cc docs>
--- reference profile, 1000 documents: 998 documents, 4970 chunks ---

knowledge/part-002/doc-00298.md  title: `<word>` is how documentation writes a placeholder (298)
knowledge/part-007/doc-00785.md  title: "Quantified at 1.0" now means Milestone 7 (785)
```

Both raise `FrontmatterError` from the adapter — correctly: the first is a reserved
indicator at the start of a plain scalar, the second a quoted scalar with text after it.

## Expected vs. actual

- **Expected:** a document per index, each compiled, so *1 000 documents* means a thousand.
- **Actual:** a document whose title is not valid YAML, quarantined; the corpus is 998.

## Root cause

`_document()` formats the title with an f-string and `title.replace(':', ' -')`, which
escapes one YAML-significant character out of several. It should emit the title as a YAML
string — through the YAML library the adapter reads with, or JSON's string form, which YAML
accepts.

## Impact

Low. Every arm of a measurement sees the same corpus, so a comparison inside one run is
unaffected, and a count that is two short is two tenths of a percent. What it undermines is
the claim a report makes when it says *at the stated conditions*: the cold-build budget is
stated at 1 000 documents, and a run that compiles 998 is reporting a neighbouring size.
Roadmap 7.4's report says 998 wherever it matters. **Wider than first thought**: reading
every published manifest's `scales[].documents` at the fix found that no reference-profile
run had ever compiled the size it named — 998 of 1 000 on 2026-09-17, 998 / 2 493 / 4 988 on
2026-09-19, 249 / 999 / 2 498 / 4 989 on 2026-09-20, and 249 of 250 in 7.6's own before run
— so the cold-build budget spec 01 §8 states at 1 000 documents had never been measured at
1 000 until the after run.

## Fix / workaround

Fixed at roadmap 7.6, with BUG-0034. `_document()` writes the title as a JSON string, which
YAML reads as a double-quoted scalar, so a heading opening with a backtick, a quote, a dash or
a hash survives as the title it is; `tests/test_reference_profile_generator.py` parses six
such shapes through the adapter. And `compiled_all()` refuses a run whose build compiled
fewer documents than were generated — `benchmark_reference_profile.py`'s cold-build and
profile measurements and `measure_cache_ceiling.py`'s generated scales all call it — so a
corpus that quarantined a document can no longer be reported at the size it names.

## References

- Fixing PR: #N (roadmap 7.6)
- `CHANGELOG` entry: [Unreleased] › Fixed
- Related: [BUG-0034](BUG-0034-the-reference-profile-harvests-one-of-the-two-corpora-it-names.md),
  roadmap 7.4 ([ADR-0154](../../../adr/0154-price-the-remote-cache-before-its-trigger-and-give-the-trigger-a-reading.md))
