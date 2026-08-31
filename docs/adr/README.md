# Architecture Decision Records

One numbered Markdown file per decision, in the lightweight
[Michael Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
format. Numbering is sequential and never reused or renumbered. Template:
[`template.md`](template.md).

Open an ADR when a choice affects the public surface or compatibility, when two reasonable
options exist and the rationale is non-obvious, when a **design pattern** is adopted, or
when superseding a prior decision. Do **not** open one for routine implementation details
or trivially reversible choices.

Status transitions: `Proposed` → `Accepted` → (`Superseded by ADR-XXXX` | `Deprecated`).

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-adopt-cross-language-source-layout.md) | Adopt the cross-language source layout | Superseded by ADR-0003 |
| [0003](0003-adopt-flat-python-src-layout.md) | Adopt the flat Python src-layout (D-024) | Accepted |
| [0004](0004-adopt-pydantic-v2-record-contracts.md) | Adopt pydantic v2 record contracts with JSON Schema 2020-12 export | Accepted |
| [0005](0005-adopt-in-repo-identity-library.md) | Implement the identity library in-repo, with an injectable monotonic ULID factory | Accepted |
| [0006](0006-adopt-markdown-it-adapter-and-kir-node-fields.md) | Adapt Markdown to KIR over markdown-it, and give KIR nodes declared per-kind fields | Accepted |
| [0007](0007-adopt-structure-first-chunking.md) | Chunk on document structure, with a dependency-free token estimate | Accepted |
| [0008](0008-adopt-sqlite-store-behind-a-store-protocol.md) | Keep SQLite behind a store protocol, and index lexically in a standalone FTS5 table | Accepted |
| [0009](0009-adopt-build-publication-semantics.md) | Fix the build's publication semantics — lock file, transaction-then-swap, identity pinned at first build | Accepted |
| [0010](0010-adopt-cli-output-conventions.md) | CLI output conventions — one JSON document on stdout, ASCII chrome, UTF-8 content | Accepted |
| [0011](0011-implement-mcp-stdio-in-repo.md) | Implement the MCP stdio server in-repo, and prove conformance with the reference client | Accepted |
| [0012](0012-adopt-the-g6-determinism-gate.md) | State what determinism claims, and gate it with a reviewable golden | Accepted |
| [0013](0013-adopt-the-evaluation-harness.md) | Evaluate against the grep incumbent, and publish the harness's limits with its numbers | Accepted |
| [0014](0014-adopt-partial-strict-configuration.md) | Load `mycelium.toml` strictly, honour it partially, and say which is which | Accepted |
| [0015](0015-adopt-content-addressed-incremental-builds.md) | Compile incrementally through a content-addressed stage cache | Accepted |
| [0016](0016-make-snapshots-restorable.md) | Make snapshots restorable, and give garbage collection a defined live set | Accepted |
| [0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) | Ship a local embedder and hybrid retrieval, and let gate G2 choose the default | Accepted |
| [0018](0018-build-the-graph-from-authored-links.md) | Build the graph from authored links, and resolve it globally on every build | Accepted |
| [0019](0019-adopt-watch-mode.md) | Let filesystem events decide *when* to build, never *what* to build | Accepted |
| [0020](0020-adopt-the-jsonl-interchange-bundle.md) | Make the export bundle a verifiable claim, not a directory of files | Accepted |
| [0021](0021-scope-the-corpus-and-gate-the-evaluation.md) | Scope the corpus, then let the gates run in CI | Accepted |
| [0022](0022-measure-the-agent-loop-without-an-agent.md) | Measure the agent loop without an agent, and say what that leaves out | Accepted |
| [0023](0023-make-the-chunk-target-steer-size.md) | Make `target_tokens` steer chunk size, and let the evaluation pick its default | Accepted |
| [0024](0024-serve-what-the-configuration-admits.md) | Make the vocabulary filters set-valued, and enforce the serving policy at one seam | Accepted |
| [0025](0025-make-lexical-evidence-the-vector-legs-precondition.md) | Make lexical evidence the vector leg's precondition, and refuse every similarity floor | Accepted |
| [0026](0026-pack-the-vectors-into-a-memory-mapped-matrix.md) | Pack the vectors into a memory-mapped matrix, and keep the SQL scan as the definition | Accepted |
| [0027](0027-split-dev-from-release-and-judge-a-corpus-we-did-not-write.md) | Split dev from release, and judge a corpus we did not write | Accepted |
| [0028](0028-keep-the-vector-scan-exact.md) | Keep the vector scan exact, because every way of shortening it costs more than it saves | Accepted |
