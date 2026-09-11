# 2026-09-11 — the stage that could not exist (roadmap 5.15)

- **Session scope:** roadmap 5.15 — chat distillation: the synthesis lane pointed at a
  transcript (doc 08 §7), and the D-023 pipeline-stage mechanism the item expected to need.
- **PR:** #114 (`feat/chat-distillation`). Follows #113, merged as `6629655`.
- **Milestone 5:** 5.15 done. Nothing new filed.
- **ADR:** [ADR-0087](../../../adr/0087-distil-a-conversation-at-authoring-time-and-cite-the-message.md).

## The half of the item that was wrong, and how long it took to notice

5.15 was filed at 5.5 with a prediction attached: distillation *"is the one thing in the
module that would use D-023's **pipeline-stage** mechanism … so this item carries both
halves: the stage contract … and its first consumer, which is the only order that avoids
designing a contract against no user."* It is a good argument. It is also unbuildable, and
the reason is one sentence in spec 02 §2 that has been there since the architecture was
written: *"The build (`mycelium build`) remains a pure function and never writes tiers 1–2."*

A distillation writes `knowledge/candidate/…`. That is tier 2. A pipeline stage runs inside
the build. There is no arrangement of those three facts that works.

What makes it worth a journal entry is that the prediction was not careless. It was written
by the session that had just built the module mechanism, knew D-023's four mechanisms cold,
and correctly observed that three of them had no consumer. It reached for the one that
sounded like a fit — *distillation is a transformation, transformations are stages* — from
one directory up, without opening the authority model. Half an hour of reading closed it,
and nothing but reading would have.

The non-determinism is the near miss, not the disqualifier. A stage may declare itself
non-deterministic; the embed stage does. What a stage may not do is write into somebody's
Git working tree every time they compile. Put those together and the honest description of
"synthesis as a pipeline stage" is a robot with commit access.

So the mechanism still has no consumer, and this is the third time in Milestone 5 the work
has ended there: 5.1 declined to freeze `Extractor`, 5.5 declined three mechanisms, 5.14
declined an SDK façade. That is not a run of bad luck. Spec 05 §4.1.1 is a *menu* written
before there were any modules, and the useful reading of "this mechanism is unbuilt" is
`no one has needed it`, not `we are behind`.

## The half of the item that was right

The open question was the good one: *"a message anchor is stable and a conversation is long,
so grounding may want the message rather than the document."*

Half the answer was already in the tree. 5.5 gave every message its own heading — for anchor
stability, not for citations — and that decision made `[[conversation#12 · assistant]]`
resolve through the ordinary contract with no core change at all. The precise citation
existed and nobody had noticed.

What was missing was the refusal of the imprecise one, and measuring it turned up the part I
would have got wrong by reasoning. The coarse citation has **two spellings**. `[[conversation]]`
is obvious. The other is the projection's own title heading: `section_text` on it returns 724
characters and the whole document returns 724 characters, the same bytes, because every
message heading is its child. A rule that closed only the first would have left the second
open wearing a section's name, and the closed vocabulary would have gone on offering it.

The fix is the shape the citation contract already has — pair the vocabulary with the check.
`EvidenceDocument.cite_sections_only` stops `citable_names` *offering* the whole-document
form and stops `review` *accepting* it; the module narrows its citable headings to the
message headings. Offering without enforcing is a suggestion, enforcing without offering is
a trap, and rule 1 has worked that way since ADR-0035.

## What building it found in the prompt

The evidence block of the prompt annotated every heading with `(cite as [[doc#Heading]])`
and the document with `cite as [[doc]]` — reading the citable set off the KIR, while `review`
read it off `evidence.headings`. The two had always agreed, because `evidence_of` fills the
second from the first. The first evidence document to narrow its headings made them
disagree, and the symptom was the prompt's Evidence block offering exactly what its CITABLE
block forbade. The model would have been pulled two ways and blamed for the result.

It cost nothing to fix and no shipped behaviour moved, because no evidence document had ever
narrowed its headings. Two sources of truth agreeing by construction is worth having anyway:
this one agreed by coincidence for four months.

The other small thing: `check` classified violations by the `[[` prefix, so my new one was
reported as *"cites 1 thing(s) that do not exist"*. The document does exist. That is a
true-sounding sentence pointing at the wrong problem — and the repair round-trip would have
been sent after it too, quoting a violation the model could not act on. `CitationReport` now
carries the kind beside the prose, because three failures need three sentences.

## What was left asymmetric on purpose

`mycelium verify` rebuilds its evidence set with `evidence_of`, which knows nothing about
section-only evidence. So a hand-edited candidate could add `[[conversation]]` and clear gate
G7 where the lane would have refused it. I looked for a way to close this and each one made
the core read something a module wrote.

Then I found the precedent, in the configuration this lane already has:
`min_citation_coverage` defaults to **1.0** against G7's **0.95**, with the reason written
out — *"G7 decides whether an existing candidate may be promoted, this decides whether one is
written at all, and it is easier to relax a floor than to un-publish an unsupported claim."*
Write time being stricter than verify time is the established shape here, not a gap. And it
costs nothing for a document this lane wrote: its citations name messages, and verify
re-checks exactly those.

## Lesson

A roadmap item written three items ago is a hypothesis with a confident voice, and the
confidence is the part that ages worst. Both halves of 5.15 were written by the same session
on the same day: the question it asked was excellent and the answer it assumed was
impossible. Read the spec the item cites before building what the item predicts — the item
is a note from a colleague who had less information than you do.
