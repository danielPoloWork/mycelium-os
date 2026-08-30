<div align="center">
  <img src="docs/assets/brand/mycelium-os-banner.png" alt="Mycelium OS" width="720">
</div>

<div align="center">

![Status](https://img.shields.io/badge/Status-v0.1.0-blue)
[![CI](https://github.com/danielPoloWork/mycelium-os/actions/workflows/ci.yml/badge.svg)](https://github.com/danielPoloWork/mycelium-os/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/danielPoloWork/mycelium-os?include_prereleases)](https://github.com/danielPoloWork/mycelium-os/releases)
[![License](https://img.shields.io/github/license/danielPoloWork/mycelium-os)](LICENSE)
[![Security Policy](https://img.shields.io/badge/security-policy-green)](SECURITY.md)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)

**English** (canonical) · [Italiano](docs/i18n/README.md#it) ·
[中文（简体）](docs/i18n/README.md#zh-hans) · [日本語](docs/i18n/README.md#ja) —
*translations are tracked and [pending](docs/i18n/translation-status.md)*

</div>

> **The knowledge compiler for AI agents.** Compile a repository's knowledge once; serve it
> with citations an agent can check.

Coding agents re-read the same documents every session. They have no map of what is
authoritative or superseded, cannot see past the repo boundary into the PDFs and wikis that
govern the code, and assemble context by heuristics with no citations and no way to measure
quality. Teams compensate by hand-maintaining `CLAUDE.md` and `AGENTS.md` files — knowledge
compilation *by hand*. The practice proves the need; the tooling is missing.

Mycelium OS compiles authored Markdown (and, from Milestone 4, ingested PDF/DOCX/HTML) into
a deterministic, versioned, queryable substrate, and serves it over CLI and MCP. It is a
knowledge **compiler and serving layer** — not an agent runtime, not a RAG framework, not a
chat product (D-001). v1 targets repo-scale, local-first, single-tenant corpora of
10²–10⁵ documents (D-002), offline by default: no accounts, no API keys, no telemetry.

The design of record is [RFC-0001](docs/rfc/0001-mycelium-os-v1.md); the specification is
[`docs/specs/01_spec_mycelium.md`](docs/specs/01_spec_mycelium.md).

## Try it

```bash
mycelium init              # scaffold knowledge/, mycelium.toml, the gitignore entry
mycelium build             # compile every document into a published snapshot
mycelium search "retry policy"
mycelium show "mycelium://<doc-id>#retries/0"
mycelium eval              # score a judged case set against the snapshot
mycelium doctor            # store, snapshot pointer, and lock health
mycelium serve             # read-only MCP server over stdio, for your agent
```

Write Markdown under `knowledge/` and build. The first build writes a `mycelium_id` into
each document's frontmatter — that pinned identity is what makes rebuilds deterministic and
citations survive renames, so commit those files. Every read command takes `--json`, exits
0/1/2 (ok / failed / usage), and honours `NO_COLOR`.

Point an MCP-capable agent at `mycelium serve` and it gets two read-only tools —
`mycelium_search` and `mycelium_fetch` — returning verbatim passages with `mycelium://`
citations, trust class, and verification status. Every response states in words that its
content is data, never instructions: retrieved text is quoted evidence, and injection
resistance is a tested property, not a promise (D-017).

## How it compiles

```text
knowledge/**.md ─▶ parse ─▶ KIR ─▶ chunk ─▶ index ─▶ snapshot ─▶ CURRENT
                    │        │       │        │         │
              markdown-it   thin   heading-  SQLite   immutable
              + profile     AST    bounded   FTS5     manifest
```

Every stage is a pure, typed function whose output is keyed by a build key — a digest over
the stage id, its implementation version, its input digests, the config, and the schema
version. Unchanged inputs are not recomputed, deterministic stages rebuild byte-identically
(gate G6, enforced in CI), and publication is an atomic pointer swap: readers never observe
a torn state, and an interrupted build leaves the previous snapshot untouched (D-008/D-015).

Citations key on document identity rather than path, so a `mycelium://` URI survives a file
being renamed or moved — including the `candidate/` → `verified/` promotion that records a
document as checked (D-021). A dead anchor returns a typed `ANCHOR_GONE` with the nearest
surviving ancestor, never silently wrong content.

## What makes it different

| | Retrieval-time RAG | Mycelium OS |
|---|---|---|
| **When work happens** | Every query re-chunks and re-embeds | Once, at build; queries read a compiled snapshot |
| **Rebuild cost** | Full re-index | Content-addressed and incremental — only what changed |
| **Reproducibility** | Best-effort | Byte-identical rebuilds are a tested gate (G6) |
| **Provenance** | Chunks, often unattributed | Every result carries a citation, trust class, and verification status |
| **Publication** | Index mutated in place | Immutable snapshots; rollback is a pointer swap |
| **Quality** | Asserted | Measured against a judged case set, with the agent's own `grep` as the baseline to beat (D-010) |

That last row is the honest one: the evaluation harness ships in Milestone 2, not as a
victory lap. If compiled knowledge cannot beat grep on a corpus, the harness is built to say
so.

## Inspiration & Origins

This project was directly inspired by [Andrej Karpathy](https://github.com/karpathy)'s
**[llm-wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)** — the
pattern where an LLM incrementally builds and maintains a persistent wiki of interlinked
Markdown files instead of re-deriving knowledge from raw sources at every query. The core
insight, **knowledge should be compiled, not retrieved**, is the foundation this is built on.

llm-wiki has a deliberate scope: a flat index and direct LLM navigation, elegant up to a few
hundred documents. Past that, context windows saturate and the index becomes the bottleneck.
Mycelium OS keeps the insight and changes what carries it — a content-addressed incremental
compiler, immutable snapshots, and structural retrieval over the compiled artifact — so the
knowledge base can grow without the index becoming the limit.

> Credit where it is due: none of this would exist without Karpathy's idea opening the door.

## Build, test, run

```bash
uv sync --all-extras --dev
uv run pytest -q
uv run hatch build
```

- **Toolchain:** Hatch (PEP 517/518), pytest (+ hypothesis for property tests),
  ruff format (Black-compatible), ruff check + mypy --strict.
- **Supported platforms:** Linux / Windows / macOS on CPython 3.12+.
- Consumers import the public surface via `from mycelium.sdk.types import KirDocument`;
  the plugin SDK is `mycelium.sdk`.

See [`docs/development/local-build.md`](docs/development/local-build.md) for the full local
setup.

## Status

Pre-1.0 and milestone-driven. The walking skeleton is complete: Mycelium OS compiles and
serves this repository's own documentation, rebuilds byte-identically under a CI gate, and
reports its retrieval quality against a grep baseline. Milestone 3 makes the compiler
incremental; the five stable contracts freeze at 1.0.

| # | Title | Status |
|---|---|---|
| 1 | Project bootstrap & CI | ✅ done |
| 2 | Walking skeleton (spec Phase 0) | ✅ done |
| 3 | v0.1 — The compiler (spec Phase 1) | ⏳ planned |
| 4 | v0.2 — Ingestion (spec Phase 2) | ⏳ planned |
| 5 | v0.3 — Structure (spec Phase 3) | ⏳ planned |
| 6 | v1.0 — Stable (spec Phase 4) | ⏳ planned |
| 7 | v2.x — Team & platform (spec Phase 5; separate RFC cycle) | ⏳ planned |

The numbered plan, with what each item delivered, is [`ROADMAP.md`](ROADMAP.md).

## How this project is run

Part of the **Mycelium LABS** series, built to an enterprise bar: full CI matrix, static
analysis, property tests, documented design decisions, SemVer releases.

| Document | Purpose |
|---|---|
| [`AGENTS.md`](AGENTS.md) | How AI agents (and humans) work in this repo — the contract. |
| [`ROADMAP.md`](ROADMAP.md) | The numbered plan and what is done. |
| [`docs/adr/`](docs/adr/) | Why it is built the way it is (Architecture Decision Records). |
| [`docs/rfc/`](docs/rfc/) | Design of record, reviewed and approved before code. |
| [`docs/patterns/`](docs/patterns/) | Design patterns adopted, rejected, or considered. |
| [`docs/workflow/`](docs/workflow/) | Git, documentation, release, and maintenance conventions. |
| [`docs/journal/`](docs/journal/) | Dated session checkpoints — how the work actually went. |
| [`CHANGELOG.md`](CHANGELOG.md) | User-visible changes per release. |
| [`SECURITY.md`](SECURITY.md) | How to report a vulnerability. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to propose and submit a change (DCO required). |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Community standards for participation. |

## License

Apache-2.0 © 2026 Daniel Polo. See [`LICENSE`](LICENSE).
Brand assets: [`docs/assets/brand/`](docs/assets/brand/README.md).
