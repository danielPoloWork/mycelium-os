# ADR-0004: Adopt pydantic v2 record contracts with JSON Schema 2020-12 export

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03
- **Related:** RFC-0001; spec 03 §§1–7 (`.draft-specs/03-data-model.md`); D-002, D-003,
  D-016; roadmap 2.2; patterns catalogue (Immutable Object)

## Context

Roadmap 2.2 lays down `mycelium.sdk.types` — the record schemas (document, KIR, chunk,
symbol, edge, entity, snapshot manifest) that every later milestone builds on
(sets-pattern). The spec already makes the load-bearing calls: records are **pydantic
models** exported as **JSON Schema 2020-12** so non-Python consumers get machine-readable
contracts without Mycelium OS becoming polyglot (spec 03 intro, D-003), every record
carries `schema_version` (D-016, migration policy v1: rebuild), and `namespace` is
reserved for Phase-5 tenancy (D-002). What the spec leaves open — and this ADR fixes — is
the pydantic major/minor floor, the model discipline (mutability, unknown-field policy,
collection types, time handling), the KIR node shape, and the export format's determinism
guarantees. This is also the project's **first runtime dependency**: until now the
package had none.

Two records need shape decisions the spec's examples only sketch: KIR nodes are
heterogeneous per `kind` (20 kinds, field sets defined only for the kinds the examples
show), and the spec's §1 conventions ("`namespace` and `trust_class` appear in every
record") disagree with its own §3–§7 examples (only `Document` carries `trust_class`;
KIR and the manifest carry neither).

## Decision

Implement the v0 records as **frozen pydantic ≥ 2.11 models** in
`src/mycelium/sdk/types.py`, all extending one `Record` base with
`frozen=True, extra="forbid"`, alias-faithful validation *and* serialization
(`serialize_by_alias`, needed for the `from` field on edges — the 2.11 floor). Sequences
are tuples (immutable all the way down), `schema_version` is a `Literal` with the exact
spec tag as default, identity formats are validated by pattern (ULID, `sha256:` digests,
anchors), and timestamps are RFC 3339 UTC: naive datetimes rejected, aware ones
normalized to UTC, serialized in the spec's `Z`-suffixed form. JSON Schema export lives
in `src/mycelium/sdk/schema.py`: `model_json_schema()` stamped with `$schema` (the
2020-12 dialect) and `$id` (the record's own `schema_version` tag), serialized with
sorted keys, LF endings, and a trailing newline so exports are **byte-deterministic on
every platform** — the same doctrine as build artifacts (G6). Files are named
`<record>.<version>.schema.json`, keyed like the manifest's `schema_versions` map.

Shape calls: `KirNode` is a **single open record** (common core + the kind-specific
fields the spec shows: `level`; `media_type`/`blob`/`note` for `opaque`), not a per-kind
discriminated union — per-kind refinement lands with the first producer (roadmap 2.4).
Where §1's conventions and the §3–§7 examples disagree, **the examples win** (they are
the concrete contract); the one addition is `Entity`, whose abbreviated §6 field list
gains `schema_version` and `namespace` because it omits even the fields D-016 mandates
everywhere — it is a summary, not an exhaustive shape.

## Alternatives Considered

- **`dataclasses` + hand-written JSON Schemas** — stdlib-only, zero dependencies.
  Rejected: validation and schema become two hand-maintained artifacts that drift; the
  spec's per-field constraints (patterns, ranges, aliases) would be re-implemented, badly,
  and the spec itself pins pydantic.
- **`msgspec`** — faster validation and native JSON Schema export. Rejected: raw
  throughput is not a v1 constraint (10²–10⁵ documents, D-002), and pydantic's
  validation-error ergonomics and ecosystem alignment (typer/MCP tooling ahead in the
  roadmap) matter more; switching would also deviate from the spec without cause.
- **Authoring JSON Schema first, generating Python models from it** — schema-first sounds
  contract-pure. Rejected: it inverts ownership; the spec names the Python models as the
  source and the schemas as the export (D-003), and generated models would resist the
  validators and docstrings the contracts need.
- **Per-kind discriminated union for `KirNode`** — the enterprise default for tagged
  heterogeneous nodes. Rejected *for v0*: the spec fixes the 20-kind vocabulary but not
  every kind's field set, so a union today would invent contracts; revisit at the
  markdown-adapter item (2.4) when real producers pin real fields.
- **`extra="allow"` on KIR for plugin tolerance** — parsers are plugins; an open IR
  tolerates innovation. Rejected *for v0*: pre-1.0 the priority is catching producer
  drift at the boundary; KIR "adds fields by minor version" means *declared* evolution
  (a schema change), not undeclared passengers. Revisit at the contract freeze (6.1).

## Consequences

- pydantic (+ pydantic-core, annotated-types, typing-extensions, typing-inspection)
  enters the runtime closure — accepted supply-chain surface; offline/zero-key posture
  (D-013/D-017) is unaffected.
- `extra="forbid"` means adding a field to any record is a deliberate, versioned event —
  exactly the D-016 discipline, at the cost of forward-tolerance pre-freeze.
- Frozen models with `dict`-typed fields (`schema_versions`, `timings_ms`, synthesizer
  `parameters`) are equality-comparable but not hashable — do not use records as set/dict
  keys; identity keys (digests, ULIDs) are the spec's answer for that (§2).
- `mycelium.sdk.types` shadows the stdlib `types` module *only* for code executed with
  `src/mycelium/sdk/` itself on `sys.path` (never the case under the src-layout); the
  name is fixed by RFC-0001's public import path.
- The exported schemas are not yet written anywhere by a build — the orchestrator (2.7)
  wires `export_json_schemas` into `schemas/` at build time.
- Testing: the spec's own §3–§7 examples are executable fixtures; vocabulary exactness
  (8 edge types, 20 node kinds) is asserted so growth is a conscious RFC-gated act
  (D-014/F-9).

## References

- Spec: `.draft-specs/03-data-model.md` §§1–7 · `.draft-specs/02-architecture.md` §10
  (stable contracts)
- RFC-0001 — API contract / Data & schema sections
- Decision log: D-002, D-003, D-014, D-016 (`.draft-specs/00-verdict-and-decisions.md`)
- Patterns: Immutable Object (`docs/patterns/README.md`)
