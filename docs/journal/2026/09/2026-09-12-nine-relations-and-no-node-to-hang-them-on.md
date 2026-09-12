# 2026-09-12 — nine relations and no node to hang them on (roadmap 5.21)

- **Session scope:** roadmap 5.21 — is *amends* a ninth edge type, earned through an RFC, or is
  a partial correction something a reader resolves from prose? Decided on the cases (spec 03 §6;
  D-014; F-9).
- **PR:** #119 (`docs/amendment-vocabulary`). Follows #118 (5.19), merged as `35b3de2`.
- **Milestone 5:** 5.21 done. 5.22 and 5.23 remain open.
- **ADR:** [ADR-0092](../../../adr/0092-leave-the-amendment-relation-in-prose-and-check-the-prose.md).

## The count was wrong, and the missing half decided it

5.10 measured five ADRs carrying an amendment in their `Status:` line. Scanning bodies as well
as headers turns up **nine** relations across eight ADRs — and the four extra ones are stated as
a blockquote note *at the paragraph they change*: ADR-0034, ADR-0062, and ADR-0053 **twice**.

That last one is the whole argument in a single case. ADR-0053 is narrowed twice by ADR-0056, at
two different paragraphs of one section. A document-to-document edge carries one relation between
that pair, so it would collapse two facts into one; a section-level edge — the finest node the
graph has (spec 03 §3.1) — cannot separate them either, because both paragraphs are in the same
section. The corpus already solves this by putting the note where the change applies, which is a
granularity the vocabulary has no node for.

## Three verbs, two kinds, one word would have flattened both

Reading the nine, *amended* is not one relation:

- **Evidence corrected.** ADR-0026's 10⁵ figures were a benchmark artifact; ADR-0028's latency
  table said 78 ms where the truth is ~31. Both decisions are untouched, and ADR-0028's own line
  says its refusal is *"unchanged and stronger for it"*.
- **Decision moved.** ADR-0014 had a **ruling reversed** — `target_tokens` went from *not
  honoured* to *honoured and steering chunk size*. ADR-0007, ADR-0048, ADR-0034, ADR-0053 and
  ADR-0062 each had a clause, a mechanism or a paragraph replaced or narrowed.

One type naming both would answer *"is this record still good?"* identically for a decision that
was strengthened by its correction and one that was overturned. That is the opposite of what a
type is for.

## What an edge could have said, and why it is not worth saying

`ADR-0023 amends ADR-0014` asserts that *something* changed while hiding *what* — and *what* is
the entire content of the relation. A reader who follows the edge opens the prose anyway, and
learns from the prose the thing the edge could not carry. That is ADR-0018's own bar, which
refused edges to external URLs as *"neighbours nothing can fetch"*, applied to a neighbour
nothing can use.

So: **no ninth type.** The vocabulary stays at eight, all eight derived since 5.10, and F-9's
valve has now been invoked and held for the first time. Worth saying plainly, because the
temptation ran the other way: 5.10 adopted `supersedes` on **one** instance in one corpus, and
nine looks like a stronger case than one. It is not, and the difference is not volume. A
supersession is total, is about the whole record, and has a node at each end. An amendment is
none of those.

## What ships instead

The refusal's premise is that a reader resolves the relation from prose, so the prose has to be
followable — which is a checkable claim, in the shape 5.10 used for supersession. The relation is
now declared on **one line**, in the `Status:` field or in a note at the paragraph, and
`consistency_lint.py` gains `check_amendments`: the amender is named as a **link**, that ADR
exists, and it mentions the record it amends. All nine pass today, which is the point — it is a
ratchet, not a repair. Each rule is verified by breaking it.

One implementation detail worth the line it takes: only the *declaring* line is read. ADR-0062's
narrowing note discusses other records in its prose, and a check that scanned the whole
blockquote would have demanded reciprocity from a document that was merely cited.

The three verbs stay. *Corrected* for evidence, *amended* for a decision, *narrowed* for a rule
that still holds in a smaller scope — the distinction a single edge type would have flattened is
exactly the one prose keeps for free.

## Lesson

A vocabulary extension is tempting in proportion to how often the relation appears, and that is
the wrong measure. What decides it is whether the graph has a node for each end and whether the
edge carries the payload — and here it has neither. Counting the instances properly was still
worth doing, because the four the earlier count missed are the ones that show the relation is
sub-document, and one pair carrying two of them is a case no edge could have represented at all.
