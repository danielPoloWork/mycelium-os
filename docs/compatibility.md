# Compatibility

What `mycelium-os` promises to keep stable, from which version, and how a change to
any of it is made. This is the **1.0 compatibility promise** that architecture §10 and
spec 06 §Phase 4 call for. It is *published* with roadmap 6.1, in the Milestone 6 line
that ships as v0.6.0, and it *binds* at the **v1.0.0** tag: until then the pre-1.0 rule
below applies, and the suite that checks the promise runs from the day it was published
(ADR-0114).

## The five stable contracts

Spec 02 §10 names five things v1 may not change casually, because the Phase-5 platform
has to be buildable without breaking v1 users. Everything else — SQLite, the `.mycelium/`
layout, in-process execution — is an implementation detail and may change at any
release.

| # | Contract | Authority | Where it lives | Version token | Golden |
|---|---|---|---|---|---|
| 1 | **Identity rules** — content digests, ULIDs, heading slugs, chunk anchors, `mycelium://` citation URIs, the `doc:` / `sym:` / `ent:` reference forms, edge identity | spec 03 §§1–2 | `mycelium.sdk.identity`, and the string patterns in `mycelium.sdk.types` | none — append-only, for good | `identity.json` |
| 2 | **KIR schema** — `KirDocument`, `KirNode`, the node-kind vocabulary and which fields each kind carries | spec 03 §4 | `mycelium.sdk.types` | `schema_version = "mycelium/kir/v0"` | `kir.v0.json` |
| 3 | **Snapshot manifest schema** — `SnapshotManifest` and the artifact classes it reports | spec 03 §7 | `mycelium.sdk.types`, `mycelium.sdk.schema` | `schema_version = "mycelium/manifest/v0"` | `manifest.v0.json` |
| 4 | **MCP tool contracts** — the four tools' names, input schemas and output schemas, the six error codes and the fields each may carry, the notice every response carries, the protocol revisions served | spec 05 §3 | `mycelium.mcp.tools`, `mycelium.mcp.schemas`, `mycelium.mcp.errors`, `mycelium.mcp.server` | none — versioned by the package that serves it | `mcp-tools.json` |
| 5 | **Plugin protocols** — `Connector`, `Parser`, `Synthesizer`, `Module`; the transport records `PluginMeta`, `Blob`, `EvidenceDocument`, `SynthesisContext`, `Synthesis`; the two entry-point groups; the exported names of the three SDK modules | spec 05 §4 | `mycelium.sdk.protocols`, `mycelium.sdk.types`, `mycelium.sdk.identity` | `MYCELIUM_API_VERSION = 0` | `plugin-api.v0.json` |

The goldens live under [`tests/fixtures/contracts/`](../tests/fixtures/contracts/). Each is
the contract's **shape**: types, required keys, enums, patterns, bounds and defaults, with
every description and title stripped, so that a docstring edit is not a contract event
and a schema change always is.

## What "stable" means

### Until v1.0.0 — from the Milestone 6 line onward

- **A change to a stable contract is announced, never silent.** It needs an RFC under
  `docs/rfc/` (spec 06 §4), an ADR, a migration note under `[Unreleased]` in
  `CHANGELOG.md`, and the re-blessed golden in the same pull request. The compatibility
  suite makes the silent case impossible; the process makes the announced one reviewable.
- **It happens at a MINOR release only**, never at a PATCH (spec 05 §5: *"pre-1.0, minor
  may break with CHANGELOG migration notes"*).
- **An incompatible change bumps the contract's version token first** — `schema_version`
  for a record, `MYCELIUM_API_VERSION` for the protocols. The golden file is named for the
  token, so the bump renames the file and the old shape stays in the repository's history.
  An *additive* change keeps the token: `spans` joined `KirNode` at roadmap 5.23 and
  `entities` joined the manifest's counts at 5.4, both under `v0`, because a reader of the
  old shape reads the new one.

### From v1.0.0

- **Additive changes are MINOR releases** — a new optional field on a record, a new tool, a
  new optional Protocol member, a new query key on a citation URI — with the same RFC,
  ADR, migration note and re-bless as before.
- **Incompatible changes are MAJOR releases**, and no other kind of release may carry one.
  A deprecation is announced in a MINOR with a runtime warning and removed no earlier than
  the next MAJOR ([`docs/workflow/maintenance.md`](workflow/maintenance.md)).
- **The identity rules never change incompatibly at all.** Every digest, ULID, anchor and
  citation URI minted under this promise stays valid and resolves the same way in every
  later release, because a citation sitting in an agent's transcript is something no
  migration can reach. The identity golden therefore has no version token: its vectors
  may only ever be added to.

### Reader rules, and why there are two of them

- **Records refuse unknown fields.** Every record in `mycelium.sdk.types` is closed
  (`extra="forbid"`): a field a producer added without declaring it is producer drift,
  and the boundary is where it is caught (ADR-0004). KIR *"adds fields by minor version,
  never repurposes them"* (spec 03 §4) — declared evolution, not undeclared passengers.
- **Citation URIs ignore unknown query keys.** A URI travels between versions, in
  transcripts and notes that nothing can update, so the parser reads the keys it knows and
  steps over the rest (ADR-0089). A malformed *known* key is still an error.
- **Snapshots.** A newer Mycelium OS that cannot read an older snapshot must say so and
  offer `mycelium build` — rebuild-as-migration (D-016) — and never reinterpret it
  silently (spec 05 §5). Within one manifest token a newer reader loads every earlier
  manifest and KIR document: [`tests/fixtures/contracts/history/`](../tests/fixtures/contracts/history/)
  holds what a v0.5.0 build wrote, and the suite loads it.
- **Plugins.** `PluginMeta.api_min` and `api_max` declare the generations a plugin
  supports; the registry refuses one outside the range with an error naming both numbers.
  The generation bumps only when a Protocol changes in a way a plugin can observe.

## How the promise is checked

[`tests/test_contracts.py`](../tests/test_contracts.py) projects each contract to a
canonical JSON document ([`mycelium.contracts`](../src/mycelium/contracts.py)) and compares
it, section by section, with the committed golden. It also validates every tool's real
payload against its `outputSchema`, every error payload against the error schema, and loads
the v0.5.0 records with today's readers.

```bash
uv run pytest tests/test_contracts.py -q
```

A failure is one of two things: a contract changed by accident, or on purpose. For the
second:

```bash
python tools/update_contract_goldens.py
```

re-blesses the goldens and prints what a changed golden obliges you to do. The diff is
the change, and it belongs in the pull request beside the RFC and the migration note.

## What is not covered

- **The CLI.** `mycelium …` is a public surface (spec 05 §1, FR-2) under SemVer like the
  rest of the package, but not one of the five: its flags and human-readable output have
  no golden and no RFC requirement. `--json` output follows ADR-0010's conventions.
- **The other record schemas.** `document`, `chunk`, `symbol`, `edge`, `entity`,
  `custody`, `fidelity`, `quarantine`, `eval-case` and `eval-run` are exported into every
  build's `schemas/` directory with their own `schema_version` and may change at a MINOR
  with a `CHANGELOG.md` line. Only KIR and the manifest are frozen (spec 02 §10).
- **`mycelium.toml`.** The configuration file is a contract of its own kind (spec 05 §2):
  unknown keys are refused by design (ADR-0014). It is public surface under SemVer, with
  no golden.
- **The module-facing surface.** `mycelium.modules.MODULE_SURFACE` declares six
  components a module may import beyond the SDK — `config`, `modules`, `ingest`,
  `chunking`, `cli.output`, `synthesis` — and declares them *not frozen* (ADR-0086). The
  freeze review found the same single consumer it had at 5.14 and left the question
  open; it closes with the second module, or at the v1.0.0 tag, whichever comes first.
- **`Embedder`.** Spec 05 §4.1 lists it among the plugin Protocols. It lives in
  `mycelium.embedding.base`, and no entry point can supply one — `[embedding] provider`
  resolves exactly two names — so there is no third-party embedder for a frozen protocol
  to protect. It joins `mycelium.sdk.protocols`, additively, the day a provider resolves
  through the registry.
- **`Chunker`, `Extractor`, `Reranker`.** In the spec's sketch and in no code (ADR-0032,
  ADR-0073, ADR-0076). The freeze binds what exists.
- **Evaluation records and `AgentTask`.** Harness assets that change with the harness
  (ADR-0022).
- **Retrieval behaviour.** What a query returns is gated by the evaluation harness
  (G1–G7), not by this promise: a ranking change is a measured change, not a contract
  change.

## Where this is decided

- [ADR-0114](adr/0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md)
  — the decision: goldens of shape rather than prose, publication before the tag that
  binds, and the disposal of every question earlier records deferred to the freeze.
- `.draft-specs/02-architecture.md` §10 and `.draft-specs/05-interfaces-and-plugins.md`
  §5 — the five contracts and the compatibility policy they sit under.
- [`docs/workflow/maintenance.md`](workflow/maintenance.md) — the post-1.0 SemVer decision
  tree and the deprecation policy.
