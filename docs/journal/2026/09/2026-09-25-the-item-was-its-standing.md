# 2026-09-25 — the item was its standing (roadmap 7.11)

- **Session scope:** roadmap 7.11 — the maintainer's *check that 7.2 was implemented
  correctly*. Nothing of 7.2 is implemented, by design, so the audit was of its standing:
  the readings of its three triggers, whether anything grew ahead of them, and what its RFC
  will owe.
- **PR:** #N (`docs/audit-7-2-standing`). Follows #202, merged as `03aa106`.
- **Milestone 7:** 7.11 closed; 7.13 filed.
- **Record it leaves:** [`docs/rfc/server-profile-checklist.md`](../../../rfc/server-profile-checklist.md).
  No ADR: an audit decides nothing.

## Read the item before the code

"Implemented correctly" had one honest answer before anything was opened: the item is held
at three spec 06 §3 triggers, so correct means *still not implemented*, and the question
becomes whether the holding is sound. That turned the audit into three checks with evidence
each — the readings against ADR-0155, `src/` against the Milestone 7 heading, and the
blueprint against the frozen contracts.

## The readings hold, and one borrowed definition lost half of itself

The report does what ADR-0155 says, and the tests pin most of it; a live run read *holding*,
*unreadable*, *holding*. The gap was in how a definition was reused. D-030's engaged actor
excludes the owner of **this** repository; turned on a plugin's repository it excludes **that**
plugin's owner — and nothing else. So the maintainer's own comment on somebody else's plugin
would fire the trigger alone. It is ADR-0138's lesson in a new place: a definition that says
who is not counted has to be moved with both of its exclusions. Filed as 7.13 rather than
fixed, because it edits a reading the owner accepted.

## Nothing grew ahead of its trigger

A scan of `src/` for server, database, telemetry and policy imports found three network
touches, all known and all bounded (the lock's hostname, the model fetch, the opt-in
synthesis provider), MCP on stdio only, and a four-package dependency list. The only thing
that looked like a server was `uvicorn` in the environment, and it arrives through `mcp`, a
dev dependency the contract tests use as a client.

## The blueprint lives outside the repository

Spec 06 calls `gpt-specs` the reference blueprint, and it is not vendored here; it was read
from the maintainer's `kos` checkout, and the checklist names where. Its requirement IDs
anchor twenty-eight questions. The expensive ones are all contract questions rather than
engineering ones: a tenant has no slot in the citation URI grammar, an access label absent
from an existing record has to mean *deny*, and isolating plugins that are in-process
Protocols is either a wire protocol beside them or a MAJOR.

## What the next session should know

- **7.12 is the maintainer's large review panel** — a Workflow run, which needs their
  explicit opt-in and a size decision, not an agent's initiative.
- **7.13 is small and has a test to write first**: a plugin repository with one engaged
  actor who is this repository's owner must not fire the trigger.
