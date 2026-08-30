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
| 10 | Content-Addressed Cache | Implemented | build keys — SHA-256 over (stage, impl version, input digests, config slice, schema) — index canonical-JSON blobs stored by their own digest, so rebuilds reuse any artifact ever produced under the same inputs (D-008); the cache self-heals because a blob that does not hash to its name is discarded | [src/mycelium/build/cas.py](../../src/mycelium/build/cas.py) | [ADR-0015](../adr/0015-adopt-content-addressed-incremental-builds.md) / PR #31 |
| 8 | Snapshot | Implemented | immutable manifests + atomic CURRENT pointer swap give torn-free publication (D-015); the one crash window v0 cannot close is documented in the ADR rather than denied. Refined at 3.2: with a single mutable store the swap alone cannot roll back, so a snapshot also carries restorable state | [src/mycelium/build/publish.py](../../src/mycelium/build/publish.py) | [ADR-0009](../adr/0009-adopt-build-publication-semantics.md) / PR #20, refined by [ADR-0016](../adr/0016-make-snapshots-restorable.md) / PR #32 |
| — | Plugin (typed Protocols + entry points) | Planned | Parser/Chunker/Embedder/Extractor/Synthesizer/Reranker plus four generic extension mechanisms; pinned resolution, never 'best available' (D-012/D-023) | _TBD_ | _spec (intake)_ |
| 4 | Adapter | Implemented | parsers wrap the existing ecosystem (docling, markdown-it, pandoc) behind KIR — Mycelium OS owns the representation and its guarantees, not the parsers (D-007); markdown-it is the first one adapted | [src/mycelium/markdown/adapter.py](../../src/mycelium/markdown/adapter.py) | [ADR-0006](../adr/0006-adopt-markdown-it-adapter-and-kir-node-fields.md) / PR #17 |
| 5 | Strategy | Implemented | token counting is one interchangeable algorithm behind a fixed signature: the default estimate ships no model and is reproducible, while a caller that needs a specific tokenizer supplies it through `ChunkingPolicy.count_tokens`. Applied again at 3.3 to **embedding**: text in, unit vectors out, plus the identity a manifest must record — the local ONNX encoder is one implementation, a plugin (D-023) or an API provider another, and a test double satisfies it in a dozen lines, which is the check that a plugin can | [src/mycelium/chunking.py](../../src/mycelium/chunking.py), [src/mycelium/embedding/base.py](../../src/mycelium/embedding/base.py) | [ADR-0007](../adr/0007-adopt-structure-first-chunking.md) / PR #18, extended by [ADR-0017](../adr/0017-adopt-the-local-embedder-and-hybrid-retrieval.md) / PR #33 |
| 6 | Repository | Implemented | the compiler and serving layer speak records, never rows: the `Store` protocol states every operation a store must offer, so SQLite is replaceable at the platform phase (D-019) rather than load-bearing | [src/mycelium/store/base.py](../../src/mycelium/store/base.py) | [ADR-0008](../adr/0008-adopt-sqlite-store-behind-a-store-protocol.md) / PR #19 |
| 7 | Data Mapper | Implemented | records and rows stay independent — mapping lives in two functions at the store boundary, so a schema change never reaches a record and a record change never reaches SQL | [src/mycelium/store/sqlite.py](../../src/mycelium/store/sqlite.py) | [ADR-0008](../adr/0008-adopt-sqlite-store-behind-a-store-protocol.md) / PR #19 |
| 11 | Memento | Implemented | rollback must hand the compiler back a previous state without any consumer of a snapshot depending on that state's shape: each publication captures its whole `doc_state` table as one content-addressed blob, and restoring it reinstates both the served corpus and the incremental build state it must reason from next | [src/mycelium/build/snapshots.py](../../src/mycelium/build/snapshots.py) | [ADR-0016](../adr/0016-make-snapshots-restorable.md) / PR #32 |


## Rejected

_No rejections recorded yet._

| # | Pattern | Considered for | Rejected because | ADR / PR |
|---|---------|----------------|------------------|----------|
| — | —       | —              | —                | —        |

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
