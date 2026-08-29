#!/usr/bin/env python3
"""Tests for gate-executability (eados_lint #17, issue #164): workflow.yaml's `runs:` commands
and `wired:` claims are validated against the code — a missing script, a fabricated flag, a bad
`wired` value, or a wired/GATE_EVALUATORS mismatch must each be flagged; the real tree passes;
and the exact `manifest-valid` command documented in workflow.yaml runs successfully against the
reference manifest (the drift this check exists to prevent). Dependency-free.

    python .eados-core/tools/tests/test_gate_executability.py
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint  # noqa: E402  (the module under test)

REPO_ROOT = os.path.dirname(os.path.dirname(TOOLS))

# In-memory fixtures: two known scripts, one knowing --real.
FAKE_SOURCES = {
    "tools/a.py": 'parser.add_argument("--real")\n',
    "tools/b.py": "print('no flags')\n",
}


def fake_find(rel):
    return FAKE_SOURCES.get(rel)


def gate(gid, runs, wired="external"):
    return {"id": gid, "kind": "lint", "runs": runs, "wired": wired,
            "blocking": True, "required_for": []}


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    probs = lint.gate_executability_problems

    # --- the pure check: each defect class is flagged, a clean registry is not ---
    check("clean registry yields no problems",
          probs([gate("g", "python tools/a.py <x> --real")], fake_find, set()) == [], failures)
    check("missing script flagged",
          any("missing script" in p for p in
              probs([gate("g", "python tools/ghost.py")], fake_find, set())), failures)
    check("fabricated flag flagged",
          any("does not know flag '--bogus'" in p for p in
              probs([gate("g", "python tools/a.py --bogus")], fake_find, set())), failures)
    check("flag on a flagless script flagged",
          probs([gate("g", "python tools/b.py --real")], fake_find, set()) != [], failures)
    check("manual gate makes no executable claim",
          probs([gate("g", "manual:someone decides")], fake_find, set()) == [], failures)
    check("missing/invalid wired value flagged",
          any("wired must be one of" in p for p in
              probs([{"id": "g", "runs": "manual:x"}], fake_find, set())), failures)
    check("wired: in-process without a GATE_EVALUATORS entry flagged",
          any("GATE_EVALUATORS has no entry" in p for p in
              probs([gate("g", "manual:x", wired="in-process")], fake_find, set())), failures)
    check("GATE_EVALUATORS entry without wired: in-process flagged",
          any("does not mark it wired" in p for p in
              probs([gate("g", "manual:x")], fake_find, {"g"})), failures)

    # --- wired_in_process_ids reads eados.py's registry statically ---
    ids = lint.wired_in_process_ids('GATE_EVALUATORS = {\n    "a-b": f,\n    "c": g,\n}\n')
    check("wired_in_process_ids parses dict keys", ids == {"a-b", "c"}, failures)
    check("wired_in_process_ids on sourceless text is empty",
          lint.wired_in_process_ids("nothing here") == set(), failures)

    # --- the real tree: workflow.yaml's registry is honest against the real code ---
    workflow = lint._load_spec("workflow")
    check("workflow spec parses", isinstance(workflow, dict), failures)
    real_wired = lint.wired_in_process_ids(
        lint.read(os.path.join(TOOLS, "eados.py")))
    check("eados.py declares in-process evaluators", len(real_wired) >= 3, failures)
    real_problems = probs((workflow or {}).get("gates"), lint.find_gate_script, real_wired)
    check(f"the real gate registry passes ({real_problems})", real_problems == [], failures)

    # --- acceptance (#164): the EXACT documented manifest-valid command works ---
    mv = next((g for g in (workflow or {}).get("gates", [])
               if isinstance(g, dict) and g.get("id") == "manifest-valid"), {})
    runs = str(mv.get("runs") or "")
    check("manifest-valid documents a render.py command", "render.py" in runs, failures)
    argv = runs.replace("<manifest>",
                        ".eados-core/orchestrator/examples/reference.yaml").split()
    argv[0] = sys.executable                      # "python" -> this interpreter
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=REPO_ROOT)
    check(f"documented command exits 0 (got {proc.returncode}: "
          f"{(proc.stdout + proc.stderr).strip()[:120]})", proc.returncode == 0, failures)
    check("documented command reports Check: OK", "Check: OK" in proc.stdout, failures)

    if failures:
        print("test-gate-executability: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-gate-executability: OK — the gate registry's runs/wired claims match the code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
