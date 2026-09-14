# 2026-09-14 — shape, not prose (roadmap 6.1)

- **Session scope:** roadmap 6.1 — freeze the five stable contracts and build the
  compatibility suite. The first item of Milestone 6.
- **PR:** #146 (`feat/freeze-five-contracts`). Follows #144, the v0.5.0 cut, merged as `a7676a5`.
- **Milestone 6:** opened. 6.1 delivered; 6.2–6.12 open.
- **Decision it records:** [ADR-0114](../../../adr/0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md).

## What was actually pinned before this item

Nothing, in the sense the spec meant. Spec 05 §5 asked for compatibility tests on the five
contracts *from Phase 1*, and five milestones later the honest inventory was: G6 pins a whole
build and is re-blessed at every intended compiler change, the MCP tests pin the four tool
*names*, the schema tests pin the version *tags*, and the protocol tests prove two of four
Protocols are satisfiable. Every one of those is a test of the current behaviour that a
contributor changing the behaviour would update in the same commit. A field could join the
manifest, a signature could change, a slug rule could move every anchor in every corpus, and
the only thing that fired would be a gate whose re-bless is routine.

The tool output was the sharpest case. `tools/list` has always carried an `inputSchema` per
tool; the shape of what came *back* — the thing an agent actually depends on — existed only as
the dictionary each handler happened to build. Four handlers, four habits, no contract.

## The version question, answered

ADR-0113's correction left one thing open: M6 ships v0.6.0 and 1.0 lands at M7, so where does
"1.0 compatibility promise published" — an M6 exit gate — go? Answered here: the promise is
*published* with M6 and *binds* at the v1.0.0 tag. The gate says published, not in force; a
promise is worth publishing before it binds so plugin authors know what to build against; and
binding at 0.6.0 would make 6.7 and 7.2, both of which may touch a contract, MAJOR events at a
version number that cannot express one. Until the tag, spec 05 §5's pre-1.0 clause governs —
a change at a MINOR, announced by an RFC, an ADR, a migration note and a re-blessed golden.

## Shape, not prose

The mechanism is G6's — a projection, a committed golden, a section-wise compare, a re-bless
tool sharing the projection's code — with one difference that decides whether the gate
survives contact with this repository: the golden holds the *shape* of a schema and none of
its prose. pydantic writes every docstring into `description`, and this repository edits
docstrings in most pull requests. A golden of the exported schema files byte for byte would
fire on nearly every change and be re-blessed by reflex, which is how a gate becomes
decoration (ADR-0053). So `schema_shape` strips `description`, `title`, `examples` and
`$comment` at every level that is a schema — and treats the values of `properties` as names,
so a property that happens to be called `title` survives.

Two projections are worth noting for how they were taken rather than what they hold. The
KIR per-kind field table is *asked of the record*: every kind is tried with every
kind-specific field and the answer recorded, so the golden pins behaviour and not the private
constant that implements it. And the plugin protocols are spelled with qualified names only,
because `pathlib.PurePosixPath` became `pathlib._local.PurePosixPath` between Python 3.12 and
3.13 and both are in the CI matrix — a golden must not carry a standard library's module
layout.

## The freeze review's disposals

Six ADRs and one owner decision had addressed a question to "6.1" by name. Each got an
answer: `extra="forbid"` on KIR stays (declared evolution is the only evolution); no per-kind
union (it would change the wire schema at the moment of freezing, and the golden pins the field
sets behaviourally); `Embedder` stays outside the frozen protocols (no entry point can supply
one, so there is no third-party implementation to protect — pinned by a test that says when the
premise changes); no `Extractor` (three core stages, none resolvable as a plugin); the module
façade refused again on the same single consumer, with the trigger re-armed to the v1.0.0 tag;
and D-029's spin-outs wait for the tag that binds.

## Two small things the golden caught

The first run wrote `Infinity` into the identity golden — the vector that hands `inf` to
`canonical_json` to prove it is refused. Python's `json` writes and reads `Infinity` without
complaint; a strict parser refuses it. A golden a strict parser cannot read is not a golden,
so non-finite floats are rendered explicitly.

And the first draft of the output-schema test assumed a sixty-token budget truncates the
fixture corpus. It does not — three short chunks fit — so the budget is now sized from the
first result's own cost, the way the existing MCP budget test sizes it. The schema was
right; the test's picture of the corpus was not.

## Lesson

A policy that has been in the spec since Phase 1 and pinned nothing for five milestones is
not a policy; it is a sentence. The freeze became real the moment each contract had a
committed statement of its shape that a change could disagree with — and it will stay real
only as long as the golden holds shape rather than prose, because a gate that fires on a
docstring is re-blessed without being read.
