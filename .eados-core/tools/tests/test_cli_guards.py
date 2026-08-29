#!/usr/bin/env python3
"""Issue #131 — a CLI tool must report a missing or invalid input path as a clean non-zero exit,
not a raw Python traceback. Each CLI's main() is called with a path that does not exist; the test
asserts it returns non-zero (or sys.exits non-zero) and never propagates an exception. Output is
captured so a tool's normal chatter doesn't pollute the run. Dependency-free.

    python .eados-core/tools/tests/test_cli_guards.py
"""

import contextlib
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import doctor          # noqa: E402
import eados           # noqa: E402
import phase_runner    # noqa: E402
import traceability    # noqa: E402
import rfc_check       # noqa: E402


def guarded(label, call, failures):
    """A tool main() given a bad input path must fail cleanly: a non-zero return (or a non-zero
    SystemExit), never a propagated exception."""
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = call()
    except SystemExit as exc:            # argparse-style exits are acceptable if non-zero
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        if code == 0:
            failures.append(f"{label}: exited 0 on a missing input")
    except Exception as exc:             # the regression this guards against
        failures.append(f"{label}: raised {type(exc).__name__} instead of a clean exit")
    else:
        if not rc:                       # 0 or None means it did not report the bad input
            failures.append(f"{label}: returned {rc!r} (expected non-zero) on a missing input")


def main():
    failures = []
    with tempfile.TemporaryDirectory() as d:
        nope = os.path.join(d, "nope.yaml")   # the directory exists; the file does not
        guarded("doctor", lambda: doctor.main([nope]), failures)
        guarded("eados", lambda: eados.main(["status", nope]), failures)
        guarded("phase_runner", lambda: phase_runner.main([nope]), failures)
        guarded("traceability", lambda: traceability.main([nope, "RFC-0001"]), failures)
        guarded("rfc_check", lambda: rfc_check.main([nope]), failures)

    if failures:
        print("test-cli-guards: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} CLI(s) do not fail cleanly on a bad input path.")
        return 1
    print("test-cli-guards: OK - doctor / eados / phase_runner / traceability / rfc_check report a "
          "missing input as a clean non-zero exit, not a traceback (#131).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
