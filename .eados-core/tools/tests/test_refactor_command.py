#!/usr/bin/env python3
"""Issue #243 — `/eados refactor`, the code-quality cross-cutting command (ADR-0019 class 3),
shipping now the #236 rename vacated the name. Follows the shape `test_debug_command.py` pins:
the canonical procedure states the manifest boundary (refuse + route), the acting roles
(tech-lead authors, reviewer holds the quality-bar verdict), the **behavior-preservation gate**
(a green suite on both sides; characterization tests first), the patterns-catalogue hand-off, and
the sibling boundaries (no defect-fix / no optimization / no migrate); the command registry row is
available and the alias verb is live; and the authority data lets the tech-lead draft the
catalogue row. Dependency-free.

    python .eados-core/tools/tests/test_refactor_command.py
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
    proc_path = os.path.join(commands, "refactor.md")
    check("orchestrator/commands/refactor.md exists", os.path.isfile(proc_path), failures)
    proc = read(proc_path) if os.path.isfile(proc_path) else ""
    for label, needle in [
        ("the manifest boundary (ADR-0019: refuse + route)", "manifest is required"),
        ("routes greenfield to /eados init", "/eados init"),
        ("routes an ungoverned repo to /eados adopt", "/eados adopt"),
        ("the tech-lead authors the restructure", "tech-lead"),
        ("the reviewer holds the quality-bar verdict", "reviewer"),
        ("behavior preservation is the guarantee", "behavior"),
        ("a named single target (open-ended scope refused)", "target per run"),
        ("the behavior-preservation gate: test-covered before restructuring",
         "test-covered before"),
        ("characterization tests fill missing coverage first", "characterization test"),
        ("guided by the patterns catalogue", "patterns catalogue"),
        ("a structural pattern earns its ADR", "ADR"),
        ("the catalogue row flips Planned -> Implemented", "Planned"),
        ("no public-API change without SemVer/ADR", "public-API"),
        ("a Preconditions section (like the existing rows)", "## Preconditions"),
        ("a Boundary section (like the existing rows)", "## Boundary"),
        ("a worked example on a fixture module", "## Worked example"),
        ("non-state-advancing: never writes delivery_state.phase", "delivery_state.phase"),
        ("the human merges (AGENTS.md §6)", "human opens"),
    ]:
        check(f"refactor.md states {label}", needle in proc, failures)

    # sibling boundaries: refactor delegates behavior/perf/standardization, does not absorb them
    for sibling in ("/eados debug", "/eados optimize", "migrate"):
        check(f"refactor.md draws its boundary against {sibling}", sibling in proc, failures)

    # --- the registry: an available command row + a LIVE alias verb (no `planned` marker) ---
    readme = read(commands, "README.md")
    check("commands/README.md carries the available `/eados refactor` row",
          re.search(r"^\|\s*`/eados refactor`\s*\|[^|]*\|[^|]*\*\*available\*\*", readme, re.M)
          is not None, failures)
    alias = re.search(r"^\|\s*`refactor`[^|]*\|[^|]*`/eados refactor`[^|]*\|[^|]*\|([^|]*)\|",
                      readme, re.M)
    check("the alias table keeps its `refactor` row", alias is not None, failures)
    if alias:
        check("the `refactor` alias row dropped its `planned` marker (it shipped)",
              "planned" not in alias.group(1), failures)

    # --- the adapter: ships and points at the canonical procedure (pointer, never a copy) ---
    adapter_path = os.path.join(REPO, ".claude", "commands", "eados", "refactor.md")
    if os.path.exists(os.path.join(REPO, ".eados-dev")):   # factory checkout only (like #239)
        check(".claude/commands/eados/refactor.md ships", os.path.isfile(adapter_path), failures)
        adapter = read(adapter_path) if os.path.isfile(adapter_path) else ""
        check("the adapter points at the canonical procedure",
              ".eados-core/orchestrator/commands/refactor.md" in adapter, failures)
        check("the adapter is a pointer, not a copy (no procedure body)",
              "## Procedure" not in adapter, failures)

    # --- authority: the tech-lead may draft the catalogue row it is told to write ---
    authority = render.load_yaml(
        read(EADOS, "orchestrator", "os", "authority", "authority.yaml"))
    tech_lead = next((r for r in authority.get("roles", [])
                      if isinstance(r, dict) and r.get("name") == "tech-lead"), {})
    check("authority.yaml: tech-lead may_draft docs/patterns/**",
          "docs/patterns/**" in (tech_lead.get("may_draft") or []), failures)
    check("authority.yaml: an ownership_map row resolves docs/patterns/** to the tech-lead (draft)",
          any(om.get("glob") == "docs/patterns/**" and om.get("role") == "tech-lead"
              and om.get("action") == "draft"
              for om in authority.get("ownership_map", []) if isinstance(om, dict)), failures)

    if failures:
        print("test-refactor-command: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} refactor-command invariant(s) broken.")
        return 1
    print("test-refactor-command: OK — /eados refactor ships governed (manifest boundary, "
          "behavior-preservation gate, patterns-catalogue hand-off, sibling boundaries, live "
          "registry row + pointer adapter, tech-lead authority) (#243).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
