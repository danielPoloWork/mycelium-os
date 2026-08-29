#!/usr/bin/env python3
"""Negative-path tests for the consistency lint that ships into EVERY generated repo.

The render-smoke proves a freshly-rendered repo PASSES consistency_lint.py (the positive
control). But that lint is the factory's downstream product — a regression that makes it
permissive would silently propagate to every generated project. This renders the reference,
then injects one defect at a time and asserts the matching congruence check actually FAILS.
Dependency-free (render.py is standard-library only); renders into the system temp dir
(outside the EADOS repo, per the renderer's --out containment guard).

    python .eados-core/tools/tests/test_consistency_lint.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
RENDER_PY = os.path.join(TOOLS, "render.py")
REFERENCE = os.path.join(ROOT, "orchestrator", "examples", "reference.yaml")


def _lint(repo):
    return subprocess.run([sys.executable, os.path.join(repo, "tools", "consistency_lint.py")],
                          capture_output=True, text=True)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _append(path, text):
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


# Each defect mutates a clean render and must trip exactly the named check.
DEFECTS = [
    ("version-lockstep",
     lambda d: _write(os.path.join(d, "docs", "releases", "v1.2.3.md"), "# v1.2.3\n")),
    ("milestones",
     lambda d: _append(os.path.join(d, "ROADMAP.md"), "\n- [y] malformed checkbox\n")),
    ("adr-index",
     lambda d: _write(os.path.join(d, "docs", "adr", "0009-orphan.md"), "# 0009 orphan\n")),
]


def main():
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "base")
        proc = subprocess.run([sys.executable, RENDER_PY, REFERENCE, "--out", base],
                              capture_output=True, text=True)
        check("reference renders cleanly", proc.returncode == 0, failures)
        if proc.returncode != 0:
            print("test-consistency-lint: FAIL\n  render failed:\n" + proc.stdout + proc.stderr)
            return 1

        # Positive control: a freshly-generated repo must pass.
        clean = _lint(base)
        check("clean render passes consistency_lint", clean.returncode == 0, failures)

        # Negative controls: each injected defect must fail the matching check.
        for name, mutate in DEFECTS:
            work = os.path.join(tmp, name)
            shutil.copytree(base, work)
            mutate(work)
            res = _lint(work)
            out = res.stdout + res.stderr
            check(f"{name}: defect makes lint exit non-zero", res.returncode == 1, failures)
            check(f"{name}: report names the [{name}] check", f"[{name}]" in out, failures)

    if failures:
        print("test-consistency-lint: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} negative-path check(s) did not behave as expected.")
        return 1
    print(f"test-consistency-lint: OK — clean render passes; {len(DEFECTS)} injected defects "
          "each trip their check.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
