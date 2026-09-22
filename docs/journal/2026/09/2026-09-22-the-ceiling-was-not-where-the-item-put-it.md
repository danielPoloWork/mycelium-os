# 2026-09-22 — the ceiling was not where the item put it (roadmap 6.36)

- **Session scope:** roadmap 6.36 — the CLI pays for the whole engine to print `--help`.
  Measure before choosing between ~20 local imports and a lazy command-group loader, and
  be willing to conclude the win is too small to buy the scatter.
- **PR:** #PRNUM (`perf/stop-importing-the-engine-to-print-help`). Follows #185, merged as
  `7c5bffb`.
- **Milestone 6:** 6.36 closed. 6.37 remains open.
- **Decision it records:**
  [ADR-0151](../../../adr/0151-let-the-command-line-import-what-it-parses-with.md).

## The item told me what it expected, and that is exactly why measuring first mattered

6.36 came with a hypothesis attached: `mycelium.sdk.types` is ~1 s of pydantic that "no
arrangement avoids", so the honest ceiling is near 1 s, and "the answer may be that it is
not worth the scatter". That is a well-formed prediction, and the instruction was to
measure before choosing. Measuring took about twenty minutes and moved the conclusion from
*probably not worth it* to *−78 % of the import cost*.

The first surprise came from the cheapest possible check. `mycelium.cli.output` — a module
importing nothing but stdlib and typer — measured the same 481 modules as `cli.app`,
because `mycelium/cli/__init__.py` re-exports `app`. That was a false lead, but it forced
the habit of measuring each layer rather than the one the item named, and the next three
readings are the item's three premises failing:

**The floor was not pydantic.** Typer needs `EdgeType`, `TrustClass` and
`VerificationStatus` at tree-build time because they are option types. They are stdlib
`StrEnum`s. They were merely *sitting next to* twenty-five pydantic models, so importing
one built all of them: **954 ms / 221 modules**, against **18 ms / 55** once moved into
`mycelium.sdk.enums`.

**Typer evaluates default values too**, which the item did not account for. Five literals —
`10`, `30`, `3`, `"export"`, `".mycelium"` — imported from `build.snapshots`, `graph`,
`export` and `store`, cost **1 229 ms and 253 modules**. More than everything else put
together, for five plain values that had simply been defined next to the behaviour they
configure.

**Most of what looked immovable was not.** An AST pass over `app.py` said twelve subsystem
imports were needed at import time because their names appear in signatures — then reading
those signatures showed every one belongs to a private helper (`_report_build`,
`_query_embedder`, `_open_store`). Nothing introspects a private helper, so
`from __future__ import annotations` plus a `TYPE_CHECKING` block frees all twelve without
touching a single command.

## What the numbers then made easy to decide

`import mycelium.cli.app`: **1 894 → 420 ms**, **481 → 164 modules**. The floor that
`typer` + `sdk.enums` sets is 412 ms / 154 modules, so the result sits 8 ms above it — which
settles the item's open question without argument. A lazy command-group loader could have
bought at most those 8 ms, and ADR-0077 already refused that mechanism because it hides a
module's subcommands from `--help`.

## The number I nearly reported, and the one that is true

End to end, `mycelium --version` improved by **11 %**, not the ~78 % the import measurement
promised. Splitting the invocation into interpreter, import and `main()` found the reason:
`main()` was costing ~1.75 s on its own, because it mounts installed modules and this
repository has the `chats` module installed — `mount()` imports every installed module by
design, so that `--help` lists their subcommands.

Part of that was the core's fault and got fixed: `mycelium.modules` imported the plugin
contracts merely to *discover* what was installed, which is entry-point metadata;
validation now happens inside `load_module`, where there is something to validate
(**1 077 → 375 ms**). The rest is the module's own import graph, and ADR-0077 says plainly
that this is the price of complete `--help`.

So the headline needed a qualifier rather than a rounding. With no module installed — the
plain `pip install mycelium-os` case — `--version` goes **2 454 → 1 057 ms (−56.9 %)** and
`--help` **3 068 → 1 540 ms (−49.8 %)**. With a module installed it is ~11 %. Both are in
the ADR, in that order, because quoting only the first would describe a machine this one
is not.

## What shipped, and what it cost

Twenty-five command bodies now open with an import block: the scatter the item feared, at
the size it predicted. Three tests that monkeypatched `cli_app.build_judge` now patch
`mycelium.verification` — the module that defines it — which is the more correct spelling
and is recorded where the module handle is bound, because the next person will hit it.

`--help` was captured for the top level and all seventeen commands before the change and
diffed after: byte-identical. The regression guard is a property rather than a timing —
`tests/test_cli_import_cost.py` asserts which modules `sys.modules` holds after the import,
seventeen that may not appear and two that must — because a wall-clock assertion would be
flaky on a runner and would not say what regressed. The failure it catches is one line: a
future command's author adding `from mycelium.store import SqliteStore` at the top of the
file.
