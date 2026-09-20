# 2026-09-19 — six hundred and forty-six judgements (roadmap 6.8)

- **Session scope:** roadmap 6.8 — author the judged release sets to the count
  `enforceable_at` derives for each slice, so the per-slice condition stops being a per-case
  veto.
- **PR:** #171 (`feat/grow-the-judged-release-sets`). Follows #170, merged as `ca1b6c1`.
- **Milestone 6:** 6.8 closed; 6.33 filed for the dev sets.
- **Decisions it records:**
  [ADR-0136](../../../adr/0136-author-the-judged-sets-to-the-count-their-own-bar-needs.md)
  (the authoring) and
  [ADR-0137](../../../adr/0137-let-a-gated-default-follow-its-ablation-and-narrow-the-rule-that-would-refuse-it.md)
  (the default the authoring falsified, and the rule that had to be narrowed to land it).

## The item was reading, and the reading is the deliverable

ADR-0123 left one sentence of work: *"What is left is the authoring."* Six hundred and forty-six
judgements later, that is still the honest description of the session. Almost none of the time
went on code — the generators, the validator and the carry all existed and none of them needed
changing. It went on opening documents: uv's eighty-one pages, and this repository's own ADRs,
specifications, workflow documents and bug records.

The method is ADR-0067's, at ten times the scale. Read the document. Decide what a reader would
ask it. Decide which passage answers, and at what grade. Write the note that says why. Never
run a retriever to find out what it likes — the generator's build validates that an anchor
*exists*, and nothing but reading can validate that it *answers*.

## What the conventions did under load

Applying a rule 646 times is the strongest test it gets, and the three that carried the most
weight held:

- **`symbol` names the documenting section** (ADR-0062), the framing section is a 2, the
  feature-list entry is a 1. uv's documentation fits this almost everywhere, because it is
  written as concepts plus guides plus a feature list — the three tiers were sitting there
  waiting.
- **`exact` names the section that documents the literal** (ADR-0101), not every section that
  contains the string. This is the one that takes discipline: `UV_NO_MODIFY_PATH` appears in
  two documents and only one of them explains it.
- **A judgement may name a section** (ADR-0029) where the answer is spread across it.

Where the corpus did not fit the convention, the case says so rather than being forced: three
commands that the feature list is the *only* home of, a licence section of 27 tokens that is a
complete answer, a 26-token section that is a command's entire documentation. The stub lint
flags two of them on every run, and the notes say why they were kept.

## Two things I deliberately did not do

**No new slice.** Our own release set has four gated rows, and a `symbol` row would have
arrived needing fifty cases of its own. A fifth under-powered row is not a gain.

**No dev-set work.** They are reported, never gated. Growing them buys an overfitting signal
rather than enforcement, and doubling a 646-judgement review surface for it is the wrong trade
in one change. Filed as 6.33 with the reason.

## The part nobody planned

Judging a document for the first time takes a format slot in the twin's rotation, and 38 of
uv's 81 documents had never been judged. `format-rotation.json` is append-only and only grows
when a render actually happens (ADR-0056), so the honest path was to extend it and re-render:
13 PDFs through the pinned typst, 12 DOCX/HTML through pandoc, the evidence re-projected, the
carry re-derived. The assignment went from 29 judged documents in three formats to 66, and the
judged span of that corpus is no longer a third of it.

One document is held back from that, and it took a failing test to see why. `docs/index.md` is
the only document in the corpus with raw inline HTML, and it is the site roadmap 5.40 measured
ADR-0110's rule on, end to end, through the HTML lane. Judged, it would have rotated into PDF —
where the caption does not survive at all — and the claim would have lost its only instrument.
So three cases that named it are re-anchored, one is dropped, and the landing page stays a
distractor. That is a different trade from the one above and the ADR says both out loud.

The alternative was to keep every judgement inside the 29 documents that already had slots —
125 of the 380 new uv cases touch the newcomers — and that is fitting the judgements to the
instrument. The test that caught it (`test_every_judged_document_has_a_recorded_slot`) is
doing exactly the job it was written for.

## The set falsified a shipped default, which is the whole point of having one

I had written *"no retrieval change rides along"* into the ADR before I ran the ablations,
because that is what this item was supposed to be. Then the symbol leg's runner came back
inverted.

The leg was switched on at roadmap 5.25 on a held-out gain measured over **four** judged
`symbol` cases, and ADR-0096 put the caveat in the record rather than a footnote: *"on the
release sets the gain is one case"*. This session took that slice to **58**. At that size the
reading flips on the very corpus the gain was claimed for — `uv/release` still earns it
(+5.0 % on the slice) and `uv-ingested/release`, the twin 5.25 cited, **regresses** −5.8 % on
the slice and −0.7 % overall. The bar has never moved: a release-set gain with no overall
regression on any set. So `[retrieval] symbol_lookup` goes back off, and ADR-0080's rule — the
flag follows the measurement, in both directions — gets applied in the direction nobody had
had to apply it in yet.

Nothing about the leg changed. What changed was the denominator, and four cases could not see
it. That is the instrument ADR-0123 built doing the job it was built for, on the first set
large enough to run it.

Then it collided with a rule I had been leaning on one paragraph earlier. Flipping the flag
means editing `config.py`, which is a tuning path, and `check_frozen_release_sets.py` refuses a
change that moves a release set *and* a tuning path — for a good reason, and the reason is the
one I had just written down. No ordering of two pull requests gets out of it: the sets alone
leave `measure_symbol_leg.py --check` red on `main`, and the flag alone has no evidence,
because on the committed four-case slice the leg still earns it.

The maintainer took the decision: land both, narrow the rule. The narrowing is ADR-0056's
argument applied a second time — retire a proxy where the direct check exists and is stronger.
A *gated default* is one an ablation runner already holds, and that runner re-measures on the
sets in the same tree, so a default cannot be chosen to flatter a set without the runner saying
so. Three flags qualify, each named beside its runner; the exemption applies only when the
gated default is the whole of what the diff binds in `config.py`; and it prints which flag it
allowed and which runner authorised it, because an exemption that fires silently is how an
exemption rots.

The consequence that surprised me least, on reflection: the determinism golden moved.
`observe_build` records a `config_digest`, so a shipped default changing it is the golden
working. Had it not moved, the digest would not have covered what it claims to.

## The bless had to happen somewhere else

Our own corpus is our own documentation, and the working tree held the maintainer's
uncommitted work as well as this change's. A baseline taken there records a corpus nobody can
reproduce, and G3 would then report *"the corpus has changed"* forever instead of enforcing —
which is precisely the failure this item exists to end. So all three release baselines were
re-blessed, both arms, in a clean checkout of the merge tree — and then again, after the
default flip, because a shipped default changes what every arm measures. Gate G2's verdict was
re-recorded with them. Every figure in the ADRs, the changelog and the roadmap is read from
that second round; the ones written before it were a percentage point out, which is exactly
how a number quoted from the wrong run looks.

## What a reviewer can actually check

Not 646 judgements by reading them. What is checkable: the method, the conventions (all four
already on the record), the mechanical validation that every anchor resolves against a clean
build, the carry's printed drops, and a sample. The notes exist for the sample — each says why
*this* passage answers *this* query, so a wrong judgement is visible without leaving the file.
That limit is stated in the ADR rather than left for a reviewer to discover.
