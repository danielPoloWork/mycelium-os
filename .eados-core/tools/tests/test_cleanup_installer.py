#!/usr/bin/env python3
"""Tests for cleanup_installer — tidy the guided-installer leftovers at a repo root (M9 follow-up).

Dependency-free: exercises the pure `installer_leftovers` core + the guarded `remove_leftovers` +
`main` against temp dirs. The key safety property: it removes ONLY the known installer artifacts
(`setup.sh`/`setup.ps1`/`setup.bat`/`setup.command`, and a `setup/` dir only when it holds nothing
else) — never `.eados-core/`, the agent contract, or a user's own files.

    python .eados-core/tools/tests/test_cleanup_installer.py
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import cleanup_installer as ci  # noqa: E402  (module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def touch(path, content="x"):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def main():
    failures = []

    # empty root -> nothing
    with tempfile.TemporaryDirectory() as root:
        check("empty root has no leftovers", ci.installer_leftovers(root) == [], failures)

    # loose installer files alongside real content -> only the installer files are reported
    with tempfile.TemporaryDirectory() as root:
        touch(os.path.join(root, "setup.sh"))
        touch(os.path.join(root, "setup.ps1"))
        touch(os.path.join(root, "AGENTS.md"))
        os.makedirs(os.path.join(root, ".eados-core", "tools"))
        touch(os.path.join(root, ".eados-core", "tools", "render.py"))
        got = ci.installer_leftovers(root)
        check("reports the loose installer files", set(got) == {"setup.sh", "setup.ps1"}, failures)
        check("does NOT report AGENTS.md / .eados-core", ".eados-core/" not in got and "AGENTS.md" not in got,
              failures)
        # --apply removes only those; real content survives
        ci.main([root, "--apply"])
        check("removed the installer files", not os.path.exists(os.path.join(root, "setup.sh"))
              and not os.path.exists(os.path.join(root, "setup.ps1")), failures)
        check("preserved AGENTS.md", os.path.exists(os.path.join(root, "AGENTS.md")), failures)
        check("preserved .eados-core/", os.path.isdir(os.path.join(root, ".eados-core")), failures)

    # a setup/ dir that holds ONLY installer files -> reported (and removable)
    with tempfile.TemporaryDirectory() as root:
        os.mkdir(os.path.join(root, "setup"))
        touch(os.path.join(root, "setup", "setup.sh"))
        touch(os.path.join(root, "setup", "setup.command"))
        check("a setup/ of only installer files is reported", "setup/" in ci.installer_leftovers(root),
              failures)
        ci.main([root, "--apply"])
        check("the setup/ dir is removed", not os.path.exists(os.path.join(root, "setup")), failures)

    # a setup/ dir with the user's own content -> NEVER touched
    with tempfile.TemporaryDirectory() as root:
        os.mkdir(os.path.join(root, "setup"))
        touch(os.path.join(root, "setup", "setup.sh"))
        touch(os.path.join(root, "setup", "my_app.py"))
        check("a setup/ with other content is NOT reported", "setup/" not in ci.installer_leftovers(root),
              failures)
        ci.main([root, "--apply"])
        check("the user's setup/ survives --apply", os.path.exists(os.path.join(root, "setup", "my_app.py")),
              failures)

    # an empty setup/ dir -> reported (a bare leftover)
    with tempfile.TemporaryDirectory() as root:
        os.mkdir(os.path.join(root, "setup"))
        check("an empty setup/ is reported", "setup/" in ci.installer_leftovers(root), failures)

    # a setup/ whose entry only NAME-matches an installer but is not a regular file (e.g. a subdir
    # named setup.bat) -> NOT a pure-installer leftover, never removed (issue #131)
    with tempfile.TemporaryDirectory() as root:
        os.mkdir(os.path.join(root, "setup"))
        os.mkdir(os.path.join(root, "setup", "setup.bat"))   # a directory, not the installer file
        check("a setup/ entry that only name-matches (a subdir) is NOT reported",
              "setup/" not in ci.installer_leftovers(root), failures)
        ci.main([root, "--apply"])
        check("…and that setup/ survives --apply",
              os.path.isdir(os.path.join(root, "setup", "setup.bat")), failures)

    # dry-run (default) removes nothing
    with tempfile.TemporaryDirectory() as root:
        touch(os.path.join(root, "setup.sh"))
        rc = ci.main([root])
        check("dry-run exits 0", rc == 0, failures)
        check("dry-run removes nothing", os.path.exists(os.path.join(root, "setup.sh")), failures)

    if failures:
        print("test-cleanup-installer: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-cleanup-installer: OK — reports + removes only the known installer leftovers "
          "(setup.* / a setup/ of only those); never touches .eados-core/, the contract, or a "
          "user's own files; dry-run is inert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
