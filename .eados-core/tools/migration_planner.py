#!/usr/bin/env python3
"""EADOS migration planner (roadmap 5.2) — READ-ONLY.

From the brownfield reader's gaps, produces an **ordered plan** of incremental migration steps —
**one logical change each** (one PR), lowest-risk / most-foundational first. It *proposes*; it does
**not** write. The actual edits happen one PR at a time inside the **write-contained sandbox** of
the `migrate` phase (M5-C), each its own reviewable, gated change. Dependency-free.

    python .eados-core/tools/migration_planner.py <repo-path>
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brownfield as bf  # noqa: E402  — the read-only reader (provides the gaps)

# Risk per standard artifact. Adding a governance doc is low-risk (additive, no code touched);
# wiring CI is medium; introducing/restructuring a source tree touches real code — high.
RISK = {
    "agent contract": "low",
    "readme": "low",
    "changelog": "low",
    "license": "low",
    "security policy": "low",
    "ADRs": "low",
    "spec": "low",
    "CI": "medium",
    "source tree": "high",
}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def plan(repo):
    """An ordered list of migration steps for `repo`'s gaps — lowest-risk / most-foundational
    first (the brownfield declared order is the tiebreaker). One step == one logical change."""
    declared = [label for label, _cands in bf.STANDARD]
    ordered = sorted(
        bf.gaps(repo),
        key=lambda label: (RISK_ORDER.get(RISK.get(label, "medium"), 1), declared.index(label)),
    )
    return [{"step": i + 1, "gap": label, "risk": RISK.get(label, "medium"),
             "action": f"add the {label}"} for i, label in enumerate(ordered)]


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: migration_planner.py <repo-path>", file=sys.stderr)
        return 2
    repo = argv[0]
    if not os.path.isdir(repo):
        print(f"migration-planner: ERROR — not a directory: {repo}", file=sys.stderr)
        return 2
    steps = plan(repo)
    if not steps:
        print(f"migration plan for {repo}: nothing to do — already meets the EADOS standard.")
        return 0
    print(f"migration plan for {repo}  ({len(steps)} step(s), one PR each, low-risk first):")
    for s in steps:
        print(f"  {s['step']}. [{s['risk']:>6}] {s['action']}")
    print("\nproposal only — edits happen one gated PR at a time in the migrate sandbox (M5-C).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
