# ADR-0128: Cache the environment, not the repository — and declare the names instead of importing them

- **Status:** Accepted
- **Date:** 2026-09-18
- **Deciders:** tech-lead (EADOS delivery agent)
- **Related:** [ADR-0120](0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md)
  (the reference profile that found this, and the report this amends),
  [ADR-0077](0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-what-it-could-not-reach.md)
  (why `load_config` asks what is installed at all),
  [ADR-0086](0086-declare-the-module-facing-surface-and-refuse-to-freeze-it-from-one-consumer.md)
  (`mycelium.ingest` is module-facing, which is why half this fix is filed rather than made),
  [ADR-0032](0032-adapt-four-engines-and-pin-which-one-runs.md) (the connector/parser split
  the declared ids serve), [ADR-0014](0014-adopt-partial-strict-configuration.md) (the strict
  config read that must keep happening per call), [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)
  (a control that fires on everything selects for being ignored); RFC-0001; spec 04 §1, §7.3;
  spec 05 §2; NFR-2; roadmap 6.4, 6.18, 6.21, 6.24, 6.25

## Context

NFR-2 gives `mycelium_search` a p95 of 150 ms end to end. Roadmap 6.4's reference profile
found it missed on **every corpus measured**, including a 568-chunk corpus of somebody else's
documentation where the retrieval inside the call cost 7 ms and the call cost 278 ms. The gap
did not grow with the corpus: it was a constant of roughly 250–300 ms, which meant no corpus of
any size had ever met the budget, including ones a hundred times smaller than the condition the
budget is stated for.

Re-measured here before changing anything, on this repository's own corpus (211 documents,
1 549 chunks), twenty samples each:

| per call | cost |
|---|---:|
| `modules.installed_ids()` | **264 ms** |
| `config.load_config()` (which calls it) | **262 ms** |
| `SqliteStore.open(read_only=True)` + close | 9.9 ms |
| `handle_search`, end to end | **302 ms** |

`load_config` asks `mycelium.modules.installed_ids()` whether a configuration section names an
installed module, because a table named after a module belongs to that module (ADR-0077). That
calls :func:`importlib.metadata.entry_points`, which re-reads the metadata of **every**
installed distribution on every call. Passing `group=` does not help — the index is built whole
and then filtered — so one line inside the configuration read cost more than the entire
end-to-end budget, before a single chunk was ranked.

### Two things the 6.4 report got wrong, found by measuring them

The report's account of the first-call import cost was wrong in both its attribution and its
timing, and correcting it changed what this item had to do.

**It is not the docling/pandoc/PDFium graph.** The report said the config validator *"pulls in
the docling/pandoc/PDFium module graph"*. It does not: those three parser modules guard their
engines and raise `PluginUnavailableError` from a factory, which is exactly the design that
makes an unavailable parser a reportable fact (ADR-0032). Measured, importing
`mycelium.ingest.registry` imports **no engine module at all**. What it does import is 126
modules of which **63 are `markdown_it`** — the CommonMark parser, reached because
`mycelium/ingest/__init__.py` eagerly imports its whole package, including
`mycelium.ingest.parsers.markdown`, whose adapter needs it. The cost is real (446 ms); the
named cause was not.

**The server does not pay it on the first call.** The report said *"the first call in a process
pays a further ~616 ms of imports"*. True in a process that has imported `mycelium.config` and
nothing else — but `mycelium.mcp.tools` already imports all 20 `mycelium.ingest` modules and
all 63 `markdown_it` modules **at import time**, through `mycelium.build.publish` (imported for
`read_current`) and that package's own eager `__init__`. For the MCP server, which is what
NFR-2 is about, this is a startup cost, not a per-call one. It never appears in the p95.

So the decisive per-call cost was one thing, not two: the entry-point scan.

## Decision

**Cache the entry-point scan for the life of the process, and do not cache `mycelium.toml`.**
The filing item predicted *"two different lifetimes and probably two different caches"*. It is
right about the lifetimes and wrong about the second cache, and the measurement is what settles
it.

*The environment* is cached. `mycelium.modules._points()` scans once and returns a read-only
view; `forget_installed()` drops it. The cache is sound because of what is being cached: a set
of installed distributions is a property of the environment, and a running process cannot
honour a change to it in any case — importing a distribution installed after interpreter start
needs :func:`importlib.invalidate_caches` at minimum and is unsupported in general. Two
consequences make it safe rather than merely fast. Every CLI invocation is its own process, so
`mycelium doctor` — the surface whose entire job is to report the truth about this environment
— re-scans by construction and cannot observe the cache at all. And the one long-lived process
is the stdio MCP server, which is precisely the case that must not pay 259 ms per call; an
operator who installs a module while it runs restarts it, which they must do anyway for that
module's commands to appear in `--help`, because `mount()` builds the command tree once at
startup.

*The repository* is not cached. `mycelium.toml` is a property of the repository, an operator may
edit it under a running server, and the next query should honour the edit. With the scan cached,
that read costs **2.1 ms** — so a second cache would save less than the store open beside it
(8.9 ms) against a 150 ms budget, in exchange for an invalidation question nobody has to answer
today. Refused on the number, not on symmetry.

**Declare the four built-in parser ids instead of importing the registry to read them.**
`IngestConfig._connectors_are_not_parsers` exists to catch an operator who copied spec 05 §2's
`connectors = ["markdown", "html", "pdf"]`, and it needs four *names*. It read them from
`registry.BUILTIN_PARSERS`, paying 446 ms and 126 module imports for four dictionary keys.
`mycelium.config.BUILTIN_PARSER_IDS` declares them; `tests/test_config.py` fails if the tuple
and the registry's mapping ever disagree. This is deliberately **two lists with one test**
rather than one list with two readers, because the alternative inverts a dependency `config`
keeps lazy in the other direction — and the failure it must catch is a *fifth built-in parser
slipping past the check in silence*, which a test catches at the moment it happens.

**Keep the fresh store handle per call**, and say why now that it is the largest remaining
constant. It costs 8.9 ms and buys the correctness property a long-lived agent session depends
on: each call sees the snapshot published most recently, not the one that existed when the
server started. Caching it would trade that for a margin nothing needs. If the budget ever gets
tight enough that 9 ms decides it, the honest fix is to notice a *new* snapshot rather than to
re-open blindly.

**Correct the claims this work found false**, on sight, as this repository does: the 6.4
report's two mis-attributions above (noted in the report, which is dated and therefore amended
rather than rewritten), and gate G5's docstring, which said it measured *"end to end"* while
timing the retriever inside the harness.

## Measurement

Same machine, same corpus, after:

| per call | before | after |
|---|---:|---:|
| `modules.installed_ids()` | 264 ms | **0.00 ms** |
| `config.load_config()` | 262 ms | **2.1 ms** |
| `SqliteStore.open` + close | 9.9 ms | 8.9 ms |
| `handle_search`, end to end (mean) | 302 ms | **45 ms** |
| `handle_search`, **p95** over five varied queries | — | **58.6 ms** |

And the import path, first `load_config` in a bare process: **716 ms / +127 modules → 224 ms /
+2 modules**, with `mycelium.ingest` and `markdown_it` gone from it entirely. The remaining
224 ms is the one scan, now paid once.

**This repository's corpus meets NFR-2 end to end for the first time** — 58.6 ms p95 against
150 ms. What that does *not* mean is stated plainly, because 6.4 already measured it: at 10⁵
chunks, the condition the budget is actually stated for, the warm query **alone** is 1 816 ms
p95. Removing the constant was necessary and is nowhere near sufficient; the query path's own
scaling is roadmap 6.21's, and this ADR claims only the constant.

## Alternatives Considered

- **Cache `mycelium.toml` too, on its own lifetime** (the item's own prediction). Rejected on
  the measurement: 2.1 ms of a 150 ms budget, against an invalidation question — a build may
  rewrite the file — that would have to be answered correctly forever for no perceptible gain.
  A stat-keyed cache is the obvious shape if it is ever wanted; nothing needs it now.
- **Cache the store handle as well.** Rejected: it is the one per-call cost that buys a
  correctness property, and 8.9 ms is affordable beside ~27 ms of retrieval. Named in
  `_open_store`'s docstring so the next reader meets the reasoning rather than the number.
- **Stop asking what is installed** — drop the module-section check, or make it lazy until a
  section is actually unrecognised. Rejected: ADR-0077's rule is that a table named after an
  installed module belongs to that module and an unknown section is an error naming what it
  could have been, which requires knowing the installed set on the path that refuses. Making
  the check conditional would make the error message worse exactly when it matters.
- **`functools.lru_cache` on `_points()`.** Equivalent mechanism, and the explicit global with
  a documented `forget_installed()` was chosen because the *invalidation argument* is the whole
  decision here and it needs a docstring to live in. `cache_clear()` would have carried none of
  it.
- **Cache the `mycelium.plugins` scan in `mycelium.ingest.registry` too.** Not done, and not
  because it is wrong: that scan is on the *build* path, where parser resolution happens a
  bounded number of times per build, and `tests/test_ingest_registry.py` monkeypatches it, so
  caching would need a patchable accessor. No measurement says it costs anything that matters.
  Build cost is roadmap 6.19's, with its own numbers.
- **Take the ingest package out of the server's import graph in this PR.** Rejected as scope,
  and filed as **roadmap 6.25**. The configuration half was a declaration away; this half is a
  package façade, and `mycelium.ingest` is module-facing under `MODULE_SURFACE`, so changing how
  it exposes its names is a compatibility event for every module (ADR-0086). It is also
  startup rather than per-call, so no budget names it.
- **Make gate G5 time the handler here**, since this PR is where the gap was confirmed.
  Rejected as scope and filed as **roadmap 6.24**: it needs a decision about whether the
  evaluation harness may import a serving surface, or whether the sample belongs in the run
  manifest — a design question, not a timer. Worth noting that 6.18 is what makes it *arm-able*:
  the gate would pass today, so adding it is no longer a change that fails CI on arrival.

## Consequences

- **The constant is 13 ms, from 274 ms**, and the query path is what a tool call now spends its
  time on. That is the shape a latency budget is supposed to have.
- **A regression would be silent without a guard, so there are three.**
  `tests/test_mcp.py` counts scans across five tool calls and a fetch;
  `tests/test_modules.py` pins the scan-once property, the reset, the read-only view, and that a
  fresh process starts unscanned; `tests/test_config.py` asserts in a subprocess that reading
  the configuration imports **no** `mycelium.ingest` module and **no** `markdown_it`. All count
  or assert mechanisms, never milliseconds: a timing bar on a shared runner is a flake, and
  `tests/bench/test_config_bench.py` carries the numbers with a budget loose enough to catch a
  reintroduced scan and nothing else.
- **`mycelium.modules` gains one public name**, `forget_installed`. It is in the module's
  `__all__`, which makes it module-facing under `MODULE_SURFACE` — a widening of that surface,
  and a deliberate one: a module that manipulates its own environment is exactly the caller who
  needs it. `BUILTIN_PARSER_IDS` is deliberately **not** exported, so it stays private to
  modules by ADR-0086's rule.
- **The `[ingest]` section's `default_factory` keeps its place and loses its reason.** The
  import cycle it was written for — validator → registry → build → config — no longer runs. The
  docstring now says so, and says why the factory stays: the hazard is structural, and a
  section's construction time is not something to change for tidiness.
- **Two findings are filed rather than fixed**, 6.24 (the gate that measures the wrong
  function) and 6.25 (the server's startup import graph), each with the measurement that found
  it.
- **A limit, stated.** Every number here is from one machine, whose file-open calibration
  constant the 6.4 report publishes precisely so these figures can be read against it. The
  claim is a ratio — 302 ms to 45 ms, one line of scanning removed — not an absolute anyone
  should quote for their own hardware.

## References

- `docs/benchmarks/2026-09-17-reference-profile.md` — where the constant was found, amended
  here with the two corrections above.
- Re-runnable: `python -c "import time; from pathlib import Path; from mycelium.config import
  load_config; s=time.perf_counter(); load_config(Path('.')); print((time.perf_counter()-s)*1000)"`
  — twice, and note that the second call is the one the budget cares about.
- `uv run pytest tests/bench/test_config_bench.py --benchmark-only` — the numbers with a
  guard around them.
