# 2026-09-02 — the lane that refuses to write (roadmap 4.4)

- **Session scope:** roadmap 4.4 — the synthesis lane via the `wiki` plugin: LLM-authored
  candidate documents with mandatory wikilink citations (D-020/D-026, spec 02 §5).
- **PR:** #54 (`feat/synthesis-lane-wiki-plugin`). Follows #53 (4.3), merged as `eab3a83`.
- **Milestone 4:** 4.1–4.4 done; 4.5–4.9 open.

## The item is not about prose

Everything about 4.4 reads like a prompt-engineering task and none of it is. D-020 does not
permit an LLM to write documentation because LLM prose is good; it permits it because the
prose can be **checked** — the decision's own reason says "100 % source truth can only be
*proven* against a deterministic extraction". So the deliverable is the check, and the
prompt is what makes the check satisfiable.

That reframing decided the whole shape. `mycelium.synthesis.citations` is pure, takes no
provider and no configuration, and is the only thing that decides whether a file is written.
The plugin owns three things and the model owns none of them:

- **A closed citable vocabulary.** The prompt does not say "cite your sources"; it hands over
  the exact `[[document#Heading]]` strings that exist and says nothing else may appear. Rule
  1 — no fabricated citation — is a *trap* if the citable set is implicit and a satisfiable
  instruction if it is not. There is a test that every string the prompt offers actually
  passes the contract, because a vocabulary containing one unusable entry produces a model
  that obeys and fails.
- **One repair round-trip.** A rejected draft comes back with its violations quoted. Once,
  not until it passes: an unbounded loop spends an operator's money converging on a document
  the evidence may not support, and the second failure is information.
- **The refusal.** Nothing is written. A lane that emitted ungrounded prose with a warning
  attached would have kept the cost and dropped the justification.

## The measurement decision, and why it is not an approximation

Gate G7 (4.5) will read "cites coverage ≥ 0.95 of claim-bearing statements". A *statement*
sounds like a sentence. It is not, here: a claim-bearing statement is a KIR `paragraph` or
`list_item` node of at least five words.

KIR states block boundaries exactly and says nothing at all about sentence boundaries. A
sentence-level measure would mean this module inventing a structure the compiler does not
have, with its own abbreviation edge cases — and a grounding *number* is worth nothing
unless two runs of it agree. So the block is the unit, the ADR says so plainly, and it says
that moving to sentences later changes what the number means and has to be re-judged rather
than patched.

The floor is `1.0`, not `0.95`. The two are not in competition: G7 decides whether an
existing candidate may be *promoted*; this decides whether one is written at all, and it is
easier to relax a floor than to un-publish an unsupported claim.

## Two orderings that were wrong first

**The rules fired in the wrong order.** A document whose only citation was invented failed
rule 2 ("cites nothing") before rule 1 ("that citation does not exist"). Both statements are
true; only one is the diagnosis, and the wrong one sends the repair round-trip after the
wrong problem. A test caught it, the fix is three lines, and the comment beside them says
why the order is not cosmetic.

**The doctor check never ran.** The insertion anchor I patched against had moved when 4.2
added the custody check, the replace silently did nothing, and it took running the command
by hand to see it. A `.replace()` with no assertion is a no-op waiting to be believed.

## What the compiler makes of a candidate

The load-bearing test is the one that closes the loop: synthesize, write to
`knowledge/candidate/`, run `mycelium build`, and assert what comes out.

- `verification_status = candidate`, from the folder and nothing else (D-021).
- `provenance.origin = synthesized`, `provenance.synthesizer` carrying provider, model,
  prompt digest and parameters — recovered from a **synthesis record in tier-1 custody**
  through one frontmatter key, which is ADR-0034's mechanism pointed at a new kind of record.
- `trust_class = authored`. Deliberately: spec 03 §3's v1 vocabulary has no `synthesized`
  member, a synthesized document's *layer* is tier 2 like any authored one, and what makes it
  untrustworthy is its **status**. Adding a vocabulary member would put one fact in two
  places where they can disagree.
- Its citations are **`cites` edges**, not `links_to` — a wikilink into `evidence/` is a
  citation, folder-derived, so no store migration and no new field. `derived_from` is
  deliberately *not* emitted: at document granularity it is the deduplicated projection of
  the `cites` edges already there, and the distinction spec 03 §6 actually wants needs
  `origin` in the graph state, which 4.5 needs anyway.

## What CI can and cannot assert

Everything the lane decides runs against a scripted provider in `tests/fakes.py`, which
satisfies the seam in a dozen lines. That is the check that the seam is a seam. One test
calls the real API, is marked `llm`, and skips without a credential — it proves the request
shape is *valid* (thinking mode, effort, model id), which no stub can. Naming that boundary
is better than mocking across it.

The `anthropic` SDK rather than a hand-rolled POST, against the ADR-0011 precedent: four
packages, and what they own — credential resolution order, retry policy, a typed error
hierarchy — is exactly what a hand-rolled client reimplements badly. ADR-0011's arithmetic
came out the other way because its dependency was seventeen packages with an HTTP server in
them.

## What this deliberately does not do

The contract checks that a citation **resolves**, not that the cited text **supports** the
claim. Sampled entailment is gate G7's other half (4.5), and until it lands a
grounded-*looking* document can still misread its evidence. That limit is in the ADR's
consequences rather than discovered later by someone trusting a coverage of 1.00.
