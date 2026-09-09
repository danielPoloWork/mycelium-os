# ADR-0072: Keep our own restatements out of our own benchmark

- **Status:** Accepted
- **Date:** 2026-09-09
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.44 (this item); RFC-0001; spec 04 §7; D-010;
  [ADR-0021](0021-scope-the-corpus-and-gate-the-evaluation.md),
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)

## Context

Cutting v0.4.0 added two documents to this repository: `docs/changelog/v0/v0.4.0.md` (1 091
lines) and `docs/releases/v0.4.0.md`. This repository is one of the three corpora the
evaluation runs on, so both were immediately indexed — and a guard went red.

`test_the_grep_baseline_is_fair` asserts that the incumbent scores above 0.3 on our dev set,
with the reason in its docstring: *"a baseline built to lose proves nothing, so this one is
checked for competence."* It read **0.29983**.

The cause is specific, and measuring it is the whole decision:

| corpus scope | ours, dev | grep, dev |
|---|---:|---:|
| before the release documents | 0.539 | 0.349 |
| with them | 0.539 | **0.2998** |
| with `docs/changelog` and `docs/releases` excluded | 0.540 | **0.358** |

**Our score does not move. The incumbent's does.** A per-version changelog is dense prose
that restates, in the same vocabulary, what the ADRs and the roadmap already say canonically
— which is close to a worst case for a baseline that ranks by term counts, and nearly free
for a retriever with field weights and a stem index.

That is a benchmark contaminating itself. D-010 says *fix the product, not the benchmark*;
this is the same rule read from the other side. Every release we cut would have widened our
reported lead over the incumbent, for a reason that has nothing to do with retrieval.

The condition is not new — the v0.1.0, v0.2.0 and v0.3.0 changelogs and release notes have
been indexed all along. v0.4.0 only made it large enough to trip a guard.

## Decision

**`docs/changelog` and `docs/releases` leave the corpus**, via the `[project] exclude`
mechanism ADR-0021 built for exactly this class of file.

Two independent reasons, and the second is the one that would hold even if the numbers had
gone the other way:

1. **Benchmark integrity.** Indexing our own release prose inflates our margin over the
   incumbent. Excluding it *narrows* that margin — +0.218 → +0.186 on our release set — which
   is the direction that says nobody fitted this.
2. **Retrieval merit, independent of any benchmark.** A changelog entry and the ADR it
   summarises make the same claim in the same words, so they compete. An agent asking how
   `pack_atomic` works should get [ADR-0042](0042-let-an-atomic-block-share-its-chunk.md), not
   the changelog line announcing that a PR changed it. Duplication of a canonical source is
   not extra knowledge; it is the same knowledge, ranked against itself.

The **bar is not moved.** `> 0.3` stays exactly where it is. Redefining a guard while it is
red is the fitted parameter this project has refused fourteen times in retrieval and would be
no better here.

## Alternatives Considered

- **Redefine the guard.** The threshold is absolute and the corpus grows, so it will fire
  again eventually whatever the baseline's competence — a fair criticism of its construction.
  Rejected anyway on timing: a guard is redefined when it is green and the argument is about
  its shape, never while it is red and the argument is about a result. If the shape is wrong,
  it can be fixed in a change that has nothing at stake.
- **Exclude only `docs/changelog`**, keeping the release notes. The changelog is the
  1 091-line offender and the notes are ~95 lines. Rejected as a distinction without a
  principle: both are derived restatements of canonical content, and the reason to exclude one
  is the reason to exclude the other. Drawing the line by file size would make the next
  release's notes a fresh judgement call.
- **Leave the corpus alone and accept a red guard.** Not an option, and not only because CI
  is red: the number the guard protects is the one the README quotes.
- **Do it inside the v0.4.0 release PR.** Rejected by the maintainer, and correctly: a release
  cut should be a mechanical roll of a version, a changelog and a set of notes. A substantive
  change to what the benchmark measures, landing inside one, is a change nobody reading
  `git log` a year from now would expect to find there.
- **Exclude `docs/adr` or `docs/bugs` too.** Not considered seriously and named so it is on
  the record as *not* the decision: those are canonical. The rule here is "derived restatement
  of something else in this repository", and it selects exactly two directories.

## Consequences

- **Our reported lead over the incumbent narrows** on our own release set, +0.218 → +0.186,
  and the README table is updated with it. The `uv` corpora are untouched — they are separate
  repositories and never contained our changelog.
- **The corpus drops from 136 documents to 127.** Nine documents leave; none of them was
  judged by a case, so no judgement moves and no case is orphaned.
- **`eval/baselines/release.json` is re-blessed**, because the corpus changed. It is the
  baseline G3 *reports* on rather than enforces (ADR-0053), for the same underlying reason
  this ADR exists: this corpus is the repository, and the repository moves.
- **A release stops moving the benchmark.** That is the durable win — not the numbers, but
  that cutting v0.5.0 will no longer change what v0.4.0's numbers meant.
- **The guard did its job**, and it is worth saying plainly: a test written to check that the
  incumbent is competent caught a corpus that had quietly made it less so. It was not written
  for this and it found it anyway.

## References

- Measured this session and re-runnable with `mycelium eval . --against grep`: the three-row
  table above; ours/release 0.531 → 0.532 with grep 0.313 → 0.346.
- [ADR-0021](0021-scope-the-corpus-and-gate-the-evaluation.md) — the `[project] exclude`
  mechanism and the rule that a repository's tree carries Markdown that is not documentation.
- [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md) — why this
  corpus is reported rather than enforced, which is the same fact seen from the gate's side.
