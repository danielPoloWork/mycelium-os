#!/usr/bin/env python3
"""Negative-path tests for the migrate sandbox — a write may ONLY land inside the target repo,
never via traversal/absolute/symlink, never into `.git/`, and never clobber a file unless asked.
This is the safety backstop for the only phase that edits real user code. Dependency-free.

    python .eados-core/tools/tests/test_sandbox.py
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import sandbox as sb  # noqa: E402  (the module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def raises(fn):
    try:
        fn()
        return False
    except sb.SandboxError:
        return True


def main():
    failures = []

    with tempfile.TemporaryDirectory() as outer:
        root = os.path.join(outer, "repo")
        os.makedirs(root)

        # --- the happy path: a normal write lands inside, with content ---
        p = sb.safe_write(root, "docs/adr/0001.md", "hi")
        check("a normal write lands inside the root",
              os.path.isfile(p) and os.path.commonpath([os.path.realpath(root), p])
              == os.path.realpath(root), failures)
        check("the content is written", open(p, encoding="utf-8").read() == "hi", failures)

        # --- traversal is refused AND writes nothing outside ---
        check("a traversal path raises",
              raises(lambda: sb.safe_write(root, "../../escape.md", "x")), failures)
        check("the traversal target was not created",
              not os.path.exists(os.path.join(outer, "escape.md")), failures)

        # --- absolute / drive-qualified destinations are refused ---
        check("an absolute path raises",
              raises(lambda: sb.safe_write(root, "/etc/passwd", "x")), failures)
        check("a drive-qualified path raises",
              raises(lambda: sb.safe_write(root, "C:\\windows\\x", "x")), failures)

        # --- .git is off-limits, at the top level AND nested (submodule / embedded repo) ---
        check("writing into top-level .git raises",
              raises(lambda: sb.safe_write(root, ".git/config", "x")), failures)
        check("writing into a nested .git raises",
              raises(lambda: sb.safe_write(root, "vendor/lib/.git/config", "x")), failures)
        check("the nested .git target was not created",
              not os.path.exists(os.path.join(root, "vendor", "lib", ".git", "config")), failures)
        check("a .gitignore file (not a .git dir) is still allowed",
              os.path.isfile(sb.safe_write(root, "pkg/.gitignore", "*.log")), failures)

        # --- additive by default; explicit overwrite allowed ---
        check("overwriting an existing file raises by default",
              raises(lambda: sb.safe_write(root, "docs/adr/0001.md", "new")), failures)
        sb.safe_write(root, "docs/adr/0001.md", "new", overwrite=True)
        check("explicit overwrite succeeds",
              open(p, encoding="utf-8").read() == "new", failures)

        # --- a symlink that points outside the root is caught (realpath resolves it) ---
        link = os.path.join(root, "out")
        try:
            os.symlink(outer, link, target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError):
            pass  # symlink creation not permitted here (e.g. Windows w/o privilege) — skip
        else:
            check("a symlink escaping the root raises",
                  raises(lambda: sb.safe_write(root, "out/escape.md", "x")), failures)
            check("the symlink escape wrote nothing outside",
                  not os.path.exists(os.path.join(outer, "escape.md")), failures)

    if failures:
        print("test-sandbox: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} containment guarantee(s) failed.")
        return 1
    print("test-sandbox: OK -- writes are contained; traversal, absolute, .git, and clobber refused.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
