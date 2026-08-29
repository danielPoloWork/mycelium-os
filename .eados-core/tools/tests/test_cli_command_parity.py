#!/usr/bin/env python3
"""The host-independent CLI covers every command the registry declares (#373).

Only `claude-code` ships slash-command adapters. For `codex`, `gemini`, `opencode` — and for a model
driven through a plain API, which has **no** command mechanism at all — `eados.py` *is* the command
surface. It exposed 7 of the registry's 14 verbs, with no completion and no discoverability, while
`orchestrator/commands/README.md` advertised all 14.

The assertion that matters is **equality with the registry**, not "at least the ones we remembered":
a surface that keeps its own copy of the verb list is a surface that falls behind it, which is how
this happened. So the CLI's set is compared to the registry's, and adding a row to the registry must
turn this red.

Two kinds of command, and the split is the design rather than a shortfall: `debug`/`refactor`/
`optimize`/`testcases` author code and tests — an agent does that — so the CLI *addresses* them
(procedure, summary, class) instead of pretending to run them.

    python .eados-core/tools/tests/test_cli_command_parity.py
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import command_registry   # noqa: E402
import eados              # noqa: E402
import eados_lint         # noqa: E402

SAMPLE = """
| Command | Phase | Status | Procedure | What it does |
|---|---|---|---|---|
| `/eados init` | init | **available** (M1) | [`init.md`](init.md) | Frame a new project. |
| `/eados scaffold` | scaffold | **available** | [`../generate.md`](../generate.md) | Render it. |
| `/eados status` | — (any) | **available** (M6) | [`status.md`](status.md) | Read-only doctor. |
| `/eados later` | — (any) | planned (M99) | [`later.md`](later.md) | Not yet. |
"""


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def run(args):
    proc = subprocess.run([sys.executable, os.path.join(TOOLS, "eados.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=120)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main():
    failures = []

    # --- the parser: one module, and it reads what the table says --------------------------
    parsed = command_registry.parse(SAMPLE)
    check(f"only **available** rows are commands ({[c['name'] for c in parsed]})",
          [c["name"] for c in parsed] == ["init", "scaffold", "status"], failures)
    check("a `../` procedure link resolves out of commands/",
          parsed[1]["procedure"] == ".eados-core/orchestrator/generate.md", failures)
    check("the phase column classifies, so a re-classed command needs no code change",
          command_registry.is_phase(parsed[0]) and not command_registry.is_phase(parsed[2]),
          failures)
    check("the summary is carried", parsed[0]["summary"] == "Frame a new project.", failures)
    # A cell must not cross the line break: `[^|]` swallows the next row's leading `|`, so every
    # second row silently vanishes and the table parses as half its size with nothing said. Caught
    # by the adapter gate's 4-column fixture; pinned here because it is invisible on the real table.
    check("consecutive rows all parse — no row is eaten by its predecessor",
          len(command_registry.parse(SAMPLE)) == 3, failures)
    check("a 4-column table (no description cell) still parses — widening the shared parser must "
          "not narrow the gate that used it first",
          [c["name"] for c in command_registry.parse(
              "| `/eados a` | x | **available** | [`a.md`](a.md) |\n"
              "| `/eados b` | y | **available** | [`b.md`](b.md) |\n")] == ["a", "b"], failures)

    # ONE parser: the adapter gate and the CLI must agree by construction, not by coincidence.
    check("eados_lint reads the registry through the same module",
          getattr(eados_lint, "_COMMAND_ROW_RE", None) is None, failures)
    registry = command_registry.load()
    check(f"the real registry parses ({len(registry)} commands)", len(registry) >= 14, failures)

    # --- PARITY: the CLI's set equals the registry's ----------------------------------------
    declared = {c["name"] for c in registry}
    runs_gates = set(eados.PHASES) | {"status"}
    delegates = set(eados.DELEGATES)
    rc, listing = run(["commands"])
    check(f"`eados commands` succeeds\n{listing[-300:]}", rc == 0, failures)
    classified = runs_gates | delegates | set(eados.AGENT_AUTHORED)

    # THE PARITY ASSERTION. Listing every registry row would be vacuous — the CLI renders whatever
    # the registry says, so it can never look incomplete. The property that can actually fail is
    # that every command is classified ON PURPOSE: a new verb must be put in a bucket by a human,
    # not default into the weakest one and look handled.
    check(f"every declared command is classified (unclassified: {sorted(declared - classified)})",
          declared <= classified, failures)
    check(f"...and nothing is classified that the registry does not declare "
          f"({sorted(classified - declared)})", classified <= declared, failures)
    check("no command renders as UNCLASSIFIED", "UNCLASSIFIED" not in listing, failures)

    # Proven to bite: a registry row the CLI has not been taught about must fail the check above,
    # rather than silently landing in `agent-authored`.
    unknown = {c["name"] for c in command_registry.parse(
        SAMPLE + "| `/eados brandnew` | — (any) | **available** | [`b.md`](b.md) | New. |\n")}
    check("a NEW registry row is unclassified until someone decides — the check goes red",
          not unknown <= classified, failures)

    # --- each command answers, and says which KIND of answer it is --------------------------
    for c in registry:
        name = c["name"]
        if name in runs_gates or name in delegates:
            continue
        rc, out = run([name])
        check(f"{name}: addressable — exits cleanly\n{out[-200:]}", rc == 0, failures)
        check(f"{name}: names its procedure", c["procedure"] in out, failures)
        check(f"{name}: says plainly that the CLI cannot run it, rather than appearing to work",
              "cannot run it" in out and "AGENT" in out, failures)

    for name in sorted(delegates):
        rc, out = run([name, "--help"])
        check(f"{name}: delegates to its tool (its own --help answers)\n{out[-200:]}",
              rc == 0 and "usage:" in out.lower(), failures)

    rc, out = run(["status", os.path.join(TOOLS, "..", "orchestrator", "examples",
                                          "reference.yaml")])
    check(f"the gate-running path still works\n{out[-200:]}", "phase:" in out, failures)

    # --- completion: generated from the same list, for all three shells ---------------------
    for shell in eados.COMPLETION_SHELLS:
        rc, out = run(["completion", shell])
        check(f"completion/{shell} is emitted", rc == 0 and out.strip(), failures)
        missing = [c["name"] for c in registry if c["name"] not in out]
        check(f"completion/{shell} offers every command (missing {missing})", not missing,
              failures)
        check(f"completion/{shell} defines the `eados` shim", "eados" in out, failures)
    rc, out = run(["completion", "fish"])
    check("an unsupported shell is refused, not silently empty", rc == 2 and "needs a shell" in out,
          failures)
    # Nothing is written to disk: a checked-in completion file is a second copy of the verb list,
    # and a stale completion offers commands that no longer exist.
    check("completion writes no file", not os.path.exists(os.path.join(TOOLS, "completion.sh")),
          failures)

    if failures:
        print("test-cli-command-parity: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-cli-command-parity: OK — the CLI's command set equals the registry's, one parser "
          "serves both it and the adapter gate, each command either runs or says plainly that an "
          "agent must, and completion for all three shells is generated from the same list.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
