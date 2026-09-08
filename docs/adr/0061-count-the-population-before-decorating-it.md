# ADR-0061: Count the population before decorating it, then guard the shape

- **Status:** Accepted
- **Date:** 2026-09-08
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.32 (this item), 4.31 (where it was filed), 4.29 (which fixed its one
  live member); spec 04 §6; [ADR-0055](0055-run-the-gates-the-change-implicates.md) (why
  parallelism is refused), [ADR-0060](0060-declare-the-property-test-budget-and-keep-the-falsifying-example.md)
  (the profile this acts on),
  [BUG-0021](../bugs/2026/09/BUG-0021-a-property-test-fails-its-deadline-on-store-creation.md)

## Context

Roadmap 4.32 reads: *"Four property tests carry timing deadlines on I/O-bound work … the
deadline measures store-creation cost, not the property … so the fix is one decorator each
plus the sentence saying why."*

It is a well-specified item with a prescribed fix, and the natural way to execute it is to
add four decorators. Two things made that the wrong first move.

**The one member anyone had actually seen fail was fixed at 4.29.**
`test_any_query_text_is_safe` opens a SQLite store per hypothesis example; it failed the
200 ms deadline 5 of 6 runs locally and then failed `ubuntu-24.04` on CI at 501 ms against an
8-10 ms typical. That is BUG-0021, fixed. So of the "four", one is done and three are
unnamed.

**The number came from a configuration this project refuses.** 4.31 measured
`pytest-xdist` and rejected it: `--dist load` took 1389 s against 721 s serial, because
per-test distribution destroys the fixture reuse this suite is built on — *"every worker
rebuilds the stores and corpora that a module-scoped fixture used to make once"* — and
ADR-0055 records, in the same sentence, that it *"turned four hypothesis timing deadlines
into failures under contention"*. The four is a count of failures under 20-way
oversubscription, not a count of tests with the defect.

Those two are the whole question: **how many property tests actually have the shape 4.32
describes, and is the answer a timing measurement or a structural one?**

## Decision

**Establish the population structurally, fix what is in it, and assert the *rule* rather
than the list.**

The criterion is structural, not a threshold: a property test has this defect when its
example body — or a helper it calls, or a fixture it requests — does filesystem or store
setup, because hypothesis's deadline covers the whole example body. Such a test times its
filesystem and reports the result as a property failure, whether or not it happens to breach
200 ms today.

Walking all 24 `@given` functions under `tests/` on that criterion, **the population is two,
and both are already exempt**:

| property test | why it is I/O-bound | exempt since |
|---|---|---|
| `test_any_mutation_sequence_stays_equal_to_clean` | `TemporaryDirectory`, rebuilds a corpus per example | roadmap 3.1 |
| `test_any_query_text_is_safe` | `SqliteStore` + `tmp_path_factory` per example | roadmap 4.29 (BUG-0021) |

The other twenty-two touch no filesystem at all. **So 4.32's remaining scope is empty, and
no decorator is added by this item.** What is added is a guard in
`tests/test_hypothesis_profile.py`: any property test whose example body does that setup must
carry `deadline=None`, or the suite fails and names it. The list of four becomes a rule, and
the third such test — whenever someone writes it — is caught at authoring time instead of
months later on a busy machine.

**Reproduced, not assumed.** Re-running the configuration that produced the four
(`-n auto --dist load`, 20 cores, 1395 s — within 0.4 % of 4.31's 1389 s) now yields **zero
`DeadlineExceeded` failures**. Two other things fail under that contention, and neither is a
hypothesis deadline:

- `test_chunk_json_round_trip_property` — hypothesis's `too_slow` **health check**, not the
  deadline: *"only generated 2 valid inputs after 4.53 seconds"*. Serially it runs at 1-2 ms
  per example with 0-1 ms in generation.
- `test_ingest_hostile.py::test_every_hostile_file_fails_as_one_document[truncated.pdf]` — a
  **hand-rolled** 5 s wall-clock budget, at 5.2 s. Its own docstring says the budget is
  "generous by two orders of magnitude … the point is to catch a defence that stopped
  working, not to benchmark a CI runner".

Both are artifacts of 20-way oversubscription on a machine with 20 cores, and both are in a
configuration ADR-0055 measured and refused. **They are recorded here and deliberately not
fixed**: hardening tests against a configuration nobody runs spends the signal those
assertions exist to give, and would leave the codebase carrying suppressions for a
counterfactual. No roadmap item is filed for them either — filing work that should not be
done is a cost, not a record.

## Alternatives Considered

- **Add four decorators, as the item prescribes.** The obvious execution, and it is what the
  item asks for in so many words. Rejected because three of the four do not exist: twenty-two
  of the twenty-four property tests do no I/O, so the decorators would have to be placed by
  guessing. `deadline=None` on a test that does not need it is not neutral — it silently
  surrenders the ability to notice a twenty-fold slowdown in that property.
- **Take the timing measurement as the criterion** — decorate every property test within some
  factor of 200 ms. Rejected because it makes the population a function of the machine that
  measured it. The whole lesson of BUG-0021 was that timing readings moved three times
  (margin → local failure → CI failure) while the *shape* never moved: the fixture cost was
  inside the measured window from the day the test was written.
- **Suppress the `too_slow` health check and raise the hostile budget** so the suite survives
  `--dist load`. Rejected: parallelism is refused (ADR-0055), so this is hardening against a
  configuration nobody runs, and each suppression is a permanent loss of signal bought with a
  counterfactual. Recorded above instead, so the next person to look at twenty idle cores
  finds the measurement rather than repeating it.
- **Leave 4.32 open as a recorded limit**, which the item itself proposes. Rejected because
  the item's question is now answered and its prescribed fix has no targets. An open item
  whose scope is empty is a standing invitation to add decorators nobody needs.
- **Extend the guard to imported helpers** via cross-module analysis. Rejected as more
  machinery than the risk warrants; the limit is stated in the guard's own docstring and each
  exemption carries a comment at its site.

## Consequences

- **The class cannot regrow silently.** A new property test that opens a store or asks for a
  `tmp_path` fails `test_a_property_test_that_builds_a_store_exempts_itself_from_the_deadline`
  with the reason and the remedy in the message. Two companion tests keep the guard honest:
  one fails if the walker stops finding property tests — BUG-0020's vacuous-test lesson — and
  one names the two known members so a reader does not re-derive them.
- **A false positive is possible, and one was already caught in development.** An early hint
  list included `replace(` for `os.replace` and flagged
  `test_digest_text_ignores_line_endings_and_composition`, whose `replace` is `str.replace`
  on a line ending. The list is now short and literal; a guard that cries wolf gets deleted.
- **The guard reads only each test file and its own helpers.** I/O reached through an
  imported helper slips past. Stated in the docstring rather than implied.
- **`pytest-xdist` was installed for the measurement and removed again.** It is not a
  dependency; the numbers are recorded here so the next person does not need it either.
- **Two contention-only timing assertions are known and unfixed**, with their numbers above.
  If parallelism is ever revisited, they are what stands in the way — and that decision
  belongs to whoever revisits it, together with the 1395 s that made 4.31 refuse it.
- **Nothing in the shipped suite changes.** No decorator, no threshold, no behaviour: 4.32
  closes because its work was already done, and the deliverable is the proof plus the guard
  that keeps it true.

## References

- ROADMAP 4.32 (this item), 4.31 (filed it; measured and refused xdist), 4.29 (fixed its one
  live member), 3.1 (exempted the other).
- Measured 2026-09-08, this repository, 20 cores, Windows: `pytest -q -n auto --dist load`
  → 1395 s, 2 failed / 1519 passed / 3 skipped, **zero `DeadlineExceeded`**; 4.31's own
  figure for the same configuration was 1389 s. Serial: 1517 passed in 686-765 s.
- [ADR-0055](0055-run-the-gates-the-change-implicates.md) (parallelism refused, with the
  sentence that produced the "four"),
  [ADR-0060](0060-declare-the-property-test-budget-and-keep-the-falsifying-example.md) (the
  declared profile this acts on),
  [BUG-0021](../bugs/2026/09/BUG-0021-a-property-test-fails-its-deadline-on-store-creation.md),
  [BUG-0020](../bugs/2026/09/BUG-0020-the-rebuild-loop-guard-was-covered-by-a-vacuous-test.md)
  (why a guard must be able to fail).
