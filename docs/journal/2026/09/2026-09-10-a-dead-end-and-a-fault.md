# 2026-09-10 — a dead end, and a fault (roadmap 5.2)

- **Session scope:** roadmap 5.2 — the typed edge vocabulary and `mycelium_neighbors` over all
  of it (spec 03 §6, spec 05 §3.3, D-014). The second Milestone 5 item, straight after 5.1.
- **PR:** #101 (`feat/typed-cross-reference-edges`). Follows #100 (5.1), merged as `8eacc02`.
- **Milestone 5:** 5.1 and 5.2 done; 5.9 and 5.10 filed; 5.3 is next and now has a graph worth
  expanding over.
- **ADR:** [ADR-0074](../../../adr/0074-give-every-edge-type-a-derivation-or-a-reason-it-has-none.md).
  **Bug:** [BUG-0022](../../../bugs/2026/09/BUG-0022-tree-sitter-0-26-faults-on-a-projected-fence.md).

## The measurement that decided the item

Two of D-014's eight edge types were emitted; the item's title asks for the rest and for the
tool over all of them. Rather than pick from the list, I counted what the corpora could
actually support, and one number decided the shape of the work: **290 of the uv corpus's 657
authored links carry a `#fragment`, across 226 distinct section targets**. Spec 03 §3.1 makes
those resolve to a section node — `doc:<path>#<slug>`, finer than a document, coarser than a
chunk — and nothing ever connected that node to the document it names. A traversal arriving on
a section stopped there. A traversal arriving on a whole document carried on through its links.
For the 76 sections whose heading actually exists, the graph had a dead end where a reader sees
a cross-reference.

That is what `part_of` is for, and the measurement also settled how to emit it: the same corpus
has 554 headings. One containment edge per heading would have multiplied the graph to connect
nodes nobody references and would have crowded out every neighbour query that has a `limit`.
So it is emitted for the sections the graph already names — the node set does not change, only
its connectivity.

The second measurement went the other way. The tags queries 5.1 already runs also capture
`reference.call`, `reference.type` and friends, in eight of the ten grammars. On uv that is 84
captures over 49 distinct names, and the top of the list is `print` (15), `get` (5), `json`,
`getLogger`, `FastAPI`. Documentation *calls* libraries; it defines almost nothing. With the
resolution rule that a use becomes an edge only when the corpus defines what it names, uv
yields exactly **one** `references` edge and our own corpus **zero**. I shipped it anyway, and
the ADR says why in the alternative it was closest to losing: the mechanism is the parse the
definitions already pay for, the rule bounds it to symbols the corpus holds, and both corpora
document a *tool* rather than an API. The number is published in the README rather than implied
by its absence.

## What only `origin` could say

ADR-0018 refused `derived_from` with a precise blocker, which is the best kind of deferral to
inherit: at document granularity it would be *"the deduplicated projection of the `cites` edges
already here"*, and the distinction spec 03 §6 wants — a synthesized document versus an
authored one citing the same evidence — was *"not expressible until the graph's per-document
state carries `origin`"*. One field later, it is expressible, and the type says what it was
meant to: this document was written from that one.

Two things fell out of testing it. The fixture corpus's synthesized document cited an
**authored** file, not the evidence layer — so D-020's own citation contract, the one the
synthesis lane refuses to write without, was unrepresented in gate G6. It cites
`knowledge/evidence/extract.md` now, and `cites` and `derived_from` are exercised for the first
time. And the golden recorded an edge *count* and a folded digest, so any change to the graph
appeared as an unexplained digest move — precisely the opposite of the reviewable artifact
ADR-0012 built the gate to produce. It lists all 18 edges now, with type, status and
provenance, and this PR's diff is the first to show them.

The status column is worth a sentence of its own. `defines` and `references` are `extracted`
because a grammar found them; everything else is `authored`. Before this item every edge in
every corpus was `authored`, so "extracted never becomes authored silently" was a rule with
nothing to govern. The fixture now publishes 7 authored edges and 11 extracted ones.

## The fault

Measuring across all three corpora — which 5.1 never did by hand — the build **died**:
`Windows fatal exception: access violation`, inside the symbol stage, on the ingested corpus.
Not an exception. No traceback to catch, no quarantine record, and a stale lock left behind.

The diagnosis took five experiments and each one eliminated a plausible story. The input's
shape: the faulting fence is 20 644 bytes of PDF-projected prose tagged `python`, and its parse
tree is **14 levels deep** — not a nesting bomb. Object lifetime: holding every captured node
past the cursor and reading its text, type and parents survives. Query matching alone:
survives. Stepping the same work with prints between phases: survives. Under
`PYTHONMALLOC=debug` and with the cycle collector off: still faults, and the reported line
*moves* between runs — `code.py:504`, `:544`, `:549`. A fault whose location follows allocation
timing, in memory the extension owns, is heap corruption inside the binding.

The decisive experiment was the version. `tree-sitter==0.25.2` reads the same bytes five times
in a row without faulting and produces **byte-identical definitions** for every one of the ten
grammars' samples. So the binding is pinned `>=0.25,<0.26`, the reason is written beside the
pin, and [BUG-0022] stays `confirmed` rather than `fixed` because that is what a pin is: a
mitigation with a live cause.

It also forced an honest amendment. The threat model's B14 claimed that "a failure inside the
parser is a warning on the document, never a quarantine". That is true of an exception and
false of a fault, and the byte ceiling does not reach a 20 KB fence. The controls that hold are
the pin, the binding version already sitting in every build key (ADR-0073), and a gate ladder
that builds the reproducing corpus from `retrieval` mode upward — which is why this was caught
before a merge rather than by a contributor.

Minimising the trigger got to 14 268 bytes and no further, so no fixture is committed. The
vendored corpus is a better guard than a truncated copy of part of it.

## What was left alone

`mentions` waits for the entity stage that owns it (5.4). `supersedes` has no authored source —
this repository's ADRs use the relation constantly, in prose no machine reads, and the only
machine-read metadata an authored document has is a frontmatter contract spec 03 §3 closes on
purpose. That is a spec question, filed as 5.10 rather than answered by a side effect. Every
weight stays 1.0: the field is served because the contract promises it, and a fitted constant
here would be the move this project has refused fourteen times, with 5.3's ablation the place
one can be measured. And 5.7 is untouched: an ingested corpus's *links* still mostly do not
resolve, which is a resolution question of its own.

## Lesson

A deferral with a stated blocker is a gift to the next person: ADR-0018 named the one field
`derived_from` needed, so 5.2 spent minutes on it rather than re-deriving the argument. The
counterpart is the control that was never tested — B14 promised that a parser failure is only a
warning, and the first real fault proved the promise was about exceptions, not about faults.
Write the blocker down, and re-read your own controls as claims.
