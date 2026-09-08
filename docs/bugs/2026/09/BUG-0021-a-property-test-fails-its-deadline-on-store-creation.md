---
id: BUG-0021
title: a property test fails hypothesis's deadline on SQLite store creation, not on the property it asserts
status: fixed
severity: high
reporter: internal
discovered: 2026-09-08
affected-versions: ">=0.3.0"
fixed-in: "0.4.0"
---

# BUG-0021: a property test fails its deadline on store creation

## Summary

`tests/test_store.py::test_any_query_text_is_safe` asserts that no generated query string can
break FTS5 search. It opens a **new SQLite store per hypothesis example**, so what the
per-example deadline measures is store creation, not the property. On a Windows development
machine it exceeds the 200 ms deadline in **5 of 6 runs, each from a cleared example
database**, with observed overshoots of 269 ms and 1075 ms against a 63-74 ms typical — **and
it went on to fail CI**, on `ubuntu-24.04` / CPython 3.12, where its typical is 8-10 ms:
`Test took 501.68ms`.

Recorded here rather than left in roadmap 4.32 because it is now verified and reproducible,
which [BUG-0015](../08/BUG-0015-benchmark-times-a-pattern-no-code-has.md) established as the
bar for a defect in a verification artifact — the same reasoning
[BUG-0020](BUG-0020-the-rebuild-loop-guard-was-covered-by-a-vacuous-test.md) applied. 4.32
described it from a `pytest-xdist` measurement and reasoned that it "passes in the shipped
serial configuration". It does not, reliably, on this platform.

No product defect: the store, the query path and the injection guard all work. What is broken
is the assurance — an intermittent red on a test whose subject has nothing to do with timing.

## Environment

- **Affected versions:** `>=0.3.0` (the test and its fixture predate the profile work; the
  200 ms deadline has been in force since the test was written, as hypothesis's default).
- **Toolchain / platform:** Windows 11, CPython 3.12.10, hypothesis 6.165.10,
  `mycelium-os` 0.4.0.dev (`main` at `abdaa33`).
- **Reproduced on CI, on the second run of the same branch.** Per-example typicals are
  8-10 ms on `ubuntu-24.04`, 5-10 ms on `macos-14` and 40-62 ms on `windows-2022`
  ([run 34197166624](https://github.com/danielPoloWork/mycelium-os/actions/runs/34197166624),
  all four cells green) — and on the very next run of the same branch the `ubuntu-24.04` /
  CPython 3.12 cell failed with `DeadlineExceeded: Test took 501.68ms`
  ([run 34203353202](https://github.com/danielPoloWork/mycelium-os/actions/runs/34203353202)). A **50-60x** stall on a runner whose typical is 8-10 ms. So this
  is not a slow-filesystem developer-machine defect: it is an intermittent red on any branch,
  which is what took it from `medium` to `high`.

## Reproduction

```bash
uv run pytest tests/test_store.py -q -k any_query_text_is_safe
```

Six runs on the machine above, deleting `.hypothesis/examples` before each so that no run
inherits a remembered example:

```text
run 1: FAIL   run 2: pass   run 3: FAIL
run 4: FAIL   run 5: FAIL   run 6: FAIL
```

The failure, in full:

```text
hypothesis.errors.DeadlineExceeded: Test took 1075.21ms, which exceeds the deadline
of 200.00ms.
...
  - during generate phase (6.00 seconds):
    - Typical runtimes: ~ 63-74 ms, of which < 1ms in data generation
    - 63 passing, 1 failing, and 0 invalid test cases
  - Stopped because test was flaky
```

A second run overshot by less — `Test took 269.32ms` — which is the shape of the fault: the
typical example sits at a third of the budget, so any environmental stall crosses it.

The failing example itself, preserved by the `print_blob` this PR turned on — paste it onto
the test as a decorator to replay that exact case:

```python
@reproduce_failure('6.165.10', b'AIvyiYKlwqcL8L2dpw==')
```

It is a *timing* failure, so replaying it reproduces the input rather than guaranteeing the
overshoot; on a fast filesystem the same example passes.

**It passes inside the full suite, which is why nobody noticed.** Two full-suite runs on the
same machine (`pytest -q`: 1511 and 1517 passed) carried this test green, and so does CI.
Run the file or the test alone and it fails 5 of 6. The plausible reading is a warm store
path — SQLite, the temp directory and the page cache are all exercised by four hundred
earlier tests — which means the failure surfaces exactly when someone is iterating on
`test_store.py` and disappears when they run everything to check. That is the worst possible
shape for being believed.

**The example database is not what drives it.** Once an example has failed, hypothesis
records it and the reuse phase replays it first, so the obvious explanation for a high rate
is a remembered slow example. That was the first hypothesis here and **it is wrong**: the six
runs above each started from a deleted database and five of them still failed. The cost is in
building a store per example on this filesystem, not in which example is chosen.

## Expected vs. actual

- **Expected:** the test fails only when a generated query string breaks search.
- **Actual:** it also fails when opening a SQLite store takes longer than 200 ms, which on a
  slow filesystem it does.

### On CI

```text
hypothesis.errors.DeadlineExceeded: Test took 501.68ms, which exceeds the deadline
of 200.00ms.
FAILED tests/test_store.py::test_any_query_text_is_safe - ... [single exception in FlakyFailure]
1 failed, 1512 passed, 7 skipped in 154.69s
```

The log carried `@reproduce_failure('6.165.10', b'AITCk8KS')` and the statistics block with
it — the instrumentation roadmap 4.29 added, doing its job on the first real failure after it
landed.

## Root cause

The property's fixture cost is inside the measured window. `test_any_query_text_is_safe`
builds a store per example; hypothesis's deadline applies to the whole example body, fixture
work included. The deadline is therefore a **filesystem benchmark with a 200 ms threshold**,
asserted on every example, on every platform.

`tests/test_build_incremental.py` had the same shape and resolved it at roadmap 3.1 with
`@settings(deadline=None)` and a sentence saying why. That is the precedent and the fix.

## Impact

High. Nothing user-visible is wrong — the store, the query path and the injection guard all
work — but the test can fail **any** PR's CI, on any commit, for a reason unrelated to the
change under review. On an affected development machine it is worse than intermittent: 5 of
6 runs is a test that mostly does not pass, on the filesystem this project's maintainer
develops on.

Severity was `medium` while every CI cell was believed green. The `ubuntu-24.04` failure
moved it: a red that arrives at random teaches everyone to ignore red, which is the exact
failure mode roadmap 4.18 and 4.29 were both filed against.

## Fix / workaround

`@settings(deadline=None)` on `test_any_query_text_is_safe`, with the comment saying what the
deadline was measuring — the same instrument and the same reasoning
`tests/test_build_incremental.py` used at roadmap 3.1.

**This was recorded first and fixed second, in the same PR, and the order matters.** While
CI was green the fix belonged to roadmap 4.32, which owns these tests, and taking it early
would have closed that item silently inside a PR titled for 4.29. The `ubuntu-24.04` failure
removed the choice: a reproduced red on the matrix blocks the merge, and leaving it to be
re-run is how a flake becomes normal. The scope extension is stated rather than quiet, and
4.32 stays open for the rest of its scope — with a finding it did not have: measuring all 23
property tests found **only this one** above 10 ms per example, so 4.32's "three more behave
the same way" is unconfirmed and may be empty
([ADR-0060](../../../adr/0060-declare-the-property-test-budget-and-keep-the-falsifying-example.md)).

## References

- Fixing PR: #83 (recorded and fixed in the same PR; see *Fix* for why in that order)
- Discovered while closing roadmap 4.29 (PR #83), which declared the deadline this test fails
  against and is why the number became visible.
- Related: [ADR-0060](../../../adr/0060-declare-the-property-test-budget-and-keep-the-falsifying-example.md)
  (the profile, and why the number was not changed),
  [BUG-0020](BUG-0020-the-rebuild-loop-guard-was-covered-by-a-vacuous-test.md) and
  [BUG-0015](../08/BUG-0015-benchmark-times-a-pattern-no-code-has.md) (the bar for recording a
  defect in a verification artifact), roadmap 4.18 (a flake filed rather than absorbed).
