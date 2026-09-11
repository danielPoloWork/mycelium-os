# 2026-09-11 — one key, and a lint behind it (roadmap 5.10)

- **Session scope:** roadmap 5.10 — `supersedes` has no authored source, and the frontmatter
  contract is closed. A spec question with two named answers (spec 03 §§3, 6; D-014).
- **PR:** #108 (`feat/authored-supersedes`). Follows #107 (5.9), merged as `2a12626`.
- **Milestone 5:** 5.10 done; 5.20 filed. All eight edge types now have a derivation.
- **ADR:** [ADR-0082](../../../adr/0082-open-the-frontmatter-contract-by-one-key-and-make-the-drift-unlandable.md).

## The item asked which of two answers, and the spec had already half-answered it

5.2 deferred `supersedes` with a precise blocker: the relation needs an authored declaration,
and the only machine-read metadata an authored document has is frontmatter, whose field set
§3 closes deliberately. So the choice was to open the contract or to reserve the type — and
my instinct was that opening a deliberately closed contract for *one* relation in *one* corpus
would be hard to justify.

Reading the spec rather than reasoning about it changed that. Spec 03 §6 defines the edge
status enum as `authored` *(explicit link/**frontmatter**)*. The contract was always meant to
carry assertions into the graph; §3 simply never listed a key for this one, and `derived_from`
already ships with `provenance.kind = "frontmatter"`. That reframes the question from "should
frontmatter carry edges" — settled, yes — to "which key".

Two more checks finished it. The anti-drift rule that closed the field set refuses a `status:`
field, and its stated reason is that the *folder* owns verification status, so a field would
restate a structural fact and could go stale against a file move. Nothing owns supersession
structurally: no folder says a document was replaced, and no link says it either, because a
Markdown link carries no type — `[[old]]` in a replacement's prose is indistinguishable from
any other reference. And `title:` already shows the contract tolerating an overlap with prose
and resolving it by precedence instead of refusing the key.

## What the measurement said, including the part I did not expect

One supersession in the whole set: ADR-0002, *Superseded by ADR-0003*. Zero in both vendored
corpora. So the type earns its keep on a corpus of decision records, which is what this
repository is and what neither vendored corpus is — the same asymmetry symbols had at 5.1 and
`references` at 5.2.

The unexpected part was five *other* ADRs using the same header slot for a weaker relation:
*"Accepted — amended by ADR-0023"*, *"corrected by ADR-0030"*. That is not supersession, the
amended record still stands, and D-014 has no type for it. It would have been easy to stretch
`supersedes` over it. Filed as 5.20 instead, with the five cases, because a ninth type is an
RFC and that is precisely the valve F-9 installed.

Also worth recording: this repository's corpus carries **no frontmatter at all** — 138
documents, every one compiling with a path-derived identity. Whatever key this item added was
going to be the first contract field the corpus actually uses, which is a strange thing to
discover about a project whose own spec writes that contract.

## The asymmetry that makes the lint interesting

The ADR template states supersession on the *superseded* record — *"Status: Superseded by
ADR-0003"* — while the vocabulary names the relation from the active side, so the key belongs
on the *newer* document. The prose and the key therefore sit in different files, pointing in
opposite directions, which is a drift risk with more room to go wrong than a single-document
overlap.

So the drift is refused rather than discouraged. `consistency_lint.py` walks from each
superseded ADR to the one that replaced it and fails when the declaration is missing, when it
names a file that does not exist, or when a declaration has no prose behind it. That is roadmap
4.27's move — duplicate item numbers made unlandable rather than merely forbidden — and it is
the answer to the anti-drift objection instead of an argument with it.

I verified it bites by deleting the declaration from ADR-0003 and running the lint: it failed
by name, naming both files and the key. A lint asserted and never tested is a lint nobody
should trust.

## One rule improved on the way

`supersedes:` targets resolve through the same `CorpusIndex` as wikilinks, which was the plan.
What was not the plan is the step I had to add: a *relative* path. Writing
`supersedes: [0002-adopt-cross-language-source-layout.md]` inside `docs/adr/` resolved only by
unique basename — a heuristic — where the precise answer was available, because a path written
inside a document belongs to that document's directory. Markdown links already had that step;
the key now shares it, which both reads better in place and stops being ambiguous the day two
folders hold the same filename.

The fixture makes the point the type exists for: `retries.md` supersedes a superseded delivery
note, declared in frontmatter, with **no link between them**. The relation is in the graph and
nothing but the key put it there.

## Lesson

When an item is framed as "open the closed thing or refuse to", read what the closed thing
already says about itself before weighing preferences. The contract's own §6 had granted
frontmatter the power to assert edges, and the rule that closed §3's field set had a stated
reason that did not reach this key. The decision was narrower than the framing, and the
argument it needed was the lint — because the real objection to a second statement of a fact is
never "it is redundant", it is "it can go stale", and that is a testable claim.
