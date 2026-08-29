#!/usr/bin/env python3
"""Tests for the command-adapters self-lint check (#239, ADR-0019 class 4) —
eados_lint.command_adapter_problems.

Every AVAILABLE `/eados <name>` row of orchestrator/commands/README.md must ship its Claude Code
adapter at .claude/commands/eados/<name>.md, and the adapter must POINT at the row's own canonical
procedure (never copy it). Symmetric: an orphan adapter with no available row is stale. These pin
the pure helper off in-memory fixtures plus the live factory tree. Dependency-free.

    python .eados-core/tools/tests/test_command_adapters.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint  # noqa: E402
import command_registry    # noqa: E402  — the ONE registry parser (#373)  (the module under test)

REPO_ROOT = os.path.dirname(lint.ROOT)

# A command table with two available rows (one with the scaffold-style ../ procedure link), one
# not-yet-available row, and alias-table rows (one LIVE — the #241 class — and one planned) —
# only the available rows demand adapters; a live alias may optionally ship one.
README = (
    "| Command | Phase | Status | Procedure |\n"
    "|---------|-------|--------|-----------|\n"
    "| `/eados init` | init | **available** (M1) | [`init.md`](init.md) |\n"
    "| `/eados scaffold` | scaffold | **available** (today's factory) | "
    "[`../generate.md`](../generate.md) |\n"
    "| `/eados debug` | — | planned (M15 W2) | [`debug.md`](debug.md) |\n"
    "| Alias (wishlist verb) | Routes to | Class | Ref |\n"
    "|---|---|---|---|\n"
    "| `secure` | `/eados init` (see also `/eados scaffold`) | sub-mode | #241 |\n"
    "| `refactor` (code cleanup) | `/eados refactor` | cross-cutting | #243 · planned |\n"
    "| `later` | `/eados debug` | cross-cutting | #9 · planned |\n"
)
GOOD = {
    "init": "pointer -> `.eados-core/orchestrator/commands/init.md` (read and follow)",
    "scaffold": "pointer -> `.eados-core/orchestrator/generate.md` (read and follow)",
}
# The live-alias adapter: `secure` routes to init, so it must carry INIT's canonical procedure.
ALIAS_OK = dict(GOOD, secure="alias -> `.eados-core/orchestrator/commands/init.md` (sub-mode)")


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    P = lint.command_adapter_problems

    # --- link resolution: plain and ../-style Procedure links both canonicalize ---
    check("a plain link resolves under orchestrator/commands/",
          command_registry.canonical_procedure("init.md") == ".eados-core/orchestrator/commands/init.md",
          failures)
    check("a ../ link resolves beside orchestrator/ (the scaffold case)",
          command_registry.canonical_procedure("../generate.md") == ".eados-core/orchestrator/generate.md",
          failures)

    # --- happy path: every available row has a pointing adapter; planned rows demand nothing ---
    check("available rows with pointing adapters are clean", P(README, GOOD) == [], failures)

    # --- a missing adapter for an available row is flagged ---
    missing = P(README, {"init": GOOD["init"]})
    check("a missing adapter is flagged",
          any("scaffold.md is missing" in p for p in missing), failures)

    # --- an adapter that does not point at ITS row's procedure is flagged (pointer contract) ---
    stale = P(README, {"init": GOOD["init"], "scaffold": "follow init.md instead"})
    check("an adapter without its canonical procedure path is flagged",
          any("does not point at its canonical procedure" in p and "generate.md" in p
              for p in stale), failures)

    # --- an orphan adapter (planned command shipping early, or a deleted row) is flagged ---
    orphan = P(README, dict(GOOD, debug="pointer -> .eados-core/orchestrator/commands/debug.md"))
    check("an orphan adapter with no available row is flagged",
          any("debug.md matches no available" in p for p in orphan), failures)

    # --- alias adapters (#241): a LIVE alias verb may ship one, pointing at its TARGET's procedure ---
    check("a live-alias adapter pointing at its target's procedure is clean",
          P(README, ALIAS_OK) == [], failures)
    wrong = P(README, dict(GOOD, secure="alias -> `.eados-core/orchestrator/generate.md`"))
    check("a live-alias adapter pointing at the WRONG procedure is flagged",
          any("secure.md is an alias adapter but does not point" in p and
              "commands/init.md" in p for p in wrong), failures)
    early = P(README, dict(GOOD, later="alias -> `.eados-core/orchestrator/commands/debug.md`"))
    check("a planned-alias adapter is an orphan (must not ship before it flips live)",
          any("later.md matches no available" in p for p in early), failures)

    # --- parse-failure guard: a README with no parseable rows is a loud single problem ---
    none = P("nothing here\n", GOOD)
    check("an unparseable command table is reported loudly",
          len(none) == 1 and "could not parse" in none[0], failures)

    # --- live invariant: the factory's own table and adapters are in lockstep ---
    collected = []
    lint.check_command_adapters(lambda _name, msg: collected.append(msg))
    if os.path.exists(os.path.join(REPO_ROOT, ".eados-dev")):
        check(f"the shipped table and adapters are in lockstep (got {collected})",
              collected == [], failures)
    else:
        check("outside the factory checkout the check stays silent", collected == [], failures)

    if failures:
        print("test-command-adapters: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-command-adapters: OK — every available row demands a pointing adapter, live alias "
          "adapters must point at their target, orphans/non-pointers/early-planned are caught, "
          "and the live tree is in lockstep.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
