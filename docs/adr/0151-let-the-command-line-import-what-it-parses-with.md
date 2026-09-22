# ADR-0151: Let the command line import what it parses with, and nothing else

- **Status:** Accepted
- **Date:** 2026-09-22
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 05 §2
- **Related:** [ADR-0010](0010-adopt-cli-output-conventions.md) (the CLI's conventions),
  [ADR-0140](0140-resolve-the-build-facade-on-first-access.md) (roadmap 6.25, the serving
  half of this shape, which measured this one on the way past),
  [ADR-0077](0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-what-it-could-not-reach.md)
  (why `mount()` imports every installed module, and why `--help` completeness is what that
  buys),
  [ADR-0114](0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md)
  (`docs/compatibility.md`, the promise the re-exports keep); D-011, D-023; spec 05 §2;
  roadmap 6.25, 6.36

## Context

`import mycelium.cli.app` loaded **481 modules in ~1.9 s**, because `cli/app.py` imported
`build`, `ingest`, `embedding`, `eval`, `export`, `synthesis`, `verification` and the rest
at module scope. Every invocation paid for every subcommand: `mycelium --version` loaded
the ingestion subsystem and the ONNX embedder's import graph to print a string.

Roadmap 6.36 framed the choice as *local imports at ~20 sites* against *a lazy command-group
loader*, and warned that the win might not be worth the scatter: `mycelium.sdk.types` alone
was ~1 s of pydantic that "no arrangement avoids", so the honest ceiling might be near 1 s.
It asked for measurement first. Measurement moved the answer, because three of its premises
were wrong in the same direction.

**One: the floor is not pydantic, it is three enums that happen to live with pydantic.**
Typer needs `EdgeType`, `TrustClass` and `VerificationStatus` at tree-build time, because
they are option types in command signatures. They are stdlib `StrEnum`s and cost nothing —
but they were defined in `sdk/types.py` beside twenty-five pydantic models, so importing one
built all of them. Measured alone: `mycelium.sdk.types` **954 ms / 221 modules**, against
**18 ms / 55 modules** for the same enums once separated.

**Two: five plain literals cost more than the rest of the CLI put together.** Typer
evaluates a command's *default values* while building its tree, and five defaults —
`DEFAULT_KEEP`, `DEFAULT_CACHE_MAX_AGE_DAYS`, `MAX_DEPTH`, `DEFAULT_EXPORT_DIRNAME`,
`STORE_DIRNAME` — were imported from `build.snapshots`, `graph`, `export` and `store`. Each
of those modules reaches the record contracts, so the five values `10`, `30`, `3`,
`"export"` and `".mycelium"` cost **1 229 ms and 253 modules**. Nothing about them needs a
subsystem; they had simply been defined next to the behaviour they configure.

**Three: most of what looked stuck was not.** Twelve subsystem imports appeared to be
needed at import time because their names sit in signatures — but every one of those
signatures belongs to a *private helper* (`_report_build`, `_query_embedder`,
`_open_store`), and nothing introspects a private helper. Only the Typer commands' own
annotations must resolve at runtime.

## Decision

**The command line imports what Typer reads while building its tree, and nothing else.**
Three changes, each removing one of the three findings above; no lazy command-group loader,
and `--help` is unchanged.

**The controlled vocabularies move to `mycelium.sdk.enums`.** Ten `StrEnum`s are defined
there and re-exported by `mycelium.sdk.types`, so `from mycelium.sdk.types import EdgeType`
keeps working and stays the documented spelling — the classes are the same objects, which a
test asserts. `sdk/types.py` remains the record contracts.

**The five Typer defaults move to `mycelium.defaults`**, a module with no imports at all,
and are re-exported by the four modules that own the behaviour they configure. The module's
docstring states the rule that keeps it useful: nothing here may grow an import, because a
dependency in that file is back on the path of every invocation.

**`cli/app.py` gains `from __future__ import annotations`**, puts the eight helper-annotation
imports under `TYPE_CHECKING`, and takes a local import in each of the **25 command bodies**
that needs one. This is the scatter the item feared, at the size it predicted; what changed
is the price it buys.

**`mycelium.modules` stops importing the plugin contracts to discover that nothing is
installed.** `main()` calls it on every invocation; `Module` and `MYCELIUM_API_VERSION` are
used only inside `load_module`, so they are imported there. Discovery is entry-point
metadata and now costs metadata; validation happens when there is something to validate.
`mount()` still imports every installed module, deliberately — ADR-0077's reasoning that a
lazily-loaded group would hide a module's subcommands from `--help` is untouched.

## Measured

Import cost of `mycelium.cli.app`, minimum of seven runs (minimum rather than median: import
cost is a floor, and noise on a shared machine only adds to it):

| | ms | modules |
|---|---:|---:|
| before | 1 894 | 481 |
| **after** | **420** | **164** |
| the floor this cannot beat (`typer` + `sdk.enums`) | 412 | 154 |

**−78 % of the time and −66 % of the modules, landing 8 ms and 10 modules above a floor set
by Typer itself.** `mycelium.modules` fell from **1 077 ms to 375 ms** on the same measure.

End-to-end, what a user waits for, arms alternated on the same machine (minimum of nine
each, so a machine that gets busier moves both numbers):

| invocation | before | after | |
|---|---:|---:|---|
| `mycelium --version`, no module installed | 2 454 ms | **1 057 ms** | **−56.9 %** |
| `mycelium --help`, no module installed | 3 068 ms | **1 540 ms** | **−49.8 %** |
| `mycelium --version`, `chats` installed | 2 755 ms | 2 431 ms | −11.8 % |
| `mycelium --help`, `chats` installed | 3 077 ms | 2 749 ms | −10.7 % |

**The two rows disagree, and the disagreement is the finding.** With a module installed the
change is worth ~11 %, because `mount()` imports every installed module on every invocation
and the in-repo `chats` module's own graph then dominates — about 1.6 s of the remaining
cost. That is ADR-0077's decision working as designed: a lazily-loaded group would be
cheaper and would hide the module's subcommands from `--help`. So the honest claim is
narrow: **this item halves the core's startup, and a module's cost is the module's.** The
plain `pip install mycelium-os` case — no module installed — is the one that halves.

`--help` costs ~480 ms more than `--version` in every arm, before and after: that is Typer
introspecting seventeen commands to list them, and no import arrangement touches it.

## Alternatives Considered

- **A lazy command-group loader**, the item's second option. Rejected on ADR-0077's existing
  reasoning rather than on new grounds: the same mechanism that would defer a core group
  would defer a module's, and hiding subcommands from `--help` is the cost that decision
  already refused. It is also unnecessary — the measured floor is 412 ms and local imports
  reach 420 ms, so the machinery would buy at most 8 ms.
- **Leave it: the ceiling is near 1 s so the scatter is not worth it.** This was the item's
  own hypothesis and the outcome it invited. Rejected because the ceiling was not near 1 s
  once the enums and the defaults were looked at rather than assumed — it is 412 ms.
- **Sentinel defaults** (`None` in the signature, the real value resolved in the body) to
  avoid moving the five constants. Rejected: `--help` would stop printing the actual
  default, which is the completeness the item told this change to protect.
- **Duplicate the five constants in the CLI.** Rejected: two sources of truth for a
  retention count is a defect waiting for one of them to change.
- **Split `sdk/types.py` further**, moving the records into per-domain modules. Rejected as
  out of scope and unmeasured: the enums were separable because nothing in them depends on
  anything, and that is not true of the records.

## Consequences

- **Nothing a user sees changes.** `--help` output was captured for the top level and all
  seventeen commands before the change and diffed after: **byte-identical**.
- **`tests/test_cli_import_cost.py` pins the property rather than the timing.** It asserts
  which modules `sys.modules` holds after `import mycelium.cli.app` — seventeen subsystems
  that may not appear, and the two that must — because a wall-clock assertion would be flaky
  on a runner and would not say what regressed. The failure it catches is one line: a new
  command's author adding `from mycelium.store import SqliteStore` at the top.
- **A collaborator imported inside a command body is patched where it is defined.** Three
  tests monkeypatched `cli_app.build_judge` / `cli_app.build_synthesizer`; those names are no
  longer module attributes, and the tests now patch `mycelium.verification` and
  `mycelium.synthesis`. That is the more correct spelling — the local import resolves the
  attribute when the command runs — and `tests/test_cli.py` says so where the module handle
  is bound, because the next person will hit it.
- **The scatter is real and is the cost of this decision.** Twenty-five command bodies now
  open with an import block. A reader looking for "what does this file depend on" no longer
  finds one answer at the top; they find the top block plus the body they are reading. The
  compensation is that each block names exactly what that command uses.
- **Two new public modules**, `mycelium.defaults` and `mycelium.sdk.enums`. Both are
  re-exported by their previous homes, so no documented import changes and
  `docs/compatibility.md`'s promise is kept; `EdgeType.__module__` now reads
  `mycelium.sdk.enums`, which the contract goldens accept unchanged because they are about
  shape rather than provenance.

## References

- `src/mycelium/defaults.py`, `src/mycelium/sdk/enums.py` — the two dependency-free modules.
- `tests/test_cli_import_cost.py` — the guard, and the forbidden list as a decision record.
- Roadmap 6.25 / [ADR-0140](0140-resolve-the-build-facade-on-first-access.md) — the serving half,
  which filed this item after measuring it.
