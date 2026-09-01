<div align="center">
  <img src="docs/assets/brand/mycelium-os-banner.png" alt="Mycelium OS" width="720">
</div>

<div align="center">

![Status](https://img.shields.io/badge/Status-v0.3.0-blue)
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
mycelium init              # scaffold knowledge/, mycelium.toml, the gitignore entries
mycelium build             # compile what changed into a published snapshot
mycelium build --watch     # ...and keep doing it as you edit (needs the `watch` extra)
mycelium ingest doc.pdf    # acquire, keep, compile, project into knowledge/evidence/
                           # ...and, with an LLM configured, write a cited candidate doc
mycelium search "retry policy"          # add --hybrid for the vector leg, --explain for why
mycelium show "mycelium://<doc-id>#retries/0"
mycelium neighbors doc.md  # what this links to, and what links to it
mycelium snapshots         # what has been published, newest first
mycelium rollback <id>     # serve an earlier snapshot again - nothing recompiles
mycelium gc                # drop snapshots beyond retention and unreachable artifacts
mycelium export            # the snapshot as a JSONL bundle another tool can read
mycelium eval              # score a judged case set against the snapshot
mycelium doctor            # store, snapshot pointer, and lock health
mycelium serve             # read-only MCP server over stdio, for your agent
```

Write Markdown under `knowledge/` and build. The first build writes a `mycelium_id` into
each document's frontmatter — that pinned identity is what makes rebuilds deterministic and
citations survive renames, so commit those files. Every read command takes `--json`, exits
0/1/2 (ok / failed / usage), and honours `NO_COLOR`.

Point an MCP-capable agent at `mycelium serve` and it gets four read-only tools —
`mycelium_search`, `mycelium_fetch`, `mycelium_neighbors` (the graph of links your documents
actually contain), and `mycelium_explain` (how a query was planned, and why) — returning
verbatim passages with `mycelium://` citations, trust class, and verification status. Every response states in words that its
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
| **Publication** | Index mutated in place | Immutable snapshots; an earlier one can be served again without recompiling |
| **Quality** | Asserted | Measured against a judged case set, with the agent's own `grep` as the baseline to beat (D-010) |

That last row is the honest one: the evaluation harness ships in Milestone 2, not as a
victory lap. If compiled knowledge cannot beat grep on a corpus, the harness is built to say
so.

### Retrieval is lexical by default, and that was measured

Mycelium OS compiles vectors with a local embedder (no API key, no account, offline once the
model is on disk), and can fuse them with BM25 by Reciprocal Rank Fusion. **It does not do
so by default.** Gate G2 requires hybrid retrieval to earn the default — ≥ +5 % nDCG@10 with
no slice worse than −2 % — and on this repository's own judged cases it did not: +12.7 %
overall, but −17.8 % on the `exact` slice, and it answers every question the corpus cannot
answer, where lexical search correctly stays silent.

So the shipped default is `[retrieval] profile = "lexical"`. Turn hybrid on with one setting
or `mycelium search --hybrid`, and read the numbers, the sweep that failed to fix abstention,
and what has to change before it earns a default in
[ADR-0017](docs/adr/0017-adopt-the-local-embedder-and-hybrid-retrieval.md).

Embeddings are an optional install — `pip install mycelium-os[embeddings]` — and a build
without them publishes normally, marked `degraded: ["vectors"]`, with lexical search intact.
Nothing is ever downloaded unless `[embedding] allow_download` says so.

### Ingestion picks its parser, and you pick which one

Non-Markdown sources are compiled by adapters over engines that already exist — Mycelium OS
owns the representation, not the parsing research (D-007). Four ship: `markdown`
(markdown-it), `docling` (DOCX and HTML through docling's declarative backends), `pandoc`
(DOCX, HTML, ODT, EPUB, reStructuredText and LaTeX, through one sandboxed binary), and `pdf`
(the text layer, via PDFium). The proof that the boundary is real: one document rendered
into DOCX, HTML and reStructuredText reaches four different engines and comes back with the
*same* citable anchors as its Markdown original.

Which one runs is **pinned, in order**, and never guessed:

```toml
[ingest]
parsers = ["docling", "pandoc", "pdf"]   # first one declaring a format wins
```

An entry that cannot be resolved is an error naming what to install — not a quiet fall-back
to whatever else is installed, because a build has to be explainable from its manifest alone
(spec 05 §4.2). `mycelium doctor` tells you before a build does. The engines are an optional
install (`pip install mycelium-os[ingest]`, plus [pandoc](https://pandoc.org/installing.html)
for that one), and the default `parsers = ["markdown"]` needs none of them.

What an engine emits that KIR cannot model becomes an `opaque` node carrying the construct's
name — visible loss, never silent loss. What v1 does *not* do is read PDF structure: that
needs docling's ML pipeline, which wants `torch` and downloads model weights on first use,
against this project's offline default and its cross-platform determinism gate. The reasons,
measured, are in [ADR-0032](docs/adr/0032-adapt-four-engines-and-pin-which-one-runs.md); the
work is roadmap 4.9.

### An ingested source becomes a document you can read

`mycelium ingest report.pdf` acquires the file, keeps it, compiles it, and writes an
**evidence document** under `knowledge/evidence/` — Markdown, with provenance frontmatter,
which `mycelium build` then compiles like anything else you wrote. Nothing but the compiler
ever writes an index (D-020), so an ingested PDF gets chunks, citations and `ingested` trust
by the same path an authored note does.

Every projection comes with a **fidelity report**: how many of the document's elements were
represented, how many survived with their structure simplified, and how many did not survive
at all. The last number is the one `[ingest] max_failed_elements` bounds — 5 % by default —
and it is deliberately *only* that number. A budget that fired on a document which lost
nothing would teach you to raise the budget. Where something was lost, the projected document
says so where a person looks:

```markdown
> [!missing] page 3 has no text layer
```

So a PDF of scans is refused rather than projected as an empty document that claims to be
evidence — with its bytes and its report already in custody, so you can see why. Raise the
budget if you want it anyway.

### The original is kept, and hostile files are refused before they cost anything

An ingested source is stored **verbatim** under its own digest in tier-1 custody
(`.mycelium/cas/originals/`), together with the KIR compiled from it and a record of where
it came from. That is what makes a verbatim quote checkable a year later, when the source
file has moved or changed — and it is why `mycelium gc`, which sweeps every other blob under
`.mycelium/`, walks past that subtree and tells you how much it walked past. A blob that
stops matching its own digest is *reported* by `mycelium doctor`, never quietly deleted: the
build cache heals itself, evidence does not get to.

Untrusted files are bounded by **shape** before any engine reads them, because bytes are the
wrong unit. A 55 KB HTML file nested 5 000 elements deep took docling 45 seconds — at 50 000
it never finished — and made the pandoc adapter raise an uncaught `RecursionError`; a 51 KB
`.docx` declared 50 MB of contents. All three are now refused in under a tenth of a second,
by ceilings set two orders of magnitude clear of anything an honest document does. A hostile
file fails as **one document**, and its bytes are in custody before the refusal, so you can
still look at it. The committed suite that proves this lives in
[`tests/fixtures/ingest/hostile/`](tests/fixtures/ingest/hostile), generated by a script you
can read rather than shipped as opaque binaries
([ADR-0033](docs/adr/0033-keep-the-original-and-bound-the-hostile.md)).

### An LLM may write, but only what a machine can check

Ingestion is dual-lane. The **evidence lane** above always runs and is deterministic. The
**synthesis lane** additionally asks a model to write a readable document from that
evidence — and that is allowed for exactly one reason: every claim it makes has to cite the
evidence layer, and the citation is checked before the file is written (D-020).

```toml
[synthesis]
provider = "anthropic"         # naming one is the consent; without it, nothing calls out
min_citation_coverage = 1.0    # every claim-bearing block cites, or nothing is written
```

The check is the product, not the prose:

- **A citation that does not resolve fails the document.** Not a warning — prose that merely
  *looks* grounded is the most dangerous thing this project could produce.
- **A rejected draft gets one repair round-trip**, with the violations quoted back. A second
  failure writes nothing and says the evidence does not support the document.
- **Coverage is measured** per claim-bearing block and recorded, and the floor defaults to
  *every* block.

What comes out lands in `knowledge/candidate/` — the folder **is** the verification status
(D-021) — carrying `origin: synthesized` and the model that wrote it. `mycelium build`
compiles it like any other file, retrieval labels it a candidate, and its citations are
`cites` edges you can query. Nothing here can produce a `verified` document: promotion is a
human action in Git (roadmap 4.5).

The lane is **off unless you configure a provider**. A default install ingests entirely
offline and calls nothing; the engines are an optional install
(`pip install mycelium-os[synthesis]`). The reasoning, and the limits — coverage is per
block, and a resolving citation is not yet a *supporting* one — are in
[ADR-0035](docs/adr/0035-let-an-llm-write-only-what-a-machine-can-check.md).

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

Pre-1.0 and milestone-driven. **Milestone 3 is complete**: the compiler is incremental —
a single-document edit recompiles that document's chain, not the corpus, and the output is
byte-equal to a clean build by tested construction (ADR-0015) — snapshots are restorable,
watch mode rebuilds on save with a manual build's guarantees, and a local embedder ships
with hybrid retrieval *switched off*, because gate G2 said it had not earned the default.
The evaluation now spans two corpora, one of them documentation this project did not write,
with a frozen dev/release split gating CI. The five stable contracts freeze at 1.0.

The honest part of that paragraph is what is missing from it: on the second corpus a plain
`grep` loop still ranks better than we do, which is measured, diagnosed, and open as roadmap
4.8 — carried into the next milestone rather than closed to make this one look finished.
Milestone 4 brings ingestion, and has started: the connector and parser contracts are in
place with four engines behind them.

| # | Title | Status |
|---|---|---|
| 1 | Project bootstrap & CI | ✅ done |
| 2 | Walking skeleton (spec Phase 0) | ✅ done |
| 3 | v0.1 — The compiler (spec Phase 1) | ✅ done |
| 4 | v0.2 — Ingestion (spec Phase 2) | 🚧 in progress |
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
