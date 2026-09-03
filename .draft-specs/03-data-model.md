# 03 — Data Model and Schemas

- **Status:** Draft
- **Depends on:** [02-architecture.md](02-architecture.md)

All records are pydantic models exported as JSON Schema 2020-12 into `schemas/` at build
time, so non-Python consumers get machine-readable contracts without Mycelium OS becoming
polyglot (D-003). Every record carries `schema_version`. v1 migration policy: **rebuild**
(D-016).

---

## 1. Conventions

- **Hashes:** SHA-256. Text is hashed after normalization (UTF-8, NFC, LF line endings,
  trailing-whitespace stripped). JSON is hashed in canonical form (sorted keys, UTF-8,
  no insignificant whitespace, integers only where integral).
- **IDs:** ULIDs for entity identity (sortable, no coordination); digests for content
  identity. Logical identity ≠ content identity, always (adopted from `gpt-specs` §2.3).
- **Timestamps:** RFC 3339 UTC.
- **Reserved fields:** `namespace` (default `"default"`) and `trust_class` appear in every
  record now, so Phase-5 tenancy is a data backfill, not an identity migration (D-002).

## 2. Identity rules (stable contract — architecture §10)

| Thing | ID form | Stability rule |
|---|---|---|
| Document | `doc_id`: ULID | Authored MD: pinned in frontmatter (`mycelium_id`), survives renames/moves. Ingested: assigned at acquisition, tied to source identity. |
| Document content | `content_digest` | Changes on every edit; used for dirty detection. |
| Chunk (logical) | `anchor`: `<doc-path>#<heading-slug-path>/<ordinal>` e.g. `architecture.md#event-bus/2` | Survives edits that keep the heading path; ordinal is position within the section. |
| Chunk (content) | `chunk_digest` | Cache/embedding key component. |
| Symbol | `sym:<language>:<qualified-name>` | From tree-sitter (code) or definition syntax (docs). |
| Entity | `ent:<slug>` + ULID | Slug for readability; ULID for identity under renames. |
| Edge | digest of `(from, to, type, provenance_digest)` | Content-derived; edges are facts, not entities. |
| Snapshot | ULID | Immutable. |
| Citation URI | `mycelium://<doc_id>#<heading-slug-path>/<ordinal>` (+ optional `?lines=a-b`) | The public reference format returned to agents; must resolve against the pinned snapshot. Keyed by `doc_id` (not path) so citations survive folder moves — in particular `candidate/` → `verified/` promotion (D-021). Responses always include the human-readable `path` alongside the URI. |

Anchor survival is best-effort by construction (heading renamed ⇒ anchor dies): the build
validates all stored citations, and `mycelium_fetch` returns typed `ANCHOR_GONE` with the
nearest ancestor rather than silently wrong content (architecture §11).

## 3. Document record

```json
{
  "schema_version": "mycelium/document/v0",
  "doc_id": "01J1ZC8Q4R6XKQ3F0V9T8B2M7N",
  "path": "knowledge/architecture.md",
  "title": "Architecture",
  "namespace": "default",
  "collection": "core-docs",
  "tags": ["architecture", "event-bus"],
  "content_digest": "sha256:6f2a…",
  "trust_class": "authored",
  "curated": false,
  "verification_status": "verified",
  "verification": null,
  "provenance": {
    "origin": "authored",
    "source_uri": null,
    "source_digest": null,
    "source_trust": null,
    "connector": null,
    "connector_version": null,
    "synthesizer": null,
    "ingested_at": null
  },
  "fidelity_report": null,
  "secret_flags": [],
  "stats": { "tokens": 4180, "headings": 12, "chunks": 9, "links_out": 14 },
  "created_at": "2026-07-31T10:00:00Z",
  "updated_at": "2026-07-31T10:00:00Z"
}
```

- `trust_class` enum (v1): `authored` | `curated` | `ingested` | `external`. Retrieval
  exposes it on every result; ranking may weight it (document 04 §4).
- `verification_status` enum (D-021): `verified` | `candidate` | `evidence`. **Derived
  from the folder** (`knowledge/verified|candidate|evidence/`) at build time — the folder
  is the single source of status, visible in Git and Obsidian. The `verification` block
  (written into frontmatter by `mycelium promote`) carries the evidence: `verified_by`,
  `verified_at`, `grounding` score from the last `mycelium verify` run.
- For ingested docs, `provenance.origin = "ingested"`, `source_digest` points at the CAS
  blob (tier 1), and `fidelity_report` points at the report blob. `provenance.source_trust`
  (`high` | `medium` | `low` | `unknown`) is assigned per source/connector in `mycelium.toml` —
  origin trust and verification status are orthogonal and both surface in retrieval.
- For synthesized docs (D-020), `provenance.origin = "synthesized"` and
  `provenance.synthesizer` records provider, model, prompt digest, and parameters.
- Authored-Markdown frontmatter contract (the **only** machine fields allowed in
  frontmatter — no metadata dumps, rule adopted from `gpt-specs` §6.3):

```yaml
---
mycelium_id: 01J1ZC8Q4R6XKQ3F0V9T8B2M7N   # written once by `mycelium build`, never edited by hand
title: Architecture                   # human-owned; optional (H1 wins otherwise)
aliases: [Arch]                       # human-owned, optional (Obsidian-standard, feeds wikilink resolution)
tags: [architecture]                  # human-owned, optional
collection: core-docs                 # human-owned, optional
# ── stamped by `mycelium ingest` on generated docs; immutable thereafter ──
origin: synthesized                   # ingested | synthesized (absent = authored)
source: "https://docs.python.org/3/…" # source URI or path this doc derives from
source_trust: high                    # [sources] trust at ingestion time (high|medium|low|unknown)
generated_by: anthropic/claude-sonnet-5  # synthesizer identity (synthesized docs only)
# ── stamped by `mycelium verify` / `mycelium promote` ──
verified_by: daniel                   # written by `mycelium promote`, absent otherwise
verified_at: 2026-07-31               # written by `mycelium promote`
grounding: 0.97                       # written by `mycelium verify`
---
```

Frontmatter ownership rules (anti-drift): exactly three tool writers — `mycelium build`
(`mycelium_id` only), `mycelium ingest` (the provenance block, write-once), `mycelium verify`/`mycelium
promote` (the verification block); humans own title/aliases/tags/collection. There is
deliberately **no `status:` field**: `verification_status` is carried by the folder alone
(§ D-021), so a file move can never disagree with a stale field. All of these appear as
Obsidian properties, so in-vault queries like "synthesized docs not yet verified" or
"docs from low-trust sources" work out of the box (Dataview/Bases), with no Mycelium OS tooling
required.

### 3.1 Mycelium Markdown Profile v1 (Obsidian-flavored — D-022)

The authored format for everything under `knowledge/`:

| Element | Support | Compilation behavior |
|---|---|---|
| CommonMark + GFM tables | full | Standard KIR nodes |
| YAML frontmatter | full | Contract above; nothing else machine-read |
| Wikilinks `[[doc]]`, `[[doc#Heading]]`, `[[doc\|label]]` | full | Resolved (basename if unique, else path, `aliases` honored) → `links_to` edges; `[[doc#Heading]]` targets anchor-level |
| Callouts `> [!note]` | full | KIR `callout` nodes; atomic chunks like tables |
| Inline tags `#tag` | full | Merged into document tag index |
| Embeds `![[doc]]` | parsed as links | No build-time transclusion in v1 (deferred; embeds still produce `links_to` edges) |
| Dataview/templater/other plugin syntax | tolerated | Plain text — never breaks the build, never machine-interpreted |

Unresolvable wikilinks are build warnings (listed in the manifest), not errors. `.mycelium/`
is dot-prefixed precisely so the vault stays clean in Obsidian.

## 4. KIR — Knowledge Intermediate Representation (stable contract)

A thin, ordered, versioned document AST. Node kinds (v0):

`document, section, heading, paragraph, list, list_item, table, table_row, table_cell,
code_block, equation, image, link, wikilink, embed, callout, tag_ref, footnote, quote,
opaque`

```json
{
  "schema_version": "mycelium/kir/v0",
  "doc_id": "01J1ZD…",
  "source_digest": "sha256:9c41…",
  "nodes": [
    { "id": "n1", "kind": "heading", "level": 2, "text": "Event Bus",
      "parent": null, "ord": 4, "src": { "page": 3, "bbox": [72, 140, 520, 160] } },
    { "id": "n2", "kind": "paragraph", "text": "…", "parent": "n1", "ord": 5,
      "src": { "page": 3 } },
    { "id": "n3", "kind": "opaque", "media_type": "application/x-drawing",
      "blob": "sha256:aa10…", "parent": "n1", "ord": 6,
      "note": "vector drawing not representable; preserved as blob" }
  ],
  "warnings": ["table on page 7 has merged cells; represented row-major"]
}
```

Design rules: KIR adds fields by minor version, never repurposes them; `opaque` is the
lawful escape hatch (F-3); `src` locators use the smallest practical unit the connector
can provide (page/bbox, byte range, cell range, timecode). KIR is stored in CAS, not in
Git.

## 5. Chunk record

```json
{
  "schema_version": "mycelium/chunk/v0",
  "anchor": "architecture.md#event-bus/0",
  "doc_id": "01J1ZC…",
  "chunk_digest": "sha256:b7e3…",
  "heading_path": ["Architecture", "Event Bus"],
  "kir_nodes": ["n1", "n2"],
  "text": "…verbatim normalized text…",
  "tokens": 412,
  "lines": [88, 141],
  "kind": "prose",
  "namespace": "default"
}
```

Chunking policy (defaults; configurable in `mycelium.toml`): heading-bounded; target 200–800
tokens; oversize sections split at paragraph boundaries with ordinal suffixes; tables and
code blocks are never *split* (`atomic`), and since roadmap 4.15 they may **share** a chunk
with the prose around them (`[chunking] pack_atomic`, on by default — ADR-0042, ADR-0047);
a block that is alone in its section is still a `kind: "table" | "code"` chunk of its own.
No mid-sentence splits; overlap
0 by default (structure replaces overlap). Invariant: ordered chunk texts ⊇ normalized
document text (property-tested).

## 6. Symbols, edges, entities

```json
{ "schema_version": "mycelium/symbol/v0", "symbol": "sym:python:mycelium.compiler.BuildKey",
  "kind": "class", "defined_in": "src/mycelium/compiler.py#L84",
  "doc_refs": ["architecture.md#build-keys/0"], "namespace": "default" }
```

```json
{ "schema_version": "mycelium/edge/v0",
  "from": "doc:architecture.md", "to": "doc:agents.md",
  "type": "links_to", "status": "authored",
  "provenance": { "kind": "markdown_link", "anchor": "architecture.md#event-bus/1" },
  "weight": 1.0, "namespace": "default" }
```

- Edge `type` controlled vocabulary (v1, D-014): `links_to`, `defines`, `references`,
  `part_of`, `supersedes`, `derived_from`, `cites`, `mentions`. Extensible only via RFC —
  this is the anti-ontology-sprawl valve (F-9).
- Wikilinks (D-022) compile to `links_to` edges with `provenance.kind: "wikilink"`;
  heading links target anchor-level. Synthesized docs (D-020) additionally produce
  `derived_from` edges to their evidence documents and `cites` edges to the specific
  evidence anchors their statements reference — synthesis provenance is thus queryable
  in the graph, and `mycelium verify` computes grounding directly from `cites` coverage.
- Edge `status`: `authored` (explicit link/frontmatter) | `extracted` (mined by an
  extractor plugin). Extracted edges never gain `authored` status silently (adopted from
  `gpt-specs` assertion doctrine, reduced to one enum).
- Entities (optional stage, off by default in v1): `{ entity_id, slug, name, aliases,
  kind, status, doc_refs }` — same status discipline.

## 7. Snapshot manifest (stable contract)

```json
{
  "schema_version": "mycelium/manifest/v0",
  "snapshot_id": "01J1ZF…",
  "parent_id": "01J1ZE…",
  "created_at": "2026-07-31T10:04:12Z",
  "config_digest": "sha256:11ab…",
  "toolchain": { "mycelium": "0.1.0", "python": "3.12.4" },
  "schema_versions": { "document": "v0", "chunk": "v0", "kir": "v0", "edge": "v0" },
  "embedding": { "model_id": "bge-small-en-v1.5", "dim": 384, "deterministic": false,
                 "provider": "local-onnx" },
  "counts": { "documents": 412, "chunks": 3877, "symbols": 951, "edges": 2210,
              "vectors": 3877, "quarantined": 1 },
  "artifact_digests": { "documents": "sha256:…", "chunks": "sha256:…", "edges": "sha256:…" },
  "degraded": [],
  "warnings": ["1 document quarantined: sources/legacy.pdf (parser_crash)"],
  "timings_ms": { "total": 8412, "parse": 3100, "embed": 4100, "index": 900 }
}
```

## 8. SQLite layout (implementation detail — replaceable, architecture §10)

```sql
documents(doc_id PK, path, title, namespace, collection, trust_class, curated,
          content_digest, provenance_json, stats_json, updated_at)
chunks(anchor PK, doc_id→documents, chunk_digest, heading_path_json, text,
       tokens, kind, lines_json)
chunks_fts        -- FTS5(content=chunks.text, title, heading_path) BM25, field-weighted
vectors(chunk_digest, model_id, dim, vec BLOB)     -- sqlite-vec; PK(chunk_digest, model_id)
symbols(symbol PK, kind, defined_in, doc_refs_json)
edges(edge_id PK, from_id, to_id, type, status, weight, provenance_json)
build_cache(build_key PK, artifact_digest, created_at)
meta(key PK, value)                                 -- schema versions, current snapshot
```

Vectors key on `(chunk_digest, model_id)` — unchanged text never re-embeds, switching
models adds rows instead of destroying them (D-013), and A/B across embedders is free.

## 9. Export bundle (`mycelium export`) (D-006)

```text
export/<snapshot-id>/
├── manifest.json               # the snapshot manifest, verbatim
├── records/
│   ├── documents.jsonl
│   ├── chunks.jsonl
│   ├── symbols.jsonl
│   ├── edges.jsonl
│   └── entities.jsonl          # if present
└── markdown/**                 # optional --with-markdown copy of tier 2
```

One JSONL line = one record exactly as specified above. This is the interchange surface
for other tools (and the discussion's original instinct, honored in its correct place).
Embeddings export (`--with-vectors`, Parquet) is deferred until a consumer exists.

## 10. Evaluation records

```json
{ "schema_version": "mycelium/eval-case/v0", "case_id": "q-0042",
  "query": "where is the retry policy for the payments webhook defined?",
  "slices": ["fact", "symbol"],
  "relevant": [ { "anchor": "payments/webhooks.md#retries/0", "grade": 3 },
                { "anchor": "adr/007-retry-policy.md#decision/0", "grade": 2 } ],
  "answerable": true }
```

Eval-run manifests record snapshot id, config digest, retriever config, metrics, and
per-case results (document 04 §7). Runs are stored under `.mycelium/eval/` and committed to
the repo only for released benchmarks.
