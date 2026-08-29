#!/usr/bin/env python3
"""Tests for pr_metadata_check (M11 #141) — the pure PR-metadata presence evaluator on in-memory
fixtures. Exercises the required fields (assignee, one type label, milestone), the exactly-one-label
warn path, and the advisory Project signal. The `gh` shell is not touched. Dependency-free.

    python .eados-core/tools/tests/test_pr_metadata_check.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import pr_metadata_check as pmc   # noqa: E402  (the module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    def ev(**kw):
        base = {"number": 141, "assignees": ["danielPoloWork"], "labels": ["enhancement"],
                "milestone": "M11 — delivery-workflow automation", "project": []}
        base.update(kw)
        return pmc.evaluate_metadata(base)

    # --- the happy path: every required field set -> complete, no missing, no warnings ---
    full = ev()
    check("complete PR is complete", full["complete"] is True, failures)
    check("complete PR has no missing required", full["missing_required"] == [], failures)
    check("complete PR has no warnings", full["warnings"] == [], failures)
    statuses = {c["field"]: c["status"] for c in full["checks"]}
    check("assignee passes", statuses["assignee"] == "pass", failures)
    check("one label passes", statuses["label"] == "pass", failures)
    check("milestone passes", statuses["milestone"] == "pass", failures)

    # --- the empty PR: all three required fields missing ---
    bare = ev(assignees=[], labels=[], milestone=None)
    check("bare PR is incomplete", bare["complete"] is False, failures)
    check("bare PR reports all three required missing",
          set(bare["missing_required"]) == {"assignee", "label", "milestone"}, failures)

    # --- a single missing field is pinpointed ---
    no_assignee = ev(assignees=[])
    check("missing assignee -> incomplete", no_assignee["complete"] is False, failures)
    check("missing assignee is the only miss", no_assignee["missing_required"] == ["assignee"], failures)

    # --- exactly-one-label rule: >1 label is a warn, not a hard miss (the field IS present) ---
    two_labels = ev(labels=["enhancement", "bug"])
    check("two labels -> still complete (label present)", two_labels["complete"] is True, failures)
    check("two labels -> warned", two_labels["warnings"] == ["label"], failures)
    lbl = {c["field"]: c["status"] for c in two_labels["checks"]}["label"]
    check("two labels -> label status warn", lbl == "warn", failures)

    # --- Project is advisory: absent never fails, present passes ---
    proj_status = {c["field"]: c["status"] for c in full["checks"]}["project"]
    check("absent Project is advisory (never a failure)", proj_status == "advisory", failures)
    on_board = ev(project=[{"title": "EADOS"}])
    check("PR on a board -> project passes",
          {c["field"]: c["status"] for c in on_board["checks"]}["project"] == "pass", failures)
    check("PR on a board stays complete", on_board["complete"] is True, failures)

    # --- format_report is renderable and honest about (in)completeness ---
    rep_full = pmc.format_report(full)
    check("report marks complete PRs complete", "complete:" in rep_full, failures)
    check("report shows the milestone", "M11" in rep_full, failures)
    rep_bare = pmc.format_report(bare)
    check("report flags INCOMPLETE", "INCOMPLETE" in rep_bare, failures)
    check("report never claims to merge", "reports only" in rep_bare, failures)

    if failures:
        print("test-pr-metadata-check: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} PR-metadata-check assertion(s) broken.")
        return 1
    print("test-pr-metadata-check: OK - required-field presence, one-label warn, advisory Project (#141).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
