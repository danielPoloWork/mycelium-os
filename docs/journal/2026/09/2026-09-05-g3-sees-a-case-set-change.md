# 2026-09-05 — the third controlled variable (roadmap 4.24)

- **Session scope:** roadmap 4.24 — gate G3 cannot see a case-set change.
- **PR:** #72 (`feat/g3-sees-a-case-set-change`). Follows #71 (4.21), merged as `6e8e3c3`.
- **Milestone 4:** 4.24 done; 4.15, 4.18, 4.20, 4.22, 4.23, 4.25 open.

## Three, not one

G3 needs a controlled variable, and this repository has now found out that its controlled
variable is three things:

1. **The corpus.** BUG-0014: documentation grows, slices move, the gate fires on prose.
2. **The boundaries.** 4.13: comparability was the fold of chunk digests, so a chunking
   change tripped the not-comparable branch — and the gate best placed to judge one was blind
   to it by construction (ADR-0045).
3. **The judgements.** 4.15, found within days of fixing the second: a derived set was
   regenerated from 14 cases to 16, `fact` went from five cases to seven, and G3 reported
   `fact 0.632 → 0.494 (-21.8%)` against a baseline blessed *minutes* earlier.

The third is the same failure as the first two, and it has the same shape: a slice's score is
a mean, the case set is its denominator, and a gate comparing means over different
denominators is comparing nothing.

## The part that mattered more than the false alarm

The verdict named a slice and a percentage, in the *same words* it uses for a real
regression. That is worse than being wrong: a gate that reports population change in the
vocabulary of regression teaches everyone to discount both, which is how a gate becomes
decoration.

So the enforcing branch keeps `beyond -2%` and the abstaining branch now says
`moved beyond -2%`, followed by which variable moved. The numbers stay — a reviewer wants
them — and the word "regression" is withheld, because it would be false. The counterfactual
is a test: the identical drop with the judgements held fixed still fails.

## What is digested, and what is deliberately not

Case ids, queries, slice membership, answerability, and every judged anchor with its grade.
Cases sorted by id, so a reordered set is the same set.

**Not `note`.** It is prose for whoever re-judges the case next. A fingerprint that made the
gate abstain because someone documented a case better would teach the next person to leave
notes alone, and this project's judged sets are already thin enough (4.20) without
discouraging the one field that explains them.

That is also the reason not to digest the file's bytes, which was the one-line version: it
would catch reformatting and note edits, neither of which can move a score. A fingerprint
should be sensitive to exactly what it controls for and blind to the rest.

## Arming the existing baselines, and the evidence for it

A baseline written before today records no case-set identity, and ADR-0045 already settled
what to do: keep the comparison the baseline was written for, and say the new one is unarmed.
Reading the absent field as a match would let a baseline enforce across a case-set change —
4.15 exactly — and reading it as a mismatch would disarm G3 on every baseline at once.

But the field can be *stamped*, because a case set is a committed file and needs no build.
The question is whether stamping is honest, and the answer is in Git: if the case set has no
commit newer than the baseline, the set as it stands is the set the bless saw. All three
pairs check out today, so the rule is encoded in the stamp tool as a refusal rather than
applied by hand — an edit after the bless, or an uncommitted one, and the claim is
unverifiable.

Ours still refuses, for the pre-existing reason (its chunk fold has drifted), and I left it
alone. Stamping it would have attached a true field to numbers known to be stale and made the
file look more armed than it is, which is 4.22's decision to take, not mine to pre-empt.

Both vendored corpora now report: *same corpus, same boundaries, same judgements, no slice
regressed.*

## What this leaves open, deliberately

A set edited in one slice disarms enforcement for **all** slices, including untouched ones.
The fix is per-slice populations in the baseline, which is more machinery than the evidence
supports today and belongs with 4.20 — an item already about exactly that.
