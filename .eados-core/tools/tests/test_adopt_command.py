#!/usr/bin/env python3
"""Issue #247 — `/eados adopt`, the brownfield adoption intake (ADR-0021). Pins the whole route:
the canonical procedure (gap map -> goal menu -> manifest `adoption:` block -> a legal, human-gated
route), the registry row + pointer adapter, the workflow DATA (init->audit / init->migrate edges
gated on manifest-valid + adoption-recorded; the gate registry entry wired in-process), the
`adoption-recorded` evaluator semantics (absent -> skipped so greenfield stays green; malformed ->
FAIL; valid -> OK), the manifest validator (`render.adoption_problems` accept/reject cases +
KNOWN_SECTIONS/PROVENANCE_EXEMPT), and checkpoint-chain legality (a confirmed init->audit /
init->migrate chain passes; the greenfield pipeline is untouched). Dependency-free.

    python .eados-core/tools/tests/test_adopt_command.py
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
EADOS = os.path.dirname(TOOLS)
REPO = os.path.dirname(EADOS)
sys.path.insert(0, TOOLS)
import render        # noqa: E402
import eados         # noqa: E402
import phase_runner  # noqa: E402


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def check(label, cond, failures):
    if not cond:
        failures.append(label)


GOALS = {"governance-docs", "retro-design", "audit", "migrate", "bugfix"}
VALID_ADOPTION = {"goals": ["audit", "migrate"],
                  "gap_map_ref": "orchestrator/adoption-gap-map.md",
                  "provenance": {"goals": "asked", "gap_map_ref": "imported"}}


def main():
    failures = []
    commands = os.path.join(EADOS, "orchestrator", "commands")

    # --- the canonical procedure states the intake contract ---
    proc_path = os.path.join(commands, "adopt.md")
    check("orchestrator/commands/adopt.md exists", os.path.isfile(proc_path), failures)
    proc = read(proc_path) if os.path.isfile(proc_path) else ""
    for label, needle in [
        ("it is init's brownfield sibling, an intake not a phase", "not a phase"),
        ("the enterprise-architect owns it", "enterprise-architect"),
        ("a greenfield target is refused and routed to init", "/eados init"),
        ("an already-governed repo routes to status", "/eados status"),
        ("the gap map is read-only (brownfield.py)", "brownfield.py"),
        ("the goal menu is the closed ADR-0021 vocabulary", "governance-docs"),
        ("retro-design is a goal", "retro-design"),
        ("bugfix routes to /eados debug", "/eados debug"),
        ("the adoption block is recorded", "adoption:"),
        ("gap_map_ref names the captured report", "gap_map_ref"),
        ("interview in the maintainer's language (AGENTS.md §2)", "maintainer's language"),
        ("the earliest pipeline target wins with multiple goals", "earliest"),
        ("routes are human-gated; the maintainer confirms", "human-gated"),
        ("the greenfield pipeline is untouched", "greenfield pipeline is untouched"),
        ("a Preconditions section (like init)", "## Preconditions"),
        ("a Boundary section (like init)", "## Boundary"),
        ("a Backward compatibility section (like init)", "## Backward compatibility"),
        ("a worked example on a fixture repo", "## Worked example"),
    ]:
        check(f"adopt.md states {label}", needle in proc, failures)

    # --- the registry row + the pointer adapter ---
    readme = read(commands, "README.md")
    check("commands/README.md carries the available `/eados adopt` row",
          re.search(r"^\|\s*`/eados adopt`\s*\|[^|]*\|[^|]*\*\*available\*\*", readme, re.M)
          is not None, failures)
    adapter_path = os.path.join(REPO, ".claude", "commands", "eados", "adopt.md")
    if os.path.exists(os.path.join(REPO, ".eados-dev")):   # factory checkout only (like #239)
        check(".claude/commands/eados/adopt.md ships", os.path.isfile(adapter_path), failures)
        adapter = read(adapter_path) if os.path.isfile(adapter_path) else ""
        check("the adapter points at the canonical procedure",
              ".eados-core/orchestrator/commands/adopt.md" in adapter, failures)
        check("the adapter is a pointer, not a copy (no procedure body)",
              "## Procedure" not in adapter, failures)
        check("the adapter names the enterprise-architect", "enterprise-architect" in adapter,
              failures)

    # --- the workflow DATA: the adoption edges + the gate registry entry ---
    wf = phase_runner.load_workflow()
    by_to = {t.get("to"): t for t in phase_runner.legal_transitions(wf, "init")}
    for target in ("audit", "migrate"):
        t = by_to.get(target)
        check(f"workflow.yaml declares init -> {target}", t is not None, failures)
        if t:
            check(f"init -> {target} is gated on manifest-valid + adoption-recorded",
                  t.get("entry_gates") == ["manifest-valid", "adoption-recorded"], failures)
            check(f"init -> {target} is human-gated", t.get("human_gate") is True, failures)
    gate = next((g for g in (wf.get("gates") or [])
                 if isinstance(g, dict) and g.get("id") == "adoption-recorded"), None)
    check("the adoption-recorded gate is registered", gate is not None, failures)
    if gate:
        check("adoption-recorded is wired in-process (never decorative, ADR-0021 §4)",
              gate.get("wired") == "in-process", failures)
        check("adoption-recorded is blocking", gate.get("blocking") is True, failures)
        check("adoption-recorded declares required_for [audit, migrate]",
              gate.get("required_for") == ["audit", "migrate"], failures)

    # --- the evaluator: absent -> skipped (greenfield green); malformed -> FAIL; valid -> OK ---
    check("eados.py registers the adoption-recorded evaluator",
          "adoption-recorded" in eados.GATE_EVALUATORS, failures)
    mark, _ = eados.GATE_EVALUATORS["adoption-recorded"]({"identity": {}}, {})
    check("absent adoption block -> skipped (a greenfield project stays green)",
          mark == "skipped", failures)
    mark, detail = eados.GATE_EVALUATORS["adoption-recorded"](
        {"adoption": {"goals": ["world-domination"]}}, {})
    check("a malformed adoption block -> FAIL", mark == "FAIL", failures)
    mark, _ = eados.GATE_EVALUATORS["adoption-recorded"]({"adoption": dict(VALID_ADOPTION)}, {})
    check("a valid adoption block -> OK", mark == "OK", failures)
    marks = eados.evaluate_gates(["adoption-recorded"], {"adoption": dict(VALID_ADOPTION)}, {})
    check("evaluate_gates resolves adoption-recorded in-process (not `manual`)",
          marks.get("adoption-recorded") == "OK", failures)

    # --- the validator: accept the minimal valid block; reject each malformation ---
    check("render KNOWN_SECTIONS admits `adoption`", "adoption" in render.KNOWN_SECTIONS, failures)
    check("`adoption` is PROVENANCE_EXEMPT (its provenance lives inside, ADR-0021 §2)",
          "adoption" in render.PROVENANCE_EXEMPT, failures)
    check("the goal menu is the closed ADR-0021 vocabulary",
          render._ADOPTION_GOALS == GOALS, failures)
    check("a minimal valid block has no problems",
          render.adoption_problems(dict(VALID_ADOPTION)) == [], failures)
    for label, block, needle in [
        ("an unknown goal is rejected",
         dict(VALID_ADOPTION, goals=["audit", "webscale"]), "closed menu"),
        ("empty goals are rejected", dict(VALID_ADOPTION, goals=[]), "non-empty"),
        ("a missing gap_map_ref is rejected",
         {k: v for k, v in VALID_ADOPTION.items() if k != "gap_map_ref"}, "gap_map_ref"),
        ("an unknown key inside adoption is rejected",
         dict(VALID_ADOPTION, mood="optimistic"), "not a recognized key"),
        ("a bad provenance value is rejected",
         dict(VALID_ADOPTION, provenance={"goals": "guessed"}), "asked|defaulted|imported"),
        ("provenance without a goals entry is rejected",
         dict(VALID_ADOPTION, provenance={"gap_map_ref": "imported"}), "no entry for 'goals'"),
        ("a non-mapping block is rejected", "adopt me", "must be a mapping"),
        ("an unhashable (nested-mapping) goal is a problem, never a TypeError",
         dict(VALID_ADOPTION, goals=[{"retro": True}]), "closed menu"),
        ("an unhashable provenance value is a problem, never a TypeError",
         dict(VALID_ADOPTION, provenance={"goals": {"how": "asked"}}), "asked|defaulted|imported"),
    ]:
        problems = render.adoption_problems(block)
        check(f"adoption_problems: {label}", any(needle in p for p in problems), failures)

    # --- chain legality: one confirmed adoption checkpoint reaches audit/migrate; the ordinary
    #     pipeline is untouched (init->design first; init->scaffold still illegal) ---
    for target in ("audit", "migrate"):
        # #250: a human-gated checkpoint also records its gate marks (the honor-system closure),
        # and the recorded adoption must still EXIST (an OK-then-removed block is divergence)
        ds = {"adoption": dict(VALID_ADOPTION),
              "delivery_state": {"phase": target,
                                 "checkpoints": [{"from": "init", "to": target,
                                                  "confirmed_by": "owner",
                                                  "gate_results": {"manifest-valid": "OK",
                                                                   "adoption-recorded": "OK"}}]}}
        check(f"a confirmed init -> {target} checkpoint chain is legal",
              phase_runner.checkpoint_chain_problems(ds, wf) == [], failures)
        ds_unconfirmed = {"delivery_state": {"phase": target,
                                             "checkpoints": [{"from": "init", "to": target}]}}
        check(f"an UNconfirmed init -> {target} chain is rejected (human gate)",
              any("confirmed_by" in p
                  for p in phase_runner.checkpoint_chain_problems(ds_unconfirmed, wf)), failures)
    init_edges = phase_runner.legal_transitions(wf, "init")
    check("the greenfield default is untouched: init -> design stays the first declared edge",
          init_edges and init_edges[0].get("to") == "design", failures)
    check("init -> scaffold stays illegal (no phase-skip smuggled in)",
          phase_runner.propose_transition(wf, "init", "scaffold") is None, failures)

    # --- the manifest template documents the optional block ---
    template = read(EADOS, "orchestrator", "project.yaml.template")
    check("project.yaml.template documents the optional adoption block",
          "adoption" in template and "gap_map_ref" in template, failures)

    if failures:
        print("test-adopt-command: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} adopt-route invariant(s) broken.")
        return 1
    print("test-adopt-command: OK — /eados adopt ships governed end-to-end: intake procedure + "
          "adapter, adoption edges legal by data (human-gated, in-process gate), evaluator "
          "skipped/FAIL/OK semantics, validator accept/reject, chain legality, greenfield "
          "untouched (#247, ADR-0021).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
