# 2026-09-17 — the anchor that lies about itself (roadmap 6.7)

- **Session scope:** roadmap 6.7 — score citation precision, not only rank.
- **PR:** #157 (`feat/score-citation-precision`). Follows #156.
- **Milestone 6:** 6.7 delivered. Open: 6.8–6.10, 6.12–6.15, 6.17–6.23.
- **Decision it records:** [ADR-0122](../../../adr/0122-score-what-a-citation-names-and-read-it-from-the-chunk.md).

## The item was right about the gap and wrong about the fix

ADR-0040 filed this in its own words: *"every metric here ranks chunks, and none of them asks
whether the anchor a reader is handed names the right thing."* True, and the gap decided
roadmap 4.9 — a pipeline that turns `#/0` into `#platform-support/0` was refused partly
because its benefit was unscoreable.

The item also predicted the metric would need *"a judged notion of the correct anchor
granularity per case"*. It does not, and ADR-0029 — the seed the item named — is what says so.
A judgement that names a section has already declared that any chunk under it is an acceptable
answer, so citing one chunk of a judged section is not a citation failure by the judge's own
standard. There is nothing left for a new judged input to decide. The metric then
discriminates 0.998 against 0.000 across lanes with no judgement at all, which is the evidence
rather than the argument.

That is the third item this milestone whose premise did not survive being measured, and the
pattern is worth naming: a roadmap item is a hypothesis written by a session with less
information than the one that executes it.

## The mistake, and why it is in the ADR's title

The first implementation read locatedness out of the anchor string — does
`<doc>#<path>/<ordinal>` carry a non-empty path. Obvious, and wrong. An anchor omits the
document's single level-1 heading, because the path already identifies the document and
repeating its title in every anchor is noise (ADR-0007). So a passage under a real title and
before the first `##` is spelled `docs/patterns/README.md#/0` — indistinguishable by string
from chunk 0 of a document with no headings whatsoever.

It was caught by running the new tool against the corpus and not believing the number: 0.867
where an earlier ad-hoc script had said 0.999. 193 of this repository's 1 461 chunks, called
unstructured when one is. Worse than the wrong figure was what it would have done to the
decision this metric exists to support: it would have credited the PDF lane with the same
defect the authored lane "has", flattening the one distinction the whole item is for.
Locatedness is read from `Chunk.heading_path` now, handed to the metric as a set built from
the snapshot, exactly as gate G1's resolvable set is.

## Two findings, and the second is the bigger one

**Predicted:** the PDF lane of the ingested corpus reads **0.000** across all 37 of its
chunks, with 501-token passages against 90–197 elsewhere. ADR-0040's unscoreable benefit,
scored.

**Unpredicted:** against grep, the product's citations are **2 to 29 times smaller**. On our
own release set, 254 tokens against 7 289. The cause is grep's ranking — a passage scores by
how many query terms it contains, so the longest chunks win, and the longest chunks are
exactly the ones whose citation costs a reader most. For *"how do I report a security
vulnerability"* the product cites a 218-token `SECURITY.md#reporting-a-vulnerability/0`
first; grep cites a 10 798-token roadmap milestone first and reaches `SECURITY.md` fourth.

D-010 has said since Phase 0 that the real incumbent is the agent's own grep loop and that
the correct response to losing is to fix the product. This is the widest margin over that
incumbent the project has ever measured, and no number could express it until today.

## What is not decided

The gate. On the ingested corpus the aggregate is dominated by one lane at 0.000 for a reason
already decided, so a threshold picked now would encode ADR-0040's refusal rather than measure
anything. The premise is pinned by a test against the twin rather than left in prose, so
shipping PDF structure fails a test that names the gating decision.

And ADR-0040's re-take itself. `measure_pdf_structure.py` carries the two new columns, so it
is one command — but the command needs ~2.4 GB of packages and weights that this environment
does not carry and that ADR-0040 established CI must not. The size of the prize is now
quantified; spending 2.4 GB to collect it stays the maintainer's call.

## Lesson

A metric that reads an identifier's *spelling* is measuring the identifier's conventions, not
the thing it names. Two anchors can be the same string and mean opposite things, and the only
cure is to ask the record rather than the name — which is also why the number was checked
against a second method before it was believed.
