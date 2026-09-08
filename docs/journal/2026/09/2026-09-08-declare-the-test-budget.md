# 2026-09-08 — the flake I did not fix (roadmap 4.29)

- **Session scope:** roadmap 4.29 — a property test failed once and has not since; make the
  next occurrence diagnosable rather than lost (spec 04 §6).
- **PR:** #83 (`test/hypothesis-profile-and-statistics`). Follows #82 (4.35), merged as
  `abdaa33`.
- **Milestone 4:** 4.29 done; 4.32, 4.33, 4.34, 4.36 open. New: [BUG-0021], `high`, fixed
  here — see *The boundary I held, then had to move*.

## The item's discipline was the hard part

`test_node_list_is_always_a_well_formed_ordered_tree` failed once at 4.23 and has passed
every time since. There is a strong pull, meeting an item like that, to go and find the
cause — and every candidate cause is available to imagine: a deadline under load, a
hypothesis internal, a shared-state leak from an earlier test. None of them is *evidence*.
The run persisted no falsifying example and its tail was truncated before the traceback, so
the honest position is the one the item itself takes: **no cause is claimed.**

So the deliverable is not a fix. It is that the *second* occurrence is worth more than the
first — which the item had already worked out, and named two cheap things for.

## What was actually wrong, and it was not the test

Looking for the deadline the flake would have failed against, I found there isn't one — not
in `pyproject.toml`, not in a profile, nowhere. All twenty-three property tests run on
whatever `hypothesis` defaults to, and the pin is `>=6.112` while the installed version is
6.165.10.

That is a real finding independent of the flake: **the timing budget of twenty-three tests
is an unversioned input.** A patch release of a test dependency can move it, and this suite's
headline gate is byte-identical output (NFR-1, G6). It is the same class of problem as the
model cache the conftest already isolates — a value nobody in this repository chose, able to
change the suite's behaviour without a diff.

So the profile states `deadline = 200 ms` — *deliberately the number hypothesis already
uses*. Restating a default feels like a no-op and is not: the value becomes ours, reviewable,
and asserted in `test_hypothesis_profile.py`, so a dependency bump that moves it arrives as
one named failure instead of an intermittent one somewhere else.

## The number I refused to change

The tempting move was `deadline=None` everywhere: the flake class disappears, and a slow
example becomes a line of statistics rather than a failure. I did not take it, for a reason
that only shows up when you read the neighbouring item.

**4.32** holds four property tests whose deadline measures SQLite store creation rather than
the property they assert — 308 ms observed under `pytest-xdist` contention. Any global
change to this number decides that item by side effect: raise it and 4.32's tests quietly
start passing with no record of why; remove it and there is nothing left for 4.32 to measure;
lower it and I have pre-empted its measurement with my own. So the profile is the *seam* 4.32
acts on. One item, one decision — which turned out to matter more than I expected, for the
reason in the next section.

## I got the measurement wrong twice before I got it right

**First reading, one file.** The flaking test at `~ 0-3 ms`, its neighbour at `~ 1-2 ms`,
40x headroom, "no test is near the deadline". Straight into the ADR.

**Second reading, the whole suite.** 23 property tests, and it was wrong: one of them,
`test_any_query_text_is_safe`, came back at `~ 64-152 ms` against the 200 ms deadline. So I
rewrote the ADR around a 1.3x margin and the sentence "serially, with nothing competing".

**Third reading, and the second one was wrong too.** That number was measured while I had
other pytest invocations running on the same machine. My own contention. "Nothing competing"
was simply false, and I had written it in three files. Re-measured in isolation the typical
is 63-74 ms — and then the run *failed*:

```text
hypothesis.errors.DeadlineExceeded: Test took 1075.21ms, which exceeds the deadline
of 200.00ms.
  - Typical runtimes: ~ 63-74 ms
  - Stopped because test was flaky
```

Six runs, each from a deleted example database: five failed. My first explanation was that
the recorded slow example was being replayed by the reuse phase — plausible, and wrong; I
tested it by clearing the database before every run, and the rate held. The CI runners,
meanwhile, are entirely comfortable — 8-10 ms on `ubuntu-24.04`, 5-10 ms on `macos-14`, 40-62 ms on `windows-2022`,
all four cells green. So the honest picture is not "a narrow margin" but "a slow-filesystem
platform defect that fails outright on one machine and nowhere else".

That is [BUG-0021] — the thing 4.32 was filed for, now reproduced rather than inferred from
an xdist measurement. 4.32's own reasoning ("they pass in the shipped serial configuration,
which is why this is filed rather than urgent") does not hold. I put the numbers in its text,
filed the record, and **left the fix there**: one decorator, its item, and folding it in would
have hidden the finding inside a closed one.

That was the right call for about an hour.

## The boundary I held, then had to move

CI went green on the first run — four cells, and I said so. On the second run of the same
branch, `ubuntu-24.04` failed:

```text
hypothesis.errors.DeadlineExceeded: Test took 501.68ms, which exceeds the deadline of 200.00ms
FAILED tests/test_store.py::test_any_query_text_is_safe  [single exception in FlakyFailure]
```

501 ms on a runner whose typical for that test is **8-10 ms**. So this was never a
slow-laptop story: it is a 50-60x stall on a hosted runner, and the test can redden any
branch at random.

That removes the choice. "Leave it to 4.32" was a defensible boundary while CI was green; it
is not a boundary when the red is on the matrix, blocking this PR, and reachable by every
other PR. And "re-run it" is exactly how a flake becomes normal — the harm 4.18 and 4.29 were
both filed against. One `deadline=None` on that one test, BUG-0021 `fixed`, 4.32 still open
for the rest of its scope, and the extension written into ADR-0060 as an addendum rather than
folded in quietly.

Two things I could hand 4.32 on the way out: the fix is one decorator per test, and the
statistics over all 23 property tests found **only this one** above 10 ms per example — so
its "three more behave the same way" is unconfirmed and may be empty. Measure before
decorating.

## The instrumentation earned itself on its first real failure

The CI log did not say "a test failed, good luck". It carried
`@reproduce_failure('6.165.10', b'AITCk8KS')` and the statistics block for every property
test beside it, so the failing example, the typical runtime and the threshold it breached
were all in one place. That is precisely what 4.29 was filed to buy, and it bought it within
hours of landing — on a different test than the one that prompted it
([run 34203353202](https://github.com/danielPoloWork/mycelium-os/actions/runs/34203353202)).

The decision never moved. Keeping 200 ms was right under all three readings — a threshold
fitted to the twenty-one would have failed the store test on Windows CI too, and one
generous enough for the store test would have absorbed 4.32. What moved was an *argument*,
and the ADR now carries the correction rather than the tidier version.

## The refusal that stopped being theoretical

Reproducing the store failure wrote its slow example into the local `.hypothesis/examples`,
where the reuse phase replays it first. Had I cached that database into CI, as hypothesis's
own design suggests, a slow example from *my* filesystem would be replayed on a runner where
the same test finishes in 8 ms, and would fail it for a property that holds.

I refused the cache on reproducibility grounds — a previous run must not decide this one's
result. The demonstration is stronger than the argument: a cached example database
transports a **platform**, not just an example.

## A lead on the original flake, offered as a lead

The item says no cause is claimed, and I am not claiming one. But the same machine produced
a **1075 ms example in a test whose typical is 63-74 ms** — a 15x environmental stall, on a
box with nothing else running. A stall of that size landing inside any of the twenty-one
0-4 ms examples would breach 200 ms, be re-run by hypothesis, pass, and leave precisely the
signature 4.29 describes: failed once, passes on re-run, nothing persisted.

That is a candidate cause with evidence behind it, which is more than the item had — and the
CI failure strengthened it the same day: 501 ms in a test whose typical on that runner is
8-10 ms is a 50-60x stall, observed on a hosted runner rather than my desk. The stall
mechanism is now *observed* on the machines that run the suite; whether one landed inside the
markdown property test in particular is still unknown, so this stays a lead in 4.29's closure
rather than an answer.

## The half that took the actual thinking

"A persisted example database in CI" has two mechanisms, and they are not close to
equivalent.

`actions/cache` is the one hypothesis is designed around: a falsifying example found in one
run is replayed first in the next, so a fixed regression stays fixed. It is also **a cached
input that lets a previous run decide this one's result** — same commit, different answer —
which is exactly the property this repository builds gates to forbid. I refused it and
uploaded an artifact instead, on failure only. Cross-run replay is the price; the diagnosis
is what the item asked for, and the artifact keeps that.

The other lever is smaller and does more than I expected: `print_blob`. It puts
`@reproduce_failure('6.165.10', b'AEFk')` in the failure output itself, which no truncation
of the *database* can take away — and a truncated tail is precisely how the first occurrence
was lost. I proved it rather than trusting the flag, by deliberately failing a property test
and reading the blob out of the output.

## One thing I chose not to add

A test asserting the per-example runtime stays an order of magnitude inside the deadline. It
would have put the headroom claim in CI — and it would have been a timing-shaped assertion
on a shared runner, added while closing an item about a timing-shaped flake. The headroom
belongs in ADR-0060 with its measurement, where it cannot go red on a busy machine.

## Where this leaves the flake

Open, in the only honest sense: unexplained. If it recurs, the run now carries per-example
statistics, a reproduction blob in the log, and the example database as an artifact —
and `HYPOTHESIS_PROFILE=debug pytest <file> --hypothesis-show-statistics` is the documented
next step. That is the whole claim, and the checkbox is flipped on it rather
than on a cause.
