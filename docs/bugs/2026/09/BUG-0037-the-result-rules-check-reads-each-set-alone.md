---
id: BUG-0037
title: the result-rules check reads each release set alone, so an arm that loses everywhere else is reported as earning the default
status: fixed
severity: medium
reporter: internal
discovered: 2026-09-25
affected-versions: ">=0.6.0"
fixed-in: "1.0.0"
---

# BUG-0037: the result-rules check reads each release set alone, so an arm that loses everywhere else is reported as earning the default

## Summary

`tools/measure_result_rules.py --check` guards roadmap 6.38's refusal (ADR-0153): it fails the
day a heading-proximity boost earns a default the product does not ship. Its own docstring states
the bar every ranking change here is held to — *a gain on a release set, **no overall regression on
any set**, and no slice worse than −2 % anywhere* — but the check tested each release set on its
own. An arm that gained on one release set and lost on every other one was reported as earning.

## Environment

- **Affected versions:** since the runner landed (PR #188, roadmap 6.38).
- **Configuration:** any; the defect is in the arithmetic.

## Reproduction

Roadmap 7.10 moved eighteen sections of `README.md` into `docs/how-it-works.md`, promoting them
from H3 to H2, which changed the heading depths of this repository's own corpus. The ladder then
stopped at *result rules*:

```text
a heading-proximity arm now earns a default this product does not carry:
ours/release depth^1.05 +0.23%, ours/release depth^1.05 within-ten +0.24%.
```

in the same run that measured `depth^1.05` at **−18.95 %** on `uv/release` and **−20.71 %** on
`uv-ingested/release`. `tests/test_result_rules.py` now pins that shape.

## Expected vs. actual

- **Expected:** an arm earns the default only if it clears the bar read across every set.
- **Actual:** any release set with a gain and no slice past the floor on *that set* was enough.

## Root cause

The earning condition was evaluated inside the per-set loop — `set_name == "release" and
overall > 0 and delta >= SLICE_FLOOR` — so the "no overall regression on any set" half of the bar
was never applied, and the slice floor only on the set that gained.

## Impact

Medium, because it fails in the unsafe direction for a *guard*: a false alarm on a refusal is
cheap, but the same code would equally have let a real, one-corpus gain look like a mandate to flip
a default, which is the re-fit the bar exists to refuse. It surfaced as a false alarm, on this
repository's own corpus, which moves with every pull request.

## Fix / workaround

`earning_arms()` collects each arm's reading on every set and applies the whole bar at once: a
gain on some release set, no overall regression on any set, no slice below the floor anywhere.

## References

- Fixing PR: #202 (roadmap 7.10, the change that exposed it)
- `CHANGELOG` entry: [Unreleased] › Fixed
- Related: roadmap 6.38 ([ADR-0153](../../../adr/0153-decide-spec-04-s4s-result-set-rules-on-evidence.md)),
  roadmap 7.10 ([ADR-0159](../../../adr/0159-keep-the-front-door-to-what-a-first-reader-needs-and-move-the-rest-with-its-citations.md))
