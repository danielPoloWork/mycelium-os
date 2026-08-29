#!/usr/bin/env python3
"""Tests for the worked-example decision surfaces (#224) — the `examples:` blocks are shape-valid
few-shot policy (ask/default, adopt/decline/escalate, apply/skip), and eados_lint's `examples` shape
check catches every malformation. Dependency-free.

    python .eados-core/tools/tests/test_examples.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint  # noqa: E402  (the shape checker under test)
import render              # noqa: E402  (the dependency-free loader)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- a well-formed block yields no problems ------------------------------
    good = {"examples": {"verdicts": ["a", "b"], "cases": [
        {"input": "i1", "verdict": "a", "why": "w"},
        {"input": "i2", "verdict": "a", "why": "w"},
        {"input": "i3", "verdict": "b", "why": "w"},
        {"input": "i4", "verdict": "b", "why": "w"}]}}
    check("a well-formed examples block yields no problems",
          lint.examples_problems("t", good) == [], failures)

    # --- each defect is caught -----------------------------------------------
    check("a missing examples block is flagged",
          any("no `examples:`" in p for p in lint.examples_problems("t", {})), failures)
    check("< 2 verdicts is flagged",
          any("verdicts" in p for p in
              lint.examples_problems("t", {"examples": {"cases": good["examples"]["cases"]}})), failures)
    missing_why = {"examples": {"verdicts": ["a", "b"], "cases": [
        {"input": "i", "verdict": "a"},
        {"input": "i", "verdict": "a", "why": "w"},
        {"input": "i", "verdict": "b", "why": "w"},
        {"input": "i", "verdict": "b", "why": "w"}]}}
    check("a case missing 'why' is flagged",
          any("missing/empty 'why'" in p for p in lint.examples_problems("t", missing_why)), failures)
    bad_verdict = {"examples": {"verdicts": ["a", "b"], "cases": [
        {"input": "i", "verdict": "zzz", "why": "w"},
        {"input": "i", "verdict": "a", "why": "w"},
        {"input": "i", "verdict": "a", "why": "w"},
        {"input": "i", "verdict": "b", "why": "w"},
        {"input": "i", "verdict": "b", "why": "w"}]}}
    check("a verdict outside the declared set is flagged",
          any("not in verdicts" in p for p in lint.examples_problems("t", bad_verdict)), failures)
    thin = {"examples": {"verdicts": ["a", "b"], "cases": [
        {"input": "i", "verdict": "a", "why": "w"},
        {"input": "i", "verdict": "b", "why": "w"}]}}   # 1 each -> no verdict reaches >= 2
    check("< 2 cases per verdict (not a real decision surface) is flagged",
          any("cover >= 2 verdicts" in p for p in lint.examples_problems("t", thin)), failures)

    # --- the three real surfaces are shape-valid -----------------------------
    for rel in lint.EXAMPLE_FILES:
        data = render.load_yaml(lint.read(os.path.join(lint.ROOT, *rel.split("/"))))
        check(f"{rel} is a shape-valid examples surface",
              lint.examples_problems(rel, data) == [], failures)

    # --- contribution verdicts == its own disposition ids (cross-consistency) ---
    contrib = render.load_yaml(lint.read(os.path.join(
        lint.ROOT, "orchestrator", "os", "contribution", "contribution.yaml")))
    disp_ids = {d.get("id") for d in contrib.get("dispositions", [])}
    check("contribution example verdicts are all real disposition ids",
          set(contrib["examples"]["verdicts"]) <= disp_ids, failures)

    # --- triage verdicts == its own steps[].route names (cross-consistency) ---
    triage = render.load_yaml(lint.read(os.path.join(lint.ROOT, "orchestrator", "triage.yaml")))
    check("triage example verdicts match the steps[].route names",
          set(triage["examples"]["verdicts"]) == {s.get("route") for s in triage.get("steps", [])},
          failures)

    # --- the check is wired into the lint registry ---------------------------
    check("check_examples is registered in eados_lint.CHECKS",
          lint.check_examples in lint.CHECKS, failures)

    if failures:
        print("test-examples: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} examples invariant(s) broken.")
        return 1
    print("test-examples: OK — the ask/adopt/apply decision surfaces are shape-valid data (#224).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
