# 2026-08-30 — MCP server (roadmap 2.9)

- **Session scope:** roadmap item 2.9 — MCP server (stdio): `mycelium_search` +
  `mycelium_fetch`, typed errors, the data-not-instructions notice (spec 05 §3).
- **PR:** #22 (`feat/mcp-server`), one item, one PR. Follows #21 (2.8), merged.

## What got done

- `src/mycelium/mcp/` — `tools.py` (the two tool contracts as plain functions), `server.py`
  (the stdio JSON-RPC binding), `errors.py` (the closed six-code taxonomy),
  `__main__.py` (`python -m mycelium.mcp`).
- `mycelium serve` added to the CLI — the command ADR-0010 said would arrive here.
- Both v1 public surfaces (D-011) now exist. An agent can search the corpus and fetch
  around a result, with `mycelium://` citations, trust class, verification status, and the
  snapshot id on every response.
- ADR-0011 records the dependency decision; README gained the MCP paragraph.
- Tests: 370 passing (+43).

## The dependency call

The official `mcp` SDK resolves to **seventeen packages** — including `uvicorn` and
`starlette` (an HTTP server we never start), `pyjwt` and `cryptography` (OAuth for a
transport we do not expose), and `opentelemetry-api` (telemetry this project promises not
to emit, D-017). For a server that reads a local SQLite file and writes JSON to a pipe,
that is a poor trade, and every one of those packages would land in the 6.3 threat model.

So the stdio binding is implemented in-repo — **no new runtime dependency** — and the
obvious counter-risk ("our tests pass but a real client cannot connect") is neutralised
directly: the SDK is a *dev* dependency, and the suite spawns this server as a subprocess
and drives it with the SDK's own `ClientSession`. Conformance is checked against the
specification's own implementation while the shipped closure stays at four packages.

## The conformance test earned its place on the first run

It failed immediately, and on something no unit test of ours could have found: the server
advertised `2026-07-28` — the SDK's own `LATEST_PROTOCOL_VERSION` — and the reference
client **disconnected**. That constant is a *modern* revision, negotiated through request
metadata; the `initialize` handshake tops out at `2025-11-25`. Answering the handshake with
a modern version is not a wrong version, it is an answer to a different question.

Every test written against our own reading of the protocol passed while this was broken.
The version list now carries a comment explaining handshake versus modern, so nobody
"helpfully" re-adds the newer constant.

This is the same lesson as 2.8's encoding bug, one layer up: **the thing that talks to
someone else's software has to be tested against someone else's software.**

## Decisions worth remembering

- **Errors are tool results, not protocol errors.** A moved anchor or a too-small budget is
  a fact about the corpus that an agent should read and act on; JSON-RPC errors stay
  reserved for messages that are unintelligible as calls.
- **`budget_tokens` truncates and names what it dropped** (`omitted`, `truncated`), rather
  than silently returning less. `BUDGET_EXCEEDED` fires only when even one result cannot
  fit, and its message names the lever.
- **A fresh read-only store handle per call**, so a long-lived agent session sees each
  newly published snapshot rather than the one that existed at startup.
- **stdout belongs to the protocol** — readiness lines and diagnostics go to stderr from
  both entry points.

## Where the project stands

- Milestone 2: 2.1–2.9 ✅ · 2.10–2.14 open. The walking skeleton walks: authored Markdown
  compiles to a published snapshot and is served to agents over MCP with citations.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (370 passed), `python tools/consistency_lint.py`.

## How the next session resumes

- Wait for PR #22 to merge, then start **2.10** — the determinism golden test wired into CI
  (gate G6), route standard/medium. Most of the evidence already exists: `test_build.py`
  asserts that a second build produces identical `artifact_digests`, so 2.10 is largely
  about making that a *CI gate* over a fixture corpus rather than a unit test, and deciding
  what the golden artifact is (manifest digests? a full export?).
- Watch for the parts of the manifest that legitimately vary between runs — `snapshot_id`
  (a fresh ULID), `created_at`, and `timings_ms`. The determinism claim is about
  `artifact_digests` and counts, not about byte-identical manifests.
