# Design Patterns Catalogue

Living index of every design pattern **adopted**, **planned**, **considered and rejected**,
or **under evaluation** for `mycelium-os`. Mandatory reading whenever a PR introduces
or removes a pattern, and updated in the same PR.

- **Rules** — [`AGENTS.md`](../../AGENTS.md) §8.
- **Canonical taxonomy** — [`design-patterns.md`](design-patterns.md). All pattern names
  used here, in ADRs, and in commit messages must match its spelling and categorisation.

## Architecture style

**Committed style:** Hexagonal — from [`design-patterns.md`](design-patterns.md) §5.
**Pattern discipline:** `advisory` — `advisory` means the agent advises and the human
decides; `enforced` makes conformance to the committed style + adopted patterns a review expectation.


## How to use this catalogue

- **Adding a pattern** — when a PR lands one, add a row to *Implemented / Planned* as
  `Implemented`, with the ADR link and the code location (a real path under
  `src/mycelium/...`); a pattern decided in an ADR but not yet in code is added as `Planned`.
- **Refining** — update the row and link the new ADR.
- **Rejecting** — add it to *Rejected* with the reason; do not silently drop it.
- **Removing** — move the row to *Superseded*, link the superseding ADR, keep the history.

Status vocabulary: `Planned` (decided in an ADR, not yet landed) · `Implemented` (present
in `src/mycelium/...`, ADR `Accepted`) · `Considered` · `Rejected` · `Superseded`.

## Implemented / Planned

_Patterns named in the spec at intake are seeded below as **Planned**; each becomes
**Implemented** with its ADR and a real code location in the PR that introduces it._

| # | Pattern | Status | Problem it addresses | Code location | ADR / PR |
|---|---------|--------|----------------------|---------------|----------|
| 1 | Immutable Object | Implemented | records are facts shared across pipeline stages; post-construction mutation is a defect class removed at the type layer (frozen `Record` base, tuple sequences) | [src/mycelium/sdk/types.py](../../src/mycelium/sdk/types.py) | [ADR-0004](../adr/0004-adopt-pydantic-v2-record-contracts.md) / PR #14 |
| 2 | Monitor Object | Implemented | monotonic ULID minting is a read-modify-write on shared state; build stages run in bounded parallelism, so `UlidFactory.new` serializes on a lock or the sortability invariant is lost | [src/mycelium/sdk/identity.py](../../src/mycelium/sdk/identity.py) | [ADR-0005](../adr/0005-adopt-in-repo-identity-library.md) / PR #16 |
| 3 | Dependency Injection | Implemented | the ULID factory's only impurities — clock and entropy — are constructor-supplied, so ordering rules are asserted deterministically instead of sampled | [src/mycelium/sdk/identity.py](../../src/mycelium/sdk/identity.py) | [ADR-0005](../adr/0005-adopt-in-repo-identity-library.md) / PR #16 |
| 9 | Pipeline | Implemented | the compiler is a typed stage DAG with pure stages and declared inputs/outputs (D-008): parse → chunk → assemble per document, each stage identified by a build key, sequenced by the orchestrator and never by each other. Extended at 3.4 to the seam the graph needed: link *extraction* is a per-document stage with an explicit intermediate (`LinkRef`), link *resolution* a global one over the corpus — separating them is what keeps compilation O(changed) while the graph stays correct | [src/mycelium/build/dag.py](../../src/mycelium/build/dag.py), [src/mycelium/graph.py](../../src/mycelium/graph.py) | [ADR-0015](../adr/0015-adopt-content-addressed-incremental-builds.md) / PR #31, extended by [ADR-0018](../adr/0018-build-the-graph-from-authored-links.md) / PR #34 |
| 10 | Content-Addressed Cache | Implemented | build keys — SHA-256 over (stage, impl version, input digests, config slice, schema) — index canonical-JSON blobs stored by their own digest, so rebuilds reuse any artifact ever produced under the same inputs (D-008); the cache self-heals because a blob that does not hash to its name is discarded. Applied again at 4.2 to **tier-1 custody**, where the same addressing carries the opposite lifecycle: an acquired original is evidence, so it is never garbage-collected and a blob that fails its digest is *reported* rather than discarded — one mechanism, two policies, and the difference is the whole design | [src/mycelium/build/cas.py](../../src/mycelium/build/cas.py), [src/mycelium/ingest/custody.py](../../src/mycelium/ingest/custody.py) | [ADR-0015](../adr/0015-adopt-content-addressed-incremental-builds.md) / PR #31, extended by [ADR-0033](../adr/0033-keep-the-original-and-bound-the-hostile.md) / PR #52 |
| 8 | Snapshot | Implemented | immutable manifests + atomic CURRENT pointer swap give torn-free publication (D-015); the one crash window v0 cannot close is documented in the ADR rather than denied. Refined at 3.2: with a single mutable store the swap alone cannot roll back, so a snapshot also carries restorable state | [src/mycelium/build/publish.py](../../src/mycelium/build/publish.py) | [ADR-0009](../adr/0009-adopt-build-publication-semantics.md) / PR #20, refined by [ADR-0016](../adr/0016-make-snapshots-restorable.md) / PR #32 |
| 12 | Plugin | Implemented | ingestion is open to implementations without being open to ambiguity: `Connector` and `Parser` are typed Protocols in the SDK, third-party plugins arrive through the `mycelium.plugins` entry-point group, and resolution is *pinned* — `[ingest] parsers` in order, an unresolvable name is an error naming what to install, and a plugin may not shadow a built-in id. There is no 'best available' (D-012/D-023, spec 05 §4.2), because a build must be explainable from its manifest alone. Extended at 4.4 by `Synthesizer` — the first plugin whose output is *not* a function of its input, so it declares `deterministic = false` and returns the identity of what wrote the text. The remaining Protocols (Chunker, Extractor, Reranker) land with their milestones; `Embedder` already exists beside its subsystem and is reconciled at the 1.0 freeze (roadmap 6.1) | [src/mycelium/sdk/protocols.py](../../src/mycelium/sdk/protocols.py), [src/mycelium/ingest/registry.py](../../src/mycelium/ingest/registry.py), [src/mycelium/synthesis/wiki.py](../../src/mycelium/synthesis/wiki.py) | [ADR-0032](../adr/0032-adapt-four-engines-and-pin-which-one-runs.md) / PR #50, extended by [ADR-0035](../adr/0035-let-an-llm-write-only-what-a-machine-can-check.md) / PR #54 |
| 4 | Adapter | Implemented | parsers wrap the existing ecosystem behind KIR — Mycelium OS owns the representation and its guarantees, not the parsers (D-007); markdown-it was the first one adapted. Extended at 4.1 to three more engines — docling's declarative backends, the pandoc binary's JSON AST, and PDFium's text layer — which is where the pattern earned its keep: one document rendered into DOCX, HTML and reStructuredText reaches four different engines and comes back with the same citable anchors, and what an engine emits that KIR cannot model becomes an `opaque` node rather than a silent hole | [src/mycelium/markdown/adapter.py](../../src/mycelium/markdown/adapter.py), [src/mycelium/ingest/parsers/pandoc.py](../../src/mycelium/ingest/parsers/pandoc.py) | [ADR-0006](../adr/0006-adopt-markdown-it-adapter-and-kir-node-fields.md) / PR #17, extended by [ADR-0032](../adr/0032-adapt-four-engines-and-pin-which-one-runs.md) / PR #50 and [ADR-0034](../adr/0034-project-the-evidence-and-count-what-it-lost.md) / PR #53 |
| 5 | Strategy | Implemented | token counting is one interchangeable algorithm behind a fixed signature: the default estimate ships no model and is reproducible, while a caller that needs a specific tokenizer supplies it through `ChunkingPolicy.count_tokens`. Applied again at 3.3 to **embedding**: text in, unit vectors out, plus the identity a manifest must record — the local ONNX encoder is one implementation, a plugin (D-023) or an API provider another, and a test double satisfies it in a dozen lines, which is the check that a plugin can. Applied a third time at 4.4 to the **LLM provider**: one call, text in, text out, and the seam is what lets the whole synthesis lane — prompt, citation contract, repair, refusal — be exercised without a network. Applied a third time at 4.5 to **entailment**: a claim and the evidence it cited go in, a verdict and a reason come out, and the LLM judge is one implementation while a test double is another — which is what lets gate G7's whole decision be exercised without a model. The absent judge is deliberately *not* a strategy: see the Null Object rejection below | [src/mycelium/chunking.py](../../src/mycelium/chunking.py), [src/mycelium/embedding/base.py](../../src/mycelium/embedding/base.py), [src/mycelium/synthesis/provider.py](../../src/mycelium/synthesis/provider.py), [src/mycelium/verification/entailment.py](../../src/mycelium/verification/entailment.py) | [ADR-0007](../adr/0007-adopt-structure-first-chunking.md) / PR #18, extended by [ADR-0017](../adr/0017-adopt-the-local-embedder-and-hybrid-retrieval.md) / PR #33 and [ADR-0035](../adr/0035-let-an-llm-write-only-what-a-machine-can-check.md) / PR #54, extended by [ADR-0036](../adr/0036-measure-what-can-be-measured-and-let-a-human-outrank-the-gate.md) / PR #55 |
| 6 | Repository | Implemented | the compiler and serving layer speak records, never rows: the `Store` protocol states every operation a store must offer, so SQLite is replaceable at the platform phase (D-019) rather than load-bearing | [src/mycelium/store/base.py](../../src/mycelium/store/base.py) | [ADR-0008](../adr/0008-adopt-sqlite-store-behind-a-store-protocol.md) / PR #19 |
| 7 | Data Mapper | Implemented | records and rows stay independent — mapping lives in two functions at the store boundary, so a schema change never reaches a record and a record change never reaches SQL | [src/mycelium/store/sqlite.py](../../src/mycelium/store/sqlite.py) | [ADR-0008](../adr/0008-adopt-sqlite-store-behind-a-store-protocol.md) / PR #19 |
| 11 | Memento | Implemented | rollback must hand the compiler back a previous state without any consumer of a snapshot depending on that state's shape: each publication captures its whole `doc_state` table as one content-addressed blob, and restoring it reinstates both the served corpus and the incremental build state it must reason from next | [src/mycelium/build/snapshots.py](../../src/mycelium/build/snapshots.py) | [ADR-0016](../adr/0016-make-snapshots-restorable.md) / PR #32 |


## Rejected

| # | Pattern | Considered for | Rejected because | ADR / PR |
|---|---------|----------------|------------------|----------|
| 1 | Specification | the ingestion admission guards (`mycelium.ingest.safety`): bound an untrusted document's shape — archive expansion ratio, markup nesting depth, KIR node count — before an engine is asked to read it | it would be a force-fit, which §8 forbids. Specification composes predicates *as objects* so callers can build new selections from them; these are four fixed, media-type-specific checks with no composition and no caller that wants any. Naming a pattern here would make the catalogue less informative, not more: the honest description is "four functions that raise". Recorded rather than silently skipped, because the next reader will ask the same question | [ADR-0033](../adr/0033-keep-the-original-and-bound-the-hostile.md) / PR #52 |
| 2 | Guarded Suspension | the same guards, on the strength of the word "guard" | it is a *concurrency* pattern — block until a precondition holds, then proceed — and nothing here blocks or waits. The name would mislead on the first read | [ADR-0033](../adr/0033-keep-the-original-and-bound-the-hostile.md) / PR #52 |
| 3 | Null Object | the absent entailment judge: with no LLM provider configured, gate G7's second component has nothing to ask, and a do-nothing judge would remove the `None` check from every caller | a null judge would still have to *answer*, and every answer it could give is wrong. "Entailed" passes a document nobody checked; "not entailed" fails one nobody found fault with; a neutral 0.5 is a fabricated grounding score, which is the artifact this project refuses above all others (ADR-0035). The absence has to stay visible all the way to the operator, so it travels as `None` and the callers keep their check | [ADR-0036](../adr/0036-measure-what-can-be-measured-and-let-a-human-outrank-the-gate.md) / PR #55 |

## Superseded

_No superseded patterns yet._

| # | Pattern | Superseded by | When | ADR / PR |
|---|---------|---------------|------|----------|
| — | —       | —             | —    | —        |

## Candidate patterns to consider

The taxonomy in [`design-patterns.md`](design-patterns.md) lists every pattern in scope. As
the architecture takes shape, narrow that universe to the patterns plausibly applicable to
*this* artifact and list them here by category, each with a one-line "possible application".
A candidate remains a candidate until adopted (own ADR) or explicitly rejected.

## Out-of-scope categories

Record here any taxonomy category pre-classified as not applicable to this artifact (with a
one-line reason), so the policy of explicit rejection is honoured without filling the
*Rejected* table with N/A noise.
