# ADR-0136: Author the judged sets to the count their own bar needs, and re-bless what that moves

- **Status:** Accepted
- **Date:** 2026-09-19
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §§7.1, 7.3, 7.6
- **Related:** [ADR-0123](0123-derive-the-count-a-slice-needs-instead-of-guessing-it.md) (which
  derived the count this authors to, and left the authoring as the whole of what remained),
  [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md) (which named the denominator as the
  only fix), [ADR-0044](0044-name-what-a-two-case-slice-can-and-cannot-say.md) (what a thin
  slice can and cannot say), [ADR-0069](0069-read-g2s-slices-case-by-case-and-keep-the-bar.md)
  (gate G2's half of the same problem),
  [ADR-0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md) (dev/release,
  and who judged the documents), [ADR-0067](0067-grow-the-dev-set-before-asking-it-a-question.md)
  (the road this follows: written from the documents, committed before anything is scored),
  [ADR-0062](0062-a-symbol-judgment-names-where-the-thing-is-documented.md),
  [ADR-0101](0101-let-the-exact-slice-name-the-section-that-documents-the-literal.md),
  [ADR-0065](0065-one-section-cannot-document-two-commands.md),
  [ADR-0029](0029-let-a-judgment-name-a-section.md) (the grading conventions every new case
  follows), [ADR-0039](0039-measure-what-projection-costs.md) (the carry, unchanged),
  [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md),
  [ADR-0112](0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md)
  (what a bless is dated to), [ADR-0051](0051-hold-the-judgements-fixed-too.md) (why a
  baseline records the judgements it was taken over); spec 04 §§7.1, 7.3, 7.6; D-010;
  roadmap 4.41, 6.8

## Context

Gate G2's second condition and gate G3's are statements about a *category* of question — "no
slice worse than −2 %". At four to seven cases a slice they were statements about one
question. ADR-0123 made that visible and computable: `enforceable_at(mean, scores)` derives,
from a slice's own blessed numbers, the count at which no single case can trip its bar alone,
and G3 enforces a slice only when it holds that many. The honest consequence was stated there
and is worth repeating, because it is what this item exists to end: **G3 enforced nothing, on
any set.** Fourteen slices across three committed baselines, every one of them short, needing
**50 to 97** cases against the four to seven they held.

ADR-0123 also said what was left: *"What is left is the authoring"* — roughly 600 cases for
the release sets, each a query and a verified anchor written from the documents. It refused to
carry that work, for a reason this ADR inherits: **a judged set is permanent infrastructure,
and cases written to hit a count would measure the judge's haste for the life of the
project.**

## Decision

**The three release sets are authored to the count their own slices need, and nothing else
about the instrument moves.** No bar is re-cut, no threshold is tuned, and nothing is judged
to make a number look better. The only things that change are the judged sets, the derived
twin, and the baselines that had to be re-taken because the sets they describe are different
sets.

One retrieval change does travel with this, and it is the opposite of a tuning: at fifty-eight
`symbol` cases the symbol leg's own ablation stopped earning the default it shipped with, so
`[retrieval] symbol_lookup` goes back off. That flip is a *result* of these sets rather than an
input to them — the cases were written and committed before anything was scored — and it is
argued, with the rule it required narrowing, in [ADR-0137](0137-let-a-gated-default-follow-its-ablation-and-narrow-the-rule-that-would-refuse-it.md).

| set | cases before | cases after |
|---|---:|---:|
| `eval/release.jsonl` — this repository's documentation | 19 | **286** |
| `eval/corpora/uv-docs/eval/release.jsonl` — documentation we did not write | 25 | **404** |
| `eval/corpora/uv-docs-ingested/eval/release.jsonl` — the same, projected | 25 | **404** |

**Every case was written from the documents, and the anchors were read rather than
retrieved.** The discipline is ADR-0067's, applied at ten times the scale: the query is phrased
the way a reader would ask it, the anchor is chosen by opening the document, and no candidate
retriever was consulted at any point. The generators validate every anchor against a clean
build before either set can be written, so a case that names a passage the corpus does not hold
cannot be committed ([BUG-0026]'s discipline, now exercised 646 times).

**The grading conventions are the ones already on the record, not new ones.** A `symbol`
judgment names the section that documents the named thing, a page that frames it is a 2 and a
list entry that names it is a 1 (ADR-0062, ADR-0065); an `exact` judgment names the section
that documents the literal, not every section containing the string (ADR-0101); a judgement may
name a section rather than a chunk where the answer is spread across it (ADR-0029). Applying a
convention 646 times is the strongest test it has had, and it held: the three-tier shape fits
most commands and most literals, and where it did not — a command the corpus only ever lists,
a literal with one home — the case is graded to what the corpus actually holds and the note
says so.

**The dev sets are not grown here, and that is filed rather than forgotten.** They are scored
beside the release sets and *reported, never gated* (ADR-0027), so growing them buys an
overfitting signal rather than enforcement. Doing both in one change would double a review
surface that is already 646 judgements, and the item that matters for the gates is this one.
Roadmap 6.33 owns the dev sets.

**Our own release set gains no `symbol` slice.** It has four gated rows — `conceptual`,
`exact`, `fact`, `relationship` — and a fifth would arrive needing fifty cases of its own to be
enforceable, which is a new under-powered row rather than a gain. The symbol evidence for this
corpus stays where it is, in the dev set.

**The twin is carried, exactly as before.** `tools/build_ingested_cases.py` maps every new
anchor through the same coverage and `whole` floors; **27 anchors are dropped and every case
survives**, 15 of them landing on a chunk another judged unit also landed on. The drops are the
projection's cost, reported rather than repaired: most are uv's feature list, which the HTML
lane shatters into a heading per item (ADR-0111's shape, now with more instances of it).

**Judging a document for the first time takes a format slot, so 26 documents were re-rendered.**
This is the part of the change nobody planned and the design did: the twin's format assignment
is a mechanical rotation over an append-only record, and `format-rotation.json` only grows when
a render actually happens (ADR-0056). Before this change 29 of uv's 81 documents were judged;
the new cases judge 66, and the newcomers had no slot. So the record was extended and the
rotation re-run: **13 PDFs through the pinned typst 0.15.0 and 12 DOCX/HTML through pandoc
3.10** (ADR-0098, ADR-0105), the evidence re-projected, and the carry re-derived against it.
The assignment is now 22 DOCX, 22 PDF and 37 HTML — which is *better* evidence than the
corpus had before, because the judged documents are no longer concentrated in a third of it.
The alternative was to keep the judgements inside the 29 documents that already held slots, and
that is fitting the judgements to the instrument.

**One document is deliberately left unjudged: `docs/index.md`.** It is the only document in
that corpus with raw inline HTML — a hero caption in `<p align="center">` — and it is the
site roadmap 5.40 measured ADR-0110's rule on, end to end, through the HTML lane
(`test_the_lanes_agree_on_the_caption_they_used_to_disagree_about`). Judging it would have
moved it into the PDF rotation, where the caption does not survive at all, and the claim would
have lost its only test site in the corpus. Three cases that named it are re-anchored to where
the same facts are documented — the feature list and the pip interface — and one, the
`10-100x` speed claim, is dropped because the landing page is its only home. That is a smaller
loss than a measured claim losing its instrument, and it is stated here rather than discovered
in a diff.

**Every release baseline is re-blessed, both arms, in a clean checkout of the merge tree.** A
baseline records the judgements it was taken over (ADR-0051), so a set this much larger makes
the old one describe a different measurement. Both arms because a baseline that records only
the primary retriever leaves the incumbent's column stale. A clean checkout because this
repository's corpus is its own documentation and the working tree holds work that is not in
the change — including, on the machine this was taken on, documents belonging to the
maintainer.

## Alternatives Considered

- **Author only as many cases as it takes to pass `enforceable_at` today, and stop.** Rejected,
  and it is the temptation the item itself names: a count is a floor derived from a slice's
  current numbers, not a target, and cases chosen to reach it would be chosen for their number
  rather than for what they ask. The sets are written to the count and then judged on whether
  each case is a question a reader would ask.
- **Grow the dev sets in the same change.** Rejected on review surface and on what it buys:
  enforcement comes from the release sets, and the dev sets' job — showing the gap between the
  set tuning may read and the set it may not — is better served by authoring them against a
  product that has already changed under the new bars. Filed as roadmap 6.33.
- **Split the authoring per corpus, one pull request each.** Rejected: the baselines have to be
  re-taken either way, and re-blessing three sets twice means two chances for the corpus to
  move underneath them. One change, one bless, one review.
- **Add a `symbol` slice to our own release set for symmetry with the uv set.** Rejected —
  see the Decision. Symmetry between corpora is not a goal; an enforceable row is.
- **Re-judge the twin's carried cases by reading the projected documents.** Rejected on
  ADR-0039's standing argument, which this change does not reopen: the twin exists to measure
  what projection costs, and a judgement written against the projection cannot measure it.
- **Bless on the working tree.** Rejected: the tree held uncommitted work, some of it the
  maintainer's, and every document in it is part of this corpus. A baseline taken there records
  a corpus nobody else can reproduce, and G3 would report *"the corpus has changed"* on every
  run afterwards rather than enforcing.
- **Keep the old baselines and let G3 report the corpus change.** Rejected for the same reason
  the item exists: a gate that reports forever is a gate nobody reads.

## Consequences

- **G3 can enforce.** Every gated slice on every release set now holds at least the count
  `enforceable_at` derives for it, so the per-slice condition means what it says: no single case
  can trip a row on its own. `tools/measure_slice_power.py` reports **0 slices short**, against
  fourteen before, and the gate reads **4 of 5** enforced on our own set and **5 of 6** on each
  `uv` set — the remainder in each case being `unanswerable`, which is reported by design and
  gated by G4. That is the first time this has been true since the gate was written.
- **Gate G2's verdict is re-recorded, and the reason for the lexical default changed
  character.** ADR-0069 described a burden that could not be discharged: hybrid moves most cases
  a little and worsens some, so over five or six four-case slices *something* tripped on almost
  any set, and `G2 FAIL` said more about the set sizes than about hybrid. Measured on the
  authored sets it is a weighing instead. On both of our own sets hybrid now passes **with no
  per-slice regression at all** (release: 0.4838 → 0.5815, **+20.2 %**). On `uv/release` it gains
  **+7.2 %** and loses one slice — a regression measured over 68 cases and named case by case,
  which is what the condition was written to catch. On `uv-ingested/release` it gains
  **+3.5 %**, short of the +5 % bar, with nothing tripped. The
  decision is still `lexical`, and for the first time it rests on numbers that could have gone
  the other way.
- **The numbers move, and the movement is not a result.** A set five to sixteen times larger has
  a different mean; comparing the new baseline's figures with the old ones compares two
  different measurements. The authoring changed nothing about the retriever; the one retrieval
  change that travels with it is `symbol_lookup` shipping off again, and that flip is a
  *consequence* of these sets rather than a tuning applied to them (ADR-0137). Both are true of
  the same baselines, so every figure here is read from the run recorded after the flip.
- **The judged sets are now the largest artifact in the repository after the corpora**, and the
  generators are where they live: `tools/build_eval_cases.py` and
  `tools/build_uv_docs_cases.py` grow by roughly 7 000 lines of judgements. That is the shape
  [BUG-0026] requires — a set edited by hand is invisible to its generator and deleted by the
  next run — and the cost is a large diff that is data rather than code.
- **A reviewer cannot check 646 judgements by reading them all**, and pretending otherwise
  would be the dishonest part of this change. What a reviewer can check is the method (stated
  above), the conventions (already on the record), the mechanical validation (every anchor
  resolved against a clean build), and a sample. The notes are written for that sample: each
  says why *this* passage answers *this* query, and a wrong one is visible without leaving the
  file.
- **Spec 04 §7.6's 1.0 target is closer and still ahead.** It asks for ≥ 1 000 judged cases at
  1.0; this brings the committed sets to **1 158 cases across six sets**, of which 1 094 are
  release-set judgements and 64 are the dev sets, unchanged. The target counts cases, and what
  remains is the dev sets (6.33) and whatever corpora 1.0 adds.
- **The carry drops more than it used to**, because there are more list-shaped anchors to drop:
  27 anchors, though no case loses all of them. Every drop is printed by the generator and every
  surviving mapping is recorded in `eval/carry.json`, which is where a reviewer looks for the
  pattern rather than the instance.
- **The third corpus's binary sources changed**, for 25 of its 81 documents, and the repository
  grew with them. That is the price of judging a document the rotation had never given a format:
  either the corpus re-renders, or the judgements stay inside the documents that already had
  slots. `tools/build_ingested_corpus.py --check` still re-ingests the committed binaries and
  compares, so the evidence is checked the way it always was.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §7.1 (the sets and the freeze), §7.3
  (the gates and their per-slice condition), §7.6 (the corpus plan and the 1.0 target).
- Assets: `eval/release.jsonl`, `eval/corpora/uv-docs/eval/release.jsonl`,
  `eval/corpora/uv-docs-ingested/eval/{release.jsonl,carry.json}`, `eval/baselines/release.json`
  and the two under `eval/corpora/*/eval/baselines/`; generators `tools/build_eval_cases.py`,
  `tools/build_uv_docs_cases.py`, `tools/build_ingested_cases.py`.
- Re-runnable: `python tools/build_eval_cases.py`, `python tools/build_uv_docs_cases.py --check`,
  `python tools/build_ingested_cases.py --check`, `python tools/measure_slice_power.py`,
  `mycelium eval . --gate --against grep`.
