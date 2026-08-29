#!/usr/bin/env python3
"""Tests for eados_lint's `version-lockstep` gate — EADOS dogfooding the gate it ships (roadmap
6.7 / F4). Dependency-free.

    python .eados-core/tools/tests/test_version_lockstep.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as el  # noqa: E402  (the module under test)

REPO_ROOT = os.path.dirname(el.ROOT)

CHANGELOG = (
    "## [Unreleased]\n\n### Added\n\n"
    "## [2.0.0] - 2026-06-23\n\nthe latest is **v2.0.0**\n"
)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # in lockstep: every badge + the prose match the latest released heading
    ok = el.version_lockstep_problems(
        CHANGELOG, [("README.md", "release-v2.0.0"), ("zh/README.md", "release-v2.0.0")])
    check("aligned badges + prose -> no problems", ok == [], failures)

    # a drifted badge is flagged (and only that one)
    drift = el.version_lockstep_problems(
        CHANGELOG, [("README.md", "release-v2.0.0"), ("ja/README.md", "release-v1.9.0")])
    check("a drifted badge is flagged", len(drift) == 1 and "ja/README.md" in drift[0], failures)

    # a missing badge is flagged
    missing = el.version_lockstep_problems(CHANGELOG, [("README.md", "no badge here")])
    check("a missing badge is flagged", any("no `release-v" in p for p in missing), failures)

    # the CHANGELOG 'latest is' prose drifting from the heading is flagged
    prose = el.version_lockstep_problems(
        "## [2.0.0] - x\n\nthe latest is **v1.0.0**\n", [("README.md", "release-v2.0.0")])
    check("prose drift from the latest heading is flagged",
          any("the latest is v1.0.0" in p for p in prose), failures)

    # newest-first: [Unreleased] is skipped; the first X.Y.Z heading is the lock target
    multi = el.version_lockstep_problems(
        "## [Unreleased]\n## [2.1.0] - x\n## [2.0.0] - y\n", [("README.md", "release-v2.1.0")])
    check("the latest (first) release heading is the lock target", multi == [], failures)

    # no released heading at all -> a clear single problem
    none = el.version_lockstep_problems("## [Unreleased]\n\n### Added\n", [("README.md", "release-v2.0.0")])
    check("no released heading is reported", len(none) == 1 and "no released" in none[0], failures)

    # --- live invariant: the real repo's READMEs are in lockstep with its CHANGELOG ---
    changelog_path = os.path.join(REPO_ROOT, "CHANGELOG.md")
    if os.path.isfile(changelog_path):
        readmes = []
        en = os.path.join(REPO_ROOT, "README.md")
        if os.path.isfile(en):
            readmes.append(("README.md", el.read(en)))
        i18n = os.path.join(el.ROOT, "docs", "i18n")
        if os.path.isdir(i18n):
            for sub in sorted(os.listdir(i18n)):
                rp = os.path.join(i18n, sub, "README.md")
                if os.path.isfile(rp):
                    readmes.append((f"docs/i18n/{sub}/README.md", el.read(rp)))
        live = el.version_lockstep_problems(el.read(changelog_path), readmes)
        check(f"the live repo is in version lockstep (got: {live})", live == [], failures)

    if failures:
        print("test-version-lockstep: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-version-lockstep: OK -- badges + prose lock to the latest release; drift/missing/"
          "no-release are caught; the live repo is in lockstep.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
