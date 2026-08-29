# 2026-08-29 — heading-bounded chunker (roadmap 2.5)

- **Session scope:** roadmap item 2.5 — heading-bounded chunker with the no-content-loss
  property test (spec 03 §5).
- **PR:** #18 (`feat/heading-bounded-chunker`), one item, one PR. Follows #17 (2.4), merged.

## What got done

- `src/mycelium/chunking.py` — sections become chunks, the heading opens its section's
  first chunk, tables and code blocks are atomic, prose fills toward the ceiling and splits
  at the paragraph before breaching it. `ChunkingPolicy` carries the spec's defaults
  (200–800 tokens, overlap 0) and a pluggable token counter.
- **ADR-0007** records the four calls the spec left open: a dependency-free token estimate
  (a tokenizer would ship model files and move chunk boundaries on version bumps, breaking
  byte-identical rebuilds); the operational form of the invariant; the anchor rules; and
  why `target_min_tokens` is declared but deliberately not enforced.
- The collision case **ADR-0005 deferred to the chunker** is resolved: sibling headings
  that slug alike are numbered (`overview`, `overview-2`).
- Patterns catalogue: **Strategy** → Implemented (the pluggable token counter).
- Benchmarks: parse ≈ 21 ms and chunk ≈ 3.0 ms for a 20-section document — baseline only,
  well inside the < 2 s incremental-build budget.
- Tests: 224 passing, 26 of them for this item.

## The invariant, and what it caught

Spec 03 §5's "ordered chunk texts ⊇ normalized document text" is stated operationally as an
**ordered-subsequence check**: every KIR node's text appears in the joined chunk stream, in
document order, each occurrence consumed once so a repeated block cannot be satisfied twice
by a single match. Literal containment of the *source file* is not achievable — KIR already
dropped Markdown syntax (ADR-0006) — and pretending otherwise would have produced a test
that passes vacuously.

Two design consequences fell directly out of it:

- The heading text has to live in its section's first chunk, or it is lost.
- A heading with no content of its own still yields a chunk, for the same reason.

The anchor-uniqueness assertion caught a real collision before it shipped: a document whose
preamble precedes its title heading produced two sections with the same (empty) slug path,
both starting at ordinal 0. Ordinals are now scoped to the slug path rather than the
section, which fixes that case and any other path collision by construction.

## Where the project stands

- Milestone 2: 2.1–2.5 ✅ · 2.6–2.13 open. The compile half of the walking skeleton is
  done: source → KIR → chunks, all content-addressed and reproducible.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (224 passed), `python tools/consistency_lint.py`.

## How the next session resumes

- Wait for PR #18 to merge, then start **2.6** — the SQLite store: DDL, WAL, field-weighted
  FTS5, meta table (spec 03 §8), route standard/medium. It is the first module that owns
  state on disk, so expect it to raise questions this milestone has not had to answer:
  where `.mycelium/` lives, and how the store interface stays replaceable (spec 02 §10
  names SQLite a secondary store component, not a foundation).
- `Chunk.tokens` is an estimate. Whatever packs an MCP response against a hard model limit
  (2.9) must measure with the model's own tokenizer instead of trusting it (ADR-0007).
