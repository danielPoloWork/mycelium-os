#!/usr/bin/env python3
"""Regression test for issue #128 — CLI tools must emit UTF-8 and never crash on a
non-UTF-8 console (Windows defaults to cp1252).

We simulate that console by running a tool as a subprocess with PYTHONIOENCODING=ascii
and PYTHONUTF8=0. Without the per-main() `sys.stdout.reconfigure(encoding="utf-8")`,
printing a non-ASCII glyph (e.g. the em-dash in an argparse description, or eados_lint's
i18n-STALE `!=`) raises UnicodeEncodeError and the tool aborts with a traceback. The
behavioural cases prove the fix works end-to-end; the static case enforces that every
CLI tool carries it (so a future tool can't silently regress). Dependency-free.

    python .eados-core/tools/tests/test_utf8_stdio.py
"""

import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TOOLS))
DEF_MAIN = re.compile(r"^def main\(", re.M)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def is_utf8(raw):
    try:
        raw.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def run_ascii_console(args):
    """Run a tool as if attached to an ascii (cp1252-like) console."""
    env = {**os.environ, "PYTHONIOENCODING": "ascii", "PYTHONUTF8": "0"}
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def main():
    failures = []

    # --- Behavioural: a tool whose argparse description carries an em-dash. --help is a
    #     trivial always-reached path, so this is decoupled from the tool's own logic. ---
    pr_help = run_ascii_console([os.path.join(TOOLS, "phase_runner.py"), "--help"])
    check("phase_runner --help exits 0 on an ascii console", pr_help.returncode == 0, failures)
    check("phase_runner --help output is valid UTF-8", is_utf8(pr_help.stdout), failures)
    check("phase_runner --help keeps its em-dash (emitted as UTF-8, not crashed)",
          "—" in pr_help.stdout.decode("utf-8", "replace"), failures)

    # --- Behavioural: the headline tool from #128. It prints an em-dash on its OK line and
    #     a `!=` on the i18n-STALE failure path; neither may produce a UnicodeEncodeError. ---
    lint = run_ascii_console([os.path.join(TOOLS, "eados_lint.py")])
    check("eados_lint does not crash with UnicodeEncodeError on an ascii console",
          b"UnicodeEncodeError" not in lint.stdout
          and b"Traceback (most recent call last)" not in lint.stdout, failures)
    check("eados_lint output is valid UTF-8 on an ascii console", is_utf8(lint.stdout), failures)

    # --- Static: every CLI tool (a tools/*.py defining main()) carries the reconfigure. ---
    for path in sorted(glob.glob(os.path.join(TOOLS, "*.py"))):
        src = open(path, encoding="utf-8").read()
        if DEF_MAIN.search(src):
            name = os.path.basename(path)
            check(f"{name} reconfigures stdio in main() (#128)",
                  'reconfigure(encoding="utf-8")' in src, failures)

    if failures:
        print("test-utf8-stdio: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} UTF-8 stdio invariant(s) broken.")
        return 1
    print("test-utf8-stdio: OK - tools force UTF-8 stdio; no cp1252 crash/mojibake (#128).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
