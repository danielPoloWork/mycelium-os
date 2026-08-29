#!/usr/bin/env python3
"""Tests for the migration planner — it orders the brownfield gaps into incremental steps
(lowest-risk / foundational first), one logical change each, and is READ-ONLY. Dependency-free.

    python .eados-core/tools/tests/test_migration_planner.py
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import migration_planner as mp  # noqa: E402  (the module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def _touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x")


def main():
    failures = []

    # An empty repo: every standard artifact is a gap.
    with tempfile.TemporaryDirectory() as repo:
        before = sorted(os.listdir(repo))
        steps = mp.plan(repo)
        gaps_in_plan = [s["gap"] for s in steps]

        check("a plan step exists for every gap", len(steps) == len(mp.bf.STANDARD), failures)
        check("steps are numbered 1..N",
              [s["step"] for s in steps] == list(range(1, len(steps) + 1)), failures)

        # Ordering: low-risk before medium before high; the source tree (high) is last.
        risks = [mp.RISK_ORDER[s["risk"]] for s in steps]
        check("steps are ordered by non-decreasing risk", risks == sorted(risks), failures)
        check("the high-risk source tree is last", gaps_in_plan[-1] == "source tree", failures)
        check("the agent contract is among the first (foundational)",
              gaps_in_plan.index("agent contract") <= 1, failures)

        # READ-ONLY: planning wrote nothing into the repo.
        mp.main([repo])
        check("the planner never writes into the repo",
              sorted(os.listdir(repo)) == before, failures)

    # A conformant repo yields an empty plan.
    with tempfile.TemporaryDirectory() as repo:
        for f in ("AGENTS.md", "README.md", "CHANGELOG.md", "LICENSE", "SECURITY.md"):
            _touch(os.path.join(repo, f))
        for d in ("docs/adr", "docs/specs", ".github/workflows", "src"):
            os.makedirs(os.path.join(repo, d.replace("/", os.sep)))
        check("a conformant repo has an empty plan", mp.plan(repo) == [], failures)

    if failures:
        print("test-migration-planner: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-migration-planner: OK -- ordering, one-step-per-gap, and read-only behavior hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
