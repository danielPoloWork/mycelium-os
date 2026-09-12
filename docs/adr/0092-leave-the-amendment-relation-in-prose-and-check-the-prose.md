# ADR-0092: Leave the amendment relation in prose, and check the prose

- **Status:** Accepted
- **Date:** 2026-09-12
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §6
- **Related:** [ADR-0082](0082-open-the-frontmatter-contract-by-one-key-and-make-the-drift-unlandable.md)
  (the `supersedes` decision that filed this, and the anti-drift shape reused here),
  [ADR-0074](0074-give-every-edge-type-a-derivation-or-a-reason-it-has-none.md) (six
  derivations, and the rule that a type gets a derivation or a written reason),
  [ADR-0018](0018-build-the-graph-from-authored-links.md) (the graph's node set, and *a
  neighbour nothing can fetch*), [ADR-0031](0031-refuse-three-rerankings.md) and
  [ADR-0041](0041-bound-the-section-unit-and-refuse-six-more.md) (the shape of a measured
  refusal); spec 03 §§3.1, 6; D-014, F-9; roadmap 5.2, 5.10, 5.21

## Context

D-014 fixes a controlled edge vocabulary of eight types, *"extensible only via RFC — this is
the anti-ontology-sprawl valve (F-9)"*. Roadmap 5.10 closed the last derivation and, while
measuring supersessions, found five ADRs carrying a *weaker* relation in the same header slot:
*"Accepted — the `target_tokens` ruling is amended by ADR-0023"*, *"the latency table's premise
is corrected by ADR-0030"*. None of the eight types fits. `supersedes` is wrong because the
decision stands; `references` is wrong because no grammar found it; `links_to` is what the
prose link already produces, which is the untyped state 5.10 removed for supersession. So the
question is the one the valve was built for, and 5.21 was filed to answer it on the cases
rather than in the abstract.

Counted properly, **there are nine relations, not five**, and the four the earlier count missed
are the ones that decide the question.

| amended | by | stated in | what moved |
|---|---|---|---|
| ADR-0007 | ADR-0023 | status line | the `target_min_tokens` clause — knob renamed, now steers size |
| ADR-0014 | ADR-0023 | status line | a **ruling** reversed: the knob is honoured after all |
| ADR-0026 | ADR-0030 | status line | the 10⁵ **figures** — the filed gap was a benchmark artifact |
| ADR-0028 | ADR-0030 | status line | the latency **table's premise** — 31 ms, not 78 |
| ADR-0048 | ADR-0054 | status line | the MATCH expression and `STEM_WEIGHT`, halved |
| ADR-0034 | ADR-0090 | body, at the Decision | the projector's rule for a source's links |
| ADR-0053 | ADR-0056 | body, at the Decision | one paragraph of the decision |
| ADR-0053 | ADR-0056 | body, at a *second* paragraph | a different paragraph of the same decision |
| ADR-0062 | ADR-0065 | body, in the Context | a clause reasoned in passing, withdrawn |

Three facts fall out of that table, and each is fatal to a ninth type on its own.

**It is not one relation.** Three verbs are in use — *amended*, *corrected*, *narrowed* — over
at least two kinds. ADR-0026 and ADR-0028 had their **evidence** corrected and their decisions
untouched; ADR-0028's status line says the refusal is *"unchanged and stronger for it"*.
ADR-0014 had a **ruling reversed**. A type that gave both the same name would answer the
question *"is this record still good?"* identically for a decision that was strengthened and
one that was overturned.

**What it relates has no node.** The graph's nodes are documents, sections (`doc:<path>#<slug>`,
spec 03 §3.1) and symbols. What an amendment relates is a clause, a ruling, a figure, a table's
premise, a paragraph. ADR-0053 is narrowed **twice by the same ADR at two different paragraphs
of one section** — two relations a document-to-document edge collapses into one, and a
section-level edge cannot separate either. The corpus already solves this by putting the note
*at the paragraph it changes*, which is a granularity the vocabulary has no node for.

**The payload is the part that moved, and an edge cannot carry it.** `ADR-0023 amends ADR-0014`
asserts that something changed while hiding what, so a reader must open the prose to learn
anything actionable — and having opened it, the edge told them nothing. That is ADR-0018's own
bar, refusing edges to external URLs because they are *"neighbours nothing can fetch"*, applied
to a neighbour nothing can *use*.

## Decision

**`amends` is not a ninth edge type. The vocabulary stays at eight, and the valve holds for the
first time.** The relation is partial by definition, is at least two relations wearing one
word, and attaches to a granularity below the graph's smallest node. An RFC could add the type;
none should, and this ADR is the record so the question is not re-opened without new evidence.

**The relation stays in prose, and the prose gets one shape.** An amendment is declared on a
single line, in one of two places — whichever is closer to what moved:

- the **`Status:` field**, when the whole record is qualified: *"Accepted — the `target_tokens`
  ruling is amended by [ADR-0023](…)"*;
- a **blockquote note at the paragraph it changes**, opening `> **Amended | Narrowed |
  Corrected at roadmap N ([ADR-XXXX](…)).**`, when one part moved and the rest stands.

The verb is chosen, not fixed: *corrected* for evidence, *amended* for a decision, *narrowed*
for a rule that still holds in a smaller scope. Keeping three verbs is not untidiness — it is
the distinction one edge type would have flattened, and prose is where it can be stated.

**A relation left to prose is only as good as its prose, so the checkable half is checked.**
`consistency_lint.py` gains `check_amendments`, in the shape roadmap 5.10 used for supersession
— a rule you cannot break quietly beats one you have to remember. Two rules, both holding across
all nine relations today:

1. **The amender is named as a link.** A bare `ADR-0023` is not followable, and *"a reader
   resolves it from the prose"* is the whole premise of this refusal.
2. **The amender mentions what it amends.** An amendment the other side never heard of is a
   dangling claim — the disagreement `check_supersedes` catches from the machine side, caught
   here from the only side that exists when neither end is machine-read.

Only the **declaring line** is read, so an ADR discussed inside a note's prose is not mistaken
for a second amender. Both rules are verified by breaking them, in `tests/test_consistency_lint.py`.

## Alternatives Considered

- **Add `amends` as a ninth type, through an RFC.** The option the item was filed to consider.
  Rejected on the three facts above, and on what the edge would have been worth: nine edges in
  one corpus and zero in the other two, each asserting that something unnamed changed. The first
  extension of a closed vocabulary should buy more than that.
- **Add two types, `amends` and `corrects`,** to keep the kinds apart. Rejected more firmly than
  one: it doubles the vocabulary extension to answer a question the prose already answers, and
  it still cannot separate ADR-0053's two narrowings or say which clause moved.
- **Reuse `supersedes` with a weight below 1.0.** Rejected: the weight field is a *ranking*
  knob whose values 5.3's ablation decides (ADR-0074), not a truth qualifier — and the claim
  would be false at any weight, because the amended record is still in force.
- **Reuse `references`.** Rejected on spec 03 §6's status discipline: `references` is
  `extracted`, meaning a grammar found it, and nothing extracts this. Calling an authored
  sentence extracted is the silent promotion that discipline exists to prevent.
- **Leave the relation to the `links_to` edge the prose link already produces.** This is in fact
  what ships, and it is worth being precise about: the edge exists, it is honest, and it says
  only *"this document links to that one"* — which is all a graph can truthfully say here. What
  is refused is *typing* it as something more.
- **Normalise the five status lines and four notes to one verb and one wording.** Rejected: the
  verbs carry the distinction between a corrected measurement and a reversed ruling, which is
  precisely what a single type would have lost. The lint fixes the *shape* and leaves the
  wording to the author.
- **Extend the frontmatter contract with an `amends:` key**, as ADR-0082 did for `supersedes`.
  Rejected: that key existed to give a *typed edge* an authored source, and there is no typed
  edge here. A key that feeds nothing is a field the corpus must maintain for a machine that
  does not read it — and it could not express a relation that points at a paragraph anyway.

## Consequences

- **The vocabulary is unchanged at eight types**, all eight derived (ADR-0082). No spec change:
  nothing diverged, and spec 03 §6's *"extensible only via RFC"* is untouched — this is the
  first time it has been invoked and held.
- **Nine relations gain a guard.** `check_amendments` runs in every mode of `tools/verify.py`
  and in CI, and fails on an unlinked amender, one that does not exist, or one that never
  acknowledges the relation. It found nothing wrong in the corpus today, which is the point: it
  is a ratchet, not a repair.
- **A convention is now written down** in `docs/adr/README.md` beside the status transitions and
  in `docs/workflow/documentation.md`, so the next amendment has a shape to follow rather than
  four examples to infer one from.
- **No code, no graph, no ranking.** The edge set, the store, the manifest and every measurement
  are byte-identical; the only executable change is a lint check.
- **What would re-open this.** A corpus where amendment is dense and *whole-record* — where an
  agent would usefully ask "what amends this?" and act on the answer without reading the prose —
  and a node for the thing amended. Neither exists today. The claim being refused is not "the
  relation is unimportant"; it is "the graph cannot state it truthfully".

## References

- Spec: `.draft-specs/03-data-model.md` §6 (the vocabulary, the status discipline, the valve),
  §3.1 (section nodes); `.draft-specs/00-verdict-and-decisions.md` F-9, D-014.
- The nine relations: ADR-0007, ADR-0014, ADR-0026, ADR-0028, ADR-0048 (status lines); ADR-0034,
  ADR-0053 ×2, ADR-0062 (notes at the paragraph they change).
- Tests: `tests/test_consistency_lint.py` — the committed corpus passes, and each rule is
  verified by breaking it.
