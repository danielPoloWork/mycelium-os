#!/usr/bin/env python3
"""Tests for authority_check — the path→role gate allows in-authority paths and denies the rest,
the glob matcher handles `**`/`*`/exact, and an unknown role errors. Dependency-free.

    python .eados-core/tools/tests/test_authority_check.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import authority_check as ac  # noqa: E402  (the module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    auth = ac.load_authority()

    # --- glob matcher: ** across dirs, * within a segment, exact files ---
    check("** matches deep paths", bool(ac._glob_re("docs/rfc/**").match("docs/rfc/a/b.md")),
          failures)
    check("** matches a direct child", bool(ac._glob_re("docs/rfc/**").match("docs/rfc/0001.md")),
          failures)
    check("prefix is respected (rfcs != rfc/)",
          not ac._glob_re("docs/rfc/**").match("docs/rfcs/x.md"), failures)
    check("exact file matches", bool(ac._glob_re("AGENTS.md").match("AGENTS.md")), failures)
    check("exact file is not a prefix", not ac._glob_re("AGENTS.md").match("AGENTS.md.bak"),
          failures)
    check("** alone matches anything", bool(ac._glob_re("**").match("any/deep/path.x")), failures)

    # --- role authority (against the real authority.yaml) ---
    check("tech-lead may write an RFC",
          ac.denied_paths(auth, "tech-lead", ["docs/rfc/0002.md"]) == [], failures)
    check("tech-lead may NOT write CI",
          ac.denied_paths(auth, "tech-lead", [".github/workflows/ci.yml"]) ==
          [".github/workflows/ci.yml"], failures)
    check("architect may write anything",
          ac.denied_paths(auth, "enterprise-architect",
                          ["src/x", ".github/workflows/ci.yml", "AGENTS.md"]) == [], failures)
    check("product-manager may write a GDD (M2-A owns docs/gdd/**)",
          ac.denied_paths(auth, "product-manager", ["docs/gdd/combat.md"]) == [], failures)
    check("reviewer may write nothing",
          ac.denied_paths(auth, "reviewer", ["docs/rfc/x.md"]) == ["docs/rfc/x.md"], failures)
    check("a mixed change reports only the denied path",
          ac.denied_paths(auth, "tech-lead", ["src/main.py", ".github/x.yml"]) == [".github/x.yml"],
          failures)
    check("backslash paths are normalized",
          ac.denied_paths(auth, "tech-lead", ["docs\\rfc\\0002.md"]) == [], failures)

    # --- unknown role errors ---
    try:
        ac.denied_paths(auth, "nope", ["x"])
        check("unknown role raises", False, failures)
    except ValueError:
        pass

    if failures:
        print("test-authority-check: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-authority-check: OK — the ownership map is enforced path-by-path.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
