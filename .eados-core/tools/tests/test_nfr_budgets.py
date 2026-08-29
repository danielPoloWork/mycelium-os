#!/usr/bin/env python3
"""Issue #249 — numeric, ENFORCED NFR budgets. Proves the honor-system boolean is gone:

  * every HARD axis of every shipped domain is TYPED (unit + direction, and the game's 60fps is
    a `seed: 60` value, not a comment);
  * the manifest records budgets as typed `spec.nfr_budgets` entries, shape-validated by
    render.nfr_budget_problems (shared with validate_manifest);
  * the `nfr-budgets` gate is evaluated IN-PROCESS by eados.py: `skipped` for a domain with no
    hard axes (the software baseline), FAIL on a missing number, a target off the axis's scale,
    a non-numeric target, or a recorded measurement that violates the direction — OK otherwise;
  * the gate attaches per-domain via domain_overlays.*.add_gates (transitions into audit), and
    the base machine is untouched.

Dependency-free.

    python .eados-core/tools/tests/test_nfr_budgets.py
"""

import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
EADOS = os.path.dirname(TOOLS)
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


def game_manifest(budgets, phase="scaffold"):
    # phase matters: the evaluator's greenfield guard skips a manifest still at `init` with no
    # adoption block (budgets arrive with Phase 5) — enforcement bites from design onward.
    return {"domain": "game", "spec": {"nfr_budgets": budgets},
            "delivery_state": {"phase": phase}}


GAME_BUDGETS = [
    {"axis": "framerate", "target": 60, "unit": "fps"},
    {"axis": "memory", "target": 512, "unit": "MB"},
    {"axis": "gpu", "target": 2000, "unit": "draw calls"},
    {"axis": "load_time", "target": 30, "unit": "s"},
]


def main():
    failures = []
    ev = eados.GATE_EVALUATORS.get("nfr-budgets")
    check("eados.py registers the nfr-budgets evaluator", ev is not None, failures)

    # --- every shipped hard axis is TYPED: unit + direction, no bare boolean left (#249) ---
    domains_dir = os.path.join(EADOS, "orchestrator", "domains")
    for path in sorted(glob.glob(os.path.join(domains_dir, "*.yaml"))):
        name = os.path.basename(path)
        if name.startswith("_"):
            continue
        axes = render.load_yaml(read(path)).get("nfr_axes") or []
        for axis in axes:
            if not (isinstance(axis, dict) and axis.get("hard_budget")):
                continue
            label = f"{name}:{axis.get('axis')}"
            check(f"hard axis {label} is typed with a unit",
                  str(axis.get("unit") or "").strip() != "", failures)
            check(f"hard axis {label} declares a direction (min|max)",
                  axis.get("direction") in ("min", "max"), failures)
    game_axes = {a.get("axis"): a
                 for a in render.load_yaml(read(domains_dir, "game.yaml")).get("nfr_axes")
                 if isinstance(a, dict)}
    check("the game 60fps is a TYPED seed value, not a comment",
          game_axes.get("framerate", {}).get("seed") == 60
          and game_axes.get("framerate", {}).get("unit") == "fps"
          and game_axes.get("framerate", {}).get("direction") == "min", failures)

    # --- the shape validator (shared by validate_manifest and the evaluator) ---
    check("a minimal valid budget list has no problems",
          render.nfr_budget_problems([{"axis": "framerate", "target": 60}]) == [], failures)
    for label, budgets, needle in [
        ("a non-list is rejected", "sixty fps", "must be a list"),
        ("a non-mapping entry is rejected", ["fast"], "must be a mapping"),
        ("an empty axis is rejected", [{"axis": "", "target": 60}], "axis is missing"),
        ("a missing target is rejected", [{"axis": "framerate"}], "target must be a number"),
        ("a boolean target is rejected", [{"axis": "framerate", "target": True}],
         "target must be a number"),
        ("a non-numeric measured is rejected",
         [{"axis": "framerate", "target": 60, "measured": "slow"}], "must be a number"),
        ("an unknown key is rejected", [{"axis": "framerate", "target": 60, "vibe": "fast"}],
         "not a recognized key"),
    ]:
        check(f"nfr_budget_problems: {label}",
              any(needle in p for p in render.nfr_budget_problems(budgets)), failures)
    bad = render.validate_manifest({"spec": {"nfr_budgets": "nope"}},
                                   render.build_context({})[0])
    check("validate_manifest wires the shape check in",
          any("nfr_budgets" in p for p in bad), failures)

    # --- the evaluator: skipped / FAIL / OK semantics (the enforcement) ---
    mark, detail = ev({"domain": "software", "delivery_state": {"phase": "scaffold"}}, {})
    check("software (no hard axes) -> skipped", mark == "skipped", failures)
    # the greenfield guard: a game manifest still at init (no adoption) is not yet in scope —
    # budgets arrive with Phase 5; eados.py init stays green (the adoption-recorded precedent)
    mark, _ = ev({"domain": "game", "spec": {}}, {})
    check("a greenfield game manifest at init -> skipped (budgets arrive with Phase 5)",
          mark == "skipped", failures)
    mark, detail = ev({"domain": "game", "spec": {},
                       "adoption": {"goals": ["audit"]},
                       "delivery_state": {"phase": "init"}}, {})
    check("an ADOPTED game manifest at init IS held to the bar -> FAIL",
          mark == "FAIL" and "no recorded budget" in detail, failures)
    mark, detail = ev({"domain": "game", "spec": {},
                       "delivery_state": {"phase": "scaffold"}}, {})
    check("a game manifest with NO budgets -> FAIL",
          mark == "FAIL" and "no recorded budget" in detail, failures)
    mark, _ = ev(game_manifest(GAME_BUDGETS), {})
    check("a game manifest with all four hard budgets -> OK", mark == "OK", failures)
    partial = [b for b in GAME_BUDGETS if b["axis"] != "gpu"]
    mark, detail = ev(game_manifest(partial), {})
    check("a missing hard axis (gpu) -> FAIL naming it",
          mark == "FAIL" and "gpu" in detail, failures)
    violated = [dict(b) for b in GAME_BUDGETS]
    violated[0]["measured"] = 45          # framerate direction: min — 45 < 60 violates
    mark, detail = ev(game_manifest(violated), {})
    check("a measured 45 fps against a min-60 budget -> FAIL 'violates'",
          mark == "FAIL" and "violates" in detail, failures)
    satisfied = [dict(b) for b in GAME_BUDGETS]
    satisfied[0]["measured"] = 72
    satisfied[1]["measured"] = 480        # memory direction: max — 480 <= 512 satisfies
    mark, _ = ev(game_manifest(satisfied), {})
    check("satisfied measurements (72 fps, 480 MB) -> OK", mark == "OK", failures)
    adjective = [dict(GAME_BUDGETS[0], target="fast")] + GAME_BUDGETS[1:]
    mark, detail = ev(game_manifest(adjective), {})
    check("an adjective target on a numeric axis -> FAIL 'must be numeric'",
          mark == "FAIL" and "must be numeric" in detail, failures)

    # --- yamlmini fidelity: unquoted decimals arrive as STRINGS — the gate coerces them ---
    string_decimals = [dict(GAME_BUDGETS[0], target="60", measured="59.5")] + GAME_BUDGETS[1:]
    mark, detail = ev(game_manifest(string_decimals), {})
    check("string-decimal target/measured are coerced, and 59.5 < 60 min -> FAIL 'violates'",
          mark == "FAIL" and "violates" in detail, failures)
    string_ok = [dict(GAME_BUDGETS[0], target="60", measured="61.5")] + GAME_BUDGETS[1:]
    mark, _ = ev(game_manifest(string_ok), {})
    check("coerced string-decimals that satisfy the budget -> OK", mark == "OK", failures)

    # --- web: the scale axis (accessibility) and the composite axis (Core Web Vitals) ---
    def web_manifest(budgets):
        return {"domain": "web", "spec": {"nfr_budgets": budgets},
                "delivery_state": {"phase": "scaffold"}}

    web_full = [
        {"axis": "accessibility", "target": "AA"},
        {"axis": "core_web_vitals", "metric": "LCP", "target": 2.5, "unit": "s"},
        {"axis": "core_web_vitals", "metric": "INP", "target": 200, "unit": "ms"},
        {"axis": "core_web_vitals", "metric": "CLS", "target": 0.1},
    ]
    mark, _ = ev(web_manifest(web_full), {})
    check("web with a scale level + per-metric CWV numbers -> OK", mark == "OK", failures)
    mark, detail = ev(web_manifest([{"axis": "accessibility", "target": "B"}] + web_full[1:]), {})
    check("an off-scale accessibility level -> FAIL 'not on the scale'",
          mark == "FAIL" and "not on the scale" in detail, failures)
    mark, detail = ev(web_manifest(web_full[:2]), {})
    check("a composite with only LCP recorded -> FAIL naming the missing metric",
          mark == "FAIL" and "composite metric" in detail
          and ("INP" in detail or "CLS" in detail), failures)
    mark, detail = ev(web_manifest(web_full + [
        {"axis": "core_web_vitals", "metric": "FID", "target": 100}]), {})
    check("an unknown composite metric (FID) -> FAIL 'unknown metric'",
          mark == "FAIL" and "unknown metric" in detail, failures)

    # --- the wiring: in-process resolution, the registry entry, the overlay attachment ---
    marks = eados.evaluate_gates(["nfr-budgets"], game_manifest(GAME_BUDGETS), {})
    check("evaluate_gates resolves nfr-budgets in-process (not `manual`)",
          marks.get("nfr-budgets") == "OK", failures)
    wf = phase_runner.load_workflow()
    gate = next((g for g in (wf.get("gates") or [])
                 if isinstance(g, dict) and g.get("id") == "nfr-budgets"), None)
    check("the nfr-budgets gate is registered", gate is not None, failures)
    if gate:
        check("nfr-budgets is wired in-process and blocking",
              gate.get("wired") == "in-process" and gate.get("blocking") is True, failures)
        check("nfr-budgets guards transitions into audit",
              gate.get("required_for") == ["audit"], failures)
    for domain in ("web", "game", "mobile"):
        merged = phase_runner.apply_overlay(wf, domain)
        into_audit = [t for t in (merged.get("transitions") or [])
                      if isinstance(t, dict) and t.get("to") == "audit"]
        check(f"the {domain} overlay attaches nfr-budgets to every transition into audit",
              into_audit and all("nfr-budgets" in (t.get("entry_gates") or [])
                                 for t in into_audit), failures)
    base_sc = [t for t in (wf.get("transitions") or [])
               if isinstance(t, dict) and t.get("from") == "scaffold"][0]
    check("the base machine (software) is untouched",
          "nfr-budgets" not in (base_sc.get("entry_gates") or []), failures)

    # --- the intake + spec surfaces carry the vocabulary ---
    interview = read(EADOS, "orchestrator", "interview.md")
    check("interview.md Q5.3 records typed spec.nfr_budgets entries",
          "spec.nfr_budgets" in interview and "nfr-budgets" in interview, failures)
    questionnaire = read(EADOS, "orchestrator", "questionnaire.yaml")
    check("questionnaire.yaml Q5.3 sets spec.nfr_budgets",
          "spec.nfr_budgets" in questionnaire, failures)
    spec_tmpl = read(EADOS, "templates", "docs", "specs", "template.md")
    check("the generated spec §3 carries the scalability/load vocabulary",
          "saturation point" in spec_tmpl and "p50/p99" in spec_tmpl, failures)

    if failures:
        print("test-nfr-budgets: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} NFR-budget invariant(s) broken.")
        return 1
    print("test-nfr-budgets: OK — hard axes are typed data, budgets are typed manifest entries, "
          "and the nfr-budgets gate enforces presence + scale + direction in-process (#249).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
