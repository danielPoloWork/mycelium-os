# 2026-09-08 — the flake I did not fix (roadmap 4.29)

- **Session scope:** roadmap 4.29 — a property test failed once and has not since; make the
  next occurrence diagnosable rather than lost (spec 04 §6).
- **PR:** #83 (`test/hypothesis-profile-and-statistics`). Follows #82 (4.35), merged as
  `abdaa33`.
- **Milestone 4:** 4.29 done; 4.32, 4.33, 4.34, 4.36 open.

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
acts on, and today it changes nothing about what passes. One item, one decision.

## And then the measurement changed my mind about the measurement

My first reading was of one file: the flaking test at `~ 0-3 ms`, its neighbour at
`~ 1-2 ms`, 40x headroom, "no test is near the deadline". I wrote that into the ADR. Then
the whole-suite run came back — 23 property tests, serial, 765 s — and it was wrong:

| property test | per example | margin at 200 ms |
|---|---:|---|
| twenty-one others, incl. the flaking one | 0-10 ms | ≥ 20x |
| `test_any_query_text_is_safe` | **64-152 ms** | **1.3x** |
| `test_any_mutation_sequence_stays_equal_to_clean` | 890-1784 ms | already `deadline=None` |

Two things follow, and the second is the reason it was worth running the whole suite rather
than the one file.

**A "measured" deadline would have broken the suite.** Fitting a threshold to the twenty-one
CPU-bound tests gives something like 100 ms at 10x their worst example — defensible-sounding,
and it fails `test_any_query_text_is_safe` on the spot. Setting a global threshold from a
sample of the population is how you ship a flake while believing you removed one. Keeping the
status quo was not the timid option; it was the only number the whole population supports.

**4.32 is less comfortable than its own text says.** That item calls itself "filed rather
than urgent" because the four tests pass in the shipped serial configuration. They do — one
of them at 76 % of its deadline, serially, with nothing else competing. It is one busy
machine away from being the next 4.29. I put the number into 4.32's text and left the fix
there: the decorators are its work, not mine, and merging the two would have hidden this
finding inside a closed item.

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
