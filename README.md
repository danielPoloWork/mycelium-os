<div align="center">
  <img src="docs/assets/brand/mycelium-os-banner.png" alt="Mycelium OS" width="720">
</div>

<div align="center">

![Status](https://img.shields.io/badge/Status-v0.6.0-blue)
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

Mycelium OS compiles authored Markdown and ingested PDF/DOCX/HTML into
a deterministic, versioned, queryable substrate, and serves it over CLI and MCP. It is a
knowledge **compiler and serving layer** — not an agent runtime, not a RAG framework, not a
chat product (D-001). v1 targets repo-scale, local-first, single-tenant corpora of
10²–10⁵ documents (D-002), offline by default: no accounts, no API keys, no telemetry.

**Who it is for:** teams whose coding agents work in a repository with more documentation than
fits in a context window — ADRs, specs, runbooks, and the PDFs and wikis that govern the code —
and who want answers an agent can cite and a person can check. It runs on one machine, against
one corpus, and nothing leaves that machine unless you configure a provider to send it.

**Ten minutes to a cited answer** is the budget the specification sets (NFR-4): install below,
then follow the [tutorial](docs-site/tutorial.md). The design of record is
[RFC-0001](docs/rfc/0001-mycelium-os-v1.md); the specification is
[`docs/specs/01_spec_mycelium.md`](docs/specs/01_spec_mycelium.md).

## Install

The package is **not on PyPI yet** — the publish pipeline is built and the first upload is
the maintainer's to make (roadmap [6.11](ROADMAP.md), [ADR-0116](docs/adr/0116-publish-under-a-name-already-decided-and-let-the-artifact-be-a-defined-thing.md)).
Until then it installs from the tag, which is the same artifact CI builds:

```bash
pip install "mycelium-os @ git+https://github.com/danielPoloWork/mycelium-os@v0.6.0"
mycelium --version
```

Every extra named below — `embeddings`, `symbols`, `ingest`, `synthesis`, `watch` — goes
inside the brackets the same way:
`pip install "mycelium-os[embeddings] @ git+https://github.com/danielPoloWork/mycelium-os@v0.6.0"`.
Once the first release is published this collapses to `pip install mycelium-os[embeddings]`,
which is how the rest of this page writes it.
## Try it

```bash
mycelium init              # scaffold knowledge/, mycelium.toml, the gitignore entries
mycelium build             # compile what changed into a published snapshot
mycelium build --no-pin    # ...without writing anything into your documents
mycelium build --watch     # ...and keep doing it as you edit (needs the `watch` extra)
mycelium ingest doc.pdf    # acquire, keep, compile, project into knowledge/evidence/
                           # ...and, with an LLM configured, write a cited candidate doc
mycelium search "retry policy"          # add --hybrid for the vector leg, --explain for why
                                        # ...and --related to expand over the graph (spec 04 s2)
mycelium show "mycelium://<doc-id>#retries/0"
mycelium neighbors doc.md  # what this links to, and what links to it
mycelium snapshots         # what has been published, newest first
mycelium rollback <id>     # serve an earlier snapshot again - nothing recompiles
mycelium gc                # drop snapshots beyond retention and unreachable artifacts
mycelium export            # the snapshot as a JSONL bundle another tool can read
mycelium verify            # measure grounding on synthesized documents (gate G7)
mycelium promote doc.md    # candidate -> verified, in Git, once the gate passes
mycelium demote doc.md     # ...and back again, verification block removed
mycelium eval              # score a judged case set against the snapshot
mycelium doctor            # store, snapshot pointer, and lock health
mycelium serve             # read-only MCP server over stdio, for your agent
mycelium chats import ...  # ...with the `chats` module installed and enabled
```

Write Markdown under `knowledge/` and build. The first build writes a `mycelium_id` into
each document's frontmatter — that pinned identity is what makes rebuilds deterministic and
citations survive renames, so commit those files. It is the only thing a build ever writes
into your tree, and `--no-pin` switches it off: the corpus is compiled, published and
searchable, your files are byte-identical afterwards, and a document with no id takes one
derived from its path so the snapshot still reproduces exactly
([ADR-0046](docs/adr/0046-derive-an-identity-rather-than-mint-one-when-a-build-may-not-write.md)).
Reach for it when you are measuring a corpus rather than authoring one. A rebuild reads only
what moved: a document whose size and mtime are what the last build recorded keeps its digest
without being opened, so editing one document in a thousand rebuilds in well under two seconds
where it used to cost a read of every file
([ADR-0133](docs/adr/0133-raise-the-floor-off-the-contents-and-state-the-corpus-the-budget-holds-for.md));
`--rescan` reads everything once when you have reason to doubt that, and `mycelium doctor`
tells you when you do. Every read command takes `--json`, exits 0/1/2 (ok / failed / usage),
and honours `NO_COLOR`.

Point an MCP-capable agent at `mycelium serve` and it gets four read-only tools —
`mycelium_search`, `mycelium_fetch`, `mycelium_neighbors` (the typed graph your documents
actually contain — links, sections, citations, and the symbols they define and use), and
`mycelium_explain` (how a query was planned, why, and what each of
its words actually reached in the index) — returning
verbatim passages with `mycelium://` citations, trust class, and verification status. Every response states in words that its
content is data, never instructions: retrieved text is quoted evidence, and injection
resistance is a tested property, not a promise (D-017).
## How it compiles

```text
knowledge/**.md ─▶ parse ─▶ KIR ─▶ chunk ─▶ extract ─▶ index ─▶ snapshot ─▶ CURRENT
                    │        │       │         │          │         │
              markdown-it   thin   heading-  links +    SQLite   immutable
              + profile     AST    bounded   symbols    FTS5     manifest
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

The rest of what makes it different is a set of decisions, each measured and each written
down with its ADR. They used to fill this page; they now live in
**[How Mycelium OS works](docs/how-it-works.md)**, one section each:

- [Retrieval is lexical by default, and that was measured](docs/how-it-works.md#retrieval-is-lexical-by-default-and-that-was-measured)
- [The lexical index matches inflections, and still prefers your exact word](docs/how-it-works.md#the-lexical-index-matches-inflections-and-still-prefers-your-exact-word)
- [Your question is answered by its content words](docs/how-it-works.md#your-question-is-answered-by-its-content-words)
- [The graph is typed, and every type is derived from something you wrote](docs/how-it-works.md#the-graph-is-typed-and-every-type-is-derived-from-something-you-wrote)
- [A fence that defines something becomes a symbol, and so does a heading that names one](docs/how-it-works.md#a-fence-that-defines-something-becomes-a-symbol-and-so-does-a-heading-that-names-one)
- [A name in your query is looked up, and fifty-eight cases took the default back off](docs/how-it-works.md#a-name-in-your-query-is-looked-up-and-fifty-eight-cases-took-the-default-back-off)
- [The graph can widen a search, and it did not earn the right to](docs/how-it-works.md#the-graph-can-widen-a-search-and-it-did-not-earn-the-right-to)
- [Your query is planned, and the plan tells you which rule chose it](docs/how-it-works.md#your-query-is-planned-and-the-plan-tells-you-which-rule-chose-it)
- [Entities are declared by your vault, not guessed from your prose](docs/how-it-works.md#entities-are-declared-by-your-vault-not-guessed-from-your-prose)
- [Your chatbot conversations become citable knowledge, through a real plugin](docs/how-it-works.md#your-chatbot-conversations-become-citable-knowledge-through-a-real-plugin)
- [A citation that has gone stale tells you, instead of quietly answering](docs/how-it-works.md#a-citation-that-has-gone-stale-tells-you-instead-of-quietly-answering)
- [An ingested document joins the graph, and is never mistaken for something someone wrote](docs/how-it-works.md#an-ingested-document-joins-the-graph-and-is-never-mistaken-for-something-someone-wrote)
- [Ingestion picks its parser, and you pick which one](docs/how-it-works.md#ingestion-picks-its-parser-and-you-pick-which-one)
- [An ingested source becomes a document you can read](docs/how-it-works.md#an-ingested-source-becomes-a-document-you-can-read)
- [The original is kept, and hostile files are refused before they cost anything](docs/how-it-works.md#the-original-is-kept-and-hostile-files-are-refused-before-they-cost-anything)
- [A refused file is written down, and a credential is not written out](docs/how-it-works.md#a-refused-file-is-written-down-and-a-credential-is-not-written-out)
- [An LLM may write, but only what a machine can check](docs/how-it-works.md#an-llm-may-write-but-only-what-a-machine-can-check)
- [Nothing becomes verified without a gate and a person](docs/how-it-works.md#nothing-becomes-verified-without-a-gate-and-a-person)

## Where the evidence lives

Every claim this project makes about itself is measured, and the measurement is committed next
to the code that produced it. The benchmark reports are the marketing (spec 06 §4), including
the ones that say a budget is missed.

| Question | Where it is answered |
|---|---|
| Does it retrieve better than an agent's own `grep`? | [`eval/`](eval/README.md) — judged case sets over three corpora, two of them documentation this project did not write; `mycelium eval --against grep` re-runs the comparison, and CI gates on it |
| Does it hold what an agent needs, at what context cost? | the agent-task suite in the same directory, run by `mycelium eval --tasks` |
| How fast is it, and on what machine? | [`docs/benchmarks/`](docs/benchmarks/README.md) — one report per scenario, each with its run manifest |
| What are the numbers for this release? | the release notes under [`docs/releases/`](docs/releases/README.md) |
| Why is it built this way, and what was refused? | [`docs/adr/`](docs/adr/README.md) — one decision record each, with the arithmetic |
| What stays stable, and how does a change to it happen? | [`docs/compatibility.md`](docs/compatibility.md) |

## Status

Pre-1.0 and milestone-driven. **v0.6.0** closed Milestone 6: the five stable contracts are
frozen behind goldens and the [1.0 compatibility promise](docs/compatibility.md) is published.
Milestone 7 leads to **v1.0.0**. What is not done is said plainly: the package is **not on a
public index yet**, so the external-adoption gate is carried by name rather than waived
([ADR-0138](docs/adr/0138-recut-the-adoption-gates-onto-acts-we-can-observe.md),
[`docs/workflow/adoption.md`](docs/workflow/adoption.md)).
| # | Title | Status |
|---|---|---|
| 1 | v0.1.0 — Project bootstrap & CI | ✅ done |
| 2 | v0.2.0 — Walking skeleton (spec Phase 0) | ✅ done |
| 3 | v0.3.0 — The compiler (spec Phase 1) | ✅ done |
| 4 | v0.4.0 — Ingestion (spec Phase 2) | ✅ done |
| 5 | v0.5.0 — Structure (spec Phase 3) | ✅ done |
| 6 | v0.6.0 — Stable (spec Phase 4) | ✅ done |
| 7 | v1.0.0 — Team & platform (spec Phase 5; separate RFC cycle) | 🚧 in progress |

The numbered plan, with what each item delivered, is [`ROADMAP.md`](ROADMAP.md).

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

## Contributing and reporting a vulnerability

Contributions are welcome through pull requests, from anyone; review and merge stay with named
maintainers. [`CONTRIBUTING.md`](CONTRIBUTING.md) says what is open to outside work and how to
get a change merged — every commit carries a DCO sign-off — and everyone taking part agrees to
the [Code of Conduct](CODE_OF_CONDUCT.md).

**Found a security problem? Do not open a public issue.** [`SECURITY.md`](SECURITY.md) says how
to report it privately and what happens next.

## How this project is run

Part of the **Mycelium LABS** series, built to an enterprise bar: full CI matrix, static
analysis, property tests, documented design decisions, SemVer releases.

| Document | Purpose |
|---|---|
| [`AGENTS.md`](AGENTS.md) | How AI agents (and humans) work in this repo — the contract. |
| [`ROADMAP.md`](ROADMAP.md) | The numbered plan and what is done. |
| [Docs site](docs-site/index.md) | Tutorial, how-to guides, the plugin-author guide, and a generated SDK reference. `uv run mkdocs serve` serves it locally; it publishes to [danielpolowork.github.io/mycelium-os](https://danielpolowork.github.io/mycelium-os/) from `main` once GitHub Pages is enabled, which is an owner setting still pending ([ADR-0127](docs/adr/0127-publish-docs-site-from-a-workflow-artifact-tracking-main.md)). |
| [Plugin cookiecutter](tools/cookiecutter-mycelium-plugin/) | Generates a `Connector`, `Parser` or `Module` plugin, checked by rendering it. |
| [`docs/adr/`](docs/adr/) | Why it is built the way it is (Architecture Decision Records). |
| [`docs/rfc/`](docs/rfc/) | Design of record, reviewed and approved before code. |
| [`docs/patterns/`](docs/patterns/) | Design patterns adopted, rejected, or considered. |
| [`docs/how-it-works.md`](docs/how-it-works.md) | Every design decision a user meets, with its measurement and its ADR. |
| [`docs/workflow/`](docs/workflow/) | Git, documentation, release, and maintenance conventions. |
| [`docs/compatibility.md`](docs/compatibility.md) | What stays stable, from which version, and how a change to it is made. |
| [`docs/security/`](docs/security/) | The threat model, the tests that hold each of its boundaries, and the registers of what each review found. |
| [`docs/benchmarks/`](docs/benchmarks/) | Performance reports, each with the run manifest and the machine it was taken on — including the three budgets this project currently misses. |
| [`docs/journal/`](docs/journal/) | Dated session checkpoints — how the work actually went. |
| [`CHANGELOG.md`](CHANGELOG.md) | User-visible changes per release. |
| [`SECURITY.md`](SECURITY.md) | How to report a vulnerability. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to propose and submit a change (DCO required). |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Community standards for participation. |

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

## License

Apache-2.0 © 2026 Daniel Polo. See [`LICENSE`](LICENSE).
Brand assets: [`docs/assets/brand/`](docs/assets/brand/README.md).
