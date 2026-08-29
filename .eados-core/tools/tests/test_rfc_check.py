#!/usr/bin/env python3
"""Tests for rfc_check — a complete RFC passes the rfc-approved gate; a missing section, an absent
approval, or a wrong approver each fail; a non-template (meta-design) RFC FAILs on the missing
template sections (issue #91 — that FAIL is by design, not a defect). Dependency-free (runnable in
the self-lint job).

    python .eados-core/tools/tests/test_rfc_check.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import rfc_check as rc  # noqa: E402  (the module under test)

GOOD = (
    "# RFC-0002: sample\n"
    "## Context\nthe problem.\n"
    "## Decision\nthe solution.\n"
    "## Alternatives\nrejected X because Y.\n"
    "## Consequences\ntradeoffs.\n"
    "## Approval\napproved-by: tech-lead (2026-06-21)\n"
    "## References\nnone.\n"
)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    proto = rc.load_protocol()

    check("a complete, approved RFC passes", rc.check_rfc(GOOD, proto) == [], failures)

    missing = GOOD.replace("## Alternatives\nrejected X because Y.\n", "")
    check("a missing required section fails",
          any("Alternatives" in p for p in rc.check_rfc(missing, proto)), failures)

    no_approval = GOOD.replace("approved-by: tech-lead (2026-06-21)\n", "")
    check("an absent approval record fails",
          any("approval" in p.lower() for p in rc.check_rfc(no_approval, proto)), failures)

    wrong = GOOD.replace("approved-by: tech-lead", "approved-by: reviewer")
    check("a wrong approver fails",
          any("requires" in p for p in rc.check_rfc(wrong, proto)), failures)

    # issue #91 — a repo's own meta-design RFC (not template-shaped) FAILs on the missing template
    # sections. That FAIL is by design, not a defect; the scope is documented in review-protocol.md
    # §Scope and the rfc_check docstring (no tool-behavior change — an M7 invariant).
    meta = ("# RFC-0001: meta-design\n## Summary\nx.\n"
            "## Approval\napproved-by: tech-lead (2026-06-27)\n")
    check("a non-template (meta-design) RFC fails on missing sections",
          any(p.startswith("missing required section") for p in rc.check_rfc(meta, proto)), failures)

    # the protocol references only declared authority roles / a real workflow gate (sanity)
    check("approver_role is set", bool(proto.get("approver_role")), failures)
    check("gate id is set", bool(proto.get("gate")), failures)

    if failures:
        print("test-rfc-check: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-rfc-check: OK — required sections + the approval record are enforced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
