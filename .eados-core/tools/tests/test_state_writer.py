#!/usr/bin/env python3
"""Tests for the phase state writer (#346, ADR-0025).

Three of the six phase procedures instructed the ACTING role to write paths `authority.yaml`
denies it — `orchestrator/project.yaml` and `.eados-core/learning/runs/`, both architect-only. The
gate was right; the procedures were wrong, and because `record_run.py` is instructed by every
phase, no non-architect role could complete its own procedure. The correct behaviour was folklore:
an unstated role switch, or splitting a phase across two PRs.

A state now declares `state_writer` alongside `role`. The property worth testing is not that the
field exists — it is that the field cannot LIE: a declared writer the authority would deny is the
original defect with an extra step, so the gate must catch it.

    python .eados-core/tools/tests/test_state_writer.py
"""

import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint      # noqa: E402
import authority_check         # noqa: E402


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    workflow = lint._load_spec("workflow")
    authority = lint._load_spec("authority")
    check("both specs load", isinstance(workflow, dict) and isinstance(authority, dict), failures)
    if not failures:
        states = workflow.get("states") or []

        # --- the shipped tree is sound -------------------------------------------------------
        check("every shipped state declares a state_writer",
              all(str(s.get("state_writer") or "").strip() for s in states), failures)
        check("the shipped tree passes the gate",
              lint.state_writer_problems(workflow, authority) == [], failures)

        # --- the writer is genuinely authorized, which is the whole point --------------------
        for s in states:
            denied = authority_check.denied_paths(authority, s["state_writer"],
                                                  list(lint.STATE_PATHS))
            check(f"state '{s['id']}': its writer may actually write the state paths",
                  denied == [], failures)

        # --- and the ACTING role of the three affected phases still may not ------------------
        # If this ever passes, either authority was widened (which ADR-0025 rejected) or the
        # separation the split exists to preserve has quietly gone.
        for phase in ("design", "plan", "audit"):
            st = next((s for s in states if s.get("id") == phase), None)
            if st is None or st.get("role") == st.get("state_writer"):
                continue
            denied = authority_check.denied_paths(authority, st["role"], list(lint.STATE_PATHS))
            check(f"'{phase}': the acting role '{st['role']}' is still denied the state paths "
                  "(the separation is real, not decorative)", denied != [], failures)

        # --- THE property: the declaration cannot lie ---------------------------------------
        # #346 expressed as data — a state whose writer is the role authority denies.
        bad = copy.deepcopy(workflow)
        design = next(s for s in bad["states"] if s["id"] == "design")
        design["state_writer"] = design["role"]          # tech-lead
        probs = lint.state_writer_problems(bad, authority)
        check("a writer the authority denies is caught", probs != [], failures)
        check("…and the message names the role and the paths",
              any("tech-lead" in p and "project.yaml" in p for p in probs), failures)

        missing = copy.deepcopy(workflow)
        next(s for s in missing["states"] if s["id"] == "plan").pop("state_writer")
        check("a state with no declared writer is caught",
              any("declares no `state_writer`" in p for p in
                  lint.state_writer_problems(missing, authority)), failures)

        ghost = copy.deepcopy(workflow)
        next(s for s in ghost["states"] if s["id"] == "init")["state_writer"] = "ghost-role"
        check("a writer that is not a declared role is caught",
              any("not a role in authority.yaml" in p for p in
                  lint.state_writer_problems(ghost, authority)), failures)

        # --- the three corrected procedures say who writes ----------------------------------
        cmds = os.path.join(os.path.dirname(TOOLS), "orchestrator", "commands")
        for name in ("design", "plan", "audit"):
            text = lint.read(os.path.join(cmds, f"{name}.md"))
            check(f"commands/{name}.md names the state writer at the recording step",
                  "state_writer" in text and "ADR-0025" in text, failures)

    if failures:
        print("test-state-writer: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-state-writer: OK — every state names a writer the authority actually permits, the "
          "acting roles of design/plan/audit are still denied (the separation is real), a lying "
          "declaration is caught, and the three procedures say who writes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
