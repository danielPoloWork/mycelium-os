#!/usr/bin/env python3
"""Issue #246 — `/eados testcases`, governed test generation (ADR-0019 class 3), the last Wave-2
command and the FIRST code command owned by the `qa-engineer` (not the tech-lead). Follows the
shape `test_debug_command.py` pins, with the QA-ownership wiring: the canonical procedure states
the manifest boundary (refuse + route), the acting role (qa-engineer authors, reviewer enforces
coverage), the **untestable-target refusal**, generation **against spec §6** using the profile
test toolchain into `src/test/**`, and the **green-or-xfail-with-a-linked-defect** discipline
(a genuine failure is handed to `/eados debug`, never enshrined as a green test). The command
registry row is available and the `testcases` alias verb is live; the `/eados:testcases` adapter
points at the canonical procedure and names the qa-engineer; and the authority data (from #245)
lets the qa-engineer draft `src/test/**`. Dependency-free.

    python .eados-core/tools/tests/test_testcases_command.py
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

    # --- the canonical procedure states the class contract + the QA-generation discipline ---
    proc_path = os.path.join(commands, "testcases.md")
    check("orchestrator/commands/testcases.md exists", os.path.isfile(proc_path), failures)
    proc = read(proc_path) if os.path.isfile(proc_path) else ""
    for label, needle in [
        ("the manifest boundary (ADR-0019: refuse + route)", "manifest is required"),
        ("routes greenfield to /eados init", "/eados init"),
        ("routes an ungoverned repo to /eados adopt", "/eados adopt"),
        ("QA ownership: the qa-engineer authors", "qa-engineer"),
        ("the reviewer enforces the coverage bar", "reviewer"),
        ("a testable target is required", "testable target"),
        ("an untestable/vague target is refused (Phase 5 discipline)", "Phase 5"),
        ("generation is against the spec's §6 verification strategy", "§6"),
        ("it uses the project profile's test toolchain", "test toolchain"),
        ("tests land under src/test/**", "src/test/**"),
        ("a green suite is one accepted outcome", "green"),
        ("an xfail marks a test that reveals a defect", "xfail"),
        ("a defect is handed to /eados debug (never enshrined)", "/eados debug"),
        ("a Preconditions section (like the existing rows)", "## Preconditions"),
        ("a Boundary section (like the existing rows)", "## Boundary"),
        ("a worked example on a fixture spec §6", "## Worked example"),
        ("non-state-advancing: never writes delivery_state.phase", "delivery_state.phase"),
        ("the human merges (AGENTS.md §6)", "human opens"),
    ]:
        check(f"testcases.md states {label}", needle in proc, failures)

    # sibling boundaries: testcases delegates the fix/restructure/optimize, does not absorb them
    for sibling in ("/eados debug", "/eados refactor", "/eados optimize"):
        check(f"testcases.md draws its boundary against {sibling}", sibling in proc, failures)

    # it must NOT claim tech-lead ownership — this is the QA-owned command
    check("testcases.md does not misattribute ownership to the tech-lead",
          "tech-lead authors" not in proc, failures)

    # --- the registry: an available command row + a LIVE alias verb (no `planned` marker) ---
    readme = read(commands, "README.md")
    check("commands/README.md carries the available `/eados testcases` row",
          re.search(r"^\|\s*`/eados testcases`\s*\|[^|]*\|[^|]*\*\*available\*\*", readme, re.M)
          is not None, failures)
    alias = re.search(r"^\|\s*`testcases`\s*\|[^|]*`/eados testcases`[^|]*\|[^|]*\|([^|]*)\|",
                      readme, re.M)
    check("the alias table keeps its `testcases` row", alias is not None, failures)
    if alias:
        check("the `testcases` alias row dropped its `planned` marker (it shipped)",
              "planned" not in alias.group(1), failures)

    # --- the adapter: ships, points at the canonical procedure, names the qa-engineer owner ---
    adapter_path = os.path.join(REPO, ".claude", "commands", "eados", "testcases.md")
    if os.path.exists(os.path.join(REPO, ".eados-dev")):   # factory checkout only (like #239)
        check(".claude/commands/eados/testcases.md ships", os.path.isfile(adapter_path), failures)
        adapter = read(adapter_path) if os.path.isfile(adapter_path) else ""
        check("the adapter points at the canonical procedure",
              ".eados-core/orchestrator/commands/testcases.md" in adapter, failures)
        check("the adapter is a pointer, not a copy (no procedure body)",
              "## Procedure" not in adapter, failures)
        check("the adapter names the qa-engineer acting role",
              "qa-engineer" in adapter, failures)

    # --- authority: the qa-engineer (from #245) may draft the src/test/** the command writes ---
    authority = render.load_yaml(
        read(EADOS, "orchestrator", "os", "authority", "authority.yaml"))
    qa = next((r for r in authority.get("roles", [])
              if isinstance(r, dict) and r.get("name") == "qa-engineer"), None)
    check("authority.yaml declares the qa-engineer role", qa is not None, failures)
    if qa:
        check("qa-engineer may_draft (and owns) src/test/**",
              "src/test/**" in (qa.get("may_draft") or [])
              and "src/test/**" in (qa.get("owns") or []), failures)
    check("authority.yaml: an ownership_map row resolves src/test/** to qa-engineer (draft)",
          any(om.get("glob") == "src/test/**" and om.get("role") == "qa-engineer"
              and om.get("action") == "draft"
              for om in authority.get("ownership_map", []) if isinstance(om, dict)), failures)

    if failures:
        print("test-testcases-command: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} testcases-command invariant(s) broken.")
        return 1
    print("test-testcases-command: OK — /eados testcases ships governed (manifest boundary, "
          "untestable-target refusal, generate-against-§6, green-or-xfail-with-linked-defect, "
          "QA ownership, live registry row + adapter) (#246).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
