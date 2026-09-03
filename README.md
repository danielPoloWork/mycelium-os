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
mycelium build --no-pin    # ...without writing anything into your documents
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
mycelium verify            # measure grounding on synthesized documents (gate G7)
mycelium promote doc.md    # candidate -> verified, in Git, once the gate passes
mycelium demote doc.md     # ...and back again, verification block removed
mycelium eval              # score a judged case set against the snapshot
mycelium doctor            # store, snapshot pointer, and lock health
mycelium serve             # read-only MCP server over stdio, for your agent
```

Write Markdown under `knowledge/` and build. The first build writes a `mycelium_id` into
each document's frontmatter — that pinned identity is what makes rebuilds deterministic and
citations survive renames, so commit those files. It is the only thing a build ever writes
into your tree, and `--no-pin` switches it off: the corpus is compiled, published and
searchable, your files are byte-identical afterwards, and a document with no id takes one
derived from its path so the snapshot still reproduces exactly
([ADR-0046](docs/adr/0046-derive-an-identity-rather-than-mint-one-when-a-build-may-not-write.md)).
Reach for it when you are measuring a corpus rather than authoring one. Every read command
takes `--json`, exits 0/1/2 (ok / failed / usage), and honours `NO_COLOR`.

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
name — visible loss, never silent loss. That is a claim, so it is a gate: the fixture corpus
carries a hand-written **declaration** of what each source document contains, and CI fails if
any engine's output differs from it without a recorded reason. It has to be hand-written,
because the fidelity report is computed from the parse and so cannot notice an element that
never arrived — which is exactly how a DOCX footnote was disappearing until the corpus asked
([BUG-0016](docs/bugs/2026/09/BUG-0016-docx-footnotes-vanish-unreported.md)).

**And it is measured, not asserted.** The third judged corpus is the second one *ingested* —
the same 81 documents rendered into DOCX, HTML and PDF and put back through `mycelium
ingest` — scored with the judgements already frozen for the Markdown originals, so the
document is the only thing that varies. The same 14 cases, twice: **recall does not move**,
and where structure survives — DOCX, HTML — the numbers are *identical*, not merely close.
PDF's apparent ranking gain is refused as an artefact of a target ten times the size
([ADR-0039](docs/adr/0039-measure-what-projection-costs.md)). What projection *does* cost is
the graph: 229 edges become 10, which is open as roadmap 5.7.

What v1 does *not* do is read PDF structure, and that was **re-tested rather than assumed**.
docling's ML pipeline recovers 82 % of a PDF's headings where the text layer recovers none —
and costs ~2.4 GB and three seconds a page to retrieve *worse* than the Markdown the document
came from, because it restores section boundaries while degrading what is inside them. Refused
on the measurements, with the one benefit it does deliver — citing a section instead of an
ordinal — named as the thing no metric here can score yet
([ADR-0040](docs/adr/0040-refuse-the-pdf-layout-pipeline-on-its-merits.md), roadmap 6.7). The
earlier reasoning is in [ADR-0032](docs/adr/0032-adapt-four-engines-and-pin-which-one-runs.md), and
`tools/measure_pdf_structure.py` re-runs every number.

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

### A refused file is written down, and a credential is not written out

Two things ingestion does with a document that should not simply pass through, and both are
about the same question: what happens when the answer is *not* "project it".

**A refusal is recorded, not just reported.** A source that cannot be acquired, that no
pinned parser reads, that breaches a shape guard, that the engine cannot compile, or that
loses more than its budget allows is **quarantined**: one record under
`.mycelium/quarantine/` naming the stage that refused it, the reason, and the digest of the
bytes that caused it — which are already in custody, because ingestion stores the original
before it tries to parse it. So an hour later you can still answer *which files failed, and
why*, and open them again. Ingesting a source successfully clears its record;
`mycelium ingest --forget <source>` clears one that is never coming back; `mycelium gc`
never sweeps them.

```console
$ mycelium doctor
warning: quarantine: 2 source(s) quarantined in .mycelium/quarantine:
         legacy.doc (dispatch: UnsupportedMediaTypeError), scans.pdf (budget: LossBudgetError)
```

A quarantined source is a **warning**, never a failed health check. It is the system working
as designed, and a `doctor` that goes red for one unreadable PDF is a `doctor` nobody runs.

**A credential found in an ingested source is redacted before it can spread.** An ingested
document is somebody else's file, and the lane's job is to write its content into your Git
tree and then into an index. So the content is scanned, and a match is replaced *before the
compiled form is stored*:

```markdown
export AWS_ACCESS_KEY_ID=[redacted: aws-access-key-id]
```

The verbatim bytes survive in exactly one place — the tier-1 original under `.mycelium/`,
which is gitignored and is what a citation is checked against. Everything derived from it
carries the placeholder. The rules that matched are recorded on the document
(`secret_flags`), **whether or not** redaction acted: `[ingest] redact_secrets = false`
turns off the redaction, not the record, and `mycelium doctor` says so while it is off.

The scan is eleven **structural** rules — vendor key prefixes, PEM armour, credentials in a
URL — and no entropy heuristic, because a scanner that fires on base64 images, digests and
UUIDs is one you would turn off within a week. That trade is deliberate and it has a cost:
a bare password or a home-grown token goes through unflagged. **This is not a substitute for
a secret scanner on your repository** — it is the check ingestion can make on content it is
about to write into your tree
([ADR-0037](docs/adr/0037-record-what-was-refused-and-redact-what-was-found.md)).

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
human action in Git, and the next section is the gate it has to pass.

The lane is **off unless you configure a provider**. A default install ingests entirely
offline and calls nothing; the engines are an optional install
(`pip install mycelium-os[synthesis]`). The reasoning, and the limits — coverage is per
block, and a resolving citation is not yet a *supporting* one — are in
[ADR-0035](docs/adr/0035-let-an-llm-write-only-what-a-machine-can-check.md). Whether a
citation *supports* its claim is what `mycelium verify` asks, below.

### Nothing becomes verified without a gate and a person

A candidate document is a claim, not truth. `mycelium verify` measures **gate G7** on it, and
the two halves of that gate are not the same kind of thing:

```bash
mycelium verify                    # measure every synthesized document
mycelium verify --gate             # ...and fail in CI on a measured shortfall
mycelium promote knowledge/candidate/webhook-retries.md
mycelium demote  knowledge/verified/webhook-retries.md
```

**Citation coverage** is recomputed against the corpus *as it is*, and that recomputation is
why the command exists. A candidate accepted last month cites evidence that may have been
edited, re-projected under a different heading, or deleted since — nothing at writing time
can catch that, and `verify` reports it as `citations-unresolved`.

**Sampled entailment** asks whether the cited evidence actually *says* what the claim says.
Nothing in this repository can answer that, so it asks the configured model — a deterministic
sample of claims, fail-closed, so a verdict that cannot be read counts as *not* entailed.
With no provider configured it is reported as **not measured**. Not zero, not a guess:

> There is deliberately no offline approximation. Term overlap between a claim and its
> citation would produce a number in the right range and it would be a fabricated grounding
> score, which is the one artifact this project refuses above all others.

The score written into the document is `min(coverage, entailment)`, because an average would
let perfect citations hide a failed entailment.

**Promotion is a file move, in Git, by a person.** `knowledge/candidate/` → `knowledge/verified/`
— the folder *is* the status (D-021) — and `promote` measures the gate first rather than
trusting the number already in the file. Below the gate it refuses and names the component
that blocked it. `--force` is your override, and it is written into the document:

```yaml
verified_by: 'Daniel Polo (forced: entailment-not-measured)'
verified_at: 2026-09-01
grounding: 1.0
```

so the override lives in the diff rather than in someone's terminal. `demote` moves a document
back and *removes* that block — a demoted document is not badly grounded, it is no longer
vouched for.

Two more things worth knowing before you rely on the number. `[verification] auto_promote`
exists and is **off**: with it on, a document clearing both components is promoted for you.
And with `[verification] model_id` unset, the model that wrote the document is the model that
judges it — a real bias, so the report, the document and the CLI all say `self-judged` rather
than averaging it away. The full reasoning is in
[ADR-0036](docs/adr/0036-measure-what-can-be-measured-and-let-a-human-outrank-the-gate.md).

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
The evaluation now spans three corpora, two of them documentation this project did not
write, with a frozen dev/release split gating CI. The five stable contracts freeze at 1.0.

The honest part of that paragraph is what is missing from it: on the second corpus a plain
`grep` loop still ranks better than we do, and roadmap 4.8 is open a second time because of
it. Ten candidate fixes have been measured and all ten refused
([ADR-0031](docs/adr/0031-refuse-three-rerankings.md),
[ADR-0041](docs/adr/0041-bound-the-section-unit-and-refuse-six-more.md)) — including one that
*passed* the release gate and was refused anyway, because the dev set the gate does not read
showed it returning a 14-token lead-in in place of the paragraph that answered. Beating that
incumbent is not the hard part: three of the ten strategies do. Beating it without paying for
it on the corpus we already win is, and the ceiling of the whole family — with per-case
foresight no planner can have — is 3 % above grep. The evidence re-runs with
`python tools/measure_ranking.py --release --oracle`.

What did move the number was the *unit*, not the ranking. `[chunking] pack_atomic` lets a code
block share a chunk with the prose it belongs to instead of ending it, which is worth **+61 %**
on that corpus (0.280 → 0.451, against grep's 0.471) with no slice regressed. It ships
**off**, because moving a chunk boundary deletes a judged anchor and five cases must be
re-anchored before the default can flip — roadmap 4.12 and 4.15, deliberately separate changes
([ADR-0042](docs/adr/0042-let-an-atomic-block-share-its-chunk.md)).

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
