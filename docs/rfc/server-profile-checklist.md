# What roadmap 7.2's RFC owes — the server-profile checklist

- **Status:** Standing record, not an RFC. It numbers nothing and approves nothing; the RFC
  that 7.2 enters through takes the next free number and answers this list.
- **Written:** 2026-09-25, by roadmap 7.11 (the audit of 7.2 as it stands)
- **Blueprint:** `gpt-specs/` — `docs/specs/01-mycelium-kos.md` (requirement IDs below are its
  own), `docs/security/threat-model.md`, `schemas/v1alpha1/plugin-manifest.schema.json`. It is
  **not vendored in this repository**; the audit read it from the maintainer's `kos` checkout.
  Spec 06 §Phase 5 names it the reference blueprint "on top of contracts that have not changed
  since Phase 1", and `.draft-specs/README.md` records which of its parts were adopted early
  and which were re-sequenced here.

## Why this exists before the RFC does

7.2 bundles the server profile — HTTP API, authn/z, namespaces and ACL with policy pushdown, a
Postgres catalog and object-store CAS, OpenSearch/Qdrant adapters, out-of-process plugin
isolation, OTel — and the Milestone 7 heading admits each part only through its spec 06 §3
trigger and its own RFC. None of the triggers has fired (the audit below), so no RFC exists and
none should be written ahead of the consumer who decides its hardest questions. What *can* be
written now is the list of questions that consumer's RFC will not be allowed to skip: each one
is a place where the blueprint's requirement meets a contract this repository has already frozen
(`docs/compatibility.md`, ADR-0114) or a decision it has already taken. Written down now, they
are not rediscovered under deadline.

The five frozen contracts are the fixed side of every row: **identity rules, KIR, the snapshot
manifest, the MCP tools, the plugin protocols** (spec 02 §10). An additive change is a MINOR;
anything else is a MAJOR after 1.0 (`docs/compatibility.md`). The `Store` protocol
(`src/mycelium/store/base.py`) is **not** among the five, which is the seam the catalog rows
below are meant to use.

## The standing, as audited (2026-09-25)

| Question | Finding | Evidence |
|---|---|---|
| Are 7.5's three readings the right ones? | Two instrumented, one reported unreadable, as ADR-0155 decides; one gap in the plugin reading (below) | ADR-0155, `tools/adoption_report.py` |
| Does the report evaluate them as ADR-0155 says? | Yes — form recognised by its rendered field headings, not its label; PRs and *not planned* issues excluded; forks and this owner's repositories excluded from plugin candidates; a refused code search is `UNREADABLE`, not a verdict; RBAC always `UNREADABLE` | `tests/test_adoption_report.py` (the form/reader agreement test and five trigger tests); a live run |
| Live state | HTTP API **holding** (no form filed); RBAC **unreadable**; plugins **holding** (no third-party repository declares `mycelium.plugins` or `mycelium.modules`) | `python tools/adoption_report.py`, 2026-09-25 |
| Has anything under `src/` grown ahead of its trigger? | **No.** No HTTP listener, no network server, no second catalog, no policy hook, no tenant field, no OTel exporter. The three network touches are the lock's `socket.gethostname()`, the explicit embedding-model fetch (threat model B8) and the opt-in synthesis provider (B10). MCP serves stdio only. `mcp` — which brings `uvicorn` and `starlette` into the development environment — is a dev dependency used by the contract tests, not a product dependency. The one mention of Postgres/OpenSearch under `src/` is the `Store` protocol's docstring naming the seam. | `pyproject.toml` `dependencies` (four packages), a scan of `src/` and `contrib/chats/src` for server, database, telemetry and policy imports |

**One gap, filed as roadmap 7.13.** The plugin trigger counts a plugin's *adoption* as one
D-030 engaged actor who is not **that plugin's** owner. D-030's own definition excludes **this
repository's** owner, and the reuse dropped that half: the maintainer commenting on somebody
else's plugin repository would, alone, fire the trigger — counting ourselves, the mistake
ADR-0138 was written against. Separately, the code excludes *every* repository this owner
holds, where ADR-0155's text says *a repository that is not this one*; the code is the stricter
and probably the intended reading, and the record should say so. Neither changes today's
verdict, because there are no candidates.

## The checklist — what the RFC must answer

Each row is a question with the blueprint requirement it comes from and the local contract or
decision it has to be reconciled with. "Unchanged v1 contracts" means: the answer is either
additive or it is a MAJOR, and the RFC says which.

### 1. Who deploys it, and which trigger let it in

| # | Question | Blueprint | Here |
|---|---|---|---|
| 1.1 | Which fired trigger admits each part, and which part is admitted by none? | — | spec 06 §3; ADR-0154, ADR-0155 |
| 1.2 | **Who is the deployer?** The RBAC row was read as a condition inside this RFC, which must name the organisation that will run the profile | FR-OPS-005 | ADR-0155 (owner decision, 2026-09-24) |
| 1.3 | Which parts ship as a separate distribution rather than in `mycelium-os`, so a local user installs none of it? | §5.3 profiles | D-011 (CLI + MCP only), D-029 (topology), ADR-0117's reachability rule |

### 2. The HTTP API and SDKs

| # | Question | Blueprint | Here |
|---|---|---|---|
| 2.1 | Is the HTTP API a transport over the **same four MCP tools** — same inputs, same `outputSchema`, same typed errors, same `snapshot_id` on every response — or a new contract? A new contract is a sixth stable surface and needs its own golden | FR-API-002, FR-API-006 | the MCP tools contract (ADR-0114), spec 05 §3 |
| 2.2 | Does it stay read-only? Mutating operations are disabled by default in the blueprint too | FR-API-004 | D-011, D-017; threat model B6 |
| 2.3 | Error model: the blueprint wants retryability and a correlation ID; the six v1 error codes carry declared fields only. Additive fields, or a new vocabulary? | FR-API-008 | `tests/fixtures/contracts/` (error codes and their fields) |
| 2.4 | SDKs: the blueprint names Rust and Python generated from versioned contracts; D-003 keeps Rust to profiled hotspots after 1.0. Which SDKs, generated from what? | FR-API-007, §5.2 | D-003 |
| 2.5 | Which consumer asked, through the *I cannot use MCP or the CLI* form, and does its reason hold? | — | ADR-0155 (the trigger) |

### 3. Authentication, tenancy, namespaces and policy pushdown

| # | Question | Blueprint | Here |
|---|---|---|---|
| 3.1 | Where do tenant and namespace live in **identity**? Citation URIs are `mycelium://<doc_id>#…` — keyed by `doc_id`, with no tenant or namespace in them. Does a tenant scope a `doc_id`, or does the grammar grow (and is that additive)? | FR-KNO-001, FR-RET-001 | spec 03 §2 (identity rules, frozen) |
| 3.2 | Where do access labels live? Filtering *inside* every candidate generator needs a label on every chunk; `Document` and `Chunk` carry none. A new optional field is additive — and a label that is absent must mean *deny*, not *public*, which is the opposite of how an optional field usually reads | FR-KNO-005, FR-KNO-006, FR-RET-002 | spec 03 §§3, 5; `docs/compatibility.md` |
| 3.3 | How is pushdown proven? The blueprint's bar is zero exposure in 10⁷ generated probes per release candidate — a property suite of the size G1–G7 have never carried | NFR-COR-005 | `pytest -m boundary` (ADR-0119) |
| 3.4 | Authentication mechanism, key storage, and what a local single-user build keeps: the blueprint keeps "the same namespace and policy model" in the local profile | NFR-SEC-001, §5.3 local | the local profile is today's product |
| 3.5 | Which trust boundaries are new? A network listener, an authenticated caller and a tenant each need a row in `docs/security/threat-model.md` and a marked boundary test **before** the code (`tests/test_threat_model.py` fails otherwise) | threat model | AGENTS.md §7; ADR-0119 |

### 4. The catalog and the content-addressed store

| # | Question | Blueprint | Here |
|---|---|---|---|
| 4.1 | Does a Postgres catalog implement the `Store` protocol (not frozen) behind the same snapshot semantics — one published snapshot per read, an atomic pointer swap, rollback by repointing? | FR-CMP-010, FR-CMP-011, NFR-COR-006 | D-015, ADR-0009, ADR-0016 |
| 4.2 | Object storage: the local CAS is `cas/<xx>/<sha256>`, the blueprint's `objects/sha256/<xx>/<rest>` — the same shape. Is the mapping one-to-one, and does tier-1 custody (never swept) get its own bucket or prefix? | §6.4 | spec 02 §3; ADR-0033 |
| 4.3 | What does the index row trust? A build-cache row is a key → digest assertion the CAS re-hash cannot check; shared across writers it is the cache-poisoning surface, and the parse key does not name its parser's version | FR-CMP-002 | ADR-0154 (the four facts), roadmap 7.1 |
| 4.4 | Snapshot manifest: does a manifest gain tenant, namespace and policy-version fields additively, or does the scale profile keep one manifest per namespace? | FR-CMP-009, §6.5 | spec 03 §7 (manifest, frozen) |
| 4.5 | Leases and fencing for concurrent workers replace the single-writer lock — and what does the local profile keep? | NFR-REL-005 | D-015, `src/mycelium/build/lock.py` |

### 5. Lexical and vector adapters

| # | Question | Blueprint | Here |
|---|---|---|---|
| 5.1 | Does an OpenSearch/Qdrant adapter reproduce the gated results? G2's verdict is recorded against `retrieval_identity()`; a new backend is a retrieval change and must re-measure, not inherit | FR-RET-003, NFR-RET-004 | ADR-0068; `tools/measure_hybrid_gate.py` |
| 5.2 | The blueprint's own hybrid bar (≥ 5 % nDCG@10 over lexical) is the one hybrid has not cleared here, and the default stayed lexical. Which bar does the RFC adopt? | NFR-RET-004 | G2; D-010 |
| 5.3 | Latency at scale: the blueprint states p95 ≤ 500 ms at 100 concurrent queries; the local reference profile misses its own 150 ms at 10⁵ chunks. Which budget, measured where? | NFR-PERF-001..007 | `docs/benchmarks/2026-09-17-reference-profile.md` |

### 6. Out-of-process plugins, sandboxing, a signed registry

| # | Question | Blueprint | Here |
|---|---|---|---|
| 6.1 | The four frozen protocols are **in-process Python Protocols** (D-012). Does isolation add a wire protocol beside them — every in-process plugin still working unchanged — or replace them (a MAJOR)? | FR-PLG-003, FR-PLG-008 | spec 05; the protocols contract (ADR-0114) |
| 6.2 | Manifest and signing: the blueprint's `plugin-manifest.schema.json` requires identity, digest, API range, capabilities and permissions; the entry-point groups carry a name. What a manifest adds, and who signs | FR-PLG-002, FR-PLG-004 | ADR-0117 (the release's own signing and SBOM) |
| 6.3 | Default-deny: no network egress, no secrets, bounded CPU, memory and time — and what the pandoc subprocess (B9) already does that generalises | FR-PLG-005, NFR-SEC-002 | threat model B7, B9 |
| 6.4 | Which third-party plugin fired the trigger, and is its adoption meaningful? (7.13's gap first) | — | ADR-0155 |

### 7. Telemetry

| # | Question | Blueprint | Here |
|---|---|---|---|
| 7.1 | The v1 design deferred OpenTelemetry past 1.0 **with its event names chosen now**; the journal's event names (`cache.invalid`, `store.recreated`, …) are that choice. Are they the span and log names, and is the exporter an optional plugin as the architecture says? | FR-OPS-001, FR-OPS-002 | RFC-0001; spec 02 (observability) |
| 7.2 | D-017 rules out telemetry *to us*. An operator's own OTel pipeline is a different thing; the RFC must say so in words a reader of `SECURITY.md` cannot misread | FR-OPS-001 | D-017 |
| 7.3 | Audit events for authentication, policy and export — an append-only record the local journal is not | FR-OPS-003 | the journal is diagnostics only (D-008) |

## What this list is not

It is not a design, a preference between answers, or a schedule. It does not make 7.2 more
likely to enter; it makes the RFC that enters it shorter to review. When that RFC is written it
cites this page and answers each row, and this page is then superseded by it.
