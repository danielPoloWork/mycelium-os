# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

- **Hybrid retrieval abstains.** Lexical evidence is now the vector leg's precondition:
  when the lexical leg finds nothing, the vector leg is withheld and hybrid returns an
  empty result with a note saying why, instead of serving the 50 nearest neighbours of a
  question the corpus cannot answer (ADR-0017 measured hybrid answering all four judged
  unanswerable cases; it now abstains on all four, with every answerable metric
  byte-identical). The guarantee is abstention parity with the G4-gated lexical baseline —
  by construction, on any corpus, with no constant to calibrate. Every similarity floor
  and score-gap rule was measured again and refused: eight near-domain unanswerable probes
  score inside the answerable band, so a floor separates "alien" from "everything else",
  not "unanswerable" from "answerable" (ADR-0025). Two side effects ship with it: the
  empty query no longer returns results under hybrid, and an abstained query pays no
  embedding latency.

- **`[retrieval] include_candidate = false` is honoured**: a deployment can serve
  `verified` and `evidence` documents and withhold `candidate` ones. It was refused by
  name until now, because the store's filter held one value per vocabulary and this needs
  the complement of one. Both vocabulary filters are now sets applied in SQL before
  ranking, the policy is enforced at the single seam the CLI, the MCP server and the
  evaluation harness share, and every query answered under it carries a note saying so —
  a smaller answer than the corpus could give should say why. Asking for exactly what the
  policy refuses returns an empty result with that note rather than an error. The default
  is unchanged: a candidate is labelled, not hidden (D-021, ADR-0024).

- **`[chunking] target_tokens` steers chunk size.** The packer closes a prose run at the
  first paragraph boundary after the run reaches the target, and still never crosses
  `max_tokens`; until now it filled toward the ceiling and the target did nothing at all
  (ADR-0014 said so in as many words). Editing either number now recompiles every
  document, because the chunk build key carries both. **The default is unchanged**: an
  unset target means the ceiling, so an existing repository compiles byte-identical output
  — the determinism golden re-blessed with a one-field diff. The evaluation is why:
  sweeping the target from 150 to 800 leaves every slice identical from 500 up, and below
  it the only slice that moves is `relationship`, down 6.1 %. A target of 300 does buy
  11 % fewer tokens per agent-task answer at an unchanged success rate, which ADR-0023
  records as an open trade rather than a default.

- **The evaluation gates run in CI** (`eval / gates G1-G6`). Every gate spec 04 §7.3
  names is now accounted for: G1 and G4 as before, G3 against a baseline committed to the
  repository (`mycelium eval --bless` writes it), G5 against the 150 ms query budget with
  the corpus size it was measured on stated beside it, G6 delegated to the compiler gate
  that owns it, and G7 explained. A gate table with silent omissions reads as though the
  missing gates passed (ADR-0021).
- `mycelium eval --tasks`: the agent-task suite D-010 asks for — 22 judged tasks run
  through the product and through the grep loop an agent would otherwise use, scoring what
  each puts in front of a model and what it costs. On this repository: evidence found on
  64 % of tasks against grep's 27 %, at half the context and a tenth of the latency. It
  reports rather than gates, and ADR-0022 states plainly what a measurement without a
  model in the loop cannot tell you.
- `[project] exclude` — glob patterns naming the Markdown in a tree that is not
  documentation (test fixtures, vendored samples, generated reports). Patterns match a
  document's path, any ancestor directory, or its file name; `*` stays within one segment
  and `**` spans them. `.mycelium/` and `export/` need no pattern: the compiler never
  reads what it writes.
- Injection resistance is now a tested property against a corpus that carries attacks
  (spec 04 §6): adversarial text comes back verbatim, inside the typed `text` field,
  labelled with its trust class, and never lifted into a field a client could read as
  protocol.

- `mycelium export [--out DIR] [--with-markdown]` writes the published snapshot as the
  JSONL interchange bundle spec 03 §9 draws — `manifest.json` verbatim, one record per
  line under `records/`, an optional verbatim copy of the compiled Markdown. The bundle
  is built to be *checked* by whoever receives it: it refuses to be assembled while the
  store and `CURRENT` disagree about which snapshot it names, its bytes are a function of
  that snapshot (declared record order, canonical JSON, LF endings — two exports are
  byte-identical), and `--with-markdown` refuses rather than shipping records from one
  build beside sources from another (ADR-0020).
- `mycelium init` gitignores `export/` alongside `.mycelium/`, which is D-006's "not
  committed by default" made true, and now appends gitignore entries individually — a
  repository scaffolded earlier gains the new entry on its next `init`.
- `mycelium build --watch`: rebuild whenever a document or `mycelium.toml` changes, until
  Ctrl-C. A save burst is debounced into one build, the derived store is never watched
  (that loop is infinite), and a build that fails — an unparseable document, an invalid
  config, another process holding the writer lock — is reported without ending the session.
  Each rebuild is the ordinary incremental build, so a watched repository publishes exactly
  what a hand-run `mycelium build` would (spec 02 §7's "identical guarantees", ADR-0019).
  A change is *proved* before a build runs — every platform reports a build's own reads as
  events by some route (inotify emits read events; FSEvents reports a read's atime update
  as a modification), so without the check each build would trigger the next one forever.
  A session therefore publishes one snapshot per real change and none in between.
  Install the watcher with `pip install mycelium-os[watch]`.
- The authored link graph, and the two MCP tools that were waiting for it (D-014).
  `mycelium build` now derives `links_to` edges from wikilinks, embeds, and Markdown links
  between documents — everything `authored`, nothing mined — resolving them by basename,
  path, or alias per spec 03 §3.1, with `[[doc#Heading]]` targeting the section. An
  unresolvable *or ambiguous* link is a build warning naming the candidates, never a guess.
- `mycelium neighbors <path|uri|anchor> [--type T] [--depth N]` and the MCP tools
  `mycelium_neighbors` and `mycelium_explain`, completing the four-tool surface spec 05 §3
  defines. Both directions are reported — what a document cites and what cites it — and
  `mycelium_explain` returns the retrieval plan, per-leg candidate ranks, per-stage timings
  and the configuration behind them, with no passage text (ADR-0018).
- A local embedding stage and hybrid retrieval (D-013/D-009). Builds compile vectors with
  `bge-small-en-v1.5` running offline through ONNX — no API key, no account — keyed
  `(chunk_digest, model_id)` so unchanged text is never re-embedded and switching models
  adds rows instead of destroying them. Install with `pip install mycelium-os[embeddings]`;
  the model is pinned by SHA-256 and **never downloaded unless `[embedding] allow_download`
  says so**. A build without the dependency or the model publishes normally, marked
  `degraded: ["vectors"]`, with lexical search untouched; `mycelium build --require-vectors`
  turns that into a failure for pipelines that promised vectors.
- `[retrieval]` is now honoured: `profile` (`lexical` | `hybrid`), `k`, and `budget_tokens`.
  `mycelium search --hybrid` opts in per query and `--explain` reports which candidate
  generators produced each result and its rank in each.
- Gate **G2** is enforced whenever the hybrid retriever runs: it scores the lexical baseline
  on the same cases and the same snapshot, because "hybrid ≥ +5 % vs BM25-only" cannot be
  read from one number.

- `mycelium snapshots`, `mycelium rollback <id>`, and `mycelium gc` (spec 05 §1).
  Snapshots are **restorable**, not just named: every build records the state it can be
  restored from, so rollback reinstates the documents, chunks, and incremental build
  state of a published snapshot from the content-addressed cache — nothing is
  recompiled, and the restored store is verified to reproduce that snapshot's published
  artifact digests before anything is committed (ADR-0016). Measured on 30 documents:
  rollback 229 ms against a 500 ms clean rebuild.
- `mycelium gc [--keep N] [--cache-max-age DAYS] [--dry-run]` removes snapshots beyond
  retention, aged build-cache entries, orphaned CAS blobs, and staging debris. The
  served snapshot is never collected, whatever the retention; every retained snapshot
  stays restorable.
- A build now reports when its snapshot is *not* restorable — for instance after
  `.mycelium/cas/` was deleted by hand, which remains safe — marking the snapshot
  `degraded` and naming `mycelium build --clean` as the repair.
- Incremental compilation (D-008, the technical differentiator): `mycelium build` now
  recompiles only documents whose source digest, mtime, or build environment changed,
  through a content-addressed stage cache (`.mycelium/cas/` blobs indexed by build keys) —
  output is byte-identical to a from-scratch build, enforced by tests per mutation kind
  and property-tested over random edit sequences (ADR-0015). On a 200-document repository
  a single-document edit rebuilds in ~0.5 s against a ~13 s cold build.
- `mycelium build --clean`: recompile everything and consult no cache — same output,
  by construction; the escape hatch when the cache is in doubt.
- Build output (human and `--json`) now reports what was reused vs rebuilt, and
  `journal.jsonl` records per-build cache statistics (`build.published` gains
  `reused`/`rebuilt`/`removed`/`parse_hits`/`chunk_hits`).

### Changed

- Store schema is `mycelium/store/v3` (`doc_state.graph_json` at 3.4). A build that meets an
  older store recreates it in place and recompiles, as before.
- The snapshot manifest's `edges` digest is now real rather than the digest of an empty
  list, and a rollback re-resolves the graph and verifies it against that digest — so a
  restored snapshot serves the graph it published, not the newer build's (ADR-0018).
- **Retrieval stays lexical by default, and now that is a measurement rather than an
  assumption.** Hybrid gains +12.7 % nDCG@10 overall on our judged cases but regresses the
  `exact` slice by 17.8 % (the bar is −2 %) and answers every unanswerable query where
  lexical abstains, so it did not earn the default — exactly the outcome spec 04 §7.3
  prescribes. The numbers, the similarity-floor sweep that failed to restore abstention, and
  the vector leg's latency limit are all in
  [ADR-0017](docs/adr/0017-adopt-the-local-embedder-and-hybrid-retrieval.md).
- Store schema is `mycelium/store/v2` (`doc_state` at 3.1, `snapshot_state` at 3.2). A build that meets an
  older store recreates it in place and recompiles — journaled, no manual deletion
  needed (D-016 rebuild policy); read-only consumers still refuse foreign stores with
  the same message as before.
- Snapshot manifest corpus digests (`artifact_digests.documents`/`.chunks`) are now
  folded from per-document artifact digests in path order instead of digesting the full
  record set, so manifest assembly is O(changed); the G6 golden was re-blessed with a
  two-line diff — every document and chunk record is byte-identical (ADR-0015).

### Deprecated

### Removed

### Fixed

- The MCP `search` tool applied a multi-valued `trust` filter *after* ranking, over-fetching
  `4 x k` candidates to make the loss less likely — which spec 04 §2 forbids, because
  post-filtering a top-k list returns fewer results than were asked for and "fewer" reads
  as "there are no more". It is now one `IN (…)` clause in SQL. No bug ledger entry: the
  under-return needs a corpus holding several trust classes, and every document this
  compiler builds is `authored` until ingestion lands at milestone 4 — the defect was
  latent, never observed (ADR-0024).

- Gate G3 compared a run against a baseline taken on a *different* corpus, so any PR
  that added documentation failed the no-regression gate without touching a retriever.
  The baseline now records a content fingerprint of the corpus it measured; G3 enforces
  when the fingerprint matches and reports — naming the deltas, and saying they are not
  comparable — when it does not
  ([BUG-0014](docs/bugs/2026/08/BUG-0014-g3-compares-incomparable-corpora.md), #38).

- The evaluation corpus included this repository's own test fixtures, so an `unanswerable`
  case was answered by a fixture and gate G4 reported 25 % where the product retriever
  now reports 0 %. The judged case was not touched — the corpus was wrong, not the case
  ([BUG-0007](docs/bugs/2026/08/BUG-0007-eval-corpus-includes-test-fixtures.md), #37).
- A build indexed the export bundle it had just written, so every build after
  `mycelium export --with-markdown` quarantined the copies as duplicate identities and
  reported a warning for a file nobody wrote
  ([BUG-0010](docs/bugs/2026/08/BUG-0010-build-indexes-its-own-export.md), #37).
- A quoted YAML key — the form PyYAML emits for `on`, `off`, `yes`, and `no` — made a
  frontmatter block parse as prose, losing the document's title, tags, and collection
  ([BUG-0011](docs/bugs/2026/08/BUG-0011-quoted-yaml-key-hides-frontmatter.md), #37).
- **A date in a non-contract frontmatter property quarantined the whole document.** YAML
  reads an unquoted `2026-08-29` as a date, which the record contract rejects, so a
  property as ordinary as Obsidian's `created:` removed its document from the index. This
  project's entire bug ledger was missing from its own corpus
  ([BUG-0012](docs/bugs/2026/08/BUG-0012-a-date-property-quarantines-the-document.md), #37).
- Links to files that exist but are not documents — `LICENSE`, a path under an excluded
  directory — were reported as unresolved, burying this repository's builds under ~150
  warnings and training the reader to skip them. Now only genuinely missing targets warn
  ([BUG-0013](docs/bugs/2026/08/BUG-0013-links-to-existing-files-warn-as-unresolved.md), #37).

- The MCP server's bare-interpreter entry point (`python -m mycelium.mcp`) wrote its
  JSON-RPC stream without configuring the encoding, so on Windows it used the console code
  page on a channel the specification defines as UTF-8. A single non-ASCII character —
  an em dash in a tool description, or any multilingual passage in a search result — made
  the client's decoder fail *inside its read loop*, so the session hung rather than
  erroring. `mycelium serve` was unaffected; both entry points now share the same stream
  setup ([BUG-0009](docs/bugs/2026/08/BUG-0009-mcp-stdio-uses-the-console-code-page.md), #34).
- A UTF-8 byte-order mark hid a document's frontmatter, because the `---` fence was no
  longer at position zero. Affected documents lost their authored metadata (title, tags,
  collection, provenance) and had the frontmatter block itself — `mycelium_id` included —
  indexed as prose, where it could come back as a search result. Windows editors emit BOMs
  routinely; found by running the real binary against files a PowerShell script had written
  ([BUG-0008](docs/bugs/2026/08/BUG-0008-bom-hides-frontmatter.md), #33).
- The release workflow built the wheel and sdist to verify the tag, then drafted the
  GitHub Release without attaching them, so v0.1.0 and v0.2.0 carried no downloadable
  artifacts while `docs/workflow/release.md` promised CI would attach them. The draft now
  carries `dist/*`, the artifact version is checked against the tag, and an existing tag
  can be re-drafted with `gh workflow run release.yml --ref main -f tag=v<X.Y.Z>`
  ([BUG-0006](docs/bugs/2026/08/BUG-0006-release-drafts-carry-no-artifacts.md), #30).

### Security

---

## Released versions

| Version | Date | Notes |
|---|---|---|
| [v0.2.0](docs/changelog/v0/v0.2.0.md) | 2026-08-30 | Milestone 2 — Walking skeleton (spec Phase 0). Release notes: [docs/releases/v0.2.0.md](docs/releases/v0.2.0.md). |
| [v0.1.0](docs/changelog/v0/v0.1.0.md) | 2026-08-29 | Milestone 1 — Project bootstrap & CI. Release notes: [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md). |
