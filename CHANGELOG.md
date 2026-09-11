# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Fixed

- **A build-side table no longer stales gate G2's verdict** (roadmap 5.12, [ADR-0084](docs/adr/0084-fingerprint-the-index-a-ranking-reads-not-the-store-it-lives-in.md)).
  `retrieval_identity()` dates the recorded verdict, and its `fts_schema` field held the whole
  store's schema version — so adding `entities` (roadmap 5.4), a table no query reads, staled a
  *retrieval* verdict and turned a schema change into a re-record only a machine with the
  embedding model could finish (CI has none, by design). The field now holds the `chunks_fts`
  statement itself, normalised, which is what BM25 can actually see. The store's version was
  strictly coarser, so this removes false positives without creating false negatives: both past
  changes to that table still move it, and a test mutates the statement four ways to show it.
  The shipped ranking is unchanged.

### Added

- **The query path has a planner, and `explain` says which rule chose the plan** (roadmap 5.11,
  [ADR-0083](docs/adr/0083-route-the-query-and-report-that-routing-cannot-save-a-lost-ablation.md)). Spec 04 §2 has asked since the specification was frozen for *a small,
  deterministic, logged rule set* whose chosen plan and matched rule appear in every response that
  explains itself; what the field called `plan` held was the name of the configured profile.
  `mycelium.planner` classifies a query — identifier-like token or quoted phrase, relationship
  phrasing, or a natural-language question — and the two derived legs now need both permissions:
  the configuration's flag, and the plan's. **The plan narrows and never widens**, so a regex
  cannot switch on a leg three measured gates decided to ship off. `mycelium search --related` and
  `mycelium_search`'s `related: true` are spec 04 §2's caller signal: they enable graph expansion
  for that one call, the way `--hybrid` enables the vector leg. Routing does **not** change either
  ablation's verdict and cannot — routing by the judged slice itself reproduces the unrouted
  `relationship` numbers exactly, on all six sets — but it cuts what an operator pays for turning
  expansion on from 0.0–4.1 % overall to 0.0 %. The shipped ranking is unchanged: both legs are
  still off by default, and no baseline moved.

- **A document can declare what it replaces** (roadmap 5.10, [ADR-0082](docs/adr/0082-open-the-frontmatter-contract-by-one-key-and-make-the-drift-unlandable.md)).
  The frontmatter contract gains one human-owned key — `supersedes: [old-note.md]` —
  which compiles to the `supersedes` edge D-014's vocabulary promised and nothing could
  emit: no folder says a document has been replaced, and a Markdown link carries no
  type. Targets resolve exactly as wikilinks do, an unresolvable or ambiguous or
  self-referential declaration warns and emits nothing, and an ingested document's
  declaration is `extracted` rather than `authored`. `mycelium_neighbors` answers both
  directions — *what replaced this* and *what did this replace* — with
  `types: ["supersedes"]`. **All eight edge types now have a derivation**, and the
  determinism gate carries all eight. For a corpus that also states the relation in
  prose, `tools/consistency_lint.py` refuses a disagreement between the two.

- **A query's names can be looked up in the symbol table** (roadmap 5.9,
  [ADR-0080](docs/adr/0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md)). Spec 04 §3's third candidate generator exists: an
  identifier-like token in a query (`RetryPolicy`, `uv.lock`, `mycelium_neighbors`) is
  looked up **exactly** in the `symbols` table and the passages that define it join the
  ranking, labelled `defines <symbol id>` by `mycelium search --explain`. It ships
  **off** — `[retrieval] symbol_lookup = false` — because its ablation lost on all six
  judged case sets, and the reason is worth more than the flag: the definition site of a
  name is a chunk that *contains* that name, so the ranking already has it, and on every
  case where the lookup fires the site is a structural listing rather than the section
  that documents the thing. `tools/measure_symbol_leg.py` runs the ablation, `--coverage`
  explains it, and CI checks the flag against it.

- **An ingested corpus is in the graph** (roadmap 5.7, [ADR-0079](docs/adr/0079-resolve-an-ingested-documents-links-through-its-source-tree-and-never-call-them-authored.md)). A link inside
  an ingested document names the tree it was acquired from — `../../concepts/resolution.md`,
  relative to wherever the source sat — while its projection landed in a flat
  `knowledge/evidence/` tree under a slugified name, so it resolved against nothing. Each
  projected document's source URI now rides in the graph state, and a link in one is
  resolved through the source tree, extension-insensitively (a page rendered to HTML keeps
  the `.md` hrefs it was written with). On the vendored ingested corpus: **29 → 54 edges**
  and **30 → 12 unresolved-link warnings**, the remaining twelve being links to sources the
  corpus never vendored, unresolved in the authored twin too. `mycelium_neighbors` answers
  on an ingested document for the first time.

- **Modules are real, and the first one archives your chatbot conversations** (roadmap 5.5,
  [ADR-0077](docs/adr/0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-what-it-could-not-reach.md)).
  `[modules] enabled = ["chats"]` now resolves against the new `mycelium.modules` entry-point
  group, and an installed module contributes a `mycelium <id> …` command group, owns the
  `[<id>]` section of `mycelium.toml`, and is refused by name when nothing provides it.
  **`mycelium-chats`** ships in `contrib/chats/` as a distribution of its own: it imports a
  ChatGPT or Claude export, a Markdown transcript, a pasted conversation or any JSON through a
  configured field mapping; keeps the original in tier-1 custody; writes a canonical
  `*.chat.jsonl` record under `chats/`; and projects each conversation into
  `knowledge/evidence/chats/` so `mycelium search` finds chat content with citations that
  resolve to a conversation *and a message*. `mycelium chats import|list|show|export|resume|delete`,
  four export formats, secret scanning, retention windows and a cascading delete. Content is
  verbatim always; structure may be inferred and says so; an unlabelled paste gets no invented
  speakers. `mycelium doctor` gains a `modules` check.

- **The optional entity stage** (roadmap 5.4, [ADR-0076](docs/adr/0076-let-the-corpus-declare-its-entities-and-refuse-to-guess-the-rest.md)). The last stage spec 02
  §4.1 draws and the last of D-014's eight edge types now exist. An entity is a name the
  corpus **declares** — a frontmatter or inline `#tag`, or an `aliases` key naming the thing
  a document is about — never one guessed from prose, and a `mentions` edge is emitted only
  where a declared name is written in a passage that did not declare it. `mycelium export`
  gains `records/entities.jsonl`, the manifest gains `counts.entities` and an `entities`
  digest, and `mycelium neighbors` reaches `ent:` nodes.

  The stage is **off by default** (`[entities] enabled`, spec 03 §6) and the default build is
  unchanged: no rows, no edges, no digest, no file. Measured before it was defaulted — with
  the stage on, this repository declares one entity (a `#NNN` placeholder in a template) and
  the vendored uv documentation declares none, because neither corpus uses tags or aliases;
  an Obsidian vault, the corpus the profile was shaped for, uses both. Turning it on costs no
  recompile: the declarations are cached whether or not it is switched on.

- **Graph expansion, measured and shipped switched off** (roadmap 5.3, [ADR-0075](docs/adr/0075-let-the-graph-propose-and-the-ranking-dispose-and-report-that-it-lost.md)).
  `[retrieval] graph_expansion` is real: with it on, retrieval walks one hop from the fused
  candidates over the typed edges, resolves the neighbouring sections, documents and symbols
  back to their chunks, ranks those with the same BM25 as everything else, and labels each one
  in `--explain` with the edge that reached it. The graph decides membership; the ranking
  decides order; expansion adds passages the ranking buried and never re-votes for one it
  already found.

  **It is off by default because spec 04 §5's ablation says so.** The bar is ≥ +3 % nDCG@10 on
  the `relationship` slice with no overall regression; across six case sets and three corpora
  the slice moved between −43.1 % and +0.0 % and every set regressed overall (−0.0 % to
  −4.1 %). It rescues the case it was filed for — `r-0018`, 0.0000 → 0.2275 — and loses six
  other relationship cases doing it. `tools/measure_graph_expansion.py` is the re-runnable
  ablation and its `--check` fails if the shipped default ever stops matching the
  measurement. Nothing about the default configuration changed, so no baseline moved.

- **Six of the eight edge types are now derived** (roadmap 5.2, [ADR-0074](docs/adr/0074-give-every-edge-type-a-derivation-or-a-reason-it-has-none.md)). A linked
  section is joined to its document by `part_of`, so a traversal that reaches a heading link carries
  on instead of stopping — 76 such dead ends on the vendored uv corpus. A document `defines` the
  symbols its fences and headings declare and `references` the ones they use, both pointing at
  `sym:` nodes, so *where is this defined* and *what uses it* are one hop each in opposite
  directions; a use becomes an edge only when the corpus defines what it names. A synthesized
  document is `derived_from` the evidence it cites, the type ADR-0018 deferred for want of a
  per-document `origin`. `defines` and `references` are the first `extracted` edges this graph has
  carried, so spec 03 §6's status discipline now governs real data. `mycelium_neighbors` and
  `mycelium neighbors` accept a symbol id as the origin and report `NOT_FOUND` for one this
  snapshot does not hold. `mentions` waits for the entity stage (5.4) and `supersedes` for a
  frontmatter field the closed contract does not have (5.10); every weight stays 1.0, because what
  the values should be is 5.3's ablation to measure.

- **Code fences and headings now define symbols** (roadmap 5.1, [ADR-0073](docs/adr/0073-take-the-grammars-word-for-a-definition-and-the-headings-for-a-name.md)). A new
  `extract` stage reads every code fence through its grammar's own tree-sitter tags query — Python,
  JavaScript, TypeScript/TSX, Rust, Go, Java, C, C++, Ruby — and qualifies each definition by its
  nesting (`sym:python:RetryPolicy.delay`); it also reads the documentation's own definition syntax:
  definition lists, and headings whose text is an identifier (`## uv.lock` defines
  `sym:doc:uv.lock`). The `symbols` table, `counts.symbols`, `artifact_digests.symbols`,
  `schema_versions.symbol` and the export bundle's `symbols.jsonl` — empty since Milestone 2 — are
  filled; each record says where the thing is defined (`path#L<line>`) and which chunks define it.
  The grammars are the new optional extra **`mycelium-os[symbols]`**: without it a build compiles and
  publishes a snapshot marked `degraded: symbols` that names the extra, `mycelium doctor` gains a
  `symbols` check listing each grammar it can load, and installing or upgrading a grammar is a build
  input the next build recompiles for. `mycelium build` reports edges and symbols beside documents
  and chunks; gate G6's fixture gains a document and its golden a `symbols` section. Nothing reads
  the table at query time yet — the retrieval leg is roadmap 5.9.

### Changed

- **`mycelium.toml` accepts a section named after an installed module** (roadmap 5.5). The
  loader is still strict — an unknown section is still refused with the list of known ones —
  but a table whose name is an installed module id is carried through to that module, which
  validates it with a schema of its own. Without this the first module could not have had a
  setting at all. A module's table participates in the config digest, so `config_digest` moves
  once for every repository and the next build recompiles through its caches.

- **`mycelium.ingest` now exports `redact_text` and `Finding`**, which existed in its
  `secrets` submodule and were not re-exported — so a module could not redact without
  reaching into an internal.

- **The determinism golden records every edge** (roadmap 5.2). It carried a count and a folded
  digest, so a change to the graph showed up as an unexplained digest move; the fixture's 18 edges
  are now listed with their type, status and provenance, which is the reviewable artifact gate G6
  exists to produce ([ADR-0012](docs/adr/0012-adopt-the-g6-determinism-gate.md)).

- **`AGENTS.md` now says what a clone contains** (roadmap 5.8). §4 draws the tree that exists —
  flat `src/mycelium/`, `eval/`, `tools/`, `.draft-specs/`, the vendored `.eados-core/` bundle and
  the Claude Code adapters — and names what is deliberately untracked and how each is regenerated;
  §13 states the owner's deviation from the EADOS default (bundle and Claude Code tree tracked,
  PR #1) instead of contradicting it three times. `.benchmarks/` is ignored, so a benchmark
  autosave no longer surfaces as untracked noise.

### Deprecated

### Removed

### Fixed

- **Ingested content can no longer forge an authored assertion** (roadmap 5.7, [ADR-0079](docs/adr/0079-resolve-an-ingested-documents-links-through-its-source-tree-and-never-call-them-authored.md)).
  The projector renders no reference nodes, which the threat model recorded as closing this
  hole — and it does, for Markdown, whose parser recognises `[[api]]` and hands back a node
  to drop. HTML, DOCX and PDF have no such syntax, so those characters are ordinary prose:
  projected verbatim, re-parsed by the compiler, and compiled into an **authored** edge.
  The same held for the entity stage, where an inline `#production` in a projected PDF
  minted an authored entity. Both are fixed at the place the assertion is made rather than
  by mangling the text: every edge and entity derived from a document whose origin is
  `ingested` is now **`extracted`**, which is what spec 03 §6 asks for. An entity a human
  also declared stays authored, with the ingested document contributing only a `doc_ref`.
  The two threat-model rows are restated to describe the control that now exists.

  Consumers should note that `status` on an edge or entity now genuinely varies: an agent
  treating `extracted` as *the corpus claims this* is reading an acquired source's
  assertion as a human's.

- **A citation whose passage has moved now says so** (roadmap 5.6, [ADR-0078](docs/adr/0078-report-a-moved-citation-rather-than-serving-it-in-silence.md)).
  `mycelium_fetch` and `mycelium show` have always minted citation URIs carrying a
  `?lines=a-b` range and have always ignored it on the way back in. They honour it now: when
  the cited range is not where that anchor sits any more, the response carries a `stale`
  block with what was cited, what is there now, the URI to cite instead, and a sentence
  telling the reader to re-read before re-quoting. The content is still returned — the
  anchor exists, and refusing to serve it would break every consumer holding a citation
  into a document being edited.

  This closes a hole found by proving the Milestone 5 exit gate. An anchor is
  `(path, heading-slug-path, ordinal)` and the ordinal is a *position*, so deleting a
  paragraph, inserting one, reordering two sections, or renaming the first of two headings
  that slugify alike all left the anchor resolving — to a different passage, in silence.
  Six citations across five refactorings, now all reported. `tests/test_stale_anchors.py`
  is the permanent proof: eleven refactorings, every citation classified, the whole outcome
  map pinned per case. A passage rewritten *in place* without changing length is still
  invisible to a positional check; that limit is stated in the tool description and filed
  as roadmap 5.17.

- **The grammar binding is pinned below 0.26.0** ([BUG-0022](docs/bugs/2026/09/BUG-0022-tree-sitter-0-26-faults-on-a-projected-fence.md), roadmap 5.2).
  `tree-sitter==0.26.0` faults with an access violation while reading one 20 KB fence of the
  vendored ingested corpus and takes the whole build process with it — not an exception, so no
  per-fence guard can catch it and the byte ceiling does not reach it. 0.25.2 reads the same bytes
  repeatedly and produces byte-identical definitions for every grammar. Anyone installing the
  `symbols` extra gets the working binding.

### Security

## Released versions

| Version | Date | Notes |
|---|---|---|
| [v0.4.0](docs/changelog/v0/v0.4.0.md) | 2026-09-09 | Milestone 4 — Ingestion (spec Phase 2). Release notes: [docs/releases/v0.4.0.md](docs/releases/v0.4.0.md). |
| [v0.3.0](docs/changelog/v0/v0.3.0.md) | 2026-08-31 | Milestone 3 — The compiler (spec Phase 1). Release notes: [docs/releases/v0.3.0.md](docs/releases/v0.3.0.md). |
| [v0.2.0](docs/changelog/v0/v0.2.0.md) | 2026-08-30 | Milestone 2 — Walking skeleton (spec Phase 0). Release notes: [docs/releases/v0.2.0.md](docs/releases/v0.2.0.md). |
| [v0.1.0](docs/changelog/v0/v0.1.0.md) | 2026-08-29 | Milestone 1 — Project bootstrap & CI. Release notes: [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md). |
