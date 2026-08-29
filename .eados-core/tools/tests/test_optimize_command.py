#!/usr/bin/env python3
"""Issue #244 — `/eados optimize`, the measure-first performance cross-cutting command (ADR-0019
class 3). Follows the shape `test_debug_command.py` pins, plus the measurement weight: the
canonical procedure states the manifest boundary (refuse + route), the acting roles (tech-lead
authors, reviewer judges the readability cost), the **numeric-target refusal** (an adjective is
refused like Phase 5 refuses an untestable requirement), the **baseline → one change →
re-measure** measurement gate with the `docs/benchmarks/` discipline, and the sibling boundaries
(no structure-only refactor / no defect fix). The command registry row is available and the
`optimizecode` alias verb is live; the `/eados:optimize` command adapter AND the
`/eados:optimizecode` alias adapter (the second alias adapter, after `security`) both point at the
canonical procedure; and the authority data lets the tech-lead draft the benchmark record.
Dependency-free.

    python .eados-core/tools/tests/test_optimize_command.py
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

    # --- the canonical procedure states the class contract + the measurement discipline ---
    proc_path = os.path.join(commands, "optimize.md")
    check("orchestrator/commands/optimize.md exists", os.path.isfile(proc_path), failures)
    proc = read(proc_path) if os.path.isfile(proc_path) else ""
    for label, needle in [
        ("the manifest boundary (ADR-0019: refuse + route)", "manifest is required"),
        ("routes greenfield to /eados init", "/eados init"),
        ("routes an ungoverned repo to /eados adopt", "/eados adopt"),
        ("the tech-lead authors the change", "tech-lead"),
        ("the reviewer judges the readability/complexity cost", "reviewer"),
        ("measure-first is the discipline", "measure-first"),
        ("a NUMERIC target is required", "numeric target"),
        ("targets come from spec §3 / the domain nfr_axes", "nfr_axes"),
        ("an adjective ('Make it faster') is refused", "Make it faster"),
        ("a benchmark baseline is recorded", "baseline"),
        ("the docs/benchmarks discipline records the configuration", "docs/benchmarks/"),
        ("capabilities.bench off -> enabling it is step zero", "capabilities.bench"),
        ("profile with evidence, then ONE change", "one"),
        ("re-measure: accept only toward budget with the suite green", "re-measure"),
        ("before/after numbers are recorded", "before/after"),
        ("a Preconditions section (like the existing rows)", "## Preconditions"),
        ("a Boundary section (like the existing rows)", "## Boundary"),
        ("a worked example on a fixture with a bench suite", "## Worked example"),
        ("the refusal path is exercised", "Refusal path"),
        ("non-state-advancing: never writes delivery_state.phase", "delivery_state.phase"),
        ("the human merges (AGENTS.md §6)", "human opens"),
    ]:
        check(f"optimize.md states {label}", needle in proc, failures)

    # sibling boundaries: optimize delegates structure-only and defect work, does not absorb them
    for sibling in ("/eados refactor", "/eados debug"):
        check(f"optimize.md draws its boundary against {sibling}", sibling in proc, failures)

    # --- the registry: an available command row + a LIVE alias verb (no `planned` marker) ---
    readme = read(commands, "README.md")
    check("commands/README.md carries the available `/eados optimize` row",
          re.search(r"^\|\s*`/eados optimize`\s*\|[^|]*\|[^|]*\*\*available\*\*", readme, re.M)
          is not None, failures)
    alias = re.search(r"^\|\s*`optimizecode`\s*\|[^|]*`/eados optimize`[^|]*\|[^|]*\|([^|]*)\|",
                      readme, re.M)
    check("the alias table keeps its `optimizecode` row", alias is not None, failures)
    if alias:
        check("the `optimizecode` alias row dropped its `planned` marker (it shipped)",
              "planned" not in alias.group(1), failures)

    # --- adapters: the command pointer + the alias adapter, both pointing at optimize.md ---
    if os.path.exists(os.path.join(REPO, ".eados-dev")):   # factory checkout only (like #239)
        canon = ".eados-core/orchestrator/commands/optimize.md"
        cmd_adapter = os.path.join(REPO, ".claude", "commands", "eados", "optimize.md")
        check(".claude/commands/eados/optimize.md ships", os.path.isfile(cmd_adapter), failures)
        cmd_text = read(cmd_adapter) if os.path.isfile(cmd_adapter) else ""
        check("the command adapter points at the canonical procedure", canon in cmd_text, failures)
        check("the command adapter is a pointer, not a copy (no procedure body)",
              "## Procedure" not in cmd_text, failures)
        alias_adapter = os.path.join(REPO, ".claude", "commands", "eados", "optimizecode.md")
        check(".claude/commands/eados/optimizecode.md (the alias adapter) ships",
              os.path.isfile(alias_adapter), failures)
        alias_text = read(alias_adapter) if os.path.isfile(alias_adapter) else ""
        check("the alias adapter points at its target's (optimize) canonical procedure",
              canon in alias_text, failures)
        check("the alias adapter is a pointer, not a copy (no procedure body)",
              "## Procedure" not in alias_text, failures)

    # --- authority: the tech-lead may draft the benchmark record it is told to write ---
    authority = render.load_yaml(
        read(EADOS, "orchestrator", "os", "authority", "authority.yaml"))
    tech_lead = next((r for r in authority.get("roles", [])
                      if isinstance(r, dict) and r.get("name") == "tech-lead"), {})
    check("authority.yaml: tech-lead may_draft docs/benchmarks/**",
          "docs/benchmarks/**" in (tech_lead.get("may_draft") or []), failures)
    check("authority.yaml: an ownership_map row resolves docs/benchmarks/** to the tech-lead (draft)",
          any(om.get("glob") == "docs/benchmarks/**" and om.get("role") == "tech-lead"
              and om.get("action") == "draft"
              for om in authority.get("ownership_map", []) if isinstance(om, dict)), failures)

    if failures:
        print("test-optimize-command: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} optimize-command invariant(s) broken.")
        return 1
    print("test-optimize-command: OK — /eados optimize ships governed (manifest boundary, "
          "numeric-target refusal, baseline->change->re-measure gate, sibling boundaries, live "
          "registry row + command & alias adapters, tech-lead benchmark authority) (#244).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
