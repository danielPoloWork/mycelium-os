# 2026-08-30 — the authored link graph, and a protocol stream that spoke cp1252 (roadmap 3.4)

- **Session scope:** roadmap item 3.4 — `mycelium_neighbors` on authored links +
  `mycelium_explain` (spec 05 §§3.3–3.4, spec 03 §§3.1, 6; D-014).
- **PR:** #34 (`feat/neighbors-and-explain`). Follows #33 (3.3), merged as `0602a0b`.
- **The v1 MCP surface is now complete**: the four tools spec 05 §3 defines, and both of
  ADR-0011's deferrals are closed.

## The decision this item turned on

Extraction was never the hard part. Resolution was — because spec 03 §3.1 resolves a
wikilink by *"basename if unique, else path, aliases honored"*, which makes `[[api]]` a
question about **every other document in the corpus**. That collides head-on with ADR-0015:
the compiler only recompiles dirty documents, so an untouched document's links would never
be reconsidered, and adding `api.md` would leave every dangling `[[api]]` dangling until
each referring file happened to change. Stale in a way nobody can predict is worse than
absent.

So the two halves are split at an explicit seam. **Extraction is per-document and cached**
(KIR → `LinkRef`s, knowing nothing about the corpus). **Resolution is global and runs every
build**, over the references kept in `doc_state` — which is why store schema v3 exists.
Spec 02 §4.2 had already named this shape: *"rebuild global artifacts whose inputs changed
— graph closure, stats"*. The property it buys is tested directly: add a document, watch a
build recompile exactly one file and settle a *different* file's dangling link.

Three smaller calls, each recorded in ADR-0018: a heading link targets a **section**
(`doc:path#slug`), not a chunk anchor, because chunk boundaries are a packing decision;
an **ambiguous** basename warns and names its candidates instead of picking one, because a
plausible wrong edge is worse than a warning; and **rollback re-resolves** the graph rather
than restoring stored edges, so reproducing the manifest's published `edges` digest is what
proves the restore.

## The bug this item found — and it was not a small one

Two of the new tool descriptions contain em dashes. That was enough to make the MCP
conformance test **hang**, and the hunt was worth recording:

1. The whole suite crawled, then stopped finishing. First suspicion — a slow build — was
   wrong: a profile showed builds at ~100 ms and graph resolution at 0 ms.
2. Second suspicion — my own new tests — was wrong too: they passed in 15 s while the
   *pre-existing* MCP tests hung.
3. `git stash`, run the same test on clean `main`: **passes in 10 s**. So it was mine.
4. Driving the server by hand answered all four tools correctly, which ruled out the server
   logic and pointed at the client.
5. Driving it with the real SDK client and a per-step timeout, capturing the server's
   stderr, produced the sentence that ended it:
   `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x97 in position 2633`.

`0x97` is cp1252's em dash. `python -m mycelium.mcp` never configured its stdout, so on
Windows the JSON-RPC stream — UTF-8 by specification — was being written in the console code
page. The client's decoder failed *inside its read loop*, so the request never resolved and
the session hung rather than erroring.

`mycelium serve` was fine: it goes through `mycelium.cli.main`, which has called
`configure_streams()` since ADR-0010 fixed exactly this for the CLI at 2.8. The *second*
entry point was left out, and nothing noticed because every existing tool description was
ASCII and because the in-process tests drive `serve_stdio` with a `StringIO`, which has no
encoding at all.

Recorded as **[BUG-0009](../../../bugs/2026/08/BUG-0009-mcp-stdio-uses-the-console-code-page.md)**,
severity high — not for the em dash, but because the trigger a *user* would hit is any
Japanese or Italian passage in a search result, on a product whose corpus is deliberately
multilingual (D-028). The reference-client conformance test that ADR-0011 argued for is what
surfaced it; a suite of in-process tests never could.

## Cost of the hunt, and the lesson

Roughly an hour, most of it spent on wrong hypotheses because **PowerShell pipes buffer
output until the process exits** — so `pytest ... | Select-Object -Last 20` shows nothing
about a run that never finishes. Redirecting to a file and tailing it, and pytest's own
`-o faulthandler_timeout=N`, are the tools that actually see inside a hang. Worth
remembering before the next one.

Second lesson, already in the ledger twice this milestone: three test processes left over
from killed background runs were competing for the machine and made the early measurements
lie. Check for orphans before believing a timing.

## What got done

- `src/mycelium/graph.py` — extraction, the corpus index, resolution (paths, basenames,
  aliases, heading slugs), edge identity, and a bounded bidirectional traversal.
- Store schema **v3**: `doc_state.graph_json` (links, aliases, headings), `put_edges`,
  `clear_edges`, `edges_of`, and edges in the snapshot state so rollback can re-resolve.
- `mycelium neighbors` plus the MCP tools `mycelium_neighbors` and `mycelium_explain`;
  `SearchOutcome` gained per-stage timings, which is what explain promises.
- **ADR-0018**; the Pipeline pattern row extended rather than a new non-canonical name
  invented ("Pipes and Filters" is not in this project's taxonomy).

## Where the project stands

- **3.4 complete** pending merge. Milestone 3: 3.1–3.4 done; 3.5–3.12 open.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (558 passed, 18 skipped), `python tools/consistency_lint.py`.
- The G6 golden gained exactly two fields — `counts.edges` 0 → 5 and the `edges` digest —
  verified field by field before re-blessing; every fixture wikilink resolved, so no new
  warnings.

## How the next session resumes

- Wait for PR #34 to merge, then **3.5** (watch mode: debounced FS events → incremental
  builds). It is where the plan-scan floor measured at 3.1 (~2 ms/document, I/O-bound)
  finally gets removed, because the OS becomes the change detector instead of a full scan.
- Carry into 3.5: watch mode rebuilds on every keystroke-ish event, so snapshot and cache
  growth matter more — 3.2's `gc` retention and the always-publish semantics deserve a
  second look under that load.
