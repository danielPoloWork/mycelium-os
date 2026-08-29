#!/usr/bin/env python3
"""Tests for the brownfield reader — it maps a repo against the EADOS standard and reports gaps,
and it is READ-ONLY (it never writes into the scanned repo). Dependency-free.

    python .eados-core/tools/tests/test_brownfield.py
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import brownfield as bf  # noqa: E402  (the module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def _touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("x")


def main():
    failures = []

    # --- a partial repo: AGENTS.md + README + a source tree; everything else missing ---
    with tempfile.TemporaryDirectory() as repo:
        _touch(os.path.join(repo, "AGENTS.md"))
        _touch(os.path.join(repo, "README.md"))
        os.makedirs(os.path.join(repo, "src"))
        before = sorted(os.listdir(repo))

        g = bf.gaps(repo)
        check("present artifacts are not gaps",
              "agent contract" not in g and "readme" not in g and "source tree" not in g, failures)
        check("missing artifacts are gaps",
              all(x in g for x in ("changelog", "license", "spec", "CI", "ADRs")), failures)

        # READ-ONLY: scanning wrote nothing into the repo
        bf.scan(repo)
        bf.main([repo])
        check("the reader never writes into the scanned repo",
              sorted(os.listdir(repo)) == before, failures)

    # --- a fully-conformant repo has no gaps ---
    with tempfile.TemporaryDirectory() as repo:
        for f in ("AGENTS.md", "README.md", "CHANGELOG.md", "LICENSE", "SECURITY.md"):
            _touch(os.path.join(repo, f))
        for d in ("docs/adr", "docs/specs", ".github/workflows", "src"):
            os.makedirs(os.path.join(repo, d.replace("/", os.sep)))
        check("a conformant repo has no gaps", bf.gaps(repo) == [], failures)

    # --- naming variants are tolerated (LICENSE.txt, docs/spec) ---
    with tempfile.TemporaryDirectory() as repo:
        _touch(os.path.join(repo, "LICENSE.txt"))
        os.makedirs(os.path.join(repo, "docs", "spec"))
        g = bf.gaps(repo)
        check("LICENSE.txt counts as the license", "license" not in g, failures)
        check("docs/spec counts as the spec", "spec" not in g, failures)

    if failures:
        print("test-brownfield: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-brownfield: OK -- the standard map, the gaps, and read-only behavior hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
