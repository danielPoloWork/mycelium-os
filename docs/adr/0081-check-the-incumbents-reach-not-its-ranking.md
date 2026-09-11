# ADR-0081: Check the incumbent's reach, not its ranking

- **Status:** Accepted
- **Date:** 2026-09-11
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.4
- **Related:** [ADR-0013](0013-adopt-the-evaluation-harness.md) (the harness and the grep
  incumbent this guards), [ADR-0072](0072-keep-our-own-restatements-out-of-our-own-benchmark.md)
  (the last time our own corpus moved this number, and the rule *not* to move the bar),
  [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md) (a
  self-hosting corpus is reported, not gated), [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md)
  (corpus growth moves a score with no retrieval change),
  [ADR-0031](0031-refuse-three-rerankings.md) (the refusals a fitted constant joins);
  spec 04 §7.2, §7.4; D-010; roadmap 5.10, 5.20

## Context

`tests/test_eval.py::test_the_grep_baseline_is_fair` has asserted
`grep.ndcg_at_10 > 0.3` since PR #24, when the harness shipped with 20 judged cases and a
37-document corpus. Its docstring states the purpose exactly: *"A baseline built to lose
proves nothing, so this one is checked for competence."*

Roadmap 5.10 found it at **0.3024** — 0.0024 above the floor — and tipped it under by adding
one ADR. That ADR documents the `supersedes` relation, and one of the judged cases is
`q-0014`, *"which ADR supersedes the cross-language source layout"*. A term-counting
incumbent ranks the new document above the two that *are* the answer, and grep falls to
0.2959 while **our own score does not move at all** (0.5435 either way). A same-size ADR on
an unrelated subject leaves grep at 0.3024, so this was not general dilution — it was one
document about the very relation a judged case asks about.

That is an uncomfortable shape and it deserves naming: writing documentation about a subject
our benchmark asks about **widens our measured lead without improving the product**. ADR-0072
met the same dynamic from the other side and fixed it by removing restatements from the
corpus, while refusing to move the bar — *"redefining a guard while it is red is the fitted
parameter this project has refused fourteen times."*

So the bar was not moved while it was red. The failing change was set aside, and the question
was asked here instead, on `main`, where the guard is **green** — which is the only honest
place to re-derive it.

**The measurement that decides it.** Five release points, with the judged set, the retriever,
the chunker and the scorer all held at today's, so that only the documents vary — the method
ADR-0044 used to separate corpus growth from a retrieval change:

| corpus | documents | chunks | grep nDCG@10 | grep recall@10 | grep recall@50 | ours nDCG@10 |
|---|---:|---:|---:|---:|---:|---:|
| v0.1.0 | 37 | 249 | 0.0961 | 0.219 | 0.281 | 0.2119 |
| v0.2.0 | 54 | 358 | 0.5198 | 0.812 | 0.948 | 0.6316 |
| v0.3.0 | 81 | 562 | 0.4854 | 0.781 | 0.948 | 0.5647 |
| v0.4.0 | 128 | 924 | 0.3580 | 0.677 | 0.812 | 0.5402 |
| today | 138 | 1013 | 0.3024 | 0.562 | 0.812 | 0.5435 |

(v0.1.0 is not a data point about dilution: today's judged set names documents that did not
exist yet, so grep and the product are both near the floor. The trend starts at v0.2.0, the
first corpus the cases can be answered from.)

Two things fall out, and they point the same way. grep's **ranking** decays monotonically
with corpus size — 42 % from v0.2.0 to today — while its **reach** moves once, at the v0.4.0
growth, and then holds at 0.812. And ours is close to flat over the same stretch, 0.5402 to
0.5435 across the last two points.

## Decision

**The competence assertion moves from `ndcg_at_10 > 0.3` to `recall_at_50 >= 0.75`.** The two
companion assertions — citation coverage exactly 1.0, false-answer rate exactly 0.0 — are
unchanged, and so is everything else about the baseline.

**The reason is a category error in the original, not the number it produced.** nDCG@10 is
*the thing under test*. Spec 04 §7.4 exists because the real incumbent is the agent's own
grep loop, and the product's claim is that a compiled, field-weighted, length-normalised
index **out-ranks term counting on a large corpus**. Asserting a floor on the incumbent's
ranking therefore asserts a floor on the quantity the product is trying to beat: the guard
fails hardest exactly when the claim is most validated. It was a time bomb, and 5.10 was
merely the PR that happened to be holding it.

**Recall is what the docstring always meant by "it finds real answers."** It says the answer
is inside the incumbent's reach — that grep sees the same corpus, in the same anchor space,
and its candidate set contains the judged passage. That is what makes the comparison *fair*.
Where the answer lands after that is the measurement, and a measurement cannot also be its
own guard.

**The threshold is derived, and the derivation is the table above.** recall@50 has taken two
values across four measurable releases, 0.948 and 0.812, with one step between them. 0.75
sits below the lower of the two with room for one more step of that size, and far above the
0.281 that a corpus the cases cannot be answered from produces. It is not the largest number
that passes today, which would be the fitted choice.

**What this deliberately does not do.** It does not lower a bar to make a red test green: the
change is made on `main` with the guard passing, and the change that failed is still on its
own branch, unmerged, and will be measured against this guard rather than the other way
round. It does not touch the corpus, the judged set, the retriever, or any number the project
publishes. And it does not weaken the check in the direction that matters — a rigged baseline
shows up as a *reach* failure, which the old floor could not see: at v0.4.0 grep's nDCG
(0.358) cleared the floor while its recall had already dropped a full step.

## Alternatives Considered

- **Re-derive the nDCG floor to a lower number**, say 0.25. Rejected: it buys one or two more
  releases and then fails again, for the same structural reason, and each re-derivation is a
  fitted constant with a shorter half-life than the last. The trend says the quantity is
  unsuitable, not that the number was wrong.
- **Assert the *ratio* instead** — that ours beats grep by some margin. Rejected outright: it
  is the product's own claim, so a guard on it could be satisfied by the product improving
  *or* by the incumbent degrading, which is precisely the failure mode this guard exists to
  detect.
- **Move the check to the vendored corpora**, applying ADR-0053's rule that a self-hosting
  corpus is reported rather than gated. Genuinely principled and the closest call here. It was
  put to the maintainer with this option beside it and was not chosen — and the reason it is a
  worse fit is that grep's *fairness* is a property of the harness, not of a corpus, so
  checking it only where the documents are frozen would stop asking the question exactly where
  the corpus is most likely to distort it.
- **Drop the competence check entirely**, since citation coverage and the shared-corpus test
  already constrain fairness. Rejected: those show grep searches the same thing, not that it
  finds anything in it. A baseline that returned the same anchors in a useless order would
  pass both.
- **Exclude ADRs from the corpus**, as ADR-0072 excluded changelogs. Rejected: a changelog
  restates what an ADR says canonically, which is why removing it improved retrieval as well
  as the benchmark. ADRs *are* the canonical documents, two of the twenty judged cases have
  ADR answers, and removing them to protect a number is the benchmark-first move D-010
  forbids.
- **Re-judge `q-0014` to credit the new ADR.** Rejected: it would raise grep by giving it a
  document it happened to rank, which is fitting a judgment to rescue a guard. By ADR-0062's
  rule the new ADR *frames* the relation and does not document it, so the judgment is right
  as it stands.

## Consequences

- **The guard now fails for a reason a reader can act on.** A drop in recall@50 means the
  incumbent has lost sight of answers it used to find — a real fairness problem. A drop in
  nDCG@10 means the corpus grew, which is not.
- **The number is still reported.** grep's nDCG@10 appears in every eval run, in the README's
  comparison, and in the gate G3 verdicts; nothing about what the project publishes changes.
  What changed is that a *test* no longer gates on it.
- **A latent failure is removed rather than deferred.** At 0.3024 the old assertion was within
  one ordinary documentation PR of red, and it would have fired on whichever change arrived
  first — a change with nothing to do with retrieval.
- **The dynamic behind it is named and stays named.** Documenting a subject our benchmark asks
  about inflates our measured lead. That is worth knowing when reading any ours/dev number,
  and it is the second time this corpus has done something like it (ADR-0072 was the first).
  It is also an argument for the vendored corpora carrying the enforcing gates, which is
  already the rule for G3 (ADR-0053).
- **Roadmap 5.10 is unblocked**, and is measured against this guard rather than the reverse:
  with its ADR in the corpus grep reads recall@50 0.812 and passes, while its nDCG reads
  0.2959 and is reported.
- **Known limit, on the record.** recall@50 will eventually decay too, on a corpus large
  enough that fifty candidates stop covering it. That is a much slower clock than ranking
  dilution — one step in four releases against a monotonic slide — and when it arrives the
  honest response is the one taken here: measure the trend, and ask what the guard is for.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §7.2 (the metrics), §7.4 (the grep
  incumbent and why it exists).
- Decision log: D-010 (fix the product, not the benchmark).
- Re-runnable: the trend table is produced by building the tree at each tag and scoring it
  with today's cases and code — `git archive <tag>`, `mycelium build --no-pin`,
  `mycelium eval . --against grep`.
- Tests: `tests/test_eval.py::test_the_grep_baseline_is_fair`.
