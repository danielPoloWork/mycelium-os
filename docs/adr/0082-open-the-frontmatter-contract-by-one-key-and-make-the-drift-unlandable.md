# ADR-0082: Open the frontmatter contract by one key, and make the drift unlandable

- **Status:** Accepted
- **Date:** 2026-09-11
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §§3, 6
- **Related:** [ADR-0074](0074-give-every-edge-type-a-derivation-or-a-reason-it-has-none.md)
  (six of eight types, and the deferral this closes),
  [ADR-0018](0018-build-the-graph-from-authored-links.md) (wikilink resolution, and why an
  unresolvable reference warns), [ADR-0079](0079-resolve-an-ingested-documents-links-through-its-source-tree-and-never-call-them-authored.md)
  (an ingested document asserts nothing), [ADR-0034](0034-project-the-evidence-and-count-what-it-lost.md)
  (the last key added to the contract, and why one key rather than four),
  [ADR-0036](0036-measure-what-can-be-measured-and-let-a-human-outrank-the-gate.md) (the
  ownership table's one recorded deviation), [ADR-0012](0012-adopt-the-g6-determinism-gate.md)
  (the golden this completes), [ADR-0075](0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md)
  (the ablation that decides edge weights, still unmoved); spec 03 §§3, 3.1, 6, spec 05 §3.3;
  D-014, D-017, D-021, D-022; roadmap 5.2, 5.10, 5.20

## Context

D-014 fixes a controlled vocabulary of eight edge types, extensible only by RFC. Roadmap 5.2
derived six and gave written reasons for the two it did not: `mentions` belongs to the entity
stage (5.4, since delivered), and `supersedes` *"needs an authored declaration — an ADR that
supersedes another says so in its own header — and the only machine-read metadata an authored
document has is frontmatter, whose field set spec 03 §3 closes deliberately"*. That deferral
named this item and named the decision: open the contract, or reserve the type.

The relation is real here. Measured across the three corpora on 2026-09-11:

| | supersessions declared | in prose |
|---|---:|---|
| this repository | 0 | **1** — ADR-0002 *Superseded by ADR-0003* |
| uv-docs | 0 | 0 |
| uv-docs-ingested | 0 | 0 |

One relation, in one corpus, stated in prose no machine reads. Two adjacent facts came out of
the same measurement. Five more ADRs carry a *weaker* relation in the same header slot —
*"Accepted — amended by ADR-0023"*, *"corrected by ADR-0030"* — for which D-014 has no type at
all. And this repository's own corpus carries **no frontmatter whatsoever**: every one of its
138 documents compiles with a path-derived identity, so whatever key this item adds is the
first contract field the corpus uses.

Three things make the decision narrower than it first looks.

**The spec already counts frontmatter as a source of edges.** Spec 03 §6 defines the status
enum as `authored` *(explicit link/**frontmatter**)* versus `extracted`. The contract was
always meant to carry assertions into the graph; §3 simply never listed a key for this one.
`derived_from` already ships with `provenance.kind = "frontmatter"` (ADR-0074).

**The anti-drift rule that closed the field set does not reach this key.** What §3 refuses is
a `status:` field, and the reason is specific: `verification_status` is carried by the folder,
so a field would restate what a *structural* mechanism owns and *"a file move can never
disagree with a stale field"*. Nothing owns supersession structurally. No folder says a
document has been replaced, and no link says it either — a Markdown link carries no type, so
`[[old]]` in a replacement's prose is indistinguishable from any other reference.

**The contract already tolerates one prose overlap, and resolves it by precedence.** `title:`
can disagree with a document's H1; §3 does not refuse the key, it ranks them. So an overlap
with prose is not itself disqualifying — what matters is whether the disagreement can be
caught.

## Decision

**The contract gains one human-owned key, `supersedes:`, and nothing else.**

```yaml
supersedes: [0002-adopt-cross-language-source-layout.md]
```

Optional, human-owned, a list of link targets. The field set goes from twelve keys to
thirteen, the tool-writer count stays at three, and no tool writes this one — a supersession
is a decision, and `mycelium build`'s only write into an authored document is still
`mycelium_id` (ADR-0009).

**It resolves exactly as a wikilink does, through the same index.** An exact path wins, then a
path relative to the declaring document, then a unique basename, then a unique alias
(spec 03 §3.1). Reusing `CorpusIndex` is the point: a corpus where `[[api]]` resolves and
`supersedes: [api]` does not would be a second resolution rule for one syntax. The relative
step is new for this key and is the reason it reads naturally in place — an author writing
`supersedes: [0002-…]` inside `docs/adr/` names the file they would have linked, and a path
written inside a document belongs to that document's directory. A Markdown link already had
that step; the key joins it rather than inventing a rule.

**Three declarations produce a warning and no edge.** An unresolvable target, because unlike a
symbol use it *asserts a document exists* — the same claim a wikilink makes, so it earns the
warning ADR-0018 gave that claim. An ambiguous basename, naming its candidates rather than
guessing. And a self-reference, because a document cannot replace itself and the edge would
make every traversal report the node as its own neighbour. A malformed *value* warns and is
dropped rather than raising, which is this contract's lopsided-failure rule: a human's typo in
a human-owned key must not stop a build.

**The status follows the document, not the key.** An *ingested* document carrying `supersedes:`
in its projected frontmatter is asserting nothing anybody here wrote — its text is untrusted by
D-017 — so its edge is `extracted`. That is ADR-0079's rule applied to a new field rather than
a new exception to it, and it is what stops a source's own metadata passing for a maintainer's
decision.

**The prose stays canonical for a reader; the key is what a machine reads; and a lint refuses a
disagreement.** This is the half that answers the anti-drift objection instead of arguing with
it. The ADR template states supersession in the *superseded* record's header — the **passive**
side — while the vocabulary names the relation from the **active** side, so the key lives on
the newer document. `tools/consistency_lint.py` now walks from each superseded ADR to the one
that replaced it and fails when the declaration is missing, when it points at a file that does
not exist, or when a declaration has no prose behind it. Roadmap 4.27 made duplicate item
numbers impossible to land rather than merely discouraged; this is the same move for the same
reason — **a rule you cannot break quietly beats one you have to remember.**

**Applied to the one real case**, so the feature ships with data rather than with a fixture
only: ADR-0003 declares `supersedes: [0002-adopt-cross-language-source-layout.md]`, which is
the first frontmatter block in this repository's corpus.

**The amendment relation stays prose, and that is a decision rather than an omission.**
*"Amended by"* and *"corrected by"* are not supersession — the amended record is still in
force — and D-014 has no type for them. Adding one is an RFC, which is exactly the valve F-9
installed. Filed as roadmap 5.20 with the five cases measured, so the next reader meets a
question rather than a silence.

## Alternatives Considered

- **Reserve the type and document it as having no derivation** — the other branch the roadmap
  named. Rejected, and it was close. D-014 promises eight types and `mycelium_neighbors`
  serves a `types` filter over all of them, so a reserved member is a filter that silently
  returns nothing: the trap roadmap 4.22 found in a baseline that read like a gate. The cost
  of the alternative is one optional key with a lint behind it; the cost of reserving is a
  vocabulary that documents a promise it does not keep.
- **Name the key `superseded_by:` and put it on the older document**, where the ADR prose
  already is. Rejected: the vocabulary's type is `supersedes`, the edge runs from the
  replacement, and a key whose name inverts its edge would need explaining at every use. The
  asymmetry is real and is handled where it belongs — in the lint that bridges the two sides.
- **Derive it from the prose instead**, parsing *"Superseded by ADR-XXXX"* out of the body.
  Rejected: that string is a convention of *this repository's* ADR template, not of the
  Mycelium Markdown Profile, and teaching the compiler to read it would put one project's
  documentation habit inside a general engine. The lint reads it, which is the right place —
  `consistency_lint.py` is this repository's congruence check, not a product feature.
- **Let a tool write the key from the prose**, keeping one human-edited source. Rejected: it
  would make a fourth tool writer and a second build-time write into an authored document,
  which ADR-0009 restricts to identity alone.
- **Allow a heading-level target** (`supersedes: [old.md#section]`). Rejected: supersession is
  a statement about a whole document. A replaced section is an amendment, which is 5.20's
  question, and admitting the syntax now would pre-judge it.
- **Give `supersedes` a weight above 1.0**, since spec 04 §5 once suggested weighting it high.
  Rejected for ADR-0074's reason, unchanged: the ablation that could measure a weight is
  5.3's, it ran, and it found nothing to weight. A constant fitted here would be the
  fifteen-times-refused move in a new costume.
- **Open the contract wider while it is open** — `related:`, `depends_on:`, `amends:`.
  Rejected outright. The field set's value is that it is closed; one key with a measured
  reason is a decision, four keys is a metadata dump, which is what the rule adopted from
  `gpt-specs` §6.3 exists to prevent.

## Consequences

- **D-014's vocabulary is complete.** All eight types now have a derivation, and the
  determinism golden carries all eight — `links_to`, `part_of`, `defines`, `references`,
  `cites`, `derived_from`, `mentions`, `supersedes` — with a test that fails if the gate ever
  loses one. Before this item two types had reasons instead of edges; now none does.
- **An agent can ask the question that matters about a decision record.** *What replaced this*
  and *what did this replace* are one hop each in opposite directions on the same node, through
  `mycelium_neighbors` with `types: ["supersedes"]`. The failure this prevents is specific and
  costly: quoting a superseded decision as current.
- **Store schema unchanged.** `doc_state.graph_json` gains `supersedes`, which older rows
  decode as empty, and `EXTRACT_STAGE_VERSION` goes to 5 so the first build after upgrading
  re-reads every document's frontmatter through the parse and chunk caches. Without the bump a
  document nothing else touched would keep declaring nothing.
- **The golden gains a document and an edge.** The fixture now holds a superseded delivery note
  that `retries.md` replaces, declared in frontmatter and with **no link between them** — which
  is the demonstration the type exists for: the relation is in the graph and no link put it
  there. `counts.documents` 7 → 8, `chunks` 25 → 27, `edges` 23 → 24.
- **`.draft-specs/03-data-model.md` §3 is amended**, which is the honest form for a spec
  question: the YAML block lists the key, the ownership paragraph names its owner, and a new
  paragraph states why the `status:` refusal does not reach it and what a corpus keeping both
  statements owes its own lint.
- **One lint check that bites.** Removing the declaration from ADR-0003 while leaving ADR-0002's
  header in place fails `consistency_lint.py` by name, which was verified rather than assumed.
- **Known limits, on the record.** Supersession is document-level only. The amendment relation
  has no type (5.20). A superseded document is not down-ranked and nothing here says it should
  be — that is a retrieval question, and the honest place for it is an ablation, not this ADR.
  And the type's yield is one edge in three corpora: it earns its keep on a corpus of decision
  records, which is what this repository is and what neither vendored corpus is — the same
  asymmetry ADR-0073 reported for symbols and ADR-0074 for `references`.

## References

- Spec: `.draft-specs/03-data-model.md` §3 (the contract and its ownership rules, amended
  here), §3.1 (wikilink resolution), §6 (the vocabulary and the status discipline);
  `.draft-specs/05-interfaces-and-plugins.md` §3.3 (typed neighbours).
- Decision log: D-014 (controlled vocabulary, RFC-only extension), D-021 (the folder owns
  verification status), D-022 (a vault's own properties are preserved, never interpreted),
  D-017 (all source content untrusted).
- Re-runnable: `mycelium build --no-pin .`, then
  `mycelium neighbors docs/adr/0002-adopt-cross-language-source-layout.md --json`; and
  `python tools/consistency_lint.py` for the congruence half.
- Tests: `tests/test_typed_edges.py` (the derivation and its refusals),
  `tests/test_markdown_frontmatter.py` (the contract key), and the golden's `edges` section.
