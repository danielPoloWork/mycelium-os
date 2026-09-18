# 2026-09-18 — the budget was spent before retrieval started (roadmap 6.18)

- **Session scope:** roadmap 6.18 — read the configuration once per server rather than once
  per tool call, the cheapest of 6.4's three findings and the one that made NFR-2 unreachable
  at every corpus size.
- **PR:** `perf/read-the-environment-once`, following the M6 work through #162.
- **Decision it records:** [ADR-0128](../../../adr/0128-cache-the-environment-not-the-repository-and-declare-the-names-instead-of-importing-them.md).

## The item was right about the cost and wrong about two of its causes

The per-call number reproduced exactly: `installed_ids()` 264 ms, `load_config()` 262 ms,
`handle_search` 302 ms end to end against a 150 ms budget. One detail the item did not mention
and which matters for anyone tempted by a narrower fix: passing `group=` to `entry_points()`
saves nothing, because the whole index is built and then filtered.

The two *explanations* did not survive measurement.

The 446 ms first-call import is not "the docling/pandoc/PDFium module graph". Those three
parser modules guard their engines behind a factory that raises `PluginUnavailableError` —
which is exactly what ADR-0032 designed so an unavailable parser is a reportable fact — and
importing the registry imports **no engine module at all**. What it imports is 126 modules of
which **63 are `markdown_it`**, because `mycelium/ingest/__init__.py` eagerly imports its whole
package and the Markdown parser's adapter needs a CommonMark engine.

And the server does not pay that on its first *call*. `mycelium.mcp.tools` already imports all
20 `mycelium.ingest` modules at *import* time, through `mycelium.build.publish` — pulled in for
`read_current`, one function — so for the process NFR-2 is actually about, it is a startup cost
that never appears in a p95. That halved the item: the decisive per-call cost was one thing, not
two.

## The invalidation argument, which is the whole decision

The item said the fix is a cache and that the argument it needs is about invalidation, and that
there were probably two lifetimes and two caches. Right about the lifetimes, wrong about the
second cache.

*The environment* gets cached. A set of installed distributions is a property of the
environment, and a running process cannot honour a change to it anyway — importing something
installed after interpreter start needs `importlib.invalidate_caches()` at minimum. Two facts
make it safe rather than merely fast: every CLI invocation is its own process, so
`mycelium doctor` re-scans **by construction** and cannot observe the cache at all; and the one
long-lived process must be restarted to pick up a new module regardless, because `mount()`
builds the command tree once at startup.

*The repository* does not. `mycelium.toml` may be edited under a running server and the next
query should honour it. And once the scan was cached, that read measured **2.1 ms** — less than
the store open sitting beside it. A second cache would have bought nothing perceptible against
a 150 ms budget in exchange for an invalidation question nobody has to answer today. Refused on
the number rather than built for symmetry.

## The other half was not a cache at all

The config validator needed four parser *names* and was importing a subsystem to read four
dictionary keys. Declaring them (`BUILTIN_PARSER_IDS`) took `load_config` from +127 modules to
**+2** in a fresh process. It is two lists with one test rather than one list with two readers,
because the alternative inverts a dependency `config` deliberately keeps lazy the other way —
and the failure worth catching is a fifth built-in parser slipping past the check in silence,
which a test catches the moment it happens.

## What it bought

`load_config` 262 → 2.1 ms. `handle_search` 302 → 45 ms mean, 58.6 ms p95. **This corpus meets
NFR-2 end to end for the first time**, and the caveat belongs in the same breath: 6.4 measured
1 816 ms p95 for the warm query alone at 10⁵ chunks, so the constant is fixed and the scaling
is 6.21's problem. Fixing a constant does not fix a slope.

## Filed rather than fixed

Gate G5's docstring claimed to measure "end to end" while timing the retriever inside the
harness — corrected here, because this project corrects a false claim on sight, and the gate
itself filed as **6.24**. It is worth arming *now* precisely because it would pass: before this
PR, adding it would have been a change that failed CI on arrival. And **6.25** owns the server's
startup import graph, which is a package-façade change touching a module-facing surface
(`mycelium.ingest` is in `MODULE_SURFACE`), not a declaration away like its twin.

## Lesson

A performance item's diagnosis is a hypothesis with a number attached, and the number can be
right while the cause is wrong. Both of this one's causal claims failed — the engines were
already lazy, and the import was paid at startup rather than per call — and re-measuring is what
turned a two-part fix into a one-part fix plus a filed item. Reproduce the measurement before
implementing the remedy, even when the remedy is obvious and the number is somebody else's
careful work.
