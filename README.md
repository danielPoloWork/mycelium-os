# mycelium-os

> The knowledge compiler for AI agents

![Status](https://img.shields.io/badge/Status-v0.1.0-blue)

Part of the **Mycelium LABS** series. A
cli written in **Python 3.12+**, built and governed to an enterprise quality
bar: full CI matrix, static analysis, sanitizers, documented design decisions, and SemVer
releases.

## What it is

Compile a project's knowledge — authored Markdown plus ingested sources (PDF, DOCX,
HTML, wikis) — into a deterministic, versioned, queryable substrate, and serve it to
AI agents over CLI and MCP with citations they can trust. Mycelium OS is a knowledge
compiler and serving layer: not an agent runtime, not a RAG framework, not a chat
product (D-001). v1 targets repo-scale, local-first, single-tenant corpora of
10^2–10^5 documents (D-002).

The frozen specification is in
[`docs/specs/01_spec_mycelium.md`](docs/specs/01_spec_mycelium.md).

## Try it

```bash
mycelium init            # scaffold knowledge/, mycelium.toml, the gitignore entry
mycelium build           # compile every document into a published snapshot
mycelium search "retry policy"
mycelium show "mycelium://<doc-id>#retries/0"
mycelium doctor          # store, snapshot pointer, and lock health
```

Write Markdown under `knowledge/` and build. The first build writes a `mycelium_id` into
each document's frontmatter — that pinned identity is what makes rebuilds deterministic and
citations survive renames, so commit those files. Every read command takes `--json`, exits
0/1/2 (ok / failed / usage), and honours `NO_COLOR`.

Milestone 2 is in progress: the compiler, store, and CLI are in place; MCP serving (2.9)
and the evaluation harness (2.11) are next.

## Build, test, run

```bash
hatch build
pytest -q
```

- **Toolchain:** Hatch (PEP 517/518, pyproject.toml), pytest (+ hypothesis for property tests), ruff format (Black-compatible), ruff check + mypy --strict.
- **Supported platforms:** Linux / Windows / macOS on CPython 3.12+.
- Consumers import the public surface via: `from mycelium.sdk.types import KirDocument`.

See [`docs/development/local-build.md`](docs/development/local-build.md) for the full local
setup.

## How this project is run

| Document | Purpose |
|---|---|
| [`AGENTS.md`](AGENTS.md) | How AI agents (and humans) work in this repo — the contract. |
| [`ROADMAP.md`](ROADMAP.md) | The numbered plan and what is done. |
| [`docs/adr/`](docs/adr/) | Why it is built the way it is (Architecture Decision Records). |
| [`docs/patterns/`](docs/patterns/) | Design patterns adopted, rejected, or considered. |
| [`docs/workflow/`](docs/workflow/) | Git, documentation, release, and maintenance conventions. |
| [`CHANGELOG.md`](CHANGELOG.md) | User-visible changes per release. |
| [`SECURITY.md`](SECURITY.md) | How to report a vulnerability. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to propose and submit a change (DCO required). |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Community standards for participation. |

## Milestones

| # | Title | Status |
|---|---|---|
| 1 | Project bootstrap & CI | ✅ done |
| 2 | Walking skeleton (spec Phase 0) | 🚧 in progress |
| 3 | v0.1 — The compiler (spec Phase 1) | ⏳ planned |
| 4 | v0.2 — Ingestion (spec Phase 2) | ⏳ planned |
| 5 | v0.3 — Structure (spec Phase 3) | ⏳ planned |
| 6 | v1.0 — Stable (spec Phase 4) | ⏳ planned |
| 7 | v2.x — Team & platform (spec Phase 5; separate RFC cycle) | ⏳ planned |


## License

Apache-2.0 © 2026 Daniel Polo. See [`LICENSE`](LICENSE).
