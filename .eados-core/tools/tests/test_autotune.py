#!/usr/bin/env python3
"""Regression test for autotune's majority logic.

autotune proposes a default change only when one value is the majority across run records.
A key overridden twice WITHIN a single record must not inflate its count past the number of
records (a false majority). This pins that, plus the genuine cross-record majority. Reuses
render.load_yaml; dependency-free.

    python .eados-core/tools/tests/test_autotune.py
"""

import contextlib
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import autotune  # noqa: E402  (the module under test)


def _write_record(directory, name, overrides):
    lines = ["overrides:"]
    for key, chosen, default in overrides:
        lines += [f"  - key: {key}", f"    chosen: {chosen}", f"    default: {default}"]
    with open(os.path.join(directory, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def _run(threshold):
    out, argv = io.StringIO(), sys.argv
    sys.argv = ["autotune.py", "--threshold", str(threshold)]
    try:
        with contextlib.redirect_stdout(out):
            autotune.main()
    finally:
        sys.argv = argv
    return out.getvalue()


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        autotune.RUNS = tmp  # redirect the run-record directory at the module global

        # One record overriding the same key twice must NOT clear a threshold of 2.
        _write_record(tmp, "r1.yaml", [("toolchain.linter", "ruff", "flake8"),
                                       ("toolchain.linter", "ruff", "flake8")])
        out = _run(2)
        check("duplicate within one record is not a false majority",
              "no default is overridden" in out, failures)

        # A second, distinct record makes it a genuine 2/2 majority -> proposal.
        _write_record(tmp, "r2.yaml", [("toolchain.linter", "ruff", "flake8")])
        out = _run(2)
        check("genuine cross-record majority is proposed",
              "toolchain.linter" in out and "ruff" in out, failures)

        # --- #198: one malformed record (a folded scalar the loader rejects) must not abort the
        #     analysis — the valid records still propose, the bad file is named on stderr, exit 0 ---
        with open(os.path.join(tmp, "bad.yaml"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("note: >\n  folded body the loader rejects\n")
        out2, err2, saved = io.StringIO(), io.StringIO(), sys.argv
        sys.argv = ["autotune.py", "--threshold", "2"]
        try:
            with contextlib.redirect_stdout(out2), contextlib.redirect_stderr(err2):
                rc = autotune.main()
        finally:
            sys.argv = saved
        check("a malformed record does not abort autotune (exit 0)", rc == 0, failures)
        check("valid records still produce a proposal despite the bad file",
              "toolchain.linter" in out2.getvalue(), failures)
        check("the malformed record is named on stderr, not a traceback",
              "skipping bad.yaml" in err2.getvalue(), failures)

    # --- #198: a record whose root parses to a non-mapping is skipped, not an AttributeError ---
    with tempfile.TemporaryDirectory() as tmp:
        autotune.RUNS = tmp
        with open(os.path.join(tmp, "list.yaml"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("x\n")
        saved_loader, saved = autotune.load_yaml, sys.argv
        autotune.load_yaml = lambda _text: ["not", "a", "dict"]   # force a non-dict record root
        out3, err3 = io.StringIO(), io.StringIO()
        sys.argv = ["autotune.py"]
        try:
            with contextlib.redirect_stdout(out3), contextlib.redirect_stderr(err3):
                rc = autotune.main()
        finally:
            autotune.load_yaml, sys.argv = saved_loader, saved
        check("a non-mapping record is skipped without an AttributeError (exit 0)", rc == 0, failures)
        check("the non-mapping record is named as skipped",
              "not a YAML mapping" in err3.getvalue(), failures)

    # --- #215: the confidence floor scales with the corpus — a 2-record majority that IS proposed at
    #     a small corpus is NOT proposed once 20% of the runs exceeds it (broader adoption required) ---
    with tempfile.TemporaryDirectory() as tmp:
        autotune.RUNS = tmp
        _write_record(tmp, "a1.yaml", [("toolchain.linter", "ruff", "flake8")])
        _write_record(tmp, "a2.yaml", [("toolchain.linter", "ruff", "flake8")])
        for i in range(9):   # 9 unrelated records -> 11 analyzed -> floor ceil(11/5) = 3
            _write_record(tmp, f"o{i}.yaml", [(f"misc.k{i}", f"v{i}", "d")])
        out = _run(2)
        check("a 2-record majority is below the scaled floor at 11 runs (not proposed)",
              "toolchain.linter" not in out and "confidence floor 3" in out, failures)

    if failures:
        print("test-autotune: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} autotune behaviour(s) wrong.")
        return 1
    print("test-autotune: OK — duplicate overrides don't fake a majority; real majorities propose.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
