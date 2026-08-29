#!/usr/bin/env python3
"""A generated repo must be able to COMMIT its run records (#353).

Every phase procedure appends a run record (`record_run.py`) under `.eados-core/learning/runs/`,
and the generated `.gitignore` excluded that whole tree — the shipped default, not a consumer
deviation. So records were written, reported as written, and never committed: the #250 audit trail
did not survive a clone, and the three tools that read it (`autotune`, `lesson_audit`, the
run-record schema gate) saw an empty corpus on every fresh checkout — indistinguishable from a
genuinely new project.

The test drives real `git check-ignore` against a real render, because the failure mode here is a
`.gitignore` rule that LOOKS right and silently does nothing: **git cannot re-include a path whose
parent directory is excluded.** The naive fix (`/.eados-core/` plus `!` lines) leaves the record
ignored, and nothing about reading it says so. Asserted below in both directions.

    python .eados-core/tools/tests/test_run_records_committable.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
REFERENCE = os.path.join(ROOT, "orchestrator", "examples", "reference.yaml")
HAVE_GIT = shutil.which("git") is not None


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def ignored(repo, rel):
    """True when git would refuse to track `rel` — the actual question, asked of actual git."""
    out = subprocess.run(["git", "check-ignore", "-q", rel], cwd=repo,
                         capture_output=True, text=True, timeout=60)
    return out.returncode == 0


def git_repo_with(tmp, gitignore_text):
    """A throwaway repo carrying `gitignore_text`, with the paths that matter present."""
    repo = tempfile.mkdtemp(dir=tmp)
    subprocess.run(["git", "init", "-q", "."], cwd=repo, capture_output=True, timeout=60)
    for rel in (".eados-core/learning/runs", ".eados-core/tools", ".eados-core/orchestrator"):
        os.makedirs(os.path.join(repo, rel), exist_ok=True)
    for rel in (".eados-core/learning/runs/2026-07-27-x.yaml", ".eados-core/tools/render.py",
                ".eados-core/orchestrator/project.yaml"):
        open(os.path.join(repo, rel), "w").close()
    with open(os.path.join(repo, ".gitignore"), "w", encoding="utf-8") as fh:
        fh.write(gitignore_text)
    return repo


def main():
    failures = []
    if not HAVE_GIT:
        print("test-run-records-committable: SKIP — git not on PATH")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        # --- the naive rule is a trap, and the test says so ---------------------------------
        # If someone "simplifies" the template back to this, the record silently stops being
        # committable again. Pinning the trap is what stops that being a quiet regression.
        naive = git_repo_with(tmp, "/.eados-core/\n"
                                   "!/.eados-core/learning/\n"
                                   "!/.eados-core/learning/runs/\n"
                                   "!/.eados-core/learning/runs/*.yaml\n")
        check("the naive `/.eados-core/` + negations form does NOT work "
              "(git cannot re-include under an excluded parent)",
              ignored(naive, ".eados-core/learning/runs/2026-07-27-x.yaml"), failures)

        # --- the shipped template, rendered for real ----------------------------------------
        out = os.path.join(tmp, "rendered")
        rc = subprocess.run([sys.executable, os.path.join(TOOLS, "render.py"), REFERENCE,
                             "--out", out], capture_output=True, text=True, timeout=180)
        check("the reference manifest renders", rc.returncode == 0, failures)
        if rc.returncode == 0:
            subprocess.run(["git", "init", "-q", "."], cwd=out, capture_output=True, timeout=60)
            for rel in (".eados-core/learning/runs", ".eados-core/tools",
                        ".eados-core/orchestrator"):
                os.makedirs(os.path.join(out, rel), exist_ok=True)
            for rel in (".eados-core/learning/runs/2026-07-27-proj-1.yaml",
                        ".eados-core/tools/render.py",
                        ".eados-core/orchestrator/project.yaml"):
                open(os.path.join(out, rel), "w").close()

            check("a rendered repo CAN commit a run record",
                  not ignored(out, ".eados-core/learning/runs/2026-07-27-proj-1.yaml"), failures)
            # The exception must stay an exception: the rest of the vendored factory is still
            # not the project's source, and re-including too much is the other way to get this
            # wrong.
            check("the vendored factory tooling is still ignored",
                  ignored(out, ".eados-core/tools/render.py"), failures)
            check("the vendored manifest is still ignored",
                  ignored(out, ".eados-core/orchestrator/project.yaml"), failures)

    if failures:
        print("test-run-records-committable: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-run-records-committable: OK — a rendered repo can commit its run records, the rest "
          "of the vendored factory stays ignored, and the naive re-include form is pinned as the "
          "trap it is.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
