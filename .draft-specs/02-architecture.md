# 02 — System Architecture (v1)

- **Status:** Draft
- **Depends on:** decisions D-001…D-019 in [00-verdict-and-decisions.md](00-verdict-and-decisions.md)

This is the architecture of the system that ships in Phases 0–4: a single-language,
local-first knowledge compiler with an MCP/CLI serving layer. §10 defines the seams that
must remain stable so the Phase-5 platform (per `gpt-specs/`) can be built on top without
an identity or contract migration.

---

## 1. System context

```text
                    ┌──────────────────────────────────────────────┐
                    │                 user's repo                  │
   PDFs, DOCX,      │  knowledge/**.md      ← tier-2 truth (Git)   │
   HTML, wikis ───▶ │  sources/** (opt.)    ← tier-1 evidence      │
   (ingestion)      │  mycelium.toml             ← configuration        │
                    │  .mycelium/                ← derived store        │
                    │    (gitignored)         │                    │
                    └─────────────┬───────────┼────────────────────┘
                                  │           │
                          ┌───────▼──────┐    │ reads
                          │ mycelium compiler │────┘
                          │ (build DAG)  │ writes snapshots
                          └───────┬──────┘
                                  │ serves (read-only)
                     ┌────────────▼─────────────┐
                     │  mycelium core query library  │
                     ├──────────────┬───────────┤
                     │  MCP server  │  mycelium CLI  │
                     └──────┬───────┴─────┬─────┘
                            │             │
                     Claude Code,      humans, CI,
                     Codex, any        scripts
                     MCP client
```

One Python package. The CLI and the MCP server are thin shells over the same core
library; there is no daemon, no service mesh, no bus. Everything below `.mycelium/` is
disposable and regenerable from the repo (D-005).

## 2. Authority model (D-004)

| Tier | Content | Mutability | Storage |
|---|---|---|---|
| 1 — Evidence | Original ingested bytes (PDF, DOCX, …) + their KIR | Immutable, content-addressed | `.mycelium/cas/` (or `sources/` in Git if the user opts to track originals) |
| 2 — Authored truth | Markdown under `knowledge/` (authored directly; projected verbatim from tier 1; or LLM-synthesized from tier 1 and then verified — D-020/D-021). All in the Mycelium Markdown Profile (Obsidian-flavored, D-022) | Human-editable, Git-versioned; `verified` vs `candidate` status encoded by folder | repo |
| 3 — Derived | Chunks, indexes, vectors, edges, symbols, manifests, caches | Machine-only, disposable | `.mycelium/` |

Rules:

- Nothing in tier 3 ever writes to tiers 1–2. The compiler is a pure function
  `(tier1, tier2, config) → tier3`.
- Ingestion writes tier 2 through **two lanes** (D-020). The **evidence lane** is
  deterministic: parser → KIR → verbatim Markdown projection under `knowledge/evidence/`,
  with provenance frontmatter (source digest, connector) and a fidelity report —
  mechanically faithful by construction. The **synthesis lane** uses an LLM to author
  readable documentation from that evidence, written under `knowledge/candidate/` with
  per-statement wikilink citations into the evidence docs; it earns `knowledge/verified/`
  only through `mycelium verify` + promotion (D-021). If a human edits any projection, the
  edit wins; divergence from tier 1 is detected by hash and recorded (`curated: true`).
  Tier 1 remains available as evidence. This resolves F-2/F-3 without pretending
  round-trips exist — and makes the fidelity claim *checkable* instead of rhetorical.
- Ingestion (`mycelium ingest`) is an **authoring-time** operation: it may write tiers 1–2.
  The build (`mycelium build`) remains a pure function and never writes tiers 1–2; promotion
  and demotion are human/Git actions, never build side effects.
- Extracted semantics (entities, edges beyond explicit links) carry `status: "extracted"`
  and never masquerade as authored truth (adopted from `gpt-specs` assertion doctrine,
  reduced to one field).
- Agent memory is out of scope. Agents keep their own state; Mycelium OS serves shared knowledge.

## 3. On-disk layout

```text
project/
├── knowledge/                  # tier-2 Markdown — also a valid Obsidian vault (D-022)
│   ├── verified/**/*.md        #   authored docs + synthesized docs that passed
│   │                           #   `mycelium verify` and were promoted (D-021)
│   ├── candidate/**/*.md       #   LLM-synthesized or unreviewed docs — indexed,
│   │                           #   served with explicit `candidate` labels
│   └── evidence/**/*.md        #   verbatim projections of ingested sources —
│                               #   mechanically faithful, regenerable from tier 1
├── sources/                    # optional: tier-1 originals tracked in Git
├── mycelium.toml                    # configuration (document 05 §3)
└── .mycelium/                       # derived store — ALWAYS gitignored
    ├── store.db                # SQLite (WAL): catalog, FTS5, vectors, edges, symbols
    ├── cas/xx/<sha256>         # content-addressed blobs: originals, KIR, fidelity reports
    ├── snapshots/<ulid>.json   # immutable snapshot manifests
    ├── CURRENT                 # pointer file → published snapshot id (atomic swap)
    ├── lock                    # advisory single-writer lock (pid, host, heartbeat)
    ├── journal.jsonl           # append-only operational log (diagnostics only, F-4)
    └── eval/                   # benchmark run manifests
```

## 4. The compiler (D-008)

### 4.1 Stage DAG

```text
discover ─▶ acquire ─▶ parse ─▶ normalize ─▶ chunk ─▶ extract ─▶ embed ─▶ index ─▶ manifest
            (tier1     (KIR)    (KIR′)       (chunks)  (symbols,  (vectors) (SQLite   (snapshot)
             custody)                                   links,               tables)
                                                        entities°)
                                                        ° optional stage
```

Stage contract — every stage is a pure, typed function with:

- declared input artifact kinds and output artifact kinds;
- a **build key** = SHA-256 over canonical serialization of
  `(stage_id, implementation_version, input_digests, config_digest, schema_version)`
  (adopted from `gpt-specs` §7.2, trimmed);
- deterministic behavior, or an explicit `deterministic: false` declaration recording
  provider/model/params digests (embeddings via remote APIs; optional LLM enrichment);
- no I/O outside its declared inputs/outputs (enforced by code review + tests, not a
  sandbox — D-012 trust stance).

### 4.2 Incremental algorithm

```text
build(repo, config):
    acquire_writer_lock()
    plan   = discover(repo, config)                 # doc set + per-doc source digests
    dirty  = docs whose source digest, config slice, or stage versions changed
    removed = docs in previous manifest but not in plan
    for doc in dirty (parallel, bounded):
        for stage in topo_order:
            key = build_key(stage, doc)
            artifact = cache.get(key) or run_stage(stage, doc)   # cache = CAS + SQLite
    stage_global = rebuild global artifacts whose inputs changed  # graph closure, stats
    staging = assemble_staging_tables(unchanged ∪ rebuilt − removed)
    validate(staging)                                # schema, referential integrity,
                                                     # citation resolvability, counts
    manifest = write_snapshot_manifest(staging)
    atomically swap CURRENT → manifest.id            # temp file + rename + fsync
    gc_unreferenced(after retention window)
    release_writer_lock()
```

Guarantees:

- **Determinism:** identical `(sources, config, toolchain)` ⇒ byte-identical artifacts
  for all deterministic stages; verified by a golden rebuild test in CI (D-008).
- **Minimality:** a one-document edit rebuilds only that document's chain plus affected
  global closures. Target: < 2 s p95 (document 01 §8).
- **No content loss in chunking:** property test — the ordered concatenation of a
  document's chunks reproduces its normalized text exactly.
- **Crash safety:** an interrupted build leaves `CURRENT` untouched; staging is discarded
  on next run. Readers never observe a torn state.

### 4.3 Snapshot manifest

Immutable JSON (schema in document 03 §7): snapshot id (ULID), parent id, schema
versions, config digest, toolchain versions, embedding model identity + dimensions,
per-artifact-class counts and digests, corpus statistics, build timings, warnings,
degradation flags (e.g. `vectors: absent` when the embedder was unavailable — the build
still publishes, marked degraded, rather than failing the lexical index with it).
`mycelium rollback <id>` repoints `CURRENT`; nothing rebuilds.

## 5. Ingestion (Phase 2 scope; architecture fixed now)

```text
                                 EVIDENCE LANE (always, deterministic)
source file ─▶ Connector.acquire() ─▶ CAS blob (tier 1) + digest
            ─▶ Parser.parse()      ─▶ KIR (versioned JSON AST; document 03 §4)
            ─▶ Projector           ─▶ knowledge/evidence/**.md (verbatim, provenance
                                   │  frontmatter, fidelity report in CAS)
                                   ▼
                                 SYNTHESIS LANE (LLM; auto-on when a provider
                                 is configured — D-020)
                KIR + evidence ─▶ Synthesizer ─▶ knowledge/candidate/**.md
                                   │  (readable doc; every claim-bearing statement
                                   │   carries a wikilink citation into evidence/)
                                   ▼
                `mycelium verify` (grounding: citation coverage + sampled entailment)
                                   ▼
                `mycelium promote` ─▶ knowledge/verified/**.md   (human/Git action)
```

- Parsers are adapters over the existing ecosystem (docling first; pandoc fallback) —
  Mycelium OS owns KIR and the custody guarantees, not the parsing research (D-007).
- Unrepresentable elements become KIR `opaque` nodes pointing at source ranges; the
  fidelity report makes loss visible (F-3). A configurable loss budget can block
  projection (`[ingest] max_failed_elements`).
- Malformed/hostile files: parser failures quarantine the source (recorded, skipped,
  reported) and never abort the whole build.
- **The synthesizer writes Markdown documents only.** Chunks, JSONL, indexes, vectors,
  and edges are always produced by the deterministic compiler from those documents —
  the LLM never writes an index (D-020).
- The synthesis stage is non-deterministic by declaration: provider, model, prompt
  digest, and parameters are recorded in the document's provenance, exactly like remote
  embeddings (§4.1). Synthesized docs never silently enter `verified` (D-021).

## 6. Serving

- **Read path:** open `store.db` read-only at the snapshot pinned by `CURRENT`; queries
  never block builds (WAL) and never see partial builds (snapshot swap).
- **MCP server** (stdio, read-only by default): tools `mycelium_search`, `mycelium_fetch`,
  `mycelium_neighbors`, `mycelium_explain` — contracts in document 05 §4.
- **CLI:** same core library (`mycelium search`, `mycelium show`, …) for humans and CI.
- Every response carries: snapshot id, citations (`mycelium://doc#anchor` + line range),
  trust/provenance labels, and truncation notices. Retrieval internals in document 04.

## 7. Concurrency and consistency (D-015)

| Concern | Mechanism |
|---|---|
| One writer | `.mycelium/lock` advisory file (pid + host + heartbeat mtime); stale after N minutes → safe takeover |
| Many readers during build | SQLite WAL + staging tables; publication is a pointer swap |
| Atomic publish | write `CURRENT.tmp` → `rename()` → `fsync(dir)` (POSIX) / `ReplaceFile` (Windows) |
| Multiple agents querying concurrently | read-only connections; no coordination needed |
| Watch mode | debounced FS events → incremental builds; identical guarantees |

## 8. Security posture (D-017)

- **All source content is untrusted data** — including the user's own documents. Retrieved
  text is returned as quoted, typed evidence; Mycelium OS never interprets instructions found in
  content, and the MCP tool descriptions state that clients must treat returned content
  as data. Injection resistance is a tested property (fixture corpus, document 04 §6).
- **Read-only by default:** the MCP server exposes no mutating tools in v1. Builds are
  explicit user actions (CLI or watch mode the user started).
- **Secrets:** ingestion runs a secret-pattern scan; hits are flagged in the document
  record and excluded from indexing by default (`[ingest] redact_secrets = true`).
- **Network:** zero network calls unless configured (remote embedder, remote sources).
  The default profile builds fully offline (D-013). Telemetry: none. An opt-in,
  documented, anonymous usage ping may be proposed post-1.0 via RFC; never default-on.
- **Path safety:** connectors resolve paths within declared roots; no symlink escape.

## 9. Observability

- `journal.jsonl`: append-only structured events (build started/finished, stage timings,
  cache hit rates, quarantines, degradations) — greppable, disposable.
- `mycelium build --profile`: per-stage wall time, cache statistics, top-N slowest documents.
- `mycelium doctor`: environment, store integrity (digest spot-checks), lock state, snapshot
  chain validity.
- OpenTelemetry export is a post-1.0 optional plugin — the event names are chosen now so
  the mapping is mechanical.

## 10. Evolution seams (what must stay stable for Phase 5)

The Phase-5 platform (`gpt-specs/` blueprint: Postgres catalog, object-store CAS,
OpenSearch/Qdrant adapters, tenancy, policy pushdown, sandboxed plugins) must be
buildable **without breaking v1 users**. Therefore these five contracts are the only
things v1 is not allowed to change casually (SemVer-major otherwise):

1. **Identity rules** (document 03 §2) — IDs and anchors survive storage migration.
2. **KIR schema** (document 03 §4) — connectors written for v1 keep working.
3. **Snapshot manifest schema** (document 03 §7) — snapshots remain the serving unit at
   every scale.
4. **MCP tool contracts** (document 05 §4) — agent integrations survive the server phase.
5. **Plugin protocols** (document 05 §5) — community plugins survive backend swaps.

Everything else — SQLite, file layout, in-process execution — is an implementation
detail, deliberately replaceable, and documented as such.

## 11. Failure modes

| Failure | Behavior |
|---|---|
| Parser crash / hostile document | Quarantine document, record reason, continue build, surface in report and `mycelium doctor` |
| Embedding provider unavailable | Publish snapshot with `degraded: vectors-absent`; lexical retrieval unaffected; `mycelium build --require-vectors` inverts the policy |
| Interrupted build (kill, power) | `CURRENT` untouched; staging discarded; next build resumes from cache |
| Corrupt `store.db` | Detected by `mycelium doctor`; remedy is `mycelium build --clean` (derived world is disposable) |
| Stale lock | Heartbeat age check → explicit takeover with journal entry |
| Two writers on shared FS | Advisory lock honored by Mycelium OS processes; documented as unsupported otherwise (team-scale answer is the Phase-5 server, not file-share heroics) |
| Chunk anchor no longer resolves after doc edit | Citation validator rewrites/expires stale anchors at build time; `mycelium_fetch` on a dead anchor returns a typed `ANCHOR_GONE` error with the nearest surviving ancestor |
