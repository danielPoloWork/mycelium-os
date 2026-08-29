# 2026-08-29 — identity library (roadmap 2.3)

- **Session scope:** roadmap item 2.3 — canonical hashing + ULID + anchor-slug identity
  library, property-tested (spec 03 §§1–2).
- **PR:** #16 (`feat/identity-library`), one item, one PR. Follows #14 (2.2), merged.

## What got done

- `src/mycelium/sdk/identity.py` — the constructors behind spec 03 §§1–2: `normalize_text`
  / `canonical_json` / `digest_bytes|text|json`; in-repo ULID encode/decode plus a
  monotonic `UlidFactory` with injected clock and entropy; `heading_slug`, `anchor` /
  `parse_anchor`, `citation_uri` / `parse_citation_uri`, and the `doc:` / `sym:` / `ent:`
  reference forms with `edge_id`.
- ADR-0005 records the four calls the spec left open: ULIDs in-repo rather than a
  dependency, how far normalization goes, the `/`-joined anchor grammar with the ordinal
  always last, and the citation URI's spec-literal `?lines=` placement.
- Patterns catalogue: **Monitor Object** and **Dependency Injection** → Implemented (both
  in the ULID factory).
- Benchmarks for the build's hot path (`digest_text` on a 16 KB document, slugging, ULID
  minting) under `tests/bench/` — baseline only, no perf claim.
- Tests: 108 passing. The rules are stated as hypothesis properties (normalization
  idempotence; digest-invariance under line endings, Unicode composition, and JSON key
  order; ULID lexicographic order equals mint order; anchor and citation round-trips),
  plus cross-layer assertions that constructed values satisfy the 2.2 record contracts.

## What the properties caught

Writing producers against 2.2's validators found two real defects:

- **BUG-0004** (filed, fixed here): the `Ulid` pattern accepted 26 Crockford characters
  carrying 130 bits, so `"8" * 26` — which has no valid decoding — passed record
  validation. Pattern tightened to `^[0-7][…]{25}$`; a regression case asserts both layers
  now refuse the same inputs.
- `ulid_timestamp` used `datetime.fromtimestamp` on a float, which is lossy at large
  magnitudes and raises `OSError` on Windows for far-future values. Replaced with an exact
  epoch offset; beyond year 9999 it raises a typed `IdentityError`.

## Where the project stands

- Milestone 2: 2.1 ✅ · 2.2 ✅ · **2.3 ✅ (this session)** · 2.4–2.13 open.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (108 passed), `python tools/consistency_lint.py`.

## How the next session resumes

- Wait for PR #16 to merge, then start **2.4** — the Markdown→KIR adapter (markdown-it),
  frontmatter contract, and Mycelium Markdown Profile v1 (D-022), route standard/medium.
  It is the first *producer* of KIR nodes, so it is also the moment ADR-0004's deferred
  question comes due: whether `KirNode` stays a single open record or becomes a per-kind
  discriminated union.
- Anchors are built by the chunker (2.5); sibling heading-slug collisions are its problem
  to solve, deliberately not the identity library's (ADR-0005).
