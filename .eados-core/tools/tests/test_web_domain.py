#!/usr/bin/env python3
"""Issue #149 — the first-class `web` domain + the enterprise posture. Beyond what eados_lint's
domain-completeness / cross-spec gates already enforce on every domain, this pins the web-specific
promises: the shipped profile exists, its roles resolve to real authority roles, its overlay is wired
into workflow.yaml, its differentiating NFR axes (accessibility + Core Web Vitals as hard budgets)
are present, the interview offers `web`, and the enterprise posture is surfaced as an orthogonal flag
(Q0.5 + a manifest field), not a fourth domain. Dependency-free (stdlib + the sibling YAML loader).

    python .eados-core/tools/tests/test_web_domain.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ORCH = os.path.join(os.path.dirname(TOOLS), "orchestrator")
sys.path.insert(0, TOOLS)
import render   # noqa: E402  — the hand-rolled YAML loader


def load(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return render.load_yaml(fh.read())


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    web = load(ORCH, "domains", "web.yaml")
    authority = load(ORCH, "os", "authority", "authority.yaml")
    workflow = load(ORCH, "os", "workflow", "workflow.yaml")
    questionnaire = load(ORCH, "questionnaire.yaml")

    # --- web.yaml: identity + schema completeness -----------------------------
    check("web.yaml domain id == 'web' (matches filename stem)", web.get("domain") == "web", failures)
    for key in ("display_name", "roles", "role_labels", "artifacts", "nfr_axes",
                "milestone_vocabulary", "cross_discipline_deps", "workflow_overlay"):
        check(f"web.yaml defines '{key}'", key in web, failures)

    # --- roles resolve to real authority roles (a domain activates, never invents) ----
    auth_roles = {r["name"] for r in authority.get("roles", []) if isinstance(r, dict)}
    check("web roles subset of authority roles", set(web.get("roles", [])) <= auth_roles, failures)
    check("web role_labels keys subset of authority roles",
          set((web.get("role_labels") or {}).keys()) <= auth_roles, failures)

    # --- overlay is wired into workflow.yaml ---------------------------------
    overlays = workflow.get("domain_overlays") or {}
    check("web.workflow_overlay == 'web'", web.get("workflow_overlay") == "web", failures)
    check("workflow.domain_overlays has a 'web' key", "web" in overlays, failures)

    # --- the differentiating NFR axes: accessibility + Core Web Vitals, both HARD ----
    axes = {a["axis"]: a for a in web.get("nfr_axes", []) if isinstance(a, dict)}
    check("web NFR axis 'accessibility' present", "accessibility" in axes, failures)
    check("web NFR axis 'core_web_vitals' present", "core_web_vitals" in axes, failures)
    check("accessibility is a hard budget", axes.get("accessibility", {}).get("hard_budget") is True, failures)
    check("core_web_vitals is a hard budget", axes.get("core_web_vitals", {}).get("hard_budget") is True, failures)
    # meaningfully differs from the software baseline (which has no hard budgets)
    software = load(ORCH, "domains", "software.yaml")
    sw_hard = any(a.get("hard_budget") for a in software.get("nfr_axes", []) if isinstance(a, dict))
    web_hard = any(a.get("hard_budget") for a in web.get("nfr_axes", []) if isinstance(a, dict))
    check("web has hard budgets where software has none (meaningful difference)",
          web_hard and not sw_hard, failures)

    # --- interview offers `web` and surfaces the enterprise posture ----------
    q = {}
    for phase in questionnaire.get("phases", []):
        for question in phase.get("questions", []) or []:
            if isinstance(question, dict) and question.get("id"):
                q[question["id"]] = question
    check("Q0.4 offers 'web' as a target", "web" in (q.get("Q0.4", {}).get("choices") or []), failures)
    q05 = q.get("Q0.5", {})
    check("Q0.5 (enterprise posture) exists", bool(q05), failures)
    check("Q0.5 offers standard + enterprise",
          set(q05.get("choices") or []) == {"standard", "enterprise"}, failures)
    check("Q0.5 sets governance.posture", "governance.posture" in (q05.get("sets") or []), failures)

    # --- the manifest template carries the posture flag (default standard) ----
    tmpl_text = open(os.path.join(ORCH, "project.yaml.template"), encoding="utf-8").read()
    check("project.yaml.template governance carries 'posture: standard'",
          "posture: standard" in tmpl_text, failures)

    if failures:
        print("test-web-domain: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} web-domain / enterprise-posture invariant(s) broken.")
        return 1
    print("test-web-domain: OK - web domain shipped (roles/overlay/hard NFR axes), interview offers "
          "web, enterprise is an orthogonal posture flag (#149).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
