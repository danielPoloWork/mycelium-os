#!/usr/bin/env python3
"""Discovery runner for the factory test suite (#168).

CI used to enumerate every test script by hand in two places (a ~33-line unit block plus a
~60-path `py_compile` line) — a forgotten line was the worst failure mode a quality system
has: a test that exists, passes review, and never runs. This runner globs
`tools/tests/test_*.py`, so a new test runs in CI (and locally) with **zero** enumeration —
the discovery IS the gate.

    python .eados-core/tools/tests/run_all.py                       # the whole suite
    python .eados-core/tools/tests/run_all.py --exclude test_x.py   # skip one (repeatable),
                                                                    # e.g. a script another CI
                                                                    # job runs in a special
                                                                    # context (PyYAML, a
                                                                    # rendered repo)

Each script runs in its own interpreter (they are standalone `main()` scripts, not a test
framework); a failing script's full output is echoed, and any failure exits non-zero.
"""

import argparse
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def discover(exclude=()):
    """Every tools/tests/test_*.py filename, sorted for a deterministic order, minus
    `exclude`. Returns names, not paths — the caller anchors them to HERE."""
    names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(HERE, "test_*.py")))
    return [n for n in names if n not in set(exclude)]


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Run every tools/tests/test_*.py (discovered, "
                                             "never enumerated).")
    ap.add_argument("--exclude", action="append", default=[], metavar="NAME",
                    help="test filename to skip (repeatable), e.g. --exclude test_loader.py")
    args = ap.parse_args(argv)

    names = discover(args.exclude)
    if not names:
        print("run-all: FAIL — no tools/tests/test_*.py discovered (broken checkout?)")
        return 1

    failed = []
    for name in names:
        proc = subprocess.run([sys.executable, os.path.join(HERE, name)],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        ok = proc.returncode == 0
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
        if not ok:
            failed.append(name)
            for line in ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines():
                print(f"      {line}")

    skipped = f", {len(args.exclude)} excluded" if args.exclude else ""
    if failed:
        print(f"\nrun-all: FAIL — {len(failed)}/{len(names)} script(s) failed: "
              f"{', '.join(failed)}")
        return 1
    print(f"run-all: OK — {len(names)} test script(s) pass{skipped}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
