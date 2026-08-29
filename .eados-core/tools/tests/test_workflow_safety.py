#!/usr/bin/env python3
"""Tests for workflow-safety (eados_lint #16): the sensitive triggers `pull_request_target` and
`workflow_run` are flagged unless allow-listed; `pull_request`/`push`/`release` are fine; the real
tree (this repo's workflows + the shipped workflow templates) passes, and the allow-list is
load-bearing (without it, the one legitimate workflow_run would be flagged). Dependency-free.

    python .eados-core/tools/tests/test_workflow_safety.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint  # noqa: E402  (the module under test)

PRT = "name: x\non:\n  pull_request_target:\njobs: {}\n"
WR = "name: x\non:\n  workflow_run:\n    workflows: [eados-ci]\n    types: [completed]\njobs: {}\n"
SAFE = "name: x\non:\n  pull_request:\n  push:\n    branches: [main]\njobs: {}\n"
INLINE_BAD = "name: x\non: [push, pull_request_target]\njobs: {}\n"


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    check("pull_request_target is flagged",
          any("pull_request_target" in p for p in
              lint.workflow_safety_problems([("x.yml", PRT)], allowlist={})), failures)
    check("workflow_run is flagged",
          lint.workflow_safety_problems([("x.yml", WR)], allowlist={}) != [], failures)
    check("an inline-list sensitive trigger is flagged",
          lint.workflow_safety_problems([("x.yml", INLINE_BAD)], allowlist={}) != [], failures)
    check("pull_request / push are not flagged",
          lint.workflow_safety_problems([("x.yml", SAFE)], allowlist={}) == [], failures)
    check("an allow-listed workflow is not flagged",
          lint.workflow_safety_problems([("ok.yml", WR)], allowlist={"ok.yml": "reviewed"}) == [],
          failures)

    # the real tree — this repo's workflows + the shipped templates — passes under the real allow-list
    items = lint._workflow_items()
    check("the real tree has workflows + templates", len(items) >= 3, failures)
    check("the real tree passes workflow-safety",
          lint.workflow_safety_problems(items) == [], failures)
    # …and the allow-list is genuinely needed (empty allow-list flags the one legit workflow_run)
    check("the allow-list is load-bearing",
          any("dependabot-pin-sync" in p for p in
              lint.workflow_safety_problems(items, allowlist={})), failures)

    if failures:
        print("test-workflow-safety: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-workflow-safety: OK — sensitive triggers are gated; the real tree is clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
