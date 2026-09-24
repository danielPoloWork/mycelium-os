---
id: BUG-0036
title: a cache report whose saving is negative is refused as malformed, so the reader drops the report that says "no pain" and a test of the round trip depends on the clock
status: fixed
severity: low
reporter: internal
discovered: 2026-09-24
affected-versions: "main from 5b08372 (PR #194) to the fixing commit; no tagged release"
fixed-in: "next release (main after the fixing PR; no tagged release carries the defect)"
---

# BUG-0036: a cache report whose saving is negative is refused as malformed, so the reader drops the report that says "no pain" and a test of the round trip depends on the clock

## Summary

`tools/adoption_report.py` reads `tools/measure_cache_ceiling.py` reports out of issues to
evaluate roadmap 7.1's trigger (ADR-0154). It validated every number with one rule — finite,
non-negative, below a bound — including `ceiling_s`, which is not a duration but a
*difference* of two: the cold build's median less the seeded build's. That difference is
negative whenever the seeded build was no faster, which on a small corpus and a fast disk is
ordinary. The reader returned `None` for such a report, so the one report that says *this
cache saved nothing* was read as no report at all.

The same rule made `test_the_report_is_what_the_trigger_reads_and_carries_no_path` depend
on the machine's clock: it builds a four-document corpus, prints its real report and asserts
the round trip parses. On the `ubuntu-24.04 / python-3.13` cell of PR #194's CI the seeded
build came out slower than the cold one, `ceiling_s` was negative, and the assertion
`len(parsed) == 1` read `0`. The other thirteen cells passed, and PR #194 merged with the one
red check.

## Environment

- **Affected versions:** `main` from `5b08372` (PR #194, 2026-09-24) until the fixing commit.
  No tagged release carries the reader.
- **Toolchain / platform:** the defect is platform-independent; the test's failure needs a
  machine whose file operations are cheap enough for a four-document seeded build to lose to
  a cold one on noise — GitHub's Linux runners, not the Windows machine of record, where a
  real-time scanner makes the cold build reliably slower.
- **Configuration:** none.

## Reproduction

```text
$ python -c "
import sys; sys.path.insert(0, 'tools')
import adoption_report as r
print(r.read_cache_report({'schema': r.CACHE_REPORT_SCHEMA, 'documents': 4, 'people': 4,
    'cold_s': {'p50': 0.61, 'min': 0.58, 'max': 0.66},
    'seeded_s': {'p50': 0.63, 'min': 0.60, 'max': 0.70},
    'ceiling_s': -0.02, 'cold_builds_per_week': 30}, login='x', issue=1))"
None
```

CI: run 35964529226, job *build / ubuntu-24.04 / python-3.13 / test*,
`tests/test_measure_cache_ceiling.py:160: AssertionError: assert 0 == 1`.

## Expected vs. actual

- **Expected:** the report parses; `is_pain` is `False`; the trigger's evidence names it as
  *not counted*, saying the cache saved nothing.
- **Actual:** `read_cache_report` returns `None`; the report is invisible; the test fails on
  a fast machine and passes on a slow one.

## Root cause

`_seconds()` was written for durations, which are non-negative, and applied to a saving,
which is a signed difference. The instrument itself never clamps the difference — its
manifest for roadmap 7.4 records `ceiling_with_seeding_s: -19.844` at 1 000 documents, a
negative saving reported as such — so the reader was stricter than the thing it read.

## Impact

Low. No report has been posted to this repository, so no evidence was lost; and the reports
the defect drops are the ones that could never fire the trigger. What it broke is the
instrument's honesty (a *no pain* report should be counted and shown as not counting) and CI:
a timing-dependent assertion that fails on the fastest cell.

## Fix / workaround

`_saving()` admits either sign, bounded in magnitude; the reader keeps refusing a saving
larger than the build it came from. `CacheReport.describe()` says *saved nothing* for a
non-positive saving instead of printing a negative ceiling. The round-trip test states why it
must not depend on the clock, and `tests/test_adoption_report.py` pins that a negative saving
parses, is not pain, and is shown as not counted.

## References

- Fixing PR: <#NNN>
- `CHANGELOG` entry: `[Unreleased]` → Fixed
- Related: roadmap 7.4
  ([ADR-0154](../../../adr/0154-price-the-remote-cache-before-its-trigger-and-give-the-trigger-a-reading.md));
  [BUG-0020](BUG-0020-the-rebuild-loop-guard-was-covered-by-a-vacuous-test.md) (the other
  test in this ledger whose defect was the test's own premise)
