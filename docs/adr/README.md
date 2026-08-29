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
