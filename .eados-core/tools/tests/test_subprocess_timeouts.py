#!/usr/bin/env python3
"""Every shipped CLI bounds its child processes, and degrades cleanly when one times out (#321).

`subprocess.run` without a `timeout` waits forever. The tools most exposed are the ones written to
degrade gracefully offline: they handle "gh is missing" and "gh returned an error" carefully, but
not "gh never returns" — which is the failure a flaky network, a rate-limit backoff, or an auth
prompt with no stdin actually produces. It then blocks until the CI job's own timeout and surfaces
as a generic job timeout rather than as the stalled call it is.

Two properties, and the second is the one that matters: a budget nobody handles just converts a
hang into a traceback.

    python .eados-core/tools/tests/test_subprocess_timeouts.py
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint      # noqa: E402
import pr_review               # noqa: E402
import route_advice            # noqa: E402
import git_check               # noqa: E402
import derive_links            # noqa: E402


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- 1. no shipped CLI leaves a child unbounded ---------------------------------------
    items = [(fn, lint.read(os.path.join(TOOLS, fn)))
             for fn in sorted(os.listdir(TOOLS)) if fn.endswith(".py")]
    problems = lint.subprocess_timeout_problems(items)
    check(f"every subprocess.run in the shipped tools has a timeout ({problems})",
          problems == [], failures)

    # The gate must actually bite, including on the shape a regex would miss.
    check("a new bare subprocess.run is caught",
          lint.subprocess_timeout_problems(
              [("new.py", "import subprocess\nsubprocess.run(['gh'])\n")]) != [], failures)
    check("…even when the call spans lines (why this is parsed, not grepped)",
          lint.subprocess_timeout_problems(
              [("new.py", "import subprocess\nsubprocess.run(\n  ['gh'],\n)\n")]) != [], failures)
    check("a guarded call is clean",
          lint.subprocess_timeout_problems(
              [("ok.py", "import subprocess\nsubprocess.run(['gh'], timeout=30)\n")]) == [],
          failures)

    # --- 2. a timeout degrades onto the path the tool ALREADY has for `gh` unavailable -----
    real = subprocess.run

    def hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0] if args else "cmd", kwargs.get("timeout", 30))

    subprocess.run = hang
    try:
        # gh-backed tools raise the same RuntimeError their callers already turn into a clean SKIP.
        for label, call in (
                ("pr_review", lambda: pr_review._gh_json(["pr", "view", "1"])),
                ("route_advice", lambda: route_advice.fetch_issue(1)),
                ("derive_links", lambda: derive_links.fetch_records(repo="o/r")),
        ):
            try:
                call()
                failures.append(f"{label}: a timed-out gh call produced no error at all")
            except RuntimeError as exc:
                check(f"{label}: a timeout says it TIMED OUT, not that gh is missing",
                      "timed out" in str(exc).lower(), failures)
            except subprocess.TimeoutExpired:
                failures.append(f"{label}: TimeoutExpired leaked to the caller as a traceback")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{label}: leaked {type(exc).__name__} instead of RuntimeError")

        # git_check's helpers degrade to None — their existing contract, unchanged by the budget.
        check("git_check._git degrades to None on a timeout",
              git_check._git(".", "status") is None, failures)
        check("git_check.open_pr_count degrades to None on a timeout",
              git_check.open_pr_count(".") is None, failures)
    finally:
        subprocess.run = real

    # The mock must not have leaked past the test.
    check("subprocess.run is restored", subprocess.run is real, failures)

    if failures:
        print("test-subprocess-timeouts: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-subprocess-timeouts: OK — no shipped CLI leaves a child unbounded, the gate catches "
          "a new one (even across lines), and a timeout degrades onto each tool's existing "
          "offline path with a message naming the real cause.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
