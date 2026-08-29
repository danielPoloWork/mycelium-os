# Mycelium OS — Specification Package (claude-specs)

- **Status:** Draft for owner review
- **Date:** 2026-07-31
- **Author:** claude (senior architect pass)
- **Language:** English (deliberate: the lingua franca of a global open-source project)

## What this package is

A decision-oriented specification for **Mycelium OS**, an open-source **knowledge compiler and
serving layer for AI agents**. It is derived from two inputs, both reviewed critically:

1. **The originating discussion** (`Mycelium OS - Knowledge OS.pdf`, 40 pp) — an ideation dialogue
   that contains several genuinely good instincts and several structural errors.
2. **`gpt-specs/`** — a prior specification package. Technically rigorous, strategically
   inverted: it specifies the endgame platform before the first user exists.

This package does three things the prior artifacts do not:

- **Renders a verdict.** Every major claim from the discussion and from `gpt-specs` is
  either adopted, adapted, or rejected — with reasons ([00-verdict-and-decisions.md](00-verdict-and-decisions.md)).
- **Adds the missing product layer.** Wedge, users, competitive positioning, adoption
  model, success metrics ([01-product-strategy.md](01-product-strategy.md)).
- **Specifies a v1 that a small team can actually ship**, with explicit seams that allow
  the system to grow into the enterprise profile later — instead of specifying the
  enterprise profile first and hoping a v1 falls out of it.

## Reading order

| # | Document | Contents |
|---|----------|----------|
| 0 | [00-verdict-and-decisions.md](00-verdict-and-decisions.md) | Critical review of both inputs; the decision log (D-001…D-019) |
| 1 | [01-product-strategy.md](01-product-strategy.md) | Mission, wedge, personas, competition, differentiation, success metrics |
| 2 | [02-architecture.md](02-architecture.md) | v1 system architecture: authority model, compiler, store, serving, concurrency |
| 3 | [03-data-model.md](03-data-model.md) | Identity, hashing, record schemas, SQLite layout, export bundles |
| 4 | [04-retrieval-and-evaluation.md](04-retrieval-and-evaluation.md) | Retrieval pipeline, honesty gates, evaluation harness |
| 5 | [05-interfaces-and-plugins.md](05-interfaces-and-plugins.md) | CLI, MCP surface, `mycelium.toml`, plugin protocols, compatibility policy |
| 6 | [06-roadmap-and-governance.md](06-roadmap-and-governance.md) | Phases with exit gates, deferred decisions, OSS governance, risk register |
| 7 | [07-mycelium-os-assessment.md](07-mycelium-os-assessment.md) | Verdict on the pre-existing `mycelium-os` codebase: rebuild vs refactor, salvage map, archival plan |
| 8 | [08-module-chats.md](08-module-chats.md) | Optional module spec: local chat archive (chatbot transcripts → canonical JSONL + Obsidian projections) — first contrib module, validates the plugin API |

## Relationship to `gpt-specs/`

`gpt-specs/` is not discarded. Its authority model, loss-aware fidelity doctrine, snapshot
semantics, evaluation principles, and threat framing are **adopted** here (with credit and
simplification). Its polyglot kernel, out-of-process plugin sandbox, HTTP/gRPC surface,
and multi-tenant policy engine are **re-sequenced** to the platform phase (Phase 5), where
that package becomes the reference blueprint. The rationale is in
[00-verdict-and-decisions.md](00-verdict-and-decisions.md), §3.

## Status semantics

Draft → In review → Accepted (by the project owner) → Superseded. Nothing in this package
is self-approved. Accepting this package means accepting the decision log in document 00;
each decision is individually overridable by a recorded counter-decision, not by silence.
