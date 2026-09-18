# ADR-0125: Exclude the root CHANGELOG.md, because `[Unreleased]` is the restatement early

- **Status:** Accepted
- **Date:** 2026-09-18
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7, D-010
- **Related:** [ADR-0072](0072-keep-our-own-restatements-out-of-our-own-benchmark.md) (amended by
  this decision), [ADR-0021](0021-scope-the-corpus-and-gate-the-evaluation.md) (the `[project]
  exclude` mechanism), [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)
  (report on the corpus we author), [ADR-0112](0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md)
  (the release-cadence rebless this decision deliberately does not trigger early); roadmap 4.44,
  6.10

## Context

ADR-0072 excluded `docs/changelog` and `docs/releases` from this repository's own corpus,
because a per-version changelog and its release notes restate, in the same vocabulary, what the
ADRs and the roadmap already say canonically — and that restatement is close to a worst case
for a term-counting baseline while nearly free for a retriever with field weights and a stem
index. It left the root `CHANGELOG.md` in the corpus, on the reasoning that only the *released*
copies were the offending restatement.

Roadmap 6.10 named the gap that reasoning missed: **`[Unreleased]` is the same restatement,
early.** The workflow's own description of the release procedure says so directly —
*"a release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md`"* — which means the text sitting under `[Unreleased]`
today is not a draft of a future restatement, it *is* the restatement, staged one release early
under a different heading. Cutting v0.4.0 demonstrated the mechanism moving in reverse: dropping
~1,000 lines out of `[Unreleased]` at the release measurably helped the grep baseline on our own
release set. So the exclusion ADR-0072 made oscillates with the release cycle in the one file it
did not reach, instead of the file staying excluded the way `docs/changelog` does.

The item asked a real question before taking the obvious fix: *is `[Unreleased]` genuinely a
restatement, or is the honest fix narrower* — keeping the small "Released versions" index table
at the foot of the file indexed, since it is navigational rather than restated prose, and
excluding only the `[Unreleased]` section above it.

**Measured today** (build `.` with `--no-pin`, `mycelium eval . --set <set> --against grep`,
195 documents before, 194 after):

| corpus scope | ours, dev | grep, dev | ours, release | grep, release |
|---|---:|---:|---:|---:|
| `CHANGELOG.md` in the corpus | 0.4739 | 0.2379 | 0.5008 | 0.2221 |
| `CHANGELOG.md` excluded | 0.4739 | 0.2433 | 0.5008 | 0.2303 |

Our own score does not move — to the fifteenth decimal place, both sets — and grep's moves up
on both, narrowing our reported lead by 0.0055 nDCG@10 on dev and 0.0082 on release. The same
shape ADR-0072 measured, the same direction, smaller in absolute terms because `[Unreleased]`
on this date is shorter than the ~1,000-line changelog v0.4.0 cut released.

## Decision

**The root `CHANGELOG.md` leaves the corpus, whole**, via the same `[project] exclude`
mechanism and the same rule ADR-0072 applied: `mycelium.toml`'s `exclude` gains one entry.

**The narrower fix is refused, on ADR-0072's own precedent and for the same reason.** ADR-0072
considered and rejected splitting `docs/changelog` (1,091 lines) from `docs/releases` (~95
lines) as *"a distinction without a principle: both are derived restatements of canonical
content, and the reason to exclude one is the reason to exclude the other."* The same argument
applies here at a smaller scale: the "Released versions" table is a handful of one-line rows
naming a version, a date, and a link — genuinely navigational rather than restated prose — but
`mycelium.toml`'s exclude mechanism has no unit smaller than a file, and building one to spare
roughly fifteen lines of index content is disproportionate to what those fifteen lines are
worth, in either direction: they contain almost no term-counting vocabulary to inflate a
baseline with, and almost no retrieval value an agent could not get faster from `ROADMAP.md` or
the per-version files under `docs/releases/`. Splitting the file on a distinction this thin, for
an item scoped `XS`, would be exactly the kind of exception ADR-0072 refused to grant `docs/releases`
on size alone.

**The bar is not moved, again.** `test_the_grep_baseline_is_fair`'s recall floor (0.75, ADR-0081)
is unaffected by this change in either direction — the measurement above shows recall untouched,
only ranking — so nothing about the guard's shape is at stake here.

**`eval/baselines/release.json` is not re-blessed in this pull request**, unlike ADR-0072's own
PR, which reblessed within the corpus-decision PR because no other cadence existed yet. ADR-0112
has since established that `ours/release` is reblessed once per release, as its own PR, dated to
what the release is cut from (`docs/workflow/release.md` step 0) — a discipline this decision
predates none of but should not bypass on its own initiative. Gate G3 reports the corpus as not
comparable to the committed baseline until the next scheduled rebless picks it up; that is the
gate working as ADR-0053 designed it — *reported, not enforced*, on a corpus this repository
writes about itself — not a defect this PR needs to fix.

## Alternatives Considered

- **Exclude only the `[Unreleased]` section, keep the "Released versions" table.** The item's
  own candidate, and the one this ADR spends most of its argument refusing: no mechanism exists
  below file granularity, the content spared is small in both directions, and ADR-0072 already
  refused the same shape of argument at ten times the size differential.
- **Leave `CHANGELOG.md` in the corpus and widen the grep-competence guard's tolerance instead.**
  Rejected on ADR-0072's own timing rule, restated because it still holds: a guard is redefined
  when it is green and the argument is about its shape, never to explain away a result. The
  guard is not red today (recall is untouched), so there is nothing here to explain away — but
  building tolerance for a self-inflicted contamination invites exactly the drift ADR-0072
  exists to stop.
- **Re-bless `eval/baselines/release.json` in this PR, matching ADR-0072's own precedent.**
  Rejected on timing: the cadence ADR-0112 established did not exist when ADR-0072 set its
  precedent, and following the older habit over the newer, dated discipline would be the same
  mistake ADR-0113's addendum found and corrected in a different form — reaching for what an
  earlier record did rather than what governs now.
- **Build a section-level exclusion primitive.** Rejected as disproportionate to what it would
  buy: one file, roughly fifteen lines of tail content, for a mechanism that would need its own
  design, its own tests, and its own review — the opposite of what an `XS` item is for.

## Consequences

- **The corpus drops from 195 documents to 194.** The document was not judged by any case in
  `eval/dev.jsonl` or `eval/release.jsonl`, so no judgment moves and no case is orphaned.
- **Our reported lead over the incumbent narrows further**, on both sets, in the direction that
  says this is not a fitted change — the same signature ADR-0072 read the same way.
- **A release no longer moves the benchmark twice.** ADR-0072 stopped the release notes and the
  per-version changelog from doing it after the fact; this stops the same content from doing it
  before the fact, closing the gap the item named.
- **`eval/baselines/release.json` reports non-comparable** against the new corpus digest until
  the next scheduled `docs/workflow/release.md` step-0 rebless. `mycelium doctor` and `mycelium
  eval --gate` both say so rather than silently comparing against a stale corpus.
- **Config digest changes for this repository's own snapshot** (`[project] exclude` is part of
  `MyceliumConfig.digest()`), which is expected of a corpus-scope decision and touches nothing
  gate G6 checks — the determinism fixture corpus under `tests/fixtures/determinism/` carries
  its own, separate `mycelium.toml` and is untouched.

## References

- Measured this session, re-runnable: `mycelium build . --no-pin --clean`, then
  `mycelium eval . --set eval/dev.jsonl --against grep --json` and the same against
  `eval/release.jsonl`. `python tools/measure_hybrid_gate.py --check` confirms gate G2's
  recorded verdict is unaffected (it fingerprints `retrieval.py`'s constants only).
- [ADR-0072](0072-keep-our-own-restatements-out-of-our-own-benchmark.md) — the rule this
  decision applies a second time, and the precedent it follows on both refusals above.
- `docs/workflow/release.md` — step 0, the cadence this decision defers the rebless to.
