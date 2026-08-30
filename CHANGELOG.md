# Changelog

All notable changes to `mycelium-os` are documented here, following
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning 2.0.0](https://semver.org/).

Every PR that introduces a user-visible change adds a line to `[Unreleased]` in the same
PR. A release PR moves the `[Unreleased]` entries into a new per-version file under
`docs/changelog/v<MAJOR>/v<X.Y.Z>.md` and adds an index row below.

## [Unreleased]

### Added

- `mycelium build --watch`: rebuild whenever a document or `mycelium.toml` changes, until
  Ctrl-C. A save burst is debounced into one build, the derived store is never watched
  (that loop is infinite), and a build that fails — an unparseable document, an invalid
  config, another process holding the writer lock — is reported without ending the session.
  Each rebuild is the ordinary incremental build, so a watched repository publishes exactly
  what a hand-run `mycelium build` would (spec 02 §7's "identical guarantees", ADR-0019).
  Only events that mean the content changed are accepted: on Linux, inotify also reports
  reads, so a build's own plan scan would otherwise trigger the next build forever.
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
