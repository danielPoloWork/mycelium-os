# 08 — Module Spec: `chats` (Local Chat Archive)

- **Status:** Draft
- **Decision:** D-025 in [00-verdict-and-decisions.md](00-verdict-and-decisions.md)
- **Depends on:** documents 02–05 (authority model, data model, plugin API)
- **Ships:** Phase 3, as the first contrib module and the end-to-end validation of the
  plugin API (D-023) before its 1.0 freeze

---

## 1. Purpose and positioning

Users hold significant knowledge inside conversations with chatbots (ChatGPT, Claude,
Gemini, …) — decisions, designs, research — and that knowledge evaporates: locked in
provider silos, unsearchable across tools, deletable by a vendor. The `chats` module
archives those conversations **locally**, in a normalized canonical format any chatbot
or tool can consume, and projects them into the vault so they become first-class,
citable, retrievable knowledge like every other source.

Three jobs, in order: **archive** (local custody of every conversation), **resume**
(re-enter an archived conversation in any chatbot and keep going), **port** (move a
conversation between providers via export adapters). Plugin id: `chats`; display name
"Mycelium Chats" (naming per D-026, document 05 §4.4).

**Boundary (D-004 stays intact):** this module archives *historical transcripts as
knowledge sources* — documents about the past. It is **not** agent memory: Mycelium OS
still never manages any agent's live working state. A conversation enters the archive
the way a PDF enters ingestion: as evidence with custody.

**Module discipline:** optional, activatable, and deliberately built as a real plugin —
if the D-023 extension points can't support this module cleanly, they get fixed *before*
the 1.0 API freeze. That is half the reason this module exists in the roadmap at all.

## 2. Module model

| Aspect | Decision |
|---|---|
| Activation | `[modules] enabled = ["chats"]` in `mycelium.toml`; inactive = zero runtime footprint |
| Tier | **contrib** (in-repo `contrib/chats/`) pre-1.0, because the plugin API is still moving; promoted to its own repo `mycelium-chats` after the 1.0 freeze (LABS ecosystem model) |
| Contributes (via D-023) | Parser plugins (chat formats), a CLI subcommand (`mycelium chats …`), an optional pipeline stage (synthesis distillation), file-layout ownership of `chats/` |
| MCP | **No new MCP tools in v1** — transcripts are indexed like any document, so `mycelium_search`/`_fetch` already serve them; the small-tool-surface rule holds |

## 3. Format decision (JSONL vs YAML vs Markdown)

Evaluated against the module's jobs — lossless archive, append/stream friendliness,
machine consumption by arbitrary chatbots, human readability, vault integration:

| Candidate | Verdict | Reason |
|---|---|---|
| **JSONL** | **Canonical record** | One message per line: append-only, streamable, greppable, lossless metadata, direct superset of the de-facto `{role, content}` message shape every chatbot API consumes; consistent with D-006 |
| **Markdown** | **Projection** | Human reading, Obsidian browsing, and compiler indexing — but lossy for metadata/tool-calls, so never the canonical store |
| YAML | **Rejected** | Multiline chat content is an escaping minefield; no append; slow parsing; already rejected for machine records in document 00 (§1.1) |

So: **dual representation, mirroring the system's own evidence doctrine** — JSONL as the
canonical, verbatim record; Markdown as the mechanically derived, regenerable view that
the compiler indexes. One source of truth, two shapes.

## 4. Canonical Chat Record (`*.chat.jsonl`)

Line 1 = conversation header; every following line = one message. Schema
`mycelium/chat/v0` (versioned like all records, data model conventions apply).

```json
{"kind":"conversation","schema_version":"mycelium/chat/v0","conv_id":"01J2A…","title":"Webhook retry design","project":"acme-payments","provider":"chatgpt","provider_conv_id":"abc123","started_at":"2026-07-30T21:14:00+02:00","imported_at":"2026-07-31T09:02:11+02:00","source_digest":"sha256:9c4…","structure_inferred":false,"participants":[{"role":"user","label":"daniel"},{"role":"assistant","label":"ChatGPT","model":"gpt-5"}],"tags":[]}
{"kind":"message","conv_id":"01J2A…","seq":1,"role":"user","ts":"2026-07-30T21:14:05+02:00","content":"…verbatim text…","meta":{}}
{"kind":"message","conv_id":"01J2A…","seq":2,"role":"assistant","model":"gpt-5","ts":null,"content":"…verbatim text…","meta":{"tool_calls":[{"…opaque, preserved as-is…":true}]}}
```

Invariants (the module's fidelity contract):

1. **`content` is always verbatim.** No rewriting, no cleanup, no summarization — ever.
2. **Structure may be inferred, content may not.** When roles/boundaries are guessed
   (pasted text), `structure_inferred: true` and per-message `meta.inferred: true`.
3. **Unknown provider fields are preserved**, not dropped: unmapped export data lands in
   `meta` (loss-aware custody, same doctrine as KIR `opaque`).
4. **Attachments/images** referenced in exports → CAS blobs, referenced by digest.
5. The original input (export file or pasted text) is CAS-archived (tier 1) with its
   digest in the header — the archive is re-derivable and auditable.

## 5. Archive layout

```text
chats/<project-name>/<year>/<month>/<YYYY-MM-DD>-<title-slug>-<ulid6>.chat.jsonl
```

- `project` is required (`--project` flag or `[chats] default_project`).
- Year/month from the conversation's own start timestamp when present, else import
  time; formatted in the configured timezone (`[chats] timezone`, default: local —
  import is an authoring action, so machine-local dates match user intuition; the
  record keeps full RFC 3339 timestamps regardless, so nothing is lost).
- `conv_id` (ULID) is identity; the filename is convenience. Renames don't break anything.

## 6. Import paths (v1)

| Input | Handling |
|---|---|
| Provider JSON exports (ChatGPT, Claude, generic) | Per-provider parser plugins + a generic JSON mapper (configurable field mapping) for unknown shapes |
| Markdown transcripts | Heading/blockquote-structured parsing; role markers from common conventions |
| Pasted plain text (web copy) | Deterministic heuristics for common patterns ("You said:", "ChatGPT:", blank-line turns); ambiguous segmentation → `structure_inferred: true` + fidelity warnings |
| Optional LLM-assisted segmentation | Off by default; when enabled, it may propose *boundaries/roles only* — content stays verbatim — and the record is labeled (`segmenter: llm/<model>`) in provenance |

Every import emits a fidelity report (messages recognized / inferred / unparsed-preserved),
consistent with ingestion doctrine. Unparseable residue is kept as a raw block in the
record (`kind: "fragment"`), never dropped.

**Security defaults (D-017 applies unchanged):** secret-pattern scan on import — hits are
redacted in the *projection and index* and flagged in the record (`meta.secrets: [...]`,
original preserved in CAS custody); optional full redaction mode rewrites the record too
(`[chats] redact_in_record = false` default). Everything stays local; nothing phones home.

## 7. Projection and indexing

Each conversation gets a deterministic Markdown projection (evidence lane — regenerable,
not hand-edited):

```text
knowledge/evidence/chats/<project>/<year>/<month>/<same-basename>.md
```

- Frontmatter: `mycelium_id`, `origin: ingested`, `source` (the `.chat.jsonl` path),
  `provider`, `project`, `started_at`, tags; `collection: chats/<project>`.
- Body: title + metadata line, then one Obsidian callout per message
  (`> [!user]` / `> [!assistant] <model>`), timestamps when known.
- **Chunking unit = message** (natural semantic unit); oversize messages split at
  paragraph boundaries per the standard chunker rules.
- Indexed like any document → `mycelium_search` finds chat content, filterable with
  `collection:chats/<project>`; citations resolve to conversation + message anchor.
- Optional distillation (synthesis lane, requires `[synthesis]` enabled): an LLM-authored
  summary doc ("decisions and outcomes of this conversation") written to
  `knowledge/candidate/…` with `cites` wikilinks into the transcript — subject to
  `mycelium verify`/`promote` exactly like every synthesized doc (D-020/D-021). This is
  where archived chats become *distilled* knowledge, under the existing governance.

## 8. Privacy, retention, deletion

- Local-first absolutely: no network egress in this module, ever (imports read files/stdin).
- `mycelium chats delete <conv_id>` cascades: record + CAS originals + projection removed,
  next build drops index entries; a tombstone line in the journal records the deletion.
- `[chats] retention_months` (optional): imports older than the window are excluded from
  projection/indexing (archive kept unless `--purge`).
- `trust_class: ingested`; `source_trust` per provider via `[sources]` as usual.

## 9. CLI surface (mounted subcommand, D-023)

| Command | Behavior |
|---|---|
| `mycelium chats import <file…\|-> --project X [--provider P] [--title T]` | Import export files, transcripts, or stdin paste → record + projection + fidelity report |
| `mycelium chats list [--project X] [--since …]` | Table of archived conversations |
| `mycelium chats show <conv_id>` | Render one conversation (human or `--json`) |
| `mycelium chats export <conv_id> --format jsonl\|markdown\|openai\|anthropic` | Emit portable formats for import into other chatbots (adapter set grows on demand) |
| `mycelium chats resume <conv_id> [--format F] [--tail N \| --budget-tokens T]` | Continuation package: the conversation (or its last N turns / a token-budgeted tail, oldest-first truncation) formatted as ready-to-paste context or provider messages, so the chat can continue in any chatbot from where it stopped |
| `mycelium chats delete <conv_id> [--purge]` | Cascading deletion as in §8 |

## 10. Acceptance gates (module-level, Phase 3)

1. Round-trip fixtures: provider-export fixture corpus (≥ 2 providers + pasted-text
   cases) imports with zero silent loss — every source element recognized, inferred, or
   preserved as fragment, per the fidelity report.
2. Projection determinism: same record → byte-identical Markdown (compiler golden rules).
3. Verbatim invariant property test: concatenated message content in record ⊇ source text.
4. Retrieval: chat content reachable via `mycelium_search` with correct citations into
   message anchors; `collection:` filter works.
5. Deletion cascade verified (record, CAS, projection, index).
6. **Plugin-API validation:** the module uses only public D-023 mechanisms — zero core
   patches. Any needed core change is an API fix, made before the 1.0 freeze.

## Deferred (explicit non-goals of module v1)

Browser-extension live capture (LABS APP territory); provider-API sync (OAuth surface —
revisit with demand); team sharing (Phase-5 server profile); multi-format export adapters
beyond the four listed; analytics/statistics dashboards.
