# ADR-0152: The ranking loss is ordering, not recall

- **Status:** Accepted
- **Deciders:** tech-lead (EADOS delivery agent) with the maintainer, per RFC-0001 /
  spec 03 §6
- **Date:** 2026-09-22
- **Related:**
  [ADR-0144](0144-measure-the-whole-diversity-family-and-refuse-it.md) (roadmap 6.29, which
  measured the ceiling this file is the shape of, and filed the shape as a follow-up),
  [ADR-0094](0094-mint-a-command-the-corpus-demonstrates-and-names-and-report-what-promotion-can-and-cannot-reorder.md)
  (report what a change can and cannot reorder — the discipline that produced the ceiling
  in the first place),
  [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) (hybrid did not earn
  the default, so the shipped profile is lexical-only — which is what makes a deep probe
  meaningful),
  [ADR-0029](0029-let-a-judgment-name-a-section.md) (section judgments, and the oracle
  correction they force),
  [ADR-0070](0070-take-the-leaf-heading-weight-on-the-third-asking.md),
  [ADR-0075](0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md),
  [ADR-0080](0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md)
  (the ranking changes this project has measured, none worth more than single digits);
  D-010, D-011;
  spec 04 §§3-4; spec 06 §3's deferred-decision table; roadmap 6.29, 6.37, 6.38

## Context

Roadmap 6.29 was filed to decide whether one document should be allowed half the slots a
search returns. It read the ceiling before tuning the heuristic (ADR-0094) and found
something much larger than the heuristic it was filed for: ordering **the same 50 fused
candidates** by their judged grade is worth **+36 % to +86 %**, against +1.4 % to +4.2 %
for the best diversity policy chosen with hindsight. ADR-0144 recorded the number, refused
the whole diversity family, and said in as many words that where that headroom actually
lives "is a different question, and the pool ceiling is the number that says it is worth
asking — filed as a follow-up rather than guessed at here."

This is that follow-up, and its first obligation is to not answer a question it has not
asked. Spec 06 §3 defers a learned/LLM reranker until *"deterministic pipeline plateaus on
frozen sets AND budget exists for the latency/cost"*. A ceiling of +36–86 % looks like the
first half of that trigger, and treating it as such would be assuming exactly what wants
establishing. So the item asked for a characterisation and nothing else: **where** in the
pool do the judged passages sit, **is** the loss concentrated in a slice, a corpus or a
document length, and — the decisive one — **does the pool contain the judged passage at
all**, which separates a ranking failure from a candidate-generation one and decides
whether the next item is about BM25 or about recall depth.

## Decision

**Record the shape, propose no mechanism, and state plainly which half of the reranker
trigger this does and does not establish.** `tools/measure_ranking_gap.py` is the
measurement; it joins `verify.py`'s `retrieval` rung to guard the conclusion rather than
the conclusion living only in this file.

### The decomposition, and why it is the right cut

A judged passage that does not score at depth 10 failed in exactly one of three places,
and they want different fixes: it is **not in the pool at all** (candidate generation
missed it, and no re-ranking recovers it); it is **in the pool but below the fold** (fusion
had it and put it out of reach); or it is **already in the ten, in the wrong order** — nDCG's
log discount means a grade-3 passage at rank 4 scores 0.43 of the same passage at rank 1,
so a case can lose half its score without a single missing candidate.

The runner separates them by re-ordering *perfectly* from progressively wider slices of one
pool: `reorder-10` may only permute the chunks already returned, `rerank-50` sees the
shipped pool, `rerank-200` a pool four times deeper than anything ships. The lexical leg is
generated `max(limit, VECTOR_CANDIDATES)` deep and the shipped profile is lexical-only
(ADR-0017), so one search per case yields all three by truncation, and every arm is
arithmetic on it.

### The oracle has to sort by the grade the metric awards

A judgment may name a chunk or a whole section (ADR-0029), and `credit_judgments` satisfies
a section judgment with any chunk under it. ADR-0144's oracle sorted by
`judged.get(anchor, 0)`, which scores a chunk under a judged section as worthless and sinks
it below unjudged candidates — an oracle understating its own ceiling. Sorting by the grade
the credit rule would award is worth **+1.6 to +3.7 points** of ceiling on the four sets
that carry section judgments (3–4 % of judgments; the two ingested sets carry none and move
+0.0). ADR-0144's headline is therefore slightly conservative, and its conclusion is
untouched — a larger ceiling only strengthens a refusal argued against it.

## Measured

Taken from a clean worktree, under the shipped configuration, because the question is where
the *shipped* ranking loses. The two frozen external corpora reproduce ADR-0144's control to
four decimal places (`uv/release` 0.6903, `uv-ingested/release` 0.6477) and its oracle
exactly (+36.2 %, +46.0 %), which is the check that this file measures what that file did.
`ours/release` has moved 0.4812 → 0.4767 because the self-hosting corpus *is* this
repository and has gained documents since 6.29.

### Where the ceiling is reachable from

| set | control | reorder-10 | rerank-50 | rerank-200 | inside the ten |
|---|---:|---:|---:|---:|---:|
| `ours/dev` | 0.6060 | 0.8142 (+34.4 %) | 0.9606 (+58.5 %) | 0.9828 (+62.2 %) | **58.7 %** |
| `ours/release` | 0.4767 | 0.7324 (+53.7 %) | 0.9143 (+91.8 %) | 0.9687 (+103.2 %) | **58.4 %** |
| `uv/dev` | 0.7395 | 0.9156 (+23.8 %) | 0.9898 (+33.8 %) | 0.9993 (+35.1 %) | **70.4 %** |
| `uv/release` | 0.6903 | 0.8665 (+25.5 %) | 0.9532 (+38.1 %) | 0.9885 (+43.2 %) | **67.0 %** |
| `uv-ingested/dev` | 0.7189 | 0.9091 (+26.5 %) | 0.9828 (+36.7 %) | 0.9951 (+38.4 %) | **72.1 %** |
| `uv-ingested/release` | 0.6477 | 0.8340 (+28.8 %) | 0.9457 (+46.0 %) | 0.9866 (+52.3 %) | **62.5 %** |

**Between 58 % and 72 % of the entire ceiling is reachable without a single new candidate.**
Permuting the ten chunks already returned is worth **+23.8 % to +53.7 %** on its own — an
order of magnitude above the single-digit percentages every ranking change this project has
measured has been worth, and it needs no new leg, no deeper pool and no additional
retrieval.

### Where the judged passages sit

Share of judgments, by the slice of the probe that holds them:

| set | in the ten | below the fold (11–50) | past the pool (51–200) | absent |
|---|---:|---:|---:|---:|
| `ours/dev` | 75.9 % | 17.5 % | 3.6 % | **3.0 %** |
| `ours/release` | 65.4 % | 19.8 % | 7.8 % | **7.0 %** |
| `uv/dev` | 85.4 % | 12.1 % | 2.3 % | **0.2 %** |
| `uv/release` | 79.3 % | 12.7 % | 5.8 % | **2.1 %** |
| `uv-ingested/dev` | 85.0 % | 11.9 % | 2.4 % | **0.7 %** |
| `uv-ingested/release` | 76.5 % | 15.4 % | 5.7 % | **2.5 %** |

**Candidate generation finds 93.0 % to 99.8 % of the judged passages.** That is the
decisive answer the item asked for: the next item is not about BM25. Nor is it about pool
depth — quadrupling the pool to 200 adds only **+3.8 % to +13.7 %** of the ceiling, and a
judgment the ten missed but the probe found sits at a median rank of **18 to 31**, in the
body of the shipped pool rather than beyond its edge.

The position data says the same thing from the other side: the best-graded judgment of a
case, when it is served at all, sits at **median rank 1** on four sets and rank 2–3 on the
two `ours` sets — but it is *first* on only **35.5 % to 59.1 %** of the cases that serve it.
The answer is usually in the ten and usually near the top; "near" is the loss.

### Where it is not concentrated

**Not in document length.** The document holding a judgment has a median 7–12 chunks when
the ten serve it and 7–12 when they do not, and the direction is not even consistent across
sets (`uv/dev` 10 vs 12, `uv/release` 12 vs 9). A long document competing with itself is not
what is happening.

**By grade, weakly — and not in the direction the item expected.** Grade 3 — the passages
that answer outright — are served 75.4 % to 93.4 % of the time; grade 2 only 38.5 % to
66.4 %. The obvious reading is that the ceiling is mostly the cost of failing to pack
*supporting* material into the ten, which would make it much less interesting than it
looks. It is not: restricting the whole measurement to grade-3 judgments alone moves the
ceiling by **−1.7 to +4.4 points**, and it moves *up* on `ours/dev` (+58.5 % → +62.9 %).
The headroom is the same size when only the passages that answer outright are allowed to
count. That was this item's first hypothesis and the measurement refused it.

**By slice, meaningfully, and it is the slice 6.29 predicted.** `relationship` is the worst
served on five of six sets (50.0 % on `ours/release` against 78.7 % for `conceptual`), which
is the same mechanism ADR-0144 found when a diversity cap cost that slice −65.2 %: a
relationship question's answer genuinely is spread across several chunks, so more of it
falls below ten. `fact` is worst on `ours/dev` (62.9 %). No slice is anywhere near
well-enough served to account for the ceiling on its own.

## Consequences

**The next item is about ordering the result set, and this file says so with a number.**
Not BM25, not chunking, not a deeper pool — all three are bounded above by the 0.2–7.0 % of
judgments that candidate generation actually misses and the +3.8–13.7 % that depth adds.
What has never been tried is re-ordering the passages the pipeline already returns.

**This does not establish the reranker trigger, and saying so is the point.** Spec 06 §3
asks whether the *deterministic* pipeline has plateaued. What is measured here is that the
remaining headroom is reachable by re-ordering — not that no deterministic rule can reach
it. Every ranking change this project has measured (ADR-0070's leaf-heading weight,
ADR-0080's symbol leg, ADR-0075's graph expansion, ADR-0144's diversity) aimed at *which
candidates are selected* or *which legs compose*; none aimed at the order of the served set.
A family with no attempts in it has not plateaued, it has not been tried, and the two are
only the same to someone who wants the conclusion. The trigger stays unmet.

**Roadmap 6.38 is aimed at the right place, and can now be priced.** Its heading-proximity
and trust-class boosts are within-the-ten re-orderings, so they are priced against the
58–72 % share rather than against the whole ceiling or against zero — the interaction 6.38
already anticipated, now with the share it needs.

**`tools/measure_ranking_gap.py` joins `verify.py`'s `retrieval` rung.** It is not an
ablation and has no arm to ship; what it guards is the *shape*, because anything filed on
this conclusion is filed on this number. `--check` fails when re-ordering the served ten
stops carrying the majority of the ceiling on a release set — a floor with real headroom
below the measured 58.4–72.1 %, not a target. The day candidate generation becomes the
binding constraint instead, this characterisation is stale and should be re-read rather
than rediscovered.

**Cost.** About one minute across six sets: one search per case, and every arm is
arithmetic on the one pool. It is the cheapest runner on the rung.
