# ADR-0029: Let a judgment name a section, and credit it once

- **Status:** Accepted
- **Date:** 2026-08-31
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.1, §7.2
- **Related:** [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md)
  (which filed this), [ADR-0013](0013-adopt-the-evaluation-harness.md),
  [ADR-0023](0023-make-the-chunk-target-steer-size.md); D-010; roadmap 3.15

## Context

ADR-0027 hit this while judging a corpus nobody here wrote. Two `exact` cases and one
`symbol` case scored **0.000** — and not because retrieval failed. For `storage directories`
the retriever returned five chunks from the right document, under the right heading, and the
case had judged the section's *opening* chunk. A section is not a chunk; the metric was
anchor-exact; so the case was measuring how well the judge had guessed where the chunker
splits.

Our own judged sets never showed it, because their anchors were chosen by someone who knew
where the boundaries fall. That is the same-author bias appearing as a *method* rather than
as a generous grade.

Two further facts make this more than a tidy-up. An anchor carries an **ordinal**
(`doc#slugs/3`), and ADR-0023 made `[chunking] target_tokens` a real knob — so a
configuration change moves every boundary and invalidates every judged anchor in the
repository. A benchmark a setting can invalidate is not durable. And the accuracy being
demanded of the judge — know the chunker — has nothing to do with the thing being measured.

## Decision

**A judged anchor may name a chunk or a section, and the notation says which.**
`docs/a.md#setup/2` is that chunk. `docs/a.md#setup/` — trailing slash — is the section, and
any chunk under it satisfies the judgment.

The trailing slash is not decoration. A heading can slug to digits (`## 2024`), so a bare
`docs/a.md#2024` cannot be told apart from ordinal 2024 of the document's lead section. The
marker removes the ambiguity instead of hoping it never arises.

**A section is credited once, however many of its chunks come back.** After the first match
the rest of the section is neither rewarded nor punished: it sits in the ranking as any
unjudged passage does. Without that rule a section split into twelve chunks would let a
retriever fill the top ten with one section and score a perfect run for finding a single
thing.

**Exact judgments are matched before section judgments**, so a set that names both means what
it wrote: the chunk, with its section as a weaker fallback.

**Which to write is a judgment about the document, not a default.** A section whose answer is
one paragraph deserves the chunk; a section whose answer is spread across a dozen deserves
the section. Making section-scope the automatic unit would credit "right neighbourhood" as
"right answer", and a reader who gets chunk 7 when the answer is in chunk 4 did not get the
answer.

**Nothing is re-judged here.** The mechanism ships; the committed sets still judge chunks, a
test asserts it, and every number is unchanged — verified rather than assumed. Re-judging is
roadmap **3.17**, deliberately a separate act: ADR-0027 froze those sets *after* seeing their
scores, and rewriting judgments in the same change that rewrites the metric is the pattern
`tools/check_frozen_release_sets.py` exists to refuse.

## What the measurement said before the decision

Section-scope was applied to the *existing* judgments — without editing them — to see what it
would move. nDCG@10, both retrievers, all four sets:

| set | retriever | chunk-exact | section-scoped |
|---|---|---:|---:|
| ours / dev | mycelium | 0.567 | 0.567 |
| ours / release | mycelium | 0.453 | 0.457 |
| uv / dev | mycelium | 0.403 | 0.403 |
| uv / release | mycelium | 0.249 | **0.335** |
| uv / release | grep | 0.409 | **0.499** |

It moves what the diagnosis predicted and nothing else: our own sets shift by 0.000–0.004,
because their anchors were already chunk-accurate, and the `uv` sets shift by ~0.09, because
theirs were not. **No comparison changes direction** — the product still beats grep on our
corpus, grep still beats it on theirs, and the dev/release gap survives — so this is a change
of unit, not of verdict.

That is also the reason it is safe to adopt while the numbers are in view: it was chosen
knowing exactly which of them it raises, and it raises them where the judgments were coarse
rather than where the product is weak.

## Alternatives Considered

- **Require judgments to enumerate every answering chunk.** Rejected: it keeps the ordinal in
  the anchor, so ADR-0023's chunking knob still invalidates the whole set, and it makes the
  judge's knowledge of the chunker a permanent input to the benchmark.
- **Make section-scope the only unit.** Rejected: it credits the right neighbourhood as the
  right answer. A section can be long, and a chunk of it can be unrelated to the query — the
  judge should be able to say "this paragraph, not this chapter".
- **Credit every matching chunk of a judged section.** Rejected: it inflates recall to 1.0
  for a retriever that finds one section and returns ten of its chunks, which is the opposite
  of what recall means.
- **Auto-grade a judged chunk's section-mates at grade 1.** Tempting, and rejected: it
  asserts relevance nobody judged. Proximity in a document is not evidence about a query.
- **Change nothing and re-judge the `uv` cases chunk-exactly.** Rejected: it treats a
  structural problem as a data-entry error, and the next chunking change would reintroduce it.

## Consequences

- **Every committed number is unchanged**, because no committed judgment uses the new form.
  The gates, the baselines and the dev/release gaps are exactly what ADR-0027 recorded.
- **When 3.17 re-judges, numbers will move**, upward, mostly on the second corpus. Any
  comparison across that boundary is invalid, and the re-judging PR is where that gets said
  loudly and the baselines get re-blessed.
- **A judged set survives a chunking change** to the extent it uses section anchors — which
  is the durability argument, and the reason to prefer them where the judgment is honestly
  about a section.
- `RelevantAnchor.anchor` widens from `Anchor` to `JudgedAnchor`. Existing sets validate
  unchanged; a consumer reading judged anchors must now expect the section form.
- **The metric definition grew a step, and it lives where the metrics live.**
  `credit_judgments` is part of what "relevant" means, not a harness convenience, so it sits
  in `mycelium.eval.metrics` beside the definitions it modifies.

## References

- Spec 04 §7.1 (judged sets), §7.2 (metrics); D-010
- [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md) — where the
  flaw surfaced, and why it was left standing
- [ADR-0023](0023-make-the-chunk-target-steer-size.md) — the knob that moves every ordinal
