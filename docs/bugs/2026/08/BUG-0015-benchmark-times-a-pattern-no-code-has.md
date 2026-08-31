---
id: BUG-0015
title: the vector benchmark times repeated mappings in one process, a pattern no code path has, and reported 78 ms where the truth is 31
status: fixed
severity: medium
reporter: internal
discovered: 2026-08-31
affected-versions: "unreleased (measurement introduced by PR #42, committed as a tool by PR #44)"
fixed-in: "0.3.0"
---

# BUG-0015: the vector benchmark times a pattern no code path has

## Summary

`tools/measure_vector_index.py` timed the packed-matrix scan by calling it repeatedly inside
one process, each call creating a fresh `np.memmap` of the same 154 MB file. That costs about
71 ms a call. A process that maps the file **once** — which is what every real code path does
— costs about 31 ms. The benchmark reported the first number as the cold-process cost, and it
reached two ADRs and a docstring in `src/`.

## Environment

- **Affected versions:** unreleased. The measurement pattern arrived with PR #42 (roadmap
  3.12) as an ad-hoc script and was committed as a tool by PR #44 (roadmap 3.14).
- **Platform:** measured on Windows 11 / CPython 3.12; the mechanism is not platform-specific
  but the magnitudes are.

## Reproduction

Time each iteration instead of the median, varying only how many there are:

```text
rounds=1:  32.3
rounds=2:  31.4  71.2
rounds=3:  29.9  70.9  70.5
rounds=5:  32.4  72.8  75.1  74.2  73.2
```

The first query in a process costs ~31 ms; every later one that re-maps the file costs ~71.
Releasing each mapping first (`del` + `gc.collect()`) does not help.

## Expected vs. actual

- **Expected:** a benchmark reports what a code path costs. There are two: a CLI invocation
  maps once and exits, and a long-lived server maps once and re-uses it (`SqliteStore._packs`,
  ADR-0026).
- **Actual:** it reported a third pattern — re-map per query in one process — which no code
  path has, and labelled it "cold process".

## Root cause

The harness's `timed()` helper ran its callable `rounds` times in-process and took the median,
which is the right shape for arithmetic and the wrong one for anything that maps a large file.
Re-mapping a file whose pages are already resident is not free, and the cost is invisible
unless every iteration is printed rather than the median.

Behind that: "cold" was never defined. Cold *disk*, cold *page cache* and cold *process* are
three different measurements, and the harness measured none of them.

## Impact

Medium, and entirely in claims rather than in behaviour. No shipped code path changed. What
changed is that:

- [ADR-0026](../../../adr/0026-pack-the-vectors-into-a-memory-mapped-matrix.md) recorded a
  ~70 ms first query at 10^5 chunks and filed a roadmap item to close a gap that was not open;
- [ADR-0028](../../../adr/0028-keep-the-vector-scan-exact.md) argued a decision against that
  premise (its conclusion survives — see ADR-0030);
- `search_vectors` documented the wrong number for readers of the code.

## Fix / workaround

`timed()` now spawns one child process per sample and times a single query inside it, so the
number reported is the number a CLI invocation pays. The warm pattern was already measured
correctly elsewhere (one mapping, many queries, ~1 ms) and is unaffected.

## References

- Fixing PR: #46 (roadmap 3.16)
- Introduced by: #42 (roadmap 3.12), committed as a tool in #44 (roadmap 3.14)
- Corrected by: [ADR-0030](../../../adr/0030-correct-the-vector-scan-cost-model.md)
