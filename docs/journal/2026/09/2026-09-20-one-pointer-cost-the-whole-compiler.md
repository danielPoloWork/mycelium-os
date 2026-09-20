# 2026-09-20 — one pointer cost the whole compiler (roadmap 6.25)

- **Session scope:** roadmap 6.25 — take the ingestion subsystem out of the MCP server's
  import graph, the half 6.18 measured and deliberately did not fix.
- **PR:** #175 (`refactor/server-import-graph`). Follows #174, merged as `8ceaf24`.
- **Milestone 6:** 6.25 closed, 6.36 filed. Open: 6.26–6.36.
- **Decision it records:**
  [ADR-0140](../../../adr/0140-resolve-the-build-facade-on-first-access.md).

## The blocker the item named was not the blocker

6.25 was filed as the hard half. Its reasoning: `mycelium.mcp.tools` needs `read_current`
from `mycelium.build.publish`, importing anything under `mycelium.build` runs the package
`__init__`, that reaches the orchestrator and through it `mycelium.ingest` — and
`mycelium.ingest` is **module-facing** under `MODULE_SURFACE`, so changing how it exposes
its names is a compatibility event for every module (ADR-0086). Hence *"a package façade,
not a declaration away"*.

All true. And it does not apply, because **`mycelium.build` is not in `MODULE_SURFACE`.**
Reading the declaration rather than the chain shows the cut can be made one package earlier,
on a package that is internal by declaration, and `mycelium.ingest` never has to change.

That is the second time in three items that the filing text's own explanation needed
correcting by measurement — 6.18 found two of its causes wrong, 6.24 found the manifest
option to be the weaker of two, and this one found the compatibility question to be about a
package that was never involved. The pattern is worth naming: **a filed item's diagnosis is
a hypothesis, and the first job of the item that delivers it is to re-take the measurement.**

## What changed

`mycelium/build/__init__.py` resolves each of its eighteen exports on first access (PEP 562
`__getattr__`) and binds it into globals, so the second access is an ordinary lookup. An
`_ORIGIN` table names the module each export comes from, and a test asserts it agrees with
`__all__` — laziness must not be able to drop an export in silence.

**The façade is hidden from mypy**, behind `if not TYPE_CHECKING:`, and that is the part
worth arguing. A module-level `__getattr__` the type checker can see answers *every*
attribute: `mycelium.build.compile_it_all` would stop being an error and become `object`. The
laziness would have bought a faster import by giving up a check on every consumer of the
package. Behind that branch mypy reads only the `TYPE_CHECKING` imports, still rejects an
unexported name, and the twelve lines it no longer checks are pinned by tests instead —
including the `AttributeError` a typo must raise.

| `import mycelium.mcp.tools` | modules | wall | `markdown_it` | `mycelium.ingest` |
|---|---:|---:|---:|---:|
| before | 367 | 1 880 ms | 63 | 21 |
| after | **234** | **1 460 ms** | **0** | **0** |

For scale: `mycelium.build.publish` cost 1 638 ms of the before, and needs 2.3 ms of it.

## What the item over-promised, and what is left

*"A short-lived CLI invocation that stops paying for an engine it never calls"* does not
follow from this change. `cli/app.py` imports `build`, `mycelium.ingest`,
`mycelium.embedding`, `mycelium.eval` and the rest **directly**, at module scope, because it
is the front door to them — `import mycelium.cli.app` still costs 431 modules and ~2.2 s.
Filed as **6.36**, with the measurement that bounds it: `mycelium.sdk.types` alone is ~1 s of
pydantic that no arrangement avoids, so the honest ceiling may be near 1 s and the answer may
be that scattering twenty import blocks is not worth it.

That same 999 ms is what remains of the 1 460 after the cut — pydantic building the record
models plus its own `importlib.metadata` scan. `sdk.types` is a frozen contract, is
module-facing, and is genuinely needed by the tool schemas. No cheap lever, so it is named
here rather than filed as work nobody can do.

Startup, not per-call. NFR-2 is untouched, and 6.24 gates that number separately.
