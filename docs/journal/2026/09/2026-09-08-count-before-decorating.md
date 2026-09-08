# 2026-09-08 — the four that were two, and had already been done (roadmap 4.32)

- **Session scope:** roadmap 4.32 — four property tests carry timing deadlines on I/O-bound
  work; the prescribed fix is one decorator each (spec 04 §6).
- **PR:** #84 (`test/deadlines-on-io-bound-properties`). Follows #83 (4.29), merged as
  `d263598`.
- **Milestone 4:** 4.32 done; 4.33, 4.34, 4.36 open. No new items filed — deliberately, see
  the last section.

## An item with a prescribed fix is the easiest kind to get wrong

4.32 names the defect, names the instrument, and tells you how many: *"four property tests …
the fix is one decorator each plus the sentence saying why."* The obvious execution is to
find four tests and decorate them. I did not, because two facts about the item were
checkable and neither survived.

**One of the four was fixed an hour before this item started.** `test_any_query_text_is_safe`
is BUG-0021, closed at 4.29 after it failed `ubuntu-24.04` at 501 ms. So the item's count was
already stale by one, and the remaining three were unnamed.

**The count came from a configuration this project refuses.** ADR-0055 records the sentence
that produced it: `--dist load` *"destroys the fixture reuse this suite depends on"* and *"turned
four hypothesis timing deadlines into failures under contention"*. That is a count of failures
under 20-way oversubscription — not a count of tests carrying the defect. Those are different
numbers and only one of them is a property of the code.

## The criterion had to stop being a threshold

The lesson I brought from 4.29 was that my timing readings moved three times — a comfortable
margin, then a local failure, then a CI failure — while the *shape* never moved. The fixture
cost was inside hypothesis's measured window from the day the test was written. So the
question "which tests have this defect" should never have been a timing question.

Structurally, then: a property test has it when its example body, a helper it calls, or a
fixture it requests does filesystem or store setup. Walking all **24** `@given` functions on
that criterion:

| property test | why | exempt since |
|---|---|---|
| `test_any_mutation_sequence_stays_equal_to_clean` | `TemporaryDirectory`, rebuilds a corpus per example | 3.1 |
| `test_any_query_text_is_safe` | `SqliteStore` + `tmp_path_factory` per example | 4.29 |
| the other twenty-two | no filesystem at all | — |

**The population is two and both were already done.** There is no third test to decorate, and
guessing three would have surrendered, silently, the ability to notice a twenty-fold slowdown
in three properties that do not need it.

One thing the walk taught me about writing the walk: my first hint list included `replace(`
for `os.replace`, and it flagged `test_digest_text_ignores_line_endings_and_composition`,
whose `replace` is `str.replace` on a line ending. A guard that cries wolf gets deleted, so
the list is now short and literal and the docstring says what it therefore cannot see.

## Reproducing the four, rather than explaining it away

"The number came from a refused configuration" is a comfortable story, and I had no right to
tell it without running the configuration. So I installed `pytest-xdist`, ran
`-n auto --dist load` on 20 cores, and removed it again.

**1395 s** — within 0.4 % of 4.31's 1389 s, so it is the same measurement — and **zero
`DeadlineExceeded`**. The four do not reproduce. Two other things fail, and neither is a
deadline:

- `test_chunk_json_round_trip_property` — hypothesis's `too_slow` **health check**: *"only
  generated 2 valid inputs after 4.53 seconds"*. Serially it runs at 1-2 ms per example, of
  which 0-1 ms is generation.
- `test_ingest_hostile.py::…[truncated.pdf]` — a **hand-rolled** 5 s wall-clock budget, at
  5.2 s. Its own docstring says it is "generous by two orders of magnitude … the point is to
  catch a defence that stopped working, not to benchmark a CI runner".

The first run of that measurement was worthless and it was my fault: I launched it and then
edited a test file while it ran, so worker gw0 collected 1519 tests and gw17 collected 1523
and xdist aborted on the mismatch. Re-run on a still tree. Not a defect, just a reminder that
a background measurement is only as stable as the tree under it.

## What ships is the rule, not the list

If the population is two and both are handled, the item's remaining value is making sure it
stays that way. So the deliverable is a guard rather than a decorator: any property test whose
example body builds a store or asks for a `tmp_path` must carry `deadline=None`, or the suite
fails and names it with the remedy.

Two companion tests keep it honest. One fails if the walker stops finding property tests —
BUG-0020 was a guard that passed because nothing reached it, and I would rather not write that
twice. The other names the two known members, so the next reader inherits the population
instead of re-deriving it.

## What I chose not to file

The two contention failures are real, measured, and recorded in ADR-0061 — and I filed no
roadmap item for them. Fixing them means suppressing a health check and raising a budget so
the suite survives a configuration ADR-0055 measured at 1389 s and refused. Each suppression
is a permanent loss of signal bought with a counterfactual, and an item asking for it would
be manufacturing work that should not be done.

That is also why 4.32 closes rather than staying open as the "recorded limit" its own text
proposed: the question is answered, and an open item with an empty scope is a standing
invitation to add decorators nobody needs.
