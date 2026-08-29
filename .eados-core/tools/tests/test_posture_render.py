#!/usr/bin/env python3
"""Issue #248 — the enterprise governance posture must MATERIALIZE, not stay prose (ADR-0015).
Proves both directions of the {{POSTURE}} / {{#IF_ENTERPRISE}} materialization:

  * `standard` (the reference manifest as shipped) renders **without** any enterprise clause and
    **without** docs/compliance/ — the greenfield default is unchanged;
  * `enterprise` (the same manifest with governance.posture: enterprise) renders the raised-bar
    clauses into AGENTS.md §3/§7/§10 AND scaffolds docs/compliance/README.md (the control
    register) — so a considered `enterprise` answer and the `standard` default no longer produce
    byte-identical repos.

Also pins the placeholder wiring (POSTURE scalar + IF_ENTERPRISE flag) and the generated
consistency_lint's posture congruence check. Dependency-free.

    python .eados-core/tools/tests/test_posture_render.py
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
EADOS = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import render  # noqa: E402

RENDER = os.path.join(TOOLS, "render.py")
REFERENCE = os.path.join(EADOS, "orchestrator", "examples", "reference.yaml")

# The enterprise-only strings that must appear in AGENTS.md ONLY under the enterprise posture.
ENTERPRISE_MARKERS = (
    "enterprise governance posture",             # §3 declaration (the lint's congruence marker)
    "Compliance docs (enterprise posture)",      # §7 bullet
    "Review (enterprise)",                       # §10 quality-bar row
    "docs/compliance/README.md",                 # the pointer to the register
)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def render_to(out, manifest_path, failures, label):
    """Render `manifest_path` into `out` (a caller-owned dir, cleaned by the caller's
    TemporaryDirectory); return True on success."""
    proc = subprocess.run([sys.executable, RENDER, manifest_path, "--out", out],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        failures.append(f"{label} render failed: {proc.stdout.decode('utf-8', 'replace')[-400:]}")
        return False
    return True


def main():
    failures = []

    # --- the wiring: POSTURE scalar (default standard) + IF_ENTERPRISE flag off the manifest ---
    scal_std, flags_std, _ = render.build_context({})
    check("POSTURE defaults to 'standard'", scal_std.get("POSTURE") == "standard", failures)
    check("IF_ENTERPRISE is falsy by default", not flags_std.get("IF_ENTERPRISE"), failures)
    scal_ent, flags_ent, _ = render.build_context({"governance": {"posture": "enterprise"}})
    check("POSTURE reflects the manifest ('enterprise')",
          scal_ent.get("POSTURE") == "enterprise", failures)
    check("IF_ENTERPRISE is true under the enterprise posture",
          flags_ent.get("IF_ENTERPRISE") is True, failures)

    # --- standard render (the reference as shipped): NO enterprise clause, NO compliance dir ---
    with tempfile.TemporaryDirectory() as std:
        if render_to(std, REFERENCE, failures, "standard"):
            agents = open(os.path.join(std, "AGENTS.md"), encoding="utf-8").read()
            for marker in ENTERPRISE_MARKERS:
                check(f"standard AGENTS.md omits the enterprise marker {marker!r}",
                      marker not in agents, failures)
            check("standard render scaffolds NO docs/compliance/",
                  not os.path.isdir(os.path.join(std, "docs", "compliance")), failures)
            # the placeholder resolved (no raw {{POSTURE}}/{{#IF_ENTERPRISE}} left behind)
            check("no raw posture placeholder leaks into standard AGENTS.md",
                  "{{POSTURE}}" not in agents and "IF_ENTERPRISE" not in agents, failures)

    # --- enterprise render (same manifest + posture: enterprise): clauses + register present ---
    ref_text = open(REFERENCE, encoding="utf-8").read()
    # inject the posture into the existing governance: block (string-level, dependency-free)
    assert "governance:\n" in ref_text, "reference.yaml has a governance: block"
    ent_text = ref_text.replace("governance:\n", "governance:\n  posture: enterprise\n", 1)
    with tempfile.TemporaryDirectory() as d:
        ent_manifest = os.path.join(d, "enterprise.yaml")
        with open(ent_manifest, "w", encoding="utf-8") as fh:
            fh.write(ent_text)
        ent = os.path.join(d, "out")
        if render_to(ent, ent_manifest, failures, "enterprise"):
            agents = open(os.path.join(ent, "AGENTS.md"), encoding="utf-8").read()
            for marker in ENTERPRISE_MARKERS:
                check(f"enterprise AGENTS.md carries the marker {marker!r}",
                      marker in agents, failures)
            register = os.path.join(ent, "docs", "compliance", "README.md")
            check("enterprise render scaffolds docs/compliance/README.md",
                  os.path.isfile(register), failures)
            if os.path.isfile(register):
                reg = open(register, encoding="utf-8").read()
                check("the register resolved its placeholders (project name in, no {{ left)",
                      "pbr-cpp-memory-pool" in reg and "{{" not in reg, failures)
            docs_index = open(os.path.join(ent, "docs", "README.md"), encoding="utf-8").read()
            check("the docs index lists docs/compliance/ under the enterprise posture",
                  "docs/compliance/" in docs_index, failures)

    # --- a bad posture value fails validation loud (not a silent standard degrade, #248) ---
    bad = render.validate_manifest({"governance": {"posture": "entrprise"}},
                                   render.build_context({})[0])
    check("a typo'd posture is rejected by validate_manifest",
          any("posture" in p and "standard|enterprise" in p for p in bad), failures)

    # --- the generated consistency_lint learned the posture↔compliance congruence check ---
    lint_src = open(os.path.join(EADOS, "templates", "tools", "consistency_lint.py"),
                    encoding="utf-8").read()
    check("the generated consistency_lint declares check_posture",
          "def check_posture" in lint_src, failures)
    check("check_posture is registered in the CHECKS list",
          "check_posture," in lint_src, failures)

    if failures:
        print("test-posture-render: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} posture-materialization invariant(s) broken.")
        return 1
    print("test-posture-render: OK — the enterprise posture materializes (AGENTS.md §3/§7/§10 "
          "clauses + docs/compliance/ register) and the standard default stays clause-free (#248).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
