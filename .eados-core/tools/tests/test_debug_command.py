#!/usr/bin/env python3
"""Issue #242 — `/eados debug`, the first cross-cutting CODE command (ADR-0019 class 3). Pins the
shape the rest of the Wave-2 class (#243/#244/#246) inherits: the canonical procedure states the
manifest boundary (refuse + route, never an ungoverned snippet chat), the acting roles (tech-lead
authors, reviewer verifies), the reproduce-FIRST discipline, the bug-ledger hand-off, and the
non-state-advancing boundary; the command registry row is available and the alias verb is live;
the authority data lets the tech-lead actually draft the ledger record; and the ledger's
documented triage vocabulary (`rejected` et al.) is honored by the generated consistency lint.
Dependency-free.

    python .eados-core/tools/tests/test_debug_command.py
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
EADOS = os.path.dirname(TOOLS)
REPO = os.path.dirname(EADOS)
sys.path.insert(0, TOOLS)
import render  # noqa: E402  — the dependency-free YAML loader


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    commands = os.path.join(EADOS, "orchestrator", "commands")

    # --- the canonical procedure states the class contract like the existing rows ---
    proc_path = os.path.join(commands, "debug.md")
    check("orchestrator/commands/debug.md exists", os.path.isfile(proc_path), failures)
    proc = read(proc_path) if os.path.isfile(proc_path) else ""
    for label, needle in [
        ("the manifest boundary (ADR-0019: refuse + route)", "manifest is required"),
        ("routes greenfield to /eados init", "/eados init"),
        ("routes an ungoverned repo to /eados adopt", "/eados adopt"),
        ("the tech-lead authors the fix", "tech-lead"),
        ("the reviewer verifies", "reviewer"),
        ("reproduce-first: a failing test before any fix", "failing test"),
        ("no fix without a red reproduction", "no fix ships without a red reproduction"),
        ("the root cause is recorded, not the symptom", "root cause"),
        ("the reproduction stays as the regression guard", "regression guard"),
        ("the ledger record lands under docs/bugs/", "docs/bugs/"),
        ("the triage trail statuses are named", "cannot-reproduce"),
        ("a Preconditions section (like the existing rows)", "## Preconditions"),
        ("a Boundary section (like the existing rows)", "## Boundary"),
        ("a worked example on a fixture defect", "## Worked example"),
        ("non-state-advancing: never writes delivery_state.phase", "delivery_state.phase"),
        ("the human merges (AGENTS.md §6)", "human opens"),
    ]:
        check(f"debug.md states {label}", needle in proc, failures)

    # --- the registry: an available command row + a LIVE alias verb (no `planned` marker) ---
    readme = read(commands, "README.md")
    check("commands/README.md carries the available `/eados debug` row",
          re.search(r"^\|\s*`/eados debug`\s*\|[^|]*\|[^|]*\*\*available\*\*", readme, re.M)
          is not None, failures)
    alias = re.search(r"^\|\s*`debug`\s*\|[^|]*`/eados debug`[^|]*\|[^|]*\|([^|]*)\|", readme, re.M)
    check("the alias table keeps its `debug` row", alias is not None, failures)
    if alias:
        check("the `debug` alias row dropped its `planned` marker (it shipped)",
              "planned" not in alias.group(1), failures)

    # --- the adapter: ships and points at the canonical procedure (pointer, never a copy) ---
    adapter_path = os.path.join(REPO, ".claude", "commands", "eados", "debug.md")
    if os.path.exists(os.path.join(REPO, ".eados-dev")):   # factory checkout only (like #239)
        check(".claude/commands/eados/debug.md ships", os.path.isfile(adapter_path), failures)
        adapter = read(adapter_path) if os.path.isfile(adapter_path) else ""
        check("the adapter points at the canonical procedure",
              ".eados-core/orchestrator/commands/debug.md" in adapter, failures)
        check("the adapter is a pointer, not a copy (no procedure body)",
              "## Procedure" not in adapter, failures)

    # --- authority: the tech-lead may draft the ledger record it is told to write ---
    authority = render.load_yaml(
        read(EADOS, "orchestrator", "os", "authority", "authority.yaml"))
    tech_lead = next((r for r in authority.get("roles", [])
                      if isinstance(r, dict) and r.get("name") == "tech-lead"), {})
    check("authority.yaml: tech-lead may_draft docs/bugs/**",
          "docs/bugs/**" in (tech_lead.get("may_draft") or []), failures)
    check("authority.yaml: an ownership_map row resolves docs/bugs/** to the tech-lead (draft)",
          any(om.get("glob") == "docs/bugs/**" and om.get("role") == "tech-lead"
              and om.get("action") == "draft"
              for om in authority.get("ownership_map", []) if isinstance(om, dict)), failures)

    # --- vocabulary congruence: every triage status the ledger templates document is one the
    #     generated consistency lint accepts (the `rejected` drift, found shipping #242) ---
    lint_text = read(EADOS, "templates", "tools", "consistency_lint.py")
    m = re.search(r"BUG_STATUSES\s*=\s*\{([^}]*)\}", lint_text)
    check("the generated lint declares BUG_STATUSES", m is not None, failures)
    statuses = set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()
    for status in ("rejected", "cannot-reproduce", "duplicate", "fixed"):
        check(f"documented ledger status '{status}' is in the generated lint's vocabulary",
              status in statuses, failures)

    if failures:
        print("test-debug-command: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} debug-command invariant(s) broken.")
        return 1
    print("test-debug-command: OK — /eados debug ships governed (manifest boundary, "
          "reproduce-first, ledger hand-off, live registry row + pointer adapter, tech-lead "
          "authority) and the ledger vocabulary is congruent (#242).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
