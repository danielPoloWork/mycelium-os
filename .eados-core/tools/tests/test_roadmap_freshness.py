#!/usr/bin/env python3
"""Tests for eados_lint's `roadmap-freshness` gate (#237) — every milestone the CHANGELOG
documents as RELEASED must have a done row in ROADMAP.md's status table, so a milestone can no
longer ship undocumented (the M10–M14 gap this issue closed). Dependency-free.

    python .eados-core/tools/tests/test_roadmap_freshness.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as el  # noqa: E402  (the module under test)

REPO_ROOT = os.path.dirname(el.ROOT)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    P = el.roadmap_freshness_problems

    # --- a released milestone with a done row is fresh ---
    check("a released, documented milestone has no problems",
          P("## [1.0.0] - x\n\n- item (#5, M1)\n",
            "| **M1 — foundation** | ✅ **done** |\n") == [], failures)

    # --- a released milestone with NO roadmap row is flagged (the M10-M14 regression class) ---
    missing = P("## [1.0.0] - x\n\n- item (#5, M1)\n", "no milestone rows here\n")
    check("a released milestone with no roadmap row is flagged",
          len(missing) == 1 and "M1" in missing[0], failures)

    # --- a roadmap row present but not marked done (no checkmark on the same line) still flags ---
    not_done = P("## [1.0.0] - x\n\n- item (#5, M1)\n",
                 "| **M1 — foundation** | 🚧 in progress |\n")
    check("a roadmap row with no ✅ on the same line is still flagged",
          len(not_done) == 1 and "M1" in not_done[0], failures)

    # --- multiple missing milestones are named together, sorted ---
    multi = P("## [1.0.0] - x\n\n- a (#5, M2)\n- b (#6, M1)\n", "nothing here\n")
    check("multiple missing milestones are reported sorted",
          len(multi) == 1 and "M1, M2" in multi[0], failures)

    # --- an already-done milestone plus a newly-released undocumented one: only the gap flags ---
    partial = P("## [1.0.0] - x\n\n- a (#5, M1)\n- b (#6, M2)\n",
                "| **M1 — foundation** | ✅ **done** |\n")
    check("only the undocumented milestone is flagged when another is already fresh",
          len(partial) == 1 and "M2" in partial[0] and "M1" not in partial[0], failures)

    # --- [Unreleased] milestone tags are exempt (tracked by their own plan doc until released) ---
    unreleased = P("## [Unreleased]\n\n- item (#9, M99)\n\n## [1.0.0] - x\n\n- item (#5, M1)\n",
                   "| **M1 — foundation** | ✅ **done** |\n")
    check("an [Unreleased] milestone tag is exempt (not yet released)",
          unreleased == [], failures)

    # --- nothing released yet -> nothing to check ---
    check("no released heading at all yields no problems",
          P("## [Unreleased]\n\n- item (#9, M1)\n", "nothing here\n") == [], failures)

    # --- an untagged CHANGELOG entry (no milestone) never forces a roadmap row ---
    check("an entry with no milestone tag forces nothing",
          P("## [1.0.0] - x\n\n- item (#5, epic #10)\n", "nothing here\n") == [], failures)

    # --- live invariant: the real repo's ROADMAP.md is fresh against its own CHANGELOG ---
    changelog_path = os.path.join(REPO_ROOT, "CHANGELOG.md")
    roadmap_path = os.path.join(el.ROOT, "docs", "rfc", "ROADMAP.md")
    if os.path.isfile(changelog_path) and os.path.isfile(roadmap_path):
        live = P(el.read(changelog_path), el.read(roadmap_path))
        check(f"the live ROADMAP.md is fresh against the live CHANGELOG.md (got: {live})",
              live == [], failures)

    if failures:
        print("test-roadmap-freshness: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-roadmap-freshness: OK -- released milestones without a roadmap done row are "
          "caught; [Unreleased] tags are exempt; the live repo is fresh.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
