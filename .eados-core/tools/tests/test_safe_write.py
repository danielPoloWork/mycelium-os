#!/usr/bin/env python3
"""Tests for the safe-write containment self-lint check (#235, guards #195/#196).

The renderer's `--in-place` clobber (#195) and its `.git`-segment escape (#196) were closed by
funnelling every rendered-repo write through `sandbox.safe_write`/`resolve` (render.write_file is
now a pure delegator). This check keeps that fix from being silently bypassed by a NEW private
write path: a direct `open(..., "w")` (or pathlib/shutil write) in a factory tool must either route
through sandbox or be allow-listed WITH a justification. These pin the pure helper off in-memory
sources — a synthetic direct write is caught, sandbox's own primitive and the three factory-internal
writers are exempt, and the shipped tree is clean — plus the symmetric allow-list staleness hygiene.
Dependency-free (runs in the self-lint job).

    python .eados-core/tools/tests/test_safe_write.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint  # noqa: E402  (the module under test)

# A tool that grows its own truncating write path — exactly the #195/#196 regression.
DIRECT_WRITE_SRC = (
    "def emit(dest, text):\n"
    "    with open(dest, \"w\", encoding=\"utf-8\") as handle:\n"
    "        handle.write(text)\n"
)
# A tool that does the right thing — it delegates to sandbox (like render.write_file today).
DELEGATED_SRC = (
    "import sandbox\n"
    "def emit(root, rel, text):\n"
    "    return sandbox.safe_write(root, rel, text)\n"
)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    P = lint.safe_write_problems

    # --- a synthetic direct write is flagged (the whole point of the check) ---
    prob = P([("newtool.py", DIRECT_WRITE_SRC)], allowlist={})
    check("a direct open(...,'w') is flagged",
          any("newtool.py" in p and "sandbox.safe_write" in p for p in prob), failures)

    # --- pathlib / shutil / os.replace variants are caught too, not just open() ---
    for verb, src in (
        ("write_text", "from pathlib import Path\nPath(dest).write_text(text)\n"),
        ("write_bytes", "from pathlib import Path\nPath(dest).write_bytes(blob)\n"),
        ("os.replace", "import os\nos.replace(tmp, dest)\n"),
        ("shutil.copy", "import shutil\nshutil.copy(src, dest)\n"),
    ):
        check(f"a {verb} write is flagged",
              P([("t.py", src)], allowlist={}) != [], failures)

    # --- a delegated write is clean ---
    check("a sandbox-delegated write is clean",
          P([("goodtool.py", DELEGATED_SRC)], allowlist={}) == [], failures)

    # --- a plain read is NOT a write (open with no mode / 'r') ---
    read_src = "def load(p):\n    with open(p, encoding=\"utf-8\") as h:\n        return h.read()\n"
    check("a read-only open() is not flagged",
          P([("reader.py", read_src)], allowlist={}) == [], failures)

    # --- an allow-listed tool with a direct write is exempt ---
    check("an allow-listed direct writer is exempt",
          P([("record_run.py", DIRECT_WRITE_SRC)]) == [], failures)

    # --- whole-line comments don't count (a commented-out example write) ---
    commented = "def emit(dest):\n    # with open(dest, \"w\") as h:  # example only\n    pass\n"
    check("a commented-out write is not flagged",
          P([("doc.py", commented)], allowlist={}) == [], failures)

    # --- the shipped allow-list is exactly the four verified direct writers ---
    check("the allow-list is the four verified factory-internal writers",
          set(lint.SAFE_WRITE_ALLOWLIST) ==
          {"sandbox.py", "record_run.py", "derive_links.py", "sync_action_pins.py"}, failures)

    # --- on-disk: the shipped tools tree is clean (render.py/render_artifact.py delegate) ---
    collected = []
    lint.check_safe_write(lambda _name, msg: collected.append(msg))
    check(f"the shipped tools tree routes every write through sandbox (got {collected})",
          collected == [], failures)

    if failures:
        print("test-safe-write: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-safe-write: OK — a direct write is caught, sandbox delegation is clean, the "
          "allow-list is the four verified writers, and the shipped tree is contained.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
