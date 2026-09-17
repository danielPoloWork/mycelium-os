# ADR-0120: Build the reference profile, publish what it says, and gate the instrument rather than the verdict

- **Status:** Accepted
- **Date:** 2026-09-17
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §§7.4–7.5
- **Related:** [ADR-0022](0022-measure-the-agent-loop-without-an-agent.md) (the agent-task
  suite, and the gate it deferred to 1.0), [ADR-0013](0013-adopt-the-evaluation-harness.md)
  (the harness and the grep baseline), [ADR-0047](0047-flip-the-packed-chunker-on-and-let-the-gate-say-so.md)
  (the chunker change that moved four task anchors),
  [ADR-0026](0026-pack-the-vectors-and-say-what-the-scan-costs.md) (the vector scan's own
  extrapolation to 10⁵), [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)
  (a gate that cannot fail selects for being ignored),
  [ADR-0112](0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md)
  (a measurement whose denominator moves under it),
  [ADR-0113](0113-close-a-milestone-on-its-gates-and-carry-an-unmet-one-by-name.md) and
  [ADR-0114](0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md)
  (M6 ships v0.6.0 and 1.0 lands at M7 — the correction this item inherits),
  [ADR-0008](0008-adopt-sqlite-store-behind-a-store-protocol.md) (the store whose write path
  turned out to be quadratic), [BUG-0031](../bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md);
  spec 01 §8, spec 04 §1 and §§7.3–7.5, spec 06 §Phase 1 and §Phase 4; NFR-2, NFR-3; D-010;
  roadmap 3.7, 6.4, 6.18, 6.19, 6.20, 6.21, 6.22, 6.23

## Context

Roadmap 6.4 asks for two things: a *public benchmark report with run manifests*, and the
*agent-task gate quantified*. Both halves turned out to rest on a measurement that had never
been taken.

### The reference profile did not exist

Three performance claims are stated in three places, and all three name the same conditions:

| Claim | Budget | Stated conditions | Where |
|---|---|---|---|
| Cold build | < 60 s | 1 000 documents | spec 01 §8 |
| Incremental single-document rebuild | < 2 s p95 | equals a clean rebuild | NFR-3, spec 06 §Phase 1 |
| End-to-end `mycelium_search` | ≤ 150 ms p95 | local profile, **10⁵ chunks**, warm store | NFR-2, spec 04 §1 |

`.draft-specs/06` §Phase 1 made the third an **exit gate** of Milestone 3: *"search p95 < 150
ms on the 10⁵-chunk reference corpus."* That milestone closed and shipped v0.3.0. The corpus
it names has never been built. The largest corpus this project has ever measured anything on
is its own, at 1 420 chunks — **seventy times smaller** than the profile.

Gate G5 enforces the query budget honestly on whatever corpus the evaluation ran and says so
in its own detail string (*"this is a floor, not the measurement spec 04 §1 asks for"*), so
nothing here was hidden. It was simply never done, and a gate measured two orders of
magnitude below its conditions cannot fail — which is the property ADR-0053 says selects for
being ignored. `docs/benchmarks/` has held a methodology, a template and an empty results
table (*"No benchmarks recorded yet"*) since Milestone 1, while spec 04 §7.5 has required
since Phase 1 that *"released benchmark reports are committed to the repo with their
manifests; a report without a manifest is exploratory and cannot satisfy a gate."*

Two more deferrals pointed at a profile that did not exist: `tests/bench/test_store_bench.py`
said *"the real gate is measured against the 10^5-chunk reference profile at roadmap 3.7"*,
and `tests/bench/test_retrieval_bench.py` states the vector scan's cost at 100 000 chunks as
*"a multiplication"* of a 10 000-chunk measurement.

### The agent-task suite had been measuring its own rot

ADR-0022 built the suite and recorded its first numbers: evidence in front of the model on
**64 %** of tasks against grep's **27 %**, at half the context. It validates every required
anchor against a real build — *at generation time*. Nothing re-checked them afterwards.

At 6.4, **four of the twenty-two tasks required anchors the corpus no longer holds.** The
cause is not an edit: the packed chunker (ADR-0047) merged ADR-0009's three `Decision` chunks
into one and shifted every ordinal after it, so `#decision/1` and `#decision/2` — and
`README.md#build-test-run/1` — name nothing. A task whose evidence does not exist was scored
as a **miss**, identically for both strategies, so the suite's headline rate had a silent
ceiling of 18/22 and had quietly become *retrieval quality plus anchor rot* with no way to
separate them. A compiler change had invalidated the benchmark's judgements and the benchmark
went on reporting.

The same measurement found a **second** defect in the same instrument, and it has the same
shape. `MAX_GREP_FILES` is 5 — *"an agent does not read forty files; it reads the first few
and re-greps"* — but the loop reads the first matching file whole regardless of budget, and
`ROADMAP.md` has grown to ~81 000 tokens, 18 % of the corpus and 45× the median document. So
grep now reads **exactly one document on 22 of 22 tasks**, and that document supplies **93 %
of its entire measured context cost**. The headline ratio is mostly a fact about our roadmap
file; grep's 4.5 % evidence rate is *"its one file was the wrong file"*. ADR-0022 measured
27 % and a 2× ratio when the documents were small, and nothing noticed the change.

### "Quantified at 1.0" now means Milestone 7

Spec 04 §7.4 and spec 01 §8 both say the agent-task comparison is scored qualitatively pre-1.0
and becomes a quantified gate **at 1.0**; ADR-0022 deferred it there explicitly. Item 6.4 sits
in Milestone 6, which spec 06 calls Phase 4 and which was believed to ship 1.0 when the item
was written. ADR-0113 corrected that: **M6 ships v0.6.0 and 1.0 lands at M7.** So the item's
phrase inherits the same question ADR-0114 answered for the compatibility promise.

## Decision

**The reference profile is generated, not committed, and the generator is the reproducible
part.** `tools/benchmark_reference_profile.py` composes documents from prose harvested out of
the corpora this repository already vendors, under a seed: same seed, same corpus, on any
machine. Committing 10⁵ chunks would make the repository mostly benchmark; committing the
generator costs one file and makes the number reproducible without the bytes. The generator's
limits are stated in the report rather than smoothed over — chiefly that its vocabulary is
closed, so a query's matching set grows linearly with the corpus and the curve is an **upper
bound** on a real corpus whose vocabulary grows with it.

**The query claim is measured at 10⁵ chunks on a store loaded directly, and the build claims
are not.** Compiling the reference corpus turned out to be impossible in practice —
[BUG-0031](../bugs/2026/09/BUG-0031-writing-a-chunk-scans-the-whole-lexical-index.md), found
by this work: `put_chunks` deletes from `chunks_fts` by an `UNINDEXED` column, SQLite answers
that with a full scan, and loading *N* chunks therefore costs O(*N*²), which puts 10⁵ chunks
at about nine hours. NFR-2's condition is *"10⁵ chunks, warm store"*, which is a statement
about what the retriever **reads**; the retriever reads the derived store and nothing else
(spec 04 §1's token-frugality contract), so a store filled by plain SQL presents the same
substrate, through the same `INSERT`s and the same tokenizer. That is checked rather than
asserted: at 4 945 chunks the directly-loaded store and the compiled one answer the same
queries within 6 %. It would be worthless for a *build* measurement, where how the rows got
there is the entire question — so the cold-build and incremental figures come only from
compiled corpora.

**The measurement is a curve, not a point.** A single reading at the reference size says
whether a budget is met and nothing about why. Measuring at several sizes says which cost
grows with the corpus and which is a constant, and that distinction is the whole finding: the
end-to-end budget is missed by a **fixed** overhead that has nothing to do with retrieval,
while the query path itself is linear in the corpus.

**The manifest carries the machine, including what a file open costs on it.** Spec 04 §7.5
already required hardware. This adds one measurement to it, because without it the build
figures are unreadable: on the machine of record a warm read of a 4 KB Markdown file costs
~1.3 ms, roughly a hundred times an unencumbered SSD, and the incremental-rebuild number is
mostly that constant times the corpus. A reader with a faster disk can divide.

**The report publishes the numbers that fail.** D-010's doctrine — *"fix the product, not the
benchmark"* — is only actionable if the product's standing is visible, and the first public
benchmark report this project has ever published says it misses three of its own budgets. The
alternative was to measure at a size where they pass, which is what the absence of this report
has amounted to for six milestones.

**Claims the measurement falsifies are corrected on sight; the capabilities are filed.** Three
statements in the tree said something now known to be untrue — `_open_store`'s *"opening costs
microseconds"*, the store bench's deferral to roadmap 3.7, and spec 06's Phase-1 exit gate
recorded as met. They are corrected where they stand. The *fixes* are six roadmap items
(6.18–6.23) and a bug record, not this one: a benchmark report and a change to what it
measures do not belong
in one pull request, for the reason ADR-0056 keeps a bless away from a retrieval change — the
published number would describe a tree that no longer exists by the time anyone read it.

**The agent-task suite reports an unresolved anchor and never scores it.** A task whose
required passage the snapshot does not hold is excluded from the rate and named, because
neither strategy can put in front of a model a passage that does not exist, so it measures
nothing about either. The four rotted tasks are re-anchored to the chunks that now carry the
same passages, judged the way ADR-0022 requires: by reading them.

**`mycelium eval --tasks --gate` gates the suite's integrity, not its verdict — and that is
the distinction the item's phrase was hiding.** Two different things were both called "the
agent-task gate":

1. *Does the comparison still measure retrieval?* Decidable today, and today it did not. CI
   and `tools/verify.py` now run the suite with `--gate`, which fails when any required
   anchor is unresolved.
2. *Does Mycelium beat grep?* Scored qualitatively until 1.0 by spec 04 §7.4, and **armed at
   the v1.0.0 tag**, which is Milestone 7 — the same answer ADR-0114 gave the compatibility
   promise, for the same reason: the spec conditions it on 1.0, and 1.0 is now M7.

**The verdict gate is quantified here even though it arms later**, which is what "quantified"
asks for. Its rule, its numbers and the margin it stands on are in the report, together with
the three properties that have to hold before it can carry weight — an integrity gate that is
green, a denominator that does not move, and a corpus that is not only our own.

**Gate G5 is unchanged and now cites the report.** It keeps enforcing the query budget on
whatever corpus ran, which is a floor worth having; what it could not say — what the budget
does at its own stated conditions — is no longer missing, it is published.

## Alternatives Considered

- **Commit the reference corpus.** Rejected: hundreds of megabytes of generated prose, in a
  repository that vendors two corpora already and whose own sdist allowlist exists because it
  once shipped the working directory (ADR-0116). The seed reproduces it.
- **Measure at a size that fits in CI and extrapolate to 10⁵.** Rejected, and this is the
  practice the item exists to end: the retrieval bench already states the vector scan's cost
  at 100 000 chunks as a multiplication, and the Phase-1 exit gate was recorded as met on the
  strength of nothing at all. A curve plus a stated upper bound is offered *in addition to* the
  measurement, never instead of it.
- **Put the reference profile in CI.** Rejected: the build alone runs for hours on the machine
  of record, and CI hardware is too noisy to gate on wall-clock anyway (the `benchmark` job
  says so already). The cheap half — `--check`, which validates the committed manifests — runs
  in CI; the expensive half is run by hand when a claim is being substantiated, and leaves a
  report behind.
- **Fix the three performance defects in this pull request.** Tempting for the first one, whose
  cause is one uncached call and whose fix is small. Rejected on reviewability: the report is
  the deliverable, its numbers describe the tree it was taken on, and `config.py` is a tuning
  path whose change derives the full retrieval ladder. Filed as 6.18–6.20 with the mechanism
  named, which is what makes them one-sitting items rather than investigations.
- **Wait for the reference corpus to compile.** Rejected once it was timed: about nine hours,
  because of BUG-0031, and the build is not what NFR-2's condition is about. The honest split
  is to measure the query claim on a store loaded directly — checked against a compiled one at
  a size both can reach — and to say plainly that the build claims are measured only where the
  compiler can actually reach.
- **Fix BUG-0031 here, since it blocks the measurement.** Rejected for the reason every other
  fix is filed: it is a change to the store's write path and to what the benchmark measures,
  in the pull request that publishes the benchmark. It also has a real choice inside it —
  two of the three candidate fixes move the lexical schema and therefore re-record gate G2's
  verdict — which deserves its own argument (6.19).
- **Score a task with an unresolved anchor as a failure** (what the suite did). Rejected: it
  reports a compiler change as a retrieval regression, which is the one thing a benchmark must
  never do.
- **Drop the four rotted tasks instead of re-anchoring them.** Rejected: the passages still
  exist and still answer the questions; what moved was where the chunker put their boundaries.
  Dropping them would shrink a denominator that spec 04 §7.4 already puts a floor under (≥ 20
  tasks) to answer a problem that re-anchoring solves exactly.
- **Arm the verdict gate now, since the item says "quantified".** Rejected on the spec's own
  words and on the evidence: spec 04 §7.4 conditions it on 1.0, the suite runs on 22 tasks over
  a self-hosting corpus that grows every merge, and one task is 4.5 % of the rate. Quantifying
  a bar and arming it are different acts, and this does the first.
- **Re-cut the budgets to what the product achieves.** Rejected outright — it is the
  benchmark-fixing D-010 forbids. If a budget is wrong it is changed by an argument about what
  a user needs, never by an argument about what we measured.

## Consequences

- **This project has a published benchmark report** —
  `docs/benchmarks/2026-09-17-reference-profile.md`, with its manifest beside it — and a lint
  that keeps the next one honest: `tools/consistency_lint.py`'s `benchmarks` check refuses a
  report citing no manifest, a citation resolving to nothing, and an orphaned manifest.
- **Three budgets are now known to be missed, with the mechanism named for each**, and six
  items carry the work (6.18–6.23). None is an investigation: each names what to change.
- **A quadratic in the compiler's write path, found by trying to build a big corpus**
  (BUG-0031). It is ~40 % of the 1 000-document cold build and the reason the reference corpus
  had never been built — a defect that could only be found by doing the thing this item
  exists to do, which is an argument for benchmarks that nothing else makes.
- **A benchmark must be taken on an idle machine, and this one nearly was not.** An early pass
  reported 1 295 ms where a quiet machine reports ~300 ms, because other work was running on
  the same box. Every figure in the committed manifest comes from a single uncontended
  invocation, and the report says so.
- **The end-to-end finding is the one that matters most and is the cheapest to fix.**
  `mycelium_search` misses its 150 ms budget on *every* corpus including a 60-document one,
  because `load_config` runs per tool call and re-scans the environment's entry points at
  ~250 ms. It is not a retrieval problem, and no amount of retrieval work would have found it:
  gate G5 times the retriever inside the harness, not the tool the NFR names.
- **The agent-task suite's rate changed meaning.** It is now over *scorable* tasks and the
  report says how many there were. Numbers taken before this change are not comparable with
  numbers taken after it, and ADR-0022's 64 %/27 % is a reading of a 22-task denominator that
  had four unanswerable tasks in it.
- **A compiler change can no longer invalidate the suite in silence.** `--gate` in CI and in
  the ladder is the check; the cost is that a chunker change which moves a judged anchor now
  fails the build until the anchors are re-judged, which is the correct bill for moving them.
- **A limit, stated.** Everything here is one machine, and the machine is slow at opening
  files. The manifest records the constant so the build figures can be scaled, but nothing
  makes a single machine's wall-clock into a portable number; the curve's *shape* travels and
  its absolute values do not. And the profile measures the shipped default, which is lexical
  (ADR-0017), so the vector path at 10⁵ chunks remains the extrapolation ADR-0026 made — filed
  as 6.21 rather than quietly inherited.

## References

- Spec: `.draft-specs/01-product-strategy.md` §8 (the three budgets);
  `.draft-specs/04-retrieval-and-evaluation.md` §1 (stage budgets), §7.3 (gate G5), §7.4 (the
  grep baseline and the agent-task suite), §7.5 (run manifests);
  `.draft-specs/06-roadmap-and-governance.md` §Phase 1 (the exit gate), §Phase 4 (this item).
- The report: `docs/benchmarks/2026-09-17-reference-profile.md` and its manifest under
  `docs/benchmarks/manifests/`.
- Re-runnable: `python tools/benchmark_reference_profile.py --out <dir> --manifest <path>`
  (hours), `python tools/benchmark_reference_profile.py --check` (instant),
  `mycelium eval . --tasks --gate`.
