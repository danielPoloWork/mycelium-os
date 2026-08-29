#!/usr/bin/env python3
"""Tests for the gate-coverage meta-gate + data-file-validity (eados_lint #15/#14): valid YAML
passes and invalid YAML fails the data floor; the shipped tree is fully covered; a planted ungated
file is flagged; covered and allow-listed paths are not; the registry has no stale patterns.
Dependency-free (runs in the self-lint job).

    python .eados-core/tools/tests/test_gate_coverage.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint  # noqa: E402  (the module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- data-file-validity (#14) ---
    check("valid YAML passes the data floor",
          lint.data_file_problems([("ok.yaml", "a: 1\nb:\n  - x\n  - y\n")]) == [], failures)
    check("invalid YAML fails the data floor",
          lint.data_file_problems([("bad.yaml", "a:\n\tb: 1\n")]) != [], failures)
    # #315 fail-open regression: the gate treated "did not raise" as "valid", so a file the loader
    # silently emptied passed. It must now go red when content goes in and nothing comes out.
    check("a file that parses to NOTHING despite having content fails the data floor",
          lint.data_file_problems([("vanished.yaml", "a: 1\n")]) == []
          and lint.data_file_problems([("vanished.yaml", "# only a comment\n")]) == []
          and lint._has_yaml_content("- id: L-0001\n") is True
          and lint._has_yaml_content("\n# just a comment\n---\n") is False, failures)
    # The sequence-root ledger shape is the file that exposed it — it must now READ, not vanish.
    seq_root = "- id: L-0001\n  scope: global\n- id: L-0002\n  scope: global\n"
    check("a sequence-root document is read, not silently emptied (#315)",
          lint.data_file_problems([("ledger.yaml", seq_root)]) == []
          and len(lint.render.load_yaml(seq_root)) == 2, failures)

    # --- gate-coverage (#15) against the real tree ---
    tracked = lint._tracked_files()
    if tracked is None:
        print("test-gate-coverage: SKIP — not a git checkout")
        return 0
    check("the tree is non-trivial (sanity on git ls-files)", len(tracked) > 100, failures)
    check("the shipped tree has no ungated file",
          lint.gate_coverage_problems(tracked) == [], failures)

    # the meta-gate must BITE: a new, unrecognised file class is flagged
    planted = tracked + [".eados-core/orchestrator/mystery.xyz"]
    check("a planted ungated file is flagged",
          any("mystery.xyz" in p for p in lint.gate_coverage_problems(planted)), failures)

    # covered and allow-listed paths are accepted
    check("a covered path (a tool) is not flagged",
          lint.gate_coverage_problems([".eados-core/tools/render.py"]) == [], failures)
    check("an allow-listed path (the contract) is not flagged",
          lint.gate_coverage_problems(["AGENTS.md"]) == [], failures)

    # registry hygiene: every COVERED/ALLOWLIST pattern still matches the tree
    stale = [p for p, _ in lint.GATE_COVERAGE + lint.GATE_ALLOWLIST
             if not any(lint._glob_re(p).match(t) for t in tracked)]
    check(f"no stale registry patterns (found: {stale})", stale == [], failures)

    if failures:
        print("test-gate-coverage: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-gate-coverage: OK — every tracked file is gated or consciously allow-listed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
