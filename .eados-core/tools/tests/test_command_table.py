#!/usr/bin/env python3
"""The generated contract lists the commands, and the list stays generated (#374).

`AGENTS.md` is the one file every host auto-loads — the only thing a Codex, Gemini or OpenCode
session is guaranteed to read. In a generated repo it carried **no command list at all**, while the
canonical registry lives inside the gitignored `.eados-core/`: the contract guaranteed to be read
pointed at a file guaranteed not to be committed.

The fix is one rendered section, so there is no second list to compare against — which means the
property worth gating is that it *stays* that way. A hand-written copy would be the second list, and
a **stale** command table is worse than none: it sends an agent at a command that no longer exists.

Driven against a real render (#359), because a template check alone cannot tell you the table
actually landed in the contract.

    python .eados-core/tools/tests/test_command_table.py
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
REFERENCE = os.path.join(ROOT, "orchestrator", "examples", "reference.yaml")
sys.path.insert(0, TOOLS)
import command_registry   # noqa: E402
import eados              # noqa: E402
import eados_lint as lint  # noqa: E402
import render             # noqa: E402

TMPL = os.path.join(ROOT, "templates", "AGENTS.md.tmpl")


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    registry = command_registry.load()
    check(f"the registry parses ({len(registry)})", len(registry) >= 14, failures)

    # --- the table is built from the registry, and classifies from data --------------------
    table = render.commands_table(registry)
    for c in registry:
        check(f"{c['name']}: in the table", f"`/eados {c['name']}`" in table, failures)
        check(f"{c['name']}: carries its description", c["summary"][:40] in table, failures)
    check("phases are classed as phases", "| `/eados init` | phase |" in table, failures)
    check("cross-cutting are not", "| `/eados status` | cross-cutting |" in table, failures)
    check("...and the agent-authored ones say so — the class comes from eados.AGENT_AUTHORED, so "
          "the contract and the CLI cannot disagree about what a CLI can run",
          all(f"| `/eados {n}` | agent-authored |" in table for n in eados.AGENT_AUTHORED),
          failures)
    check("a new registry entry flows through without touching this code",
          "`/eados brandnew`" in render.commands_table(
              registry + [{"name": "brandnew", "phase": "— (any)", "procedure": "x",
                           "summary": "New."}]), failures)

    # --- the gate: the section must stay GENERATED ------------------------------------------
    tmpl = lint.read(TMPL)
    check(f"the shipped template is clean "
          f"({lint.command_table_lockstep_problems(tmpl, table, registry)})",
          lint.command_table_lockstep_problems(tmpl, table, registry) == [], failures)
    literal = tmpl.replace("{{EADOS_COMMANDS}}",
                           "| Command | Class |\n|---|---|\n| `/eados init` | phase |")
    problems = lint.command_table_lockstep_problems(literal, table, registry)
    check(f"THE TRAP: a literal table typed into the template is caught ({len(problems)})",
          len(problems) == 2, failures)
    check("...naming both the missing placeholder and the hand-written row",
          any("EADOS_COMMANDS" in p for p in problems)
          and any("literal" in p for p in problems), failures)
    check("a rendered contract missing a declared command fails",
          lint.command_table_lockstep_problems(tmpl, "no table here", registry) != [], failures)

    # --- it actually lands in a rendered repo ------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "rendered")
        rc = subprocess.run([sys.executable, os.path.join(TOOLS, "render.py"), REFERENCE,
                             "--out", out], capture_output=True, text=True, timeout=240)
        check(f"the reference manifest renders ({rc.stderr[-200:] if rc.returncode else ''})",
              rc.returncode == 0, failures)
        if rc.returncode == 0:
            agents = lint.read(os.path.join(out, "AGENTS.md"))
            missing = [c["name"] for c in registry if f"`/eados {c['name']}`" not in agents]
            check(f"the RENDERED contract lists every command (missing {missing})", not missing,
                  failures)
            check("...and tells a host with no slash commands how to invoke one",
                  "eados.py commands" in agents and "completion" in agents, failures)
            check("...and says which commands a CLI cannot run",
                  "agent-authored" in agents, failures)
            check("no unresolved placeholder survived", "{{EADOS_COMMANDS}}" not in agents,
                  failures)

    if failures:
        print("test-command-table: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-command-table: OK — the generated contract lists every command with its class and "
          "description, rendered from the canonical registry, and typing a literal table into the "
          "template is caught.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
