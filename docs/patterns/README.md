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
| — | Pipeline | Planned | the compiler is a typed stage DAG with pure stages and declared inputs/outputs (D-008) | _TBD_ | _spec (intake)_ |
| — | Content-Addressed Cache | Planned | build keys — SHA-256 over (stage, impl version, input digests, config, schema) — make rebuilds incremental and reproducible (D-008) | _TBD_ | _spec (intake)_ |
| — | Snapshot | Planned | immutable manifests + atomic CURRENT pointer swap give torn-free reads and O(1) rollback (D-015) | _TBD_ | _spec (intake)_ |
| — | Plugin (typed Protocols + entry points) | Planned | Parser/Chunker/Embedder/Extractor/Synthesizer/Reranker plus four generic extension mechanisms; pinned resolution, never 'best available' (D-012/D-023) | _TBD_ | _spec (intake)_ |
| — | Adapter | Planned | parsers wrap the existing ecosystem (docling, markdown-it, pandoc) behind KIR — Mycelium OS owns the representation and its guarantees, not the parsers (D-007) | _TBD_ | _spec (intake)_ |


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
