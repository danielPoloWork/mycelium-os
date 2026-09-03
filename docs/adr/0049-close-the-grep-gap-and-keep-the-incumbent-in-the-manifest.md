# ADR-0049: Close the grep gap, and keep the incumbent in the manifest

- **Status:** Accepted
- **Date:** 2026-09-03
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.8 (closed here), 4.11/4.15, 4.19, 4.25 (filed here), 6.4;
  RFC-0001; spec 04 §§7.1, 7.3, 7.4, 7.5; D-010;
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0031](0031-refuse-three-rerankings.md),
  [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md),
  [ADR-0047](0047-flip-the-packed-chunker-on-and-let-the-gate-say-so.md),
  [ADR-0048](0048-index-the-stem-beside-the-surface-form.md)

## Context

Roadmap 4.8 was filed at 3.15 with a number and a doctrine. The number: on `uv`'s
documentation — a corpus this project did not write and did not judge for itself — the
agent's own `grep` loop scored nDCG@10 **0.409** against the product's **0.249**. The
doctrine is D-010, and spec 04 §7.4 states it in one line: *if Mycelium OS does not visibly
beat grep, the correct response is to fix the product, not the benchmark.*

The item then stayed open across two milestones and thirteen refused candidates. ADR-0031
refused three re-rankings and caught an overfit with the dev/release split on its first real
use. ADR-0041 refused six more, closed the section-as-unit family with an upper bound, and
named what was left standing: *"The hypothesis left standing is a **chunking** one, filed as
4.11."*

Both of the hypotheses that survived have since shipped — packing (4.11, flipped on at 4.15,
ADR-0047) and stemming beside the surface form (4.19, ADR-0048) — and neither PR asked what
they had done to 4.8. That is the second thing this ADR is about.

## Decision

**Roadmap 4.8 is closed on measurement, and the comparison that closes it becomes part of
every evaluation run rather than part of this document.**

`mycelium eval --against <retriever>` scores a second retriever over the same cases, on the
same snapshot, in the same anchor space, and records it in the run manifest spec 04 §7.5
already requires — `incumbent`, `incumbent_overall`, `incumbent_per_slice`. It is computed
the way gate G2 already computes the lexical leg beside the hybrid one, inside one run,
because two numbers taken from two runs are a comparison only if someone checked that
nothing moved between them.

CI runs it with `--against grep` on **all three** corpora. That "all three" is the point:
the finding lived on the second corpus, and CI compared only the first, so nobody could see
the gap close and nobody would have seen it reopen.

It is **reported, never gated.** Spec 04 §7.4 quantifies the gate at 1.0 (roadmap 6.4), and
a baseline that can fail the build is a baseline nobody dares improve.

## The measurement

One run, today's product, both corpora, release sets — the sets nobody develops against.

| | filed at 3.15 (uv/release) | today (uv/release) | today (ours/release) |
|---|---|---|---|
| nDCG@10 | grep **0.409** vs 0.249 | **0.548** vs grep 0.519 | **0.504** vs grep 0.271 |
| MRR | grep 0.401 vs 0.227 | **0.496** vs 0.477 | **0.521** vs 0.270 |
| R@10 | grep 0.536 vs 0.429 | **0.786** vs 0.643 | **0.708** vs 0.375 |
| R@50 | 0.857 vs grep 0.643 | 0.893 vs 0.893 (tie) | **0.917** vs 0.625 |
| p95 | 14 ms vs grep 195 ms | **12 ms** vs 185 ms | **14 ms** vs 348 ms |

And the dev sets, for completeness: ours **0.531** vs 0.353, uv **0.653** vs 0.480. The
third corpus — the same `uv` documents, ingested rather than authored — reads **0.647**
against 0.566 on its release set. The product leads every set on every corpus.

**One honesty note that belongs in the headline**: the incumbent's own score moved too,
0.409 → 0.519. The corpus was re-judged at 3.17 and 4.12 and the chunker moved at 4.15, so
this is not "we went from 0.249 to 0.548 against a fixed opponent". The claim that holds is
the one measured today, on one corpus, with one set of judgments, on both sides at once —
which is exactly why the comparison now lives inside a single run.

**What closed it was not a re-ranking.** All thirteen candidates in
`tools/measure_ranking.py` remain refused, and the two changes that closed the gap were an
indexing change and a chunking change. ADR-0041's last sentence — *the unit of indexing is
not where this gap closes* — was right about the section unit and right about where to look
next.

## What is still conceded

The overall lead hides one slice, and the harness now prints it:

```text
vs grep: nDCG@10 0.548 against grep's 0.519 (+0.029) - ahead of the incumbent;
         still conceded: fact 0.403 vs 0.497
```

`fact` on the second corpus, seven cases, is still the incumbent's by 23 % relative. It is
the largest slice on that set and the one the corpus is made of — short imperative task
pages. The third corpus concedes the same slice (0.501 against 0.537), which is what turns
it from a quirk of one set into a property of that documentation. `symbol` is 0.0000 for
**both** retrievers on the second set: not conceded, because nobody leads it; unanswered,
which is a different problem and a different item.

Neither is smuggled into this closure. `fact` is filed as roadmap 4.25.

## Alternatives Considered

- **Close 4.8 with an ADR table and no product change.** The cheapest option and the one
  that repeats the failure. The gap closed at some point between 4.15 and 4.19 and nobody
  noticed for two items, because the comparison lived in a document and in a CI step that
  looked at the wrong corpus. A finding recorded only in prose is a finding that has to be
  re-derived.
- **Make it a gate now.** Tempting: the item was filed because the product lost, and a gate
  would make losing loud. Rejected because spec 04 §7.4 explicitly defers the quantified
  gate to 1.0, and because the threshold would be invented — on a seven-case slice, "grep
  wins by 23 %" is one case moving. A gate nobody believes is a gate everyone re-blesses
  (ADR-0039's finding, one item along).
- **Compare by diffing two `mycelium eval` runs.** What the tooling did before, and it works
  until it does not: two runs can differ in snapshot, in case set, or in the anchors that
  resolve, and nothing in either output says so. Computing both inside one run makes the
  comparability structural instead of procedural.
- **Report only the overall delta.** Rejected: the overall number is the one that would have
  let this ADR say "closed" and stop. `conceded` is what turns a closure into a next item.
- **Report every slice, not only the conceded ones.** The incumbent's full per-slice table is
  already available (`--retriever grep`, still run in CI), and repeating it on the comparison
  line would bury the one row a reader needs.
- **Keep asserting "we beat grep" only on our own dev set** — the test that existed. It is
  the set tuning is allowed to read, so a product fitted to it would pass while losing where
  it counts. The assertion now also covers our release set; the vendored corpora stay in CI,
  where they are already built, because building one inside the unit suite costs four
  minutes.

## Consequences

- **`EvalRunManifest` gains three optional fields.** Pre-1.0, same shape as the
  `companion_*` pair ADR-0027 added, defaults preserve the old JSON, and `mycelium/eval-run/v0`
  stays readable. A run measured alone records nothing.
- **Every CI evaluation now carries the incumbent's numbers**, on three corpora, in a
  manifest — so "are we still ahead" is answerable from an artifact rather than from a memory
  of an ADR.
- **`tools/measure_ranking.py` stops being the place the question is asked.** Its thirteen
  refusals stay: a refusal nobody can re-run is a claim, and the next attempt should start
  from numbers. Its framing is updated to say the item closed and that nothing in it is what
  closed it.
- **Two slices are named and left open.** `fact` on the second corpus (4.25) and `symbol`,
  which neither retriever answers.
- **The comparison costs a second scoring pass** when asked for — roughly a doubling of a
  run's wall time on the grep side, which is why it is opt-in per invocation rather than
  always on.
- **A test asserts the product beats the incumbent on our release set**, not only on the dev
  set it was previously checked against.

## References

- Spec 04 §7.4 (the grep baseline, and the gate deferred to 1.0), §7.5 (run manifests),
  §7.1 (the dev/release split), §7.3 (the gate table).
- D-010 — evaluation-first: no retrieval feature ships on architectural charisma.
- [ADR-0031](0031-refuse-three-rerankings.md) and
  [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md) — the thirteen refusals, and
  the hypothesis they left standing.
- [ADR-0047](0047-flip-the-packed-chunker-on-and-let-the-gate-say-so.md) and
  [ADR-0048](0048-index-the-stem-beside-the-surface-form.md) — the two changes that closed it.
