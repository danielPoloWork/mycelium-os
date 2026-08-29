#!/usr/bin/env python3
"""Tests for seed_milestones (M11 #143) — the pure ROADMAP.md parser + the `MN — name` title /
goal-derived description / `gh api` command formatting, on in-memory fixtures and the shipped
EADOS roadmap. The `gh` shell (--run) is not touched. Dependency-free.

    python .eados-core/tools/tests/test_seed_milestones.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)                      # .eados-core/
sys.path.insert(0, TOOLS)
import seed_milestones as sm   # noqa: E402  (the module under test)

FIXTURE = """\
# Roadmap — demo

Intro prose that is not a milestone.

---

## Milestone 1 — Project bootstrap & CI

The thinnest slice that compiles, tests, and ships under the full quality bar.

- [ ] 1.1 Lay down the build system.
- [ ] 1.2 Wire the test framework.

---

## Milestone 2 — Core engine

**Goal.** Build the allocation core behind the public API.

- [x] 2.1 Pool data structure.
- [ ] 2.2 Acquire/release.
- [ ] 2.3 Thread-safety.

---

## Spec Coverage Map

| Spec | Items | Status |
|------|-------|--------|
"""


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    ms = sm.parse_roadmap(FIXTURE)

    # --- parsing: exactly the two milestones, in order; the Coverage-Map heading is not one ---
    check("parses 2 milestones", len(ms) == 2, failures)
    check("numbers in order", [m["number"] for m in ms] == [1, 2], failures)
    check("title captured after the em-dash", ms[0]["title"] == "Project bootstrap & CI", failures)
    check("second title captured", ms[1]["title"] == "Core engine", failures)

    # --- goal: first paragraph; a leading **Goal.** marker is stripped ---
    check("goal = first paragraph", ms[0]["goal"].startswith("The thinnest slice"), failures)
    check("**Goal.** marker stripped", ms[1]["goal"] == "Build the allocation core behind the public API.", failures)

    # --- items: the N.M ids under each milestone (both [ ] and [x]) ---
    check("M1 items", ms[0]["items"] == ["1.1", "1.2"], failures)
    check("M2 items incl. checked", ms[1]["items"] == ["2.1", "2.2", "2.3"], failures)

    # --- title format MN — name; description = goal + item summary ---
    check("title is 'M1 — name'", sm.milestone_title(ms[0]) == "M1 — Project bootstrap & CI", failures)
    desc2 = sm.milestone_description(ms[1])
    check("description carries the goal", desc2.startswith("Build the allocation core"), failures)
    check("description carries the item span", "2.1–2.3 (3 total)" in desc2, failures)

    # --- gh command: a runnable, shell-quoted `gh api …/milestones` create ---
    cmd = sm.gh_command(ms[0], repo="o/r")
    check("gh command targets milestones", "gh api -X POST repos/o/r/milestones" in cmd, failures)
    check("gh command sets state=open", "state=open" in cmd, failures)
    check("gh command quotes the em-dash title", "'title=M1 — Project bootstrap & CI'" in cmd, failures)
    argv = sm.gh_argv(ms[0])
    check("default argv uses :owner/:repo", "repos/:owner/:repo/milestones" in argv, failures)

    # --- no headers -> empty (caller turns this into a clear error / exit 2) ---
    check("no milestones in plain text", sm.parse_roadmap("# nothing here\n\njust prose") == [], failures)

    # --- dogfood: the shipped EADOS roadmap parses into a non-trivial MN — name set ---
    eados_roadmap = os.path.join(ROOT, "docs", "rfc", "ROADMAP.md")
    if os.path.exists(eados_roadmap):
        real = sm.parse_roadmap(open(eados_roadmap, encoding="utf-8").read())
        check("EADOS roadmap yields >= 9 milestones", len(real) >= 9, failures)
        check("every EADOS milestone has a title", all(m["title"] for m in real), failures)
        check("every EADOS title renders as 'MN — …'",
              all(sm.milestone_title(m).startswith(f"M{m['number']} — ") for m in real), failures)

    if failures:
        print("test-seed-milestones: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} seed-milestones assertion(s) broken.")
        return 1
    print("test-seed-milestones: OK - ROADMAP parse, MN — name titles, goal descriptions, gh commands (#143).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
