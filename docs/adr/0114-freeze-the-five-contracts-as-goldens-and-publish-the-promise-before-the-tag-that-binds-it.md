# ADR-0114: Freeze the five contracts as goldens, and publish the promise before the tag that binds it

- **Status:** Accepted
- **Date:** 2026-09-14
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §10, under the
  maintainer's version correction recorded in ADR-0113
- **Related:** [ADR-0113](0113-close-a-milestone-on-its-gates-and-carry-an-unmet-one-by-name.md)
  (the open question this answers), [ADR-0012](0012-adopt-the-g6-determinism-gate.md) (the
  golden discipline this borrows), [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)
  (a gate that fires on everything selects for being ignored), [ADR-0086](0086-declare-the-module-facing-surface-and-refuse-to-freeze-it-from-one-consumer.md)
  (the module surface, and the trigger it set for this review), [ADR-0089](0089-carry-both-halves-of-a-citations-identity-and-read-what-you-do-not-know.md)
  (the lenient reader the identity rules grow through), and the five records that deferred a
  question to the freeze — [ADR-0004](0004-adopt-pydantic-v2-record-contracts.md),
  [ADR-0006](0006-adopt-markdown-it-adapter-and-kir-node-fields.md),
  [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md),
  [ADR-0063](0063-split-the-leaf-heading-from-its-ancestors.md),
  [ADR-0076](0076-let-the-corpus-declare-its-entities-and-refuse-to-guess-the-rest.md);
  spec 02 §10, spec 03 §§2, 4, 7, spec 05 §§3–5, spec 06 §4 and §Phase 4; D-016, D-029;
  roadmap 5.14, 6.1, 6.7, 7.2

## Context

Spec 02 §10 names five contracts v1 may not change casually — identity rules, the KIR
schema, the snapshot manifest schema, the MCP tool contracts, the plugin protocols — and
spec 05 §5 asked, from Phase 1, that they *"get compatibility tests in CI — a PR cannot
silently break them"*. Roadmap 6.1 is where the freeze lands and the tests are built. Two
things had to be settled first, and a third had accumulated.

### What actually pinned the five before this item

| contract | what pinned it | what could move without a test noticing |
|---|---|---|
| identity rules | gate G6's golden, indirectly — a slug or digest change moves every anchor in the fixture corpus | anything, because G6 is *re-blessed at every intended compiler change* and the diff reads as a compiler change |
| KIR schema | `test_schema_version_tags_match_record_names` (the tag), `test_kir_nodes_accept_the_fields_their_kind_declares` (three kinds) | a field added or removed, a kind's field set widened, a validator tightened |
| snapshot manifest | the version tag; G6 records `schema_versions` and `counts` | a field made required, a field removed, an artifact class dropped |
| MCP tool contracts | `test_tools_list_exposes_exactly_the_four_v1_tools` (the names), one test per tool asserting a handful of keys | an input schema tightened; and the *output* had no declared shape at all — it was whatever four handlers built |
| plugin protocols | `test_a_minimal_class_satisfies_each_protocol` for two of the four | a Protocol member renamed, a signature changed, a transport field added, `MYCELIUM_API_VERSION` left alone while any of that happened |

None of this is a test of *compatibility*: each is a test of the current behaviour that a
contributor changing the behaviour would update in the same commit.

### When the promise binds

ADR-0113 relabelled the milestones and the maintainer corrected it before the v0.5.0 cut:
Milestone 6 ships **v0.6.0** and 1.0 lands at **Milestone 7**. That left one thing open, and
the note in ADR-0113 says where it belongs: *"M6's exit gates still include '1.0
compatibility promise published' while M6 now ships v0.6.0. Whether that promise publishes
at M6 or at M7 belongs with 6.1."*

### What earlier records deferred to this review

Six ADRs and one owner decision addressed a question to "the freeze" or to "6.1" by name:
ADR-0004 (revisit `extra="forbid"` on KIR), ADR-0006 (a per-kind discriminated union for
`KirNode`), ADR-0032 (reconcile `Embedder`'s import path), ADR-0063 (an additive key in
`explain` is not a shape change), ADR-0076 (design `Extractor` against all three extraction
kinds), ADR-0086 (the module-facing façade — "a second module, or the 1.0 freeze review
(roadmap 6.1), whichever comes first"), and D-029 (per-plugin spin-outs *after* the freeze).
A freeze review that did not dispose of each would leave the questions addressed to nobody.

## Decision

**The promise is published now and binds at the v1.0.0 tag.** `docs/compatibility.md` is
the 1.0 compatibility promise spec 06 §Phase 4 asks for, published with Milestone 6, and it
says two things about time: until v1.0.0 the pre-1.0 rule of spec 05 §5 applies — a contract
may change at a MINOR, announced by an RFC, an ADR, a migration note and a re-blessed golden
in the same pull request — and from v1.0.0 an incompatible change is a MAJOR release and an
additive one a MINOR. That answers ADR-0113's question: the gate says *published*, a promise
is worth publishing before it binds so that plugin authors know what to build against, and
binding it at 0.6.0 would make the two remaining pre-1.0 items that may touch a contract
(6.7's citation granularity, 7.2's server-side manifest fields) MAJOR events at a version
number that cannot express one.

**Each contract is frozen as a golden of its shape.** `mycelium.contracts` projects each of
the five to a canonical JSON document of the facts a consumer can observe and nothing else;
the five goldens under `tests/fixtures/contracts/` are committed; `tests/test_contracts.py`
compares projection and golden section by section; `tools/update_contract_goldens.py`
re-blesses. This is gate G6's discipline (ADR-0012) with one deliberate difference in what the
golden holds: **shape, not prose**. A schema projection strips `description`, `title`,
`examples` and `$comment` and keeps every keyword that constrains a producer or a consumer,
because this repository edits docstrings in most pull requests and a gate that fired on each
would be re-blessed by reflex (ADR-0053). What each golden pins:

- *identity* — sixty-eight vectors, each written to exercise one clause of spec 03 §§1–2
  (a normalization step, a grammar boundary, a refusal), plus the grammar constants and the
  four string patterns. A refusal is recorded as the exception type: what the grammar rejects
  is as much the contract as what it accepts.
- *kir* — the schema's shape, the node-kind vocabulary, the opaque dispositions, and the
  per-kind field table **asked of the record rather than read from it**: every kind is tried
  with every kind-specific field and the answer is recorded, so the golden pins behaviour
  and not a private constant.
- *manifest* — the schema's shape, the artifact classes a manifest reports, and their tags.
- *mcp-tools* — the four tools' input and output schemas, the six error codes with the
  fields each may carry, the notice sentence, and the protocol revisions served.
- *plugin-api* — `MYCELIUM_API_VERSION`, the four Protocols' members and signatures, the
  five transport records' fields and defaults, the two entry-point groups, and the exported
  names of the three SDK modules.

**A golden is named for its contract's version token, where the contract has one.**
`kir.v0.json`, `manifest.v0.json` and `plugin-api.v0.json` carry `schema_version` and
`MYCELIUM_API_VERSION`; an incompatible change bumps the token first, which renames the file
and leaves the old shape in history. Identity and the tool surface have **no token by
nature**: a citation URI in an agent's transcript carries none and must resolve in every later
release, so the identity rules are append-only for good, and the tools are versioned by the
package that serves them. Beside the goldens, `history/v0.5.0/` holds a manifest and a KIR
document a v0.5.0 build wrote; they are never regenerated, and the suite loads them with
today's readers — the reader half of the promise, which a golden of today's shape cannot test.

**The MCP output contract is declared, not inferred.** Each tool's `tools/list` entry now
carries an `outputSchema` beside the `inputSchema` it always had (`mycelium.mcp.schemas`),
and the suite validates every real payload against it — every context of `fetch`, the stale
block in both of its kinds, `search` with and without `explain`, truncated and not. The
schemas distinguish a **record**, which closes its shape, from a **map**, which fixes only the
value type: `field_weights`, `timings_ms` and a candidate's `ranks` are keyed by the names
of legs, stages and fields, which are configuration and not contract (ADR-0063's "additive
key in a debugging payload" is exactly this). The error result is declared separately
(`error_payload_schema`), because a conformant client validates `structuredContent` only when
`isError` is false; and the fields a code may carry are declared once
(`ERROR_FIELDS`) and enforced in the constructor, so the declaration is true by construction.

**The review disposes of every question addressed to it.**

- *ADR-0004, `extra="forbid"` on KIR:* **kept.** The freeze makes declared evolution the
  only evolution. An open IR would let a parser write fields no reader validates and no
  schema exports, and the exported JSON Schema is what a non-Python consumer holds.
- *ADR-0006, a per-kind union for `KirNode`:* **not adopted.** Four engines and a grammar
  extractor have shipped since and the table was amended once (`opaque.variant`, 4.3) and the
  common core once (`spans`, 5.23). A union would change the wire schema at the moment it is
  frozen; the golden pins the per-kind field sets behaviourally, which is what the union was
  for.
- *ADR-0032, `Embedder`:* **stays outside the frozen protocols.** `build_embedder` resolves
  exactly two names and no entry point can supply a third — *"API providers are an opt-in
  plugin surface, not a v1 default"* — so there is no third-party embedder for a frozen
  protocol to protect. It joins `mycelium.sdk.protocols`, additively, the day a provider
  resolves through the registry. A test pins the premise so its change is an act.
- *ADR-0076, `Extractor`:* **not added.** Three extraction kinds exist as core stages and
  none is resolvable as a plugin; a Protocol with no implementation outside the core and no
  resolver is the guess ADR-0032 refused. The freeze binds what exists.
- *ADR-0086, the module-facing façade:* **refused again, and the trigger re-armed.** The
  review found the same single consumer 5.14 had. The six unfrozen components stay declared
  and unfrozen; the promise names them as outside it; the trigger becomes *the second
  module, or the v1.0.0 tag, whichever comes first*, because a decision taken from a sample of
  one is unavoidable at the tag and premature a milestone before it.
- *D-029, spin-outs after the freeze:* the freeze *binds* at v1.0.0, so nothing spins out at
  6.1. D-029's own rationale — an external plugin repository chasing a pre-1.0 API burns the
  contributors it means to attract — is the reason.
- *ADR-0063 and ADR-0071:* confirmed, nothing to do. The former's additive key is a map entry
  in the new schema; the latter's `py.typed` is in place.

## Alternatives Considered

- **Bind the freeze at v0.6.0.** Rejected. Spec 05 §5 says pre-1.0 a MINOR may break with a
  migration note, SemVer says the same, and two items on the roadmap may still need to touch a
  contract before 1.0. A freeze that binds before the version that can express a break is a
  promise the next honest change has to violate.
- **Publish the promise at Milestone 7, with the tag.** Rejected. The gate reads
  *published*, not *in force*; the suite that checks the promise is useful from the day it
  exists; and a plugin author reading the repository between 0.6.0 and 1.0.0 deserves to know
  what will bind and what already cannot change silently.
- **Pin the exported schema files byte for byte.** The obvious mechanism — `schemas/` is
  already written by every build — and rejected because it pins prose: pydantic writes every
  docstring into `description`, and this repository edits docstrings in most pull requests.
  The gate would fire on nearly every change and be re-blessed by reflex, which is how a gate
  becomes decoration.
- **Derive the output shapes from fixture runs rather than declare them.** Rejected. A
  key-tree taken from a payload depends on the corpus — which legs ran, which stages timed —
  and a derived description is not something a client can consume. A declared `outputSchema`
  is both the contract and a thing the reference client validates against, so the existing
  conformance test now exercises the output shape for free.
- **One token for all five (`MYCELIUM_API_VERSION`), or mint tokens for identity and the
  tools.** Rejected. The records already carry `schema_version` and a second token would
  disagree with it; identity cannot carry one, because a URI already minted cannot be told
  which version it belongs to; and a token on the tool surface would restate the package
  version.
- **Freeze `Embedder` now, or design `Extractor` now, because the spec lists them.** Rejected
  on the rule every plugin decision since ADR-0032 has applied: a contract is frozen when
  something outside the core can implement it and be resolved. Freezing a shape nobody
  outside can satisfy protects nobody and binds the platform phase to a guess.
- **Build the `mycelium.sdk` façade now, because the review is the trigger ADR-0086 set.**
  Rejected for ADR-0086's reason, which the review did not change: the second consumer is
  what says which half of a one-consumer API was accidental, and none has arrived. The
  trigger is re-armed to the tag rather than dropped.
- **Freeze only by policy — RFC required, no goldens.** Rejected on this project's standing
  rule: a claim without a check is a claim. The policy was in the spec from Phase 1 and pinned
  nothing for five milestones.

## Consequences

- **`tools/list` gains `outputSchema` on every tool.** This is the one change to the served
  surface. The reference MCP client validates `structuredContent` against it, so
  `test_the_official_mcp_client_can_drive_this_server` now checks the output shape end to
  end; clients on the 2024-11-05 revision ignore the key. A handler that emits a key its
  schema does not name fails the suite, which is the point.
- **`McpToolError` refuses an undeclared field.** A `TypeError` at the raise site, which the
  server would render as an `INTERNAL` result if it ever reached a client; no current call
  site can trigger it.
- **A change to any of the five now meets a failing test**, and the diff of the re-blessed
  golden is the review artifact — beside the RFC spec 06 §4 requires and the migration note
  spec 05 §5 requires. Nothing about the product's behaviour changes: no baseline, gate,
  golden or corpus moves, and G6's golden is byte-identical.
- **`mycelium.contracts` is a new component** shared by the suite and the re-bless tool, on
  the pattern of `mycelium.determinism`. It is not module-facing and is not in
  `MODULE_SURFACE`; `mycelium.sdk.schema` gains `constraint_pattern`, the regex behind a
  constrained string alias, so the MCP schemas and the projector read the identity grammar
  from one place.
- **The spec is amended where the promise now lives**: `.draft-specs/02` §10 and `05` §5 point
  at the goldens and the binding date; spec 05 §4.3's statement about the module surface is
  unchanged and its trigger is restated in `mycelium.modules`.
- **A limitation, stated.** A golden pins what a projection can see. A change that keeps the
  shape and moves the meaning — which section `defined_in` names, how a slug is chosen for an
  input no vector covers — is not caught here; the identity vectors cover the clauses they
  list, G6 covers the fixture corpus, and the evaluation harness covers retrieval. A map's
  keys are unpinned by design. And the history fixtures were written by this pull request's
  own build of v0.5.0, on the day the freeze landed: the first record an *earlier* release
  wrote arrives with the next release, and the suite will hold it the same way.

## References

- Spec: `.draft-specs/02-architecture.md` §10 (the five contracts, amended here);
  `.draft-specs/03-data-model.md` §§2, 4, 7; `.draft-specs/05-interfaces-and-plugins.md`
  §§3–5 (the compatibility policy, amended here); `.draft-specs/06-roadmap-and-governance.md`
  §4 (an RFC per contract change) and §Phase 4 (the gate).
- The promise: `docs/compatibility.md`. The suite: `tests/test_contracts.py`. The goldens:
  `tests/fixtures/contracts/`. The re-bless: `python tools/update_contract_goldens.py`.
- Decision log: D-016 (rebuild as migration), D-023 (extension points built against
  consumers), D-029 (spin-outs after the freeze).
- Re-runnable: `uv run pytest tests/test_contracts.py -q`, and
  `python -c "from mycelium.contracts import project; print(project('plugin-api')['protocols'].keys())"`.
