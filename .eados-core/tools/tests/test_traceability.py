#!/usr/bin/env python3
"""Tests for traceability — the RFC→milestone edges and the roadmap-covers-rfcs gate.
Dependency-free (runnable in the self-lint job).

    python .eados-core/tools/tests/test_traceability.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import traceability as tr  # noqa: E402  (the module under test)

ROADMAP = (
    "# Roadmap — sample\n"
    "## Milestone 1 — Bootstrap\n"
    "- [ ] 1.1 build the skeleton and CI\n"
    "## Milestone 2 — Auth\n"
    "- [ ] 2.1 implement login per RFC-0002\n"
    "- [ ] 2.2 sessions per RFC-0002\n"
    "## Milestone 3 — Search\n"
    "- [ ] 3.1 implement search per RFC-0003\n"
)

# A roadmap whose only RFC citation is the longer RFC-00021 — used to prove that coverage
# matching is on a word boundary, not a raw substring (the B1 regression).
COLLIDE = (
    "# Roadmap — substring collision\n"
    "## Milestone 1 — Indexing\n"
    "- [ ] 1.1 implement indexing per RFC-00021\n"
)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    ms = tr.parse_milestones(ROADMAP)
    check("parses 3 milestones", len(ms) == 3, failures)
    check("milestone numbers are 1,2,3", [n for n, _, _ in ms] == ["1", "2", "3"], failures)

    check("RFC-0002 is covered by M2", tr.covering_milestones(ROADMAP, "RFC-0002") == ["2"],
          failures)
    check("RFC-0003 is covered by M3", tr.covering_milestones(ROADMAP, "RFC-0003") == ["3"],
          failures)
    check("an unreferenced RFC is covered by nothing",
          tr.covering_milestones(ROADMAP, "RFC-0099") == [], failures)

    # --- B1 regression: word-boundary match, not substring (RFC-00021 ⊅ RFC-0002) ---
    check("RFC-0002 is NOT covered by a milestone that only cites RFC-00021",
          tr.covering_milestones(COLLIDE, "RFC-0002") == [], failures)
    check("the real longer id RFC-00021 still matches its milestone",
          tr.covering_milestones(COLLIDE, "RFC-00021") == ["1"], failures)
    check("a roadmap citing only RFC-00021 leaves RFC-0002 uncovered",
          tr.uncovered_rfcs(COLLIDE, ["RFC-0002"]) == ["RFC-0002"], failures)

    check("all-covered roadmap has no violations",
          tr.uncovered_rfcs(ROADMAP, ["RFC-0002", "RFC-0003"]) == [], failures)
    check("an uncovered RFC is reported",
          tr.uncovered_rfcs(ROADMAP, ["RFC-0002", "RFC-0099"]) == ["RFC-0099"], failures)

    # --- traceability_lint: dangling-edge detection (M4-B) ---
    whole = [{"pr": 12, "rfc": "RFC-0002", "milestone": "2", "commit": "abc123",
              "release": "v0.2.0"}]
    check("a whole graph has no dangling edges",
          tr.traceability_lint(ROADMAP, ["RFC-0002"], whole) == [], failures)

    def kinds(rfcs, links):
        return [k for k, _ in tr.traceability_lint(ROADMAP, rfcs, links)]

    check("an uncovered RFC -> rfc-no-milestone",
          "rfc-no-milestone" in kinds(["RFC-0099"], []), failures)
    check("an RFC with no PR -> rfc-no-pr",
          "rfc-no-pr" in kinds(["RFC-0002"], []), failures)
    check("a PR missing its RFC -> pr-no-rfc",
          "pr-no-rfc" in kinds([], [{"pr": 14, "milestone": "2"}]), failures)
    check("a release with no commit -> release-no-pr-commit",
          "release-no-pr-commit" in
          kinds([], [{"pr": 15, "rfc": "RFC-0002", "milestone": "2", "release": "v1.0.0"}]),
          failures)

    if failures:
        print("test-traceability: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-traceability: OK -- RFC->milestone edges and roadmap-covers-rfcs hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
