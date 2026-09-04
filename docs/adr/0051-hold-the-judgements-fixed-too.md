# ADR-0051: Hold the judgements fixed too, and name a population change as one

- **Status:** Accepted
- **Date:** 2026-09-05
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.24; RFC-0001; spec 04 §§7.1, 7.3, 7.5; D-010;
  [BUG-0014](../bugs/2026/08/BUG-0014-g3-compares-incomparable-corpora.md),
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md),
  [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md),
  [ADR-0045](0045-ask-the-documents-whether-two-runs-are-comparable.md)

## Context

Gate G3 forbids a release from regressing a protected slice by more than 2 % (spec 04 §7.3).
A regression check needs a controlled variable, and this project has now discovered its
controlled variable is not one thing but three.

BUG-0014 found the first: on a self-hosting corpus the *corpus* moves, so adding
documentation moved slices and the gate fired on prose. Roadmap 4.13 found the second: the
comparability test was the fold of chunk digests, so a *chunking* change tripped the
not-comparable branch and the gate best placed to judge one was blind to it. ADR-0045 split
those apart — `content_digest` decides whether G3 enforces, `corpus_digest` records how the
corpus was cut and is reported.

Roadmap 4.15 found the third, immediately and painfully. Regenerating the derived ingested
sets grew release from **14 cases to 16**; `fact` went from five cases to seven; and G3
reported

```text
fact 0.632 -> 0.494 (-21.8%)
```

as a regression against a baseline blessed *minutes earlier*. Nothing had regressed — scored
on the same build, the old set still gave exactly its old number. A slice's score is a mean
over the cases in that slice, so changing the set changes the denominator, and the gate had
no notion of whether the judgements were the ones its baseline was taken on. The only
available response was to re-bless, which is the response the gate exists to make
unnecessary.

Worse than the false alarm was its *shape*: the verdict named a slice and a percentage, in
the same words it uses for a real regression. A gate that reports population change in the
vocabulary of regression teaches its readers to discount both.

## Decision

A baseline records the **identity of the judgements** its per-slice means were taken over,
and G3 requires that identity to match before it enforces.

`case_set_digest(cases)` digests what moves a score: each case's id, query, slice
membership, answerability, and every judged anchor with its grade — cases sorted by id, so a
reordered set is the same set. `note` is excluded: it is prose for whoever re-judges the case
next, and improving it must not disarm a gate. The digest lands in the run manifest as
`cases_digest` (spec 04 §7.5) and in the baseline beside the corpus fingerprints.

When the judgements differ, the gate **abstains and says which variable moved**, and the
movement is named as *movement*:

```text
moved beyond -2%: fact 1.0000 -> 0.6667 (-33.3%); the judgements changed since the
baseline was taken, so these numbers are means over different case populations -
reported, not enforced.
```

Never `beyond -2%`, which is reserved for the enforcing branch. The numbers are kept, because
a reviewer wants them; the word "regression" is withheld, because it would be false.

Three subordinate choices:

**A baseline with no `cases_digest` keeps the comparison it was written for**, and the
verdict says the new one is unarmed. This is ADR-0045's rule applied unchanged: reading the
absent field as a match would let a baseline enforce across a case-set change — exactly what
4.15 hit — and reading it as a mismatch would disarm G3 on every baseline at once.

**The case-set change is checked before the corpus change.** When both moved, the
judgements are the more surprising finding and the one whose remedy differs: a corpus change
is expected on a corpus under authorship, a case-set change is a deliberate act someone
performed. Only one reason is reported, because two abstention reasons in one line is noise.

**`tools/stamp_baseline_fingerprints.py` arms the existing baselines, and refuses on
evidence.** The digest needs no build — the case set is a committed file — but a stamp
asserts *"these scores were means over these judgements"*, and the only evidence available
after the fact is history. The rule: the last commit touching the case set must be an
ancestor of the last commit touching the baseline. A later edit, or an uncommitted one, and
the claim is unverifiable, so the tool refuses rather than assumes.

## Alternatives Considered

- **Fail the gate on a case-set change, rather than abstain.** Defensible: a changed set is a
  deliberate act, so make the actor re-bless. Rejected because it makes G3 red on every PR
  that adds a judged case — which is work this project wants more of (4.20 asks for exactly
  it) — and a gate that punishes the behaviour it wants is a gate people route around.
- **Record the case *count* instead of a digest.** Cheaper, and it catches 4.15's 14 → 16.
  Rejected: it is blind to the case that matters more, a re-graded anchor on the same number
  of cases, which moves a mean without moving a count.
- **Digest the whole case file's bytes.** One line, and it catches everything. Rejected
  because it catches too much: reformatting the JSONL, or improving a `note`, would disarm
  the gate for a change that cannot move a score. A fingerprint should be sensitive to
  exactly what it is controlling for.
- **Include `note` in the digest anyway, for safety.** Rejected on the same ground, from the
  other side: it would make the gate abstain because someone documented a case better, and
  the next person would learn to leave notes alone.
- **Compare per-slice case counts instead of set identity, and enforce where a slice's
  population is unchanged.** Genuinely attractive — it would keep enforcing on the slices a
  change did not touch. Rejected for now as more machinery than the evidence supports: it
  needs per-slice populations in the baseline, and the failure it buys over this is a set
  edited in one slice while another regresses. Worth revisiting with 4.20, which is already
  about slice populations.
- **Stamp `cases_digest` onto every baseline unconditionally.** It would arm the gate
  everywhere at once, including on this repository's own. Rejected: ours' scores are known
  stale (4.22), so the stamp would attach a true field to untrustworthy numbers and make the
  file look more armed than it is. Refusal is per corpus, and a corpus that refuses is left
  byte-identical — case-set fingerprint included.

## Consequences

- **G3 now states all three controlled variables in its verdict.** On both vendored corpora:
  *"same corpus, same boundaries, same judgements, no slice regressed"*. It cannot claim the
  third on a baseline that does not record it, and does not.
- **4.15's report is reproducible and now correct.** A demo set grown from 2 cases to 3
  produces `moved beyond -2%: fact 1.0000 -> 0.6667 (-33.3%)` with the gate abstaining; the
  identical drop with the judgements held fixed still fails. Both directions are tests.
- **Two baselines are armed in this change**, by stamp rather than by re-bless: added lines
  only, no score moved. This repository's own refuses, correctly and for the pre-existing
  reason — its chunk fold has drifted since the bless — and 4.22 is where that is decided.
- **`EvalRunManifest` gains `cases_digest`**, optional. Eval records are not among the five
  contracts that freeze at 1.0 (architecture §10), and a run manifest that cannot say which
  judgements produced it is not reproducible in the sense spec 04 §7.5 asks for.
- **A baseline also records `cases`**, the count. It is not what the gate compares — the
  digest is — but it is what makes a diff between two baselines legible to a person.
- **Any change that regenerates a derived case set now says so through the gate** instead of
  through an argument in a PR body, which is what 4.15 had to do by hand.
- **What this does not fix:** a set edited in one slice still disarms enforcement for *all*
  slices, including untouched ones. That is the per-slice-population alternative above, and
  it belongs with 4.20.

## References

- ROADMAP 4.24 (this item), 4.15 (where it was found), 4.13 and BUG-0014 (the same failure
  one and two levels up), 4.20 and 4.22 (what it leaves open).
- Spec 04 §7.1 (the dev/release split), §7.3 (the gate table), §7.5 (run manifests).
- [ADR-0045](0045-ask-the-documents-whether-two-runs-are-comparable.md) — the corpus half of
  the same argument, and the source of the missing-field rule reused here.
- [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) — why small slice
  populations make this gate fragile in the first place.
