#!/usr/bin/env python3
"""Issue #245 — fill the QA/test-engineer persona gap and ship a worked `config/agents/`
example. Pins: `agent/qa-engineer.md` exists with the shape every persona uses (frontmatter,
Persona, What it does, Authority & boundary) and is registered in `agent/README.md`; the
`authority.yaml` role record + `ownership_map` row let it actually draft `src/test/**`; the
`agent-registry` / `authority-personas` self-lints stay clean with the new role (the
anti-fragmentation invariant the issue calls out); and the `config/agents/` worked example ships
so a maintainer can add a custom role by copying it, without reading tool source. Dependency-free.

    python .eados-core/tools/tests/test_qa_engineer_persona.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
EADOS = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import eados_lint as lint  # noqa: E402  (the module under test)
import render               # noqa: E402  — the dependency-free YAML loader


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- the persona: shipped, with the shape every role file uses ---
    persona_path = os.path.join(EADOS, "agent", "qa-engineer.md")
    check("agent/qa-engineer.md exists", os.path.isfile(persona_path), failures)
    persona = read(persona_path) if os.path.isfile(persona_path) else ""
    for label, needle in [
        ("frontmatter name", "name: qa-engineer"),
        ("frontmatter description", "description:"),
        ("a Persona section", "## Persona"),
        ("a What-it-does section", "## What it does"),
        ("an Authority & boundary section", "## Authority & boundary"),
        ("it owns src/test/**", "src/test/**"),
        ("it negotiates the spec's §6 verification strategy", "§6"),
        ("it approves nothing alone", "approve"),
        ("the human opens/merges/publishes (AGENTS.md §6)", "AGENTS.md"),
    ]:
        check(f"qa-engineer.md states {label}", needle in persona, failures)

    # --- the registry: agent/README.md lists it, both directions agree (the #202 invariant) ---
    agent_dir = os.path.join(EADOS, "agent")
    readme = read(agent_dir, "README.md")
    check("agent/README.md lists qa-engineer.md", "qa-engineer.md" in readme, failures)
    persona_rels = set()
    for cur, _dirs, files in os.walk(agent_dir):
        for fn in files:
            if fn.endswith(".md") and fn != "README.md":
                persona_rels.add(os.path.relpath(os.path.join(cur, fn), agent_dir)
                                 .replace(os.sep, "/"))
    check("the agent-registry check is clean both ways with qa-engineer present",
          lint.agent_registry_problems(readme, persona_rels) == [], failures)

    # --- authority: the role record + ownership_map row let qa-engineer draft src/test/** ---
    authority = render.load_yaml(
        read(EADOS, "orchestrator", "os", "authority", "authority.yaml"))
    qa = next((r for r in authority.get("roles", [])
              if isinstance(r, dict) and r.get("name") == "qa-engineer"), None)
    check("authority.yaml declares the qa-engineer role", qa is not None, failures)
    if qa:
        check("qa-engineer owns src/test/**", "src/test/**" in (qa.get("owns") or []), failures)
        check("qa-engineer may_draft src/test/** and docs/specs/**",
              {"src/test/**", "docs/specs/**"} <= set(qa.get("may_draft") or []), failures)
        check("qa-engineer approves nothing alone (may_approve empty)",
              not (qa.get("may_approve") or []), failures)
    check("authority.yaml: an ownership_map row resolves src/test/** to qa-engineer (draft)",
          any(om.get("glob") == "src/test/**" and om.get("role") == "qa-engineer"
              and om.get("action") == "draft"
              for om in authority.get("ownership_map", []) if isinstance(om, dict)), failures)

    # --- the anti-fragmentation invariant itself: the live authority-personas check stays clean ---
    collected = []
    lint.check_authority_personas(lambda _name, msg: collected.append(msg))
    check(f"the live authority-personas check is clean with qa-engineer (got {collected})",
          collected == [], failures)
    collected_registry = []
    lint.check_agent_registry(lambda _name, msg: collected_registry.append(msg))
    check(f"the live agent-registry check is clean with qa-engineer (got {collected_registry})",
          collected_registry == [], failures)

    # --- the worked example: copy-adaptable, and correctly invisible to both persona lints ---
    example_path = os.path.join(EADOS, "config", "agents", "example-role.md")
    check("config/agents/example-role.md exists", os.path.isfile(example_path), failures)
    example = read(example_path) if os.path.isfile(example_path) else ""
    for label, needle in [
        ("it names the two-step mechanism: copy + register", "authority.yaml"),
        ("it points at agent/README.md's shape contract", "agent/README.md"),
        ("it contains no unresolved template placeholder", "{{"),
    ]:
        if needle == "{{":
            check("the example carries no {{ placeholder tokens", needle not in example, failures)
        else:
            check(f"example-role.md states {label}", needle in example, failures)
    check("the example is inert to agent-registry (config/agents/ is not walked)",
          "example-role.md" not in persona_rels, failures)
    check("the example is inert to authority-personas (no 'example-role' role declared)",
          not any(isinstance(r, dict) and r.get("name") == "example-role"
                  for r in authority.get("roles", [])), failures)

    # --- config/README.md documents the boundary (DBA/perf-engineer/SRE stay overlays) ---
    config_readme = read(EADOS, "config", "README.md")
    for label, needle in [
        ("the example-role.md pointer", "example-role.md"),
        ("the DBA/data-engineer overlay boundary", "data-engineer"),
        ("the performance-engineer overlay boundary", "performance-engineer"),
        ("the SRE overlay boundary", "SRE"),
    ]:
        check(f"config/README.md states {label}", needle in config_readme, failures)

    if failures:
        print("test-qa-engineer-persona: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} qa-engineer-persona invariant(s) broken.")
        return 1
    print("test-qa-engineer-persona: OK — qa-engineer ships persona+authority in lockstep, both "
          "persona self-lints stay clean, and the config/agents/ worked example is present and "
          "correctly inert (#245).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
