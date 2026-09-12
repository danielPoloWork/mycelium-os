# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Changed

- **`tools/measure_projection_cost.py` reports per case, and names any case that scores
  above its own source** (roadmap 5.26, [ADR-0097](docs/adr/0097-a-twin-case-that-outscores-its-source-is-the-defect-not-the-fall.md)).
  The twin corpus exists to measure what projection costs retrieval, and the comparison was
  reported per format only — so a case scoring *higher* on the ingested copy than on the
  Markdown it was projected from, which cannot be a real result, was invisible. Three release
  cases were doing it, all PDFs, and together they are the whole of that format's apparent
  ranking gain. No threshold and no gate: the block prints every shared case, widest gap
  first, and says which ones are above their source.

- **The symbol leg is on by default** (roadmap 5.25, [ADR-0096](docs/adr/0096-write-the-span-back-and-pin-the-arm-that-judges-it.md), amending
  [ADR-0080](docs/adr/0080-look-a-name-up-exactly-and-report-that-the-table-points-at-naming-sites.md)). Spec 04 §3's exact
  lookup in the `symbols` table has been built and switched off since roadmap 5.9, because its
  own ablation refused it three times. With the ingested corpus's command namings restored
  (below) it fires on all four of that corpus's judged `symbol` cases where it could fire on
  none, and clears the bar on a **held-out** set — `uv-ingested/release`, +5.6 % on the slice
  and +0.9 % overall, no set regressing. The flag follows the measurement, which is the rule
  `tools/measure_symbol_leg.py --check` enforces in both directions. The gain is narrow and
  stated as such: `ours/*` and `uv/release` are byte-identical with the leg on, so what it
  demonstrably does is compensate for what ingestion costs. Turn it off with
  `[retrieval] symbol_lookup = false`.

### Fixed

- **An ingested document now keeps the code spans that name a command** (roadmap 5.25,
  [ADR-0096](docs/adr/0096-write-the-span-back-and-pin-the-arm-that-judges-it.md)). The evidence projector wrote a paragraph's text flattened, so the
  backticks an HTML source puts around `uv cache prune --ci` never reached
  `knowledge/evidence/` — and a command is minted only where the corpus *names* it as code,
  so the ingested twin held **11** commands against its Markdown original's 69. The docling
  adapter now records an inline group's code runs as `KirNode.spans` and the projector writes
  them back the way it writes a link back, admitting only the spans the compiler reads back
  as exactly the words the block already held: **1 217 of 1 289**, with 66 refused for sitting
  inside a link label and 6 because they would have moved the text. Commands minted:
  **11 → 59**. No chunk changed its text, no anchor moved, and no judged case was re-carried
  differently. HTML only: docling's DOCX backend reports a run's formatting without a
  monospace flag and a PDF text layer never had one, so those two lanes are reported rather
  than guessed at.

- **An ablation's control arm no longer inherits the shipped defaults** (roadmap 5.25,
  [ADR-0096](docs/adr/0096-write-the-span-back-and-pin-the-arm-that-judges-it.md)). Both the symbol and graph ablations scored their control with
  `RetrievalConfig()` — the shipped product — so the moment a leg earned its default the
  control acquired the leg under test and the measurement went to zero. The guard could
  accept only one of the two answers it exists to choose between. A `lexical` retriever pins
  every optional leg off and is the control for both; byte-identical while a leg ships off,
  which is why no historical ablation number moves.

- **The third judged corpus was rendered by a Markdown dialect it is not written in** (roadmap 5.24,
  [ADR-0095](docs/adr/0095-read-the-corpus-in-the-dialect-it-is-written-in.md), [BUG-0025](docs/bugs/2026/09/BUG-0025-the-corpus-renderer-reads-a-dialect-the-corpus-is-not-written-in.md)). `tools/build_ingested_corpus.py` rendered the
  vendored `uv` documentation with `pandoc --from markdown`, pandoc's own dialect, which spells a
  fenced block's attributes in braces and rejects mkdocs-material's bare
  ```` ```toml title="pyproject.toml" ````. It read each such opening fence as prose, so the
  *closing* fence opened a block instead of shutting one and every boundary after it inverted:
  headings, prose and links fell inside code blocks. Measured across the 81 documents, the
  committed renderings had lost **127 headings and fabricated 59, across 21 of them**; under `gfm`
  it is 0 and 0. The corpus is re-rendered, re-ingested, its judged anchors re-carried and both
  baselines re-blessed — no document changed format or parser, and nothing was re-judged. The
  reported lead over the `grep` incumbent **narrows, +0.045 → +0.038**, because the repair gives
  the incumbent more than it gives us. A new pre-render guard refuses to render any corpus whose
  headings do not survive the configured reader, so the dialect cannot drift back silently.
  Affects the evaluation corpus only; no product behaviour changes.

### Added

- **A command the corpus both demonstrates and names is a symbol** (roadmap 5.23, [ADR-0094](docs/adr/0094-mint-a-command-the-corpus-demonstrates-and-names-and-report-what-promotion-can-and-cannot-reorder.md)).
  A prompt line in a console or shell fence (`$ uv tool install ruff`) demonstrates every prefix of
  its command run; a code span (`` `uv tool install` ``) or a shell-word heading names one; the
  intersection is minted as `sym:cli:uv tool install`, kind `command`, with `defined_in` at the
  first prompt line and `doc_refs` at every chunk that runs or names it. KIR nodes now carry
  their inline code spans (`KirNode.spans`) beside the unchanged text, from the Markdown and
  pandoc adapters. The planner gains a `command` rule — a command-shaped or quoted query is looked
  up whole, exactly, in the `cli` language — as a stated amendment to spec 04 §2. Measured on all
  six judged sets: the add-only leg stays byte-identical; promotion for `cli` clears the slice bar
  on both dev sets with no regression anywhere and is identical on both release sets, which is
  proposable rather than earned, so `[retrieval] symbol_lookup` still ships off and
  `SYMBOL_PROMOTE_LANGUAGES = ("cli",)` is the reading an operator gets on turning it on.
  `tools/measure_symbol_leg.py` gains `--oracle` (a perfect table's ceiling) and
  `--promote-languages`, and its verdict now requires a held-out gain for a default.

### Fixed

- **A projected paragraph that begins with a fence marker no longer turns the rest of the
  document into code** (roadmap 5.22, [ADR-0093](docs/adr/0093-escape-the-prose-that-would-open-a-block-and-report-what-that-costs.md),
  [BUG-0024](docs/bugs/2026/09/BUG-0024-prose-that-opens-a-fence-swallows-the-rest-of-a-projection.md)).
  When an upstream renderer flattens a fenced code block into prose — a DOCX whose smart
  quotes broke the fence, a PDF text layer that kept the backticks — the evidence projector
  wrote that prose verbatim and the compiler read a fence opener with no closing partner, so
  headings, prose and links to the end of the document became one code block. The projector
  now escapes the shapes that open block structure — a fence, an ATX heading, a bullet, an
  ordered marker, a quote marker, a thematic break, a setext underline — on every line of a
  projected paragraph. The escape is invisible to the index: CommonMark reads `\##` as a
  literal `##`, and the corpus carries exactly as many backslashes in its indexed text as
  before. On the vendored ingested corpus 34,461 characters come out of code blocks (−21 %)
  and the four affected projections recover their sections.

### Added

- **The congruence lint checks the amendment relation between ADRs** (roadmap 5.21,
  [ADR-0092](docs/adr/0092-leave-the-amendment-relation-in-prose-and-check-the-prose.md)).
  A later decision that changes *part* of a record which still stands is recorded in prose,
  and `consistency_lint.py` now requires that prose to be followable: the amending ADR is
  named as a link, it exists, and it mentions the record it amends. The edge vocabulary is
  **unchanged at eight types** — `amends` was considered and refused, because the relation
  attaches to a clause or a paragraph and the graph's smallest node is a section, so an edge
  could only assert that something changed while hiding what. The convention is written down
  in `docs/adr/README.md` and `docs/workflow/documentation.md`.

- **A heading now defines the name it is *about*, not only the name it *is*** (roadmap 5.19,
  [ADR-0091](docs/adr/0091-widen-the-heading-rule-and-refuse-to-guess-which-section-documents-a-name.md)).
  `## The pyproject.toml`, `## pylock.toml format` and `## manylinux_compatible enforcement`
  each define a documentation term, where before only a heading that was *exactly* an
  identifier did. The bound is the name plus one framing word, and it is measured rather than
  chosen: two is the widest setting at which none of the three evaluation corpora yields
  something that is not a name. The vendored uv corpus goes from 14 symbols to 23 and from 16
  definition sites to 29; its ingested twin from 12 to 19 and 12 to 23; this repository's own
  documentation is unchanged at 3. The change is strictly additive — `defined_in` now prefers a
  *direct* naming site (a fence, a definition-list term, a heading that is the name), so no
  existing record's `defined_in` moves — and nothing about ranking changes: the symbol leg
  still ships off and every judged case on every set is byte-identical.

### Changed

- **`Symbol.defined_in` is documented as a naming fact, and no longer implies an editorial
  one** (roadmap 5.19, [ADR-0091](docs/adr/0091-widen-the-heading-rule-and-refuse-to-guess-which-section-documents-a-name.md)).
  It names the most direct site at which the corpus defines a name — never "where the thing is
  best documented", which roadmap 5.19 measured four ways and could not compute: on the four
  sites uv has for `pyproject.toml`, prose volume, mention count and path order each pick a
  different section, and the one a judge grades relevant is the smallest and mentions the name
  least. Every site the corpus holds is in `doc_refs` instead.

- **Citation URIs carry a second query key, and a pre-0.5 client will refuse one**
  (roadmap 5.17, [ADR-0089](docs/adr/0089-put-content-identity-in-the-citation-and-make-the-grammar-extensible.md)). A parser built before this release accepted `?lines=`
  and rejected everything else, so a URI minted now — `?lines=15-19&digest=c9c0aa14b08c` —
  raises there rather than resolving. There is no way to avoid that for clients already
  shipped, which is the argument for doing it *now*: the identity rules are one of the five
  contracts that freeze at 1.0 (NFR-8), and this is the last window in which the citation
  grammar can gain a field at all. Citations minted **before** this release keep working
  unchanged, and are still reported when their passage moves.

### Added

- **An ingested document's links reach the graph** (roadmap 5.18, [ADR-0090](docs/adr/0090-project-a-sources-links-as-links-now-that-the-compiler-knows-who-asserted-them.md)). The
  projector renders a link, wikilink or embed back into the block that carried it — `[label](target)`
  around the very words the block already holds — so the compiler reads it, resolves it through
  the source tree and types it `extracted`, with the chunk it sits in as its provenance. Until now
  reference nodes were rendered by nobody (threat-model control B11), which roadmap 5.7 had already
  shown covered nothing the compiler's own rule did not; the row is restated. The block's text does
  not change, so no chunk, anchor, carried judgement or retrieval score moves. On the vendored
  ingested corpus: links reaching the compiler 30 → 560, edges 54 → 366 (293 links, 305 extracted),
  unresolved 12 → 42, all naming sources the corpus never vendored. `Projection` and the
  `mycelium ingest` report carry `references` and `references_dropped`. 67 of the 81 vendored
  projections change, the rest having no references to carry; the reproduction check and the
  carried cases are unchanged, 584 of 585 chunks keep their text, and the one that does not sits
  in a region a pre-existing defect makes code
  ([BUG-0024](docs/bugs/2026/09/BUG-0024-prose-that-opens-a-fence-swallows-the-rest-of-a-projection.md),
  roadmap 5.22) — so the ingested baseline is re-blessed for both retrievers and gate G2's
  verdict re-recorded, with the per-case account in ADR-0090.

- **A citation says what it was minted against, not only where** (roadmap 5.17,
  [ADR-0089](docs/adr/0089-put-content-identity-in-the-citation-and-make-the-grammar-extensible.md)).
  Every `mycelium://` URI now carries `&digest=<hex>` beside `?lines=a-b` — twelve
  characters of the cited passage's own content digest — and `mycelium_fetch` and
  `mycelium show` check the two independently. The `stale` block gains a `kind`:
  `moved` means the same words at a new position, so update the URI; `rewritten` means
  different words at the same position, so re-read before re-quoting;
  `moved_and_rewritten` means both. That closes the one drift a line range could not
  see — a passage rewritten without changing length — and it also lets a harmless move
  be reported as harmless, which position alone could never promise.

  **An unrecognised query key in a citation URI is now ignored rather than refused.**
  That is the change that made the rest possible: the parser accepted only `lines=`, so
  the grammar could not grow without every earlier client rejecting the whole URI —
  anchor and all. A malformed `lines=` is still an error, and an unreadable `digest=` is
  treated as absent evidence rather than a failure.

- **An unlabelled paste can be segmented by a model** (roadmap 5.16,
  [ADR-0088](docs/adr/0088-let-a-model-propose-line-numbers-and-slice-the-paste-ourselves.md)).
  `[chats] segmenter = "llm"` lets the provider named in `[synthesis]` propose turn
  boundaries for the one input the deterministic readers keep whole: a paste with no
  `You said:` labels, which until now became a single fragment with no message anchors
  at all. Off by default; with no provider configured the paste is archived exactly as
  before, and the import says so.

  **The model returns line numbers, never content.** A proposal is a list of
  `{line, role}` boundaries and the segments are sliced out of your own text, so
  *content stays verbatim* is a property of the shape rather than a promise checked
  afterwards — a model that invented a sentence has nowhere to put it. A proposal that
  does not partition the paste exactly is quoted back once and then abandoned, leaving
  the fragment. The record is labelled `segmenter: llm/<model>`, every message carries
  `meta.segmenter`, and the fidelity report counts the turns as `inferred` — the
  structure was read, not stated.

  **What leaves the machine is redacted.** Secrets are replaced before the paste is
  sent, and a paste holding a private-key block is not sent at all: that is the one
  rule whose redaction spans lines, which would move every index the model returned.

- **A conversation can be distilled into a cited candidate document** (roadmap 5.15,
  [ADR-0087](docs/adr/0087-distil-a-conversation-at-authoring-time-and-cite-the-message.md)).
  `mycelium chats distil <conv_id>` points the existing synthesis lane at an archived
  conversation and writes doc 08 §7's summary — *decisions and outcomes* — to
  `knowledge/candidate/`, where `mycelium verify` and `mycelium promote` treat it like
  every other synthesized document. It runs on one conversation at a time and never as a
  side effect of `import`: a provider export is a year of conversations, and `mycelium
  ingest`'s automatic synthesis would spend real money on a decision nobody made. With no
  `[synthesis] provider` configured it refuses and says so; the conversation stays
  archived, projected and searchable either way.

  **What it cites is the decision.** A claim cites the *message* it came from
  (`[[conversation#12 · assistant]]`), never the conversation, because a whole-transcript
  citation hands gate G7's judge fifty turns and asks whether one sentence is in there
  somewhere. Evidence may now declare `cite_sections_only`, which stops the synthesizer's
  closed vocabulary offering the whole-document form and stops the citation contract
  accepting it — a general rule, off by default, so every document the evidence lane
  projects keeps the behaviour it had.

  D-023's **pipeline-stage** mechanism is *not* built, and the roadmap item expected it to
  be. A distillation writes tier 2 and the build never does (spec 02 §2), so it is an
  authoring-time act like every other command in the module — and the mechanism still has
  no consumer. `mycelium.synthesis` joins the module-facing surface.

- **The core declares which of it a module may import** (roadmap 5.14, [ADR-0086](docs/adr/0086-declare-the-module-facing-surface-and-refuse-to-freeze-it-from-one-consumer.md)).
  A module needs more than the plugin API: the first one reaches for configuration, module
  activation, ingestion's custody and secret doctrine, the token estimate, and the CLI's output
  conventions — five components spec 02 §10's 1.0 freeze does not cover.
  `mycelium.modules.MODULE_SURFACE` now names them with the reason each is unavoidable, and states
  that the surface within a declared component is its `__all__`. It is a **declaration, not a
  freeze**, and the distinction is the point: a change to one of the five is a compatibility event
  for every module, which is the fact the constant puts in front of whoever makes it. The in-repo
  module's acceptance gate now reads the core's list instead of restating its own, so the failure
  is addressed to the core author who moved the surface. Choosing the eventual *shape* — a
  `mycelium.sdk` façade, or a narrower contract — waits for a second module or the 1.0 freeze
  review, because an API designed from a sample of one is one the first real second user
  contradicts.

### Fixed

- **A relative hyperlink kept the ingesting machine's path separator** ([BUG-0023](docs/bugs/2026/09/BUG-0023-docling-hyperlinks-carry-the-ingesting-machines-separator.md),
  roadmap 5.18). The docling adapter turned a `Path` hyperlink into a string with `str()`, which
  on Windows spells `../x.md` as `..\x.md` — harmless while no target was written anywhere,
  and a cross-platform reproduction failure the moment one was. `as_posix()` now.

- **A callout is its own chunk** (roadmap 5.13, [ADR-0085](docs/adr/0085-let-a-callout-bound-a-chunk-rather-than-atomise-one.md)). Spec 03 §3.1 promised that
  callouts compile to *"atomic chunks like tables"* and the chunker implemented atomicity for
  tables and code blocks only, so consecutive callouts packed together as prose and a chunk could
  hold several of them. A callout now **bounds** a chunk: its blocks pack with each other and never
  with anything outside it, so two consecutive callouts are two chunks and neither merges with the
  prose beside it. An oversize callout splits at its own paragraph boundaries, which is what doc 08
  §7 asks of a chat message and what the literal promise would have forbidden — so spec 03 §3.1 is
  amended to say what is true: right about the merging, wrong about the splitting. No judged corpus
  contains a callout, so no baseline moved; gate G6's fixture gains a second, consecutive callout so
  the gate covers the rule.

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
