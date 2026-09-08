# ADR-0060: Declare the property-test budget, and keep the falsifying example

- **Status:** Accepted
- **Date:** 2026-09-08
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.29 (this item), 4.18 (the same family, closed), 4.32 (the seam this
  opens, still open); RFC-0001; spec 04 §6; NFR-1 and gate G6;
  [ADR-0012](0012-adopt-the-g6-determinism-gate.md),
  [ADR-0055](0055-run-the-gates-the-change-implicates.md)

## Context

`test_node_list_is_always_a_well_formed_ordered_tree` failed once, in a full-suite run at
roadmap 4.23 (1439 passed, 1 failed). It passed standalone, passed a second full run of the
same tree, persisted no falsifying example, and exercises `mycelium.markdown`, which the
change under test did not touch. **No cause is claimed, and none is claimed here.** The
failure is one observation, and the tail of the run was truncated before the traceback was
captured — so there is nothing left to analyse.

That is the actual problem this item addresses: not the flake, the *lost evidence*. A
property test that fails once and leaves nothing behind will fail again and leave nothing
behind again, and the second occurrence is worth no more than the first. Meanwhile a flaky
test on the matrix teaches everyone that red CI is normal, which is the opposite of what
every gate here is for — the reason 4.18 was filed rather than absorbed.

Two facts about the suite's current state are the material for a fix:

**The timing budget is unversioned.** All twenty-three property tests run on
`hypothesis`'s library default deadline of 200 ms, because nothing in this repository names
a deadline anywhere. The pin is `hypothesis>=6.112`; the installed version is 6.165.10. A
patch release is free to move that number, and a suite whose headline gate is byte-identical
output (NFR-1, G6) should not carry an input nobody declared. It also means that when a
property test does fail on timing, the threshold it failed against is not written down.

**A failure leaves nothing durable.** Hypothesis records falsifying examples in
`.hypothesis/examples`, which a CI checkout throws away, and it does not print a
reproduction blob unless asked (`print_blob` defaults to `False`). So a CI failure is
recoverable only from the job log, and a local failure only from a terminal buffer.

Measured on 2026-09-08 with `--hypothesis-show-statistics` over the whole suite (23
property tests): **twenty-one report 0-10 ms per example on every platform** — the flaking
test itself `~ 0-4 ms` locally and `~ 0-2 ms` on `ubuntu-24.04` — so a deadline flake there
needs a twenty-fold slowdown or worse. Two do not, and the distribution decides what follows:

| property test | per example | margin at 200 ms |
|---|---:|---|
| twenty-one others, incl. the flaking one | 0-10 ms | at least 20x |
| `test_any_query_text_is_safe` (SQLite store per example) | 8-10 ms Linux CI, 40-62 ms Windows CI, **63-74 ms Windows dev** | 3x on Windows CI — **and it fails outright on a Windows dev machine** |
| `test_any_mutation_sequence_stays_equal_to_clean` (rebuilds a corpus) | 890-1784 ms | already `deadline=None` |

The store test is roadmap 4.32's, and measuring it produced a finding that item did not have:
it does not merely sit near the deadline, it **exceeds** it — 269 ms and 1075 ms observed
against a 63-74 ms typical, failing **5 of 6 runs from a cleared example database** on a
Windows development machine. And then, on the next CI run of this very branch, it failed
`ubuntu-24.04` too: `Test took 501.68ms` where that runner's typical is 8-10 ms, a 50-60x
stall ([run 34203353202](https://github.com/danielPoloWork/mycelium-os/actions/runs/34203353202)). That is now
[BUG-0021](../bugs/2026/09/BUG-0021-a-property-test-fails-its-deadline-on-store-creation.md),
`confirmed`, and the fix stays 4.32's.

> **A correction, kept rather than tidied away.** The first version of this ADR said
> "64-152 ms, a 1.3x margin, serially, with nothing competing". The 152 ms half was measured
> while other pytest invocations were running on the same machine — my own contention, not a
> clean serial figure — so the "nothing competing" clause was false. Re-measured in
> isolation the typical is 63-74 ms, and the honest worst case is not a narrow margin but an
> outright failure. The decision below did not change; one of its arguments was wrong, and
> the record says so rather than quietly reading better.

## Decision

**Declare the budget in one place, and make a failure reproducible from the log.**

`tests/conftest.py` registers two hypothesis profiles and loads one:

- **`mycelium`** — loaded everywhere, locally and in CI. `deadline = 200 ms`, stated
  explicitly and **deliberately equal to the value hypothesis 6.165 already defaults to**,
  and `print_blob = True`.
- **`debug`** — opt-in via `HYPOTHESIS_PROFILE=debug`, for chasing an intermittent property
  failure: no deadline, verbose, ten times the examples.

CI's build matrix — the only job that runs the property tests, since every other job selects
by marker — runs `pytest -q --hypothesis-show-statistics`, and on a red run uploads
`.hypothesis/` as an artifact.

**The number is not changed here, only made explicit.** Restating a default looks like a
no-op; it is not, because the value stops being a dependency's opinion and becomes this
repository's. Changing it is a different decision with a different owner: roadmap 4.32 holds
the property tests whose deadline measures SQLite store creation rather than the property
they assert — it names four; one of them fails that deadline today (BUG-0021). Raising the
profile deadline would silently absorb that item; lowering it would pre-empt its measurement.
Neither would actually fix it: a test whose fixture cost sits inside the measured window
cannot be rescued by any global threshold, only by a per-test `deadline=None`. So the profile is the *seam* 4.32 acts on, and today it changes
nothing about what passes.

## Alternatives Considered

- **`deadline = None` globally.** Removes this flake class outright: a slow example becomes a
  line in the statistics rather than a failure. Rejected because it also removes the ability
  to notice a twenty-fold slowdown in a parse-and-assert property, and because it decides
  4.32 by side effect — tests that fail on a deadline under contention would start passing,
  with no record of why. The item asked for an explicit deadline, not for no deadline.
- **A deadline derived from the measured worst case.** More in keeping with how this project
  sets numbers, and it is what I set out to do. The measurement refused it. A threshold
  fitted to the twenty-one CPU-bound tests — 100 ms would have looked defensible, at 10x
  their worst example — **would have failed `test_any_query_text_is_safe` on Windows CI as
  well as locally**, turning a one-platform intermittent into a matrix-wide red. A threshold
  generous enough for the store test would have absorbed 4.32 silently. No single number is
  both tighter than the status quo and honest, because the outlier's cost is *fixture* cost:
  per-test `deadline=None` is the only instrument that removes it, and it is 4.32's to
  wield.
- **`actions/cache` for the example database.** The mechanism hypothesis is designed
  around: a falsifying example found in one run is replayed first in the next, so a fixed
  flake stays fixed. **Rejected**, and this is the substantive choice in this ADR. A cached
  database lets a *previous* run decide this one's result — "same commit, different answer" —
  and that is precisely the property this repository gates against (NFR-1, ADR-0012). CI
  must be a function of the commit. Losing cross-run replay is the price paid; the artifact
  keeps the diagnosis, which is what the item asked for.
- **A bug-ledger record.** Rejected on the ledger's own rule (AGENTS.md §7): a record is for
  a *verified, reproducible* defect, and this is one unreproduced observation. 4.18 set the
  precedent — an item, not a bug record — and it is followed rather than revisited.
- **Do nothing until it recurs.** The default, and the reason there is nothing to look at
  now. Rejected: the whole cost of this item is one `register_profile` call and one CI step,
  paid once, against an evidence loss that repeats on every occurrence.

## Consequences

- **A dependency bump can no longer move the suite's timing budget silently.**
  `test_hypothesis_profile.py` asserts the number, so a hypothesis release that changes its
  default arrives as a named failure in one file rather than as an intermittent failure
  somewhere else.
- **A failure is reproducible from the log alone.** Proved rather than assumed: a deliberately
  failing property test emits
  `You can reproduce this test case by temporarily adding @reproduce_failure('6.165.10', b'AEFk')`,
  and the example database gains an entry. No truncation of the *database* can take that away.
- **The next occurrence has a documented route.**
  `HYPOTHESIS_PROFILE=debug pytest <file> --hypothesis-show-statistics`, written down in
  `CONTRIBUTING.md` rather than only here.
- **Roadmap 4.32 gains evidence it did not have, and a bug record.** Its own text calls
  itself "filed rather than urgent" on the grounds that the four tests pass serially. One of
  them does not: 5 of 6 runs on a Windows development machine, and then `ubuntu-24.04` on
  CI. That is BUG-0021, `fixed` here — see the addendum for why the boundary moved — and
  4.32 keeps the rest of its scope, plus the finding that only one property test in
  twenty-three runs above 10 ms per example, so its "three more behave the same way" is
  unconfirmed.
- **The `actions/cache` refusal stopped being theoretical.** Reproducing the store failure
  wrote its slow example into the local `.hypothesis/examples`, where the reuse phase replays
  it first. Had that database been cached into CI, a slow example from one filesystem would be
  replayed on runners where the same test finishes in 8 ms, failing them for a property that
  holds. The refusal was argued from reproducibility; the demonstration is that a cached
  example database transports a *platform*, not just an example. (It is not, as I first
  assumed, what drives the local failure rate — six runs from a cleared database still failed
  five times.)
- **CI output grows a statistics block per property test** in the build matrix — twenty-three
  short blocks. That is the cost of being able to read per-example runtimes against the
  deadline after the fact instead of guessing.
- **Cross-run replay is given up.** If a property regression is fixed and later reintroduced,
  CI will rediscover it by search rather than by replaying a remembered example. Accepted
  deliberately, for the reproducibility reason above.
- **The uploaded artifact carries generated test inputs, not repository content** — hypothesis
  strategies produce their own bytes. It is retained for 14 days and only written on failure.
  Recorded as a STRIDE row rather than a new trust boundary.
- **What this does not do:** it does not explain the failure, and it does not claim the flake
  is fixed. The item stays closed on the evidence it asked for, not on a cause; if the test
  fails again, 4.29's output is what makes that occurrence worth something.

## Addendum, same day: the boundary moved, and why

This ADR argued that the store test's fix belonged to roadmap 4.32 and not here, because a
global deadline change would either absorb that item or pre-empt its measurement. That
argument still holds for the *number*. It stopped holding for the *test*.

Between this PR's first CI run (four green cells) and its second, `ubuntu-24.04` failed with
`DeadlineExceeded: Test took 501.68ms`. A reproduced red on the matrix cannot be left for a
later item: it blocks this PR, it will redden unrelated PRs, and "re-run it" is precisely how
a flake becomes normal — the harm roadmap 4.18 and 4.29 exist to prevent.

So `test_any_query_text_is_safe` gets `@settings(deadline=None)` in this PR, BUG-0021 is
`fixed`, and roadmap 4.32 stays open for the remainder of its scope. The scope extension is
recorded here rather than folded in quietly, because the reason it happened — evidence
arriving after the decision — is the only thing that justifies it. Two facts hand 4.32 more
than it had: the fix is one decorator per test, and measuring all 23 property tests found
only this one above 10 ms per example, so the "three more" in its text is unconfirmed and may
be empty.

The instrumentation this item added is what made the failure legible: the CI log carried
`@reproduce_failure('6.165.10', b'AITCk8KS')` and the statistics block beside it. That was
4.29's whole deliverable, working on the first real failure after it landed.

## References

- ROADMAP 4.29 (this item), 4.18 (`test_the_observer_ignores_the_derived_store`, the same
  family, closed on evidence), 4.32 (four property tests whose deadline measures I/O).
- Measured 2026-09-08, this repository, `pytest -q --hypothesis-show-statistics`: 23 property
  tests. `test_node_list_is_always_a_well_formed_ordered_tree` reports `~ 0-4 ms` per example
  locally and `~ 0-2 ms` on `ubuntu-24.04`. `test_any_query_text_is_safe` reports 8-10 ms on
  `ubuntu-24.04`, 5-10 ms on `macos-14` and 40-62 ms on `windows-2022`
  ([run 34197166624](https://github.com/danielPoloWork/mycelium-os/actions/runs/34197166624)),
  and 63-74 ms typical locally with observed 269 ms and 1075 ms failures.
  `test_any_mutation_sequence_stays_equal_to_clean` reports `~ 890-1784 ms`. Hypothesis
  6.165.10 defaults to `deadline=200ms`, `print_blob=False`, and a database under
  `.hypothesis/examples` relative to the working directory.
- [BUG-0021](../bugs/2026/09/BUG-0021-a-property-test-fails-its-deadline-on-store-creation.md)
  — the store test's deadline failure, recorded while closing this item.
- Spec 04 §6 (property tests among the verification layers);
  [ADR-0012](0012-adopt-the-g6-determinism-gate.md) (what determinism claims, and why a
  run must be a function of its commit).
