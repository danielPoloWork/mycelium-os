# ADR-0140: Resolve the build façade on first access, and keep it invisible to the type checker

- **Status:** Accepted
- **Date:** 2026-09-20
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 02 §10
- **Related:**
  [ADR-0128](0128-cache-the-environment-not-the-repository-and-declare-the-names-instead-of-importing-them.md)
  (the twin of this on the configuration side, which measured the cost and stopped here
  deliberately),
  [ADR-0086](0086-declare-the-module-facing-surface-and-refuse-to-freeze-it-from-one-consumer.md)
  (`MODULE_SURFACE`, and why changing a module-facing component is a compatibility event),
  [ADR-0139](0139-time-the-tool-call-in-the-harness-and-keep-the-retriever-as-a-floor.md)
  (the gate that made the query path's cost legible),
  [ADR-0015](0015-adopt-content-addressed-incremental-builds.md) (the orchestrator this stops
  importing); spec 02 §§7, 10; roadmap 6.18, 6.25

## Context

`mycelium/mcp/tools.py` needs `read_current` — six lines that open `.mycelium/CURRENT` and
return the published snapshot id. `mycelium/build/publish.py`, where it lives, imports two
things: `mycelium.layout` and `mycelium.sdk.types`.

But `from mycelium.build.publish import read_current` runs `mycelium/build/__init__.py`
first, and that file re-exported eighteen names eagerly — including `build` from the
orchestrator. Behind the orchestrator: the build DAG, the Markdown adapter and `markdown_it`,
the content-addressed store, the symbol extractors, the embedding provider with `urllib` and
`ssl`, and the whole of `mycelium.ingest`.

Measured on the machine of record, `import mycelium.mcp.tools`:

| | modules | wall |
|---|---:|---:|
| before | **367** | **1 880 ms** |
| of which `mycelium.build.publish` | — | 1 638 ms |
| of which `mycelium.build.publish` actually needs | — | 2.3 ms |
| `markdown_it` | 63 | — |
| `mycelium.ingest` | 21 | — |

A read-only query path cannot call any of it.

**The filing item expected this to be hard**, and named why: `mycelium.ingest` is
module-facing under `MODULE_SURFACE`, so changing how it exposes its names is a
compatibility event for every module (ADR-0086). That is true, and it turns out not to
apply — **`mycelium.build` is not in `MODULE_SURFACE`.** The chain can be cut one package
earlier, on a package that is internal by declaration, and `mycelium.ingest` does not have
to change at all.

## Decision

**`mycelium/build/__init__.py` resolves each exported name on first access** (PEP 562
module `__getattr__`), binding it into the module's globals so the resolution runs once per
name. `__all__` is unchanged, the names come from the same modules, and `dir()` still lists
them.

An `_ORIGIN` table maps each exported name to the module it comes from. It is kept beside
`__all__` rather than derived from it, and `tests/test_build.py` asserts the two agree:
laziness must not be able to drop an export in silence.

**The façade is hidden from the type checker**, behind `if not TYPE_CHECKING:`. This is the
part worth arguing. A module-level `__getattr__` that mypy can see answers *every*
attribute, so `mycelium.build.compile_it_all` would stop being an error and start being
`object` — the laziness would buy a faster import by giving up a check on every consumer of
the package. Behind that branch, mypy reads only the `TYPE_CHECKING` imports and still
rejects a name this package does not export. The cost is that mypy no longer checks those
twelve lines; the runtime half is pinned by tests instead, including the `AttributeError` a
typo must still raise.

Alternatives considered:

- **Move `read_current` out of `mycelium.build`.** The item's other option. It fixes one
  caller, moves a public name, and leaves the next consumer of any build submodule paying
  the same 1.6 s. Refused as narrower and more disruptive at once.
- **A lazy façade on `mycelium.ingest` instead.** Unnecessary once the chain is cut above
  it, and it is the one package where laziness *would* be a module-compatibility event.

## Consequences

**Measured**, `import mycelium.mcp.tools`:

| | modules | wall | `markdown_it` | `mycelium.ingest` |
|---|---:|---:|---:|---:|
| before | 367 | 1 880 ms | 63 | 21 |
| after | **234** | **1 460 ms** | **0** | **0** |

133 modules and 420 ms, on every start of the MCP server, every evaluation run that reads
the published pointer, and every test that imports the serving surface.

**It does not touch the latency budget, and that was never the claim.** This is startup, not
per-call: NFR-2's p95 is unaffected, and roadmap 6.24 gates that number separately.

**What it does not fix, and the filing item over-promised.** *"A short-lived CLI invocation
that stops paying for an engine it never calls"* does not follow from this change:
`mycelium/cli/app.py` imports `build`, `mycelium.ingest` and the rest **directly**, at module
scope, because it is the front door to all of them. `import mycelium.cli.app` still costs
431 modules and ~2.2 s. Making the CLI lazy means deferring per-subcommand imports inside a
Typer app, which is a different change with its own trade-off — filed as roadmap **6.36**
rather than absorbed here.

**What is left, and it is not ours.** After the cut, `mycelium.sdk.types` is 999 ms of the
remaining 1 460 — pydantic building the record models, including pydantic's own
`importlib.metadata` entry-point scan at 222 ms. `sdk.types` is one of the five frozen
contracts and is module-facing; it is also genuinely needed by the tool schemas. There is no
cheap lever here, and naming it is worth more than filing it.
