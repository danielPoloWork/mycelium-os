#!/usr/bin/env python3
"""Tests for sync_action_pins — the template <- factory-CI action-pin fixer (companion of the
`action-pins` lockstep gate). Dependency-free (runnable in the self-lint job).

    python .eados-core/tools/tests/test_sync_action_pins.py
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import sync_action_pins as sap  # noqa: E402  (the module under test)
import eados_lint  # noqa: E402  (for the live-tree invariant)

# Distinct fake 40-hex commit SHAs (PIN_RE requires exactly 40 hex chars).
A, B, C, D = "a" * 40, "b" * 40, "c" * 40, "d" * 40

FACTORY = (
    "jobs:\n"
    "  ci:\n"
    "    steps:\n"
    f"      - uses: actions/checkout@{A} # v7.0.0\n"
    f"      - uses: actions/setup-python@{B} # v6.3.0\n"
)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def main():
    failures = []

    factory = sap.parse_pins(FACTORY)
    check("parse_pins finds both shared actions",
          factory == {"actions/checkout": (A, "v7.0.0"),
                      "actions/setup-python": (B, "v6.3.0")}, failures)

    # A template lagging on setup-python (old SHA C / v6.2.0), already matching on checkout.
    drifted = (
        f"      - uses: actions/checkout@{A} # v7.0.0\n"
        f"      - uses: actions/setup-python@{C} # v6.2.0\n"
    )
    new_text, changes = sap.rewrite(drifted, factory)
    check("rewrite records exactly the one drifted pin",
          changes == [("actions/setup-python", (C, "v6.2.0"), (B, "v6.3.0"))], failures)
    check("rewrite lands the factory SHA + version", f"setup-python@{B} # v6.3.0" in new_text,
          failures)
    check("rewrite leaves the already-matching pin untouched", f"checkout@{A} # v7.0.0" in new_text,
          failures)
    check("rewrite drops the stale SHA", C not in new_text, failures)

    # Idempotency: rewriting the fixed text changes nothing more.
    _again, changes2 = sap.rewrite(new_text, factory)
    check("rewrite is idempotent once in lockstep", changes2 == [], failures)

    # An action not shared with the factory CI is left alone (mirrors the gate's `action in fac`).
    foreign = f"      - uses: actions/setup-go@{D} # v5.0.0\n"
    foreign_out, foreign_changes = sap.rewrite(foreign, factory)
    check("an action absent from the factory CI is not touched",
          foreign_changes == [] and foreign_out == foreign, failures)

    # Floating tags (no 40-hex SHA) are exempt by design — the regex never matches them.
    floating = "      - uses: actions/checkout@v7\n"
    floating_out, floating_changes = sap.rewrite(floating, factory)
    check("a floating-tag ref is ignored", floating_changes == [] and floating_out == floating,
          failures)

    # drift() over real files: clean template -> none; lagging template -> flagged.
    with tempfile.TemporaryDirectory() as tmp:
        clean_path = os.path.join(tmp, "ci.yml.tmpl")
        drift_path = os.path.join(tmp, "drift.yml.tmpl")
        write(clean_path, FACTORY)
        write(drift_path, drifted)
        check("drift() finds nothing in a lockstep template",
              sap.drift(factory, [clean_path]) == [], failures)
        flagged = sap.drift(factory, [drift_path])
        check("drift() flags the lagging template's shared pin",
              len(flagged) == 1 and flagged[0][1] == "actions/setup-python", failures)

    # Live-tree invariant: the real repo is already in lockstep, so the fixer agrees with the gate
    # (a future Dependabot bump that drifts the templates trips this exactly as it trips the gate —
    # until `--fix` runs).
    if os.path.exists(sap.FACTORY_CI) and os.path.isdir(sap.TEMPLATE_WORKFLOWS):
        live = sap.parse_pins(eados_lint.read(sap.FACTORY_CI))
        check("the live repo templates are already in lockstep with the factory CI",
              sap.drift(live, sap.template_workflow_files()) == [], failures)

    if failures:
        print("test-sync-action-pins: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-sync-action-pins: OK -- drift detection, fix, idempotency, foreign/floating "
          "exemptions, and the live lockstep all hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
