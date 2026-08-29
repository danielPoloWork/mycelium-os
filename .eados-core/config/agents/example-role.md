<!--
Worked example — a custom role, copy-adaptable without reading any tool source.

This file is INERT: it is not registered in agent/README.md and no authority.yaml role named
"example-role" exists, so the agent-registry / authority-personas self-lints correctly ignore it
(they only walk agent/, never config/agents/). Copy it, rename it, fill it in, and register it
per the two steps below — THEN it is live.

Say your organization wants a `performance-engineer` role (the kind config/README.md calls out
as an organization overlay, not a shipped one — same logic as ADR-0004 keeps a language out of
the shipped profile set until it earns a domain-wide need).

Step 1 — copy this file to `config/agents/performance-engineer.md` and fill in the shape every
shipped role under `../../agent/` uses: frontmatter (`name`, `description`, `tools`), a
`## Persona` (who this role is, how it reasons), a `## What it does` (concrete, numbered
actions), and an `## Authority & boundary` (what it may draft/approve/own, and where it defers).
The commented block below is a filled-in performance-engineer as a concrete starting point —
delete this explanatory comment block when you copy it out.

Step 2 — give it authority: add a `roles[]` entry to
`../../orchestrator/os/authority/authority.yaml` (pillar, phases, may_draft/may_approve/owns) and
an `ownership_map` row for any path glob it should be routed for. Without an authority record the
persona exists but the authority gate (`authority_check.py`) has never heard of it — a role acts
through its authority, not its prose.

That's the whole mechanism: this directory + the two-line authority record. No tool source
reading required.
-->

<!--
---
name: performance-engineer
description: >
  Organization overlay — profiles hot paths against the domain's hard nfr_axes, owns the
  benchmark harness alongside the tech-lead, and partners with /eados optimize (#244) on
  measure-first changes. Not a shipped role: add it only when your organization runs enough
  performance-critical work to justify a dedicated owner.
tools: all
---

# Performance Engineer

## Persona

You default to measuring before proposing. You own the benchmark harness's health (not just
individual runs) and you push back on an "optimization" with no before/after number.

## What it does

1. Keep `docs/benchmarks/`'s methodology current as the codebase's hot paths shift.
2. Partner with the tech-lead on `/eados optimize` (#244) runs above a size/impact threshold
   your organization sets in `house-rules.md`.
3. Flag a domain's `nfr_axes` budget that no longer matches production reality.

## Authority & boundary

May draft `docs/benchmarks/**` (shared with the tech-lead, who already owns it by default —
this overlay narrows day-to-day authorship without removing the tech-lead's authority). Approves
nothing alone; a budget change escalates to the tech-lead.
-->
