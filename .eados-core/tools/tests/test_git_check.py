#!/usr/bin/env python3
"""Issue #250 — git_check.py, the deterministic evaluator for the os/git/git.yaml policy.
Pins the pure helpers (branch naming, Conventional-Commit shape) against the REAL policy data
(never a synthetic copy — the tool's whole point is that the policy is data), the exemptions
(default branch, merge commits), and the CLI overrides. Dependency-free; gh-dependent one-PR
counting is exercised only through its SKIP degradation (no network in tests).

    python .eados-core/tools/tests/test_git_check.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import git_check  # noqa: E402


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    policy = git_check.load_policy()
    check("git.yaml declares branch types", (policy.get("branch_naming") or {}).get("types"),
          failures)

    # --- branch naming: the git.yaml pattern is enforced, the default branch is exempt ---
    for label, branch, ok in [
        ("a declared-type kebab branch is clean", "feat/honor-system-hardening", True),
        ("the default branch is exempt", "main", True),
        ("an undeclared type is rejected", "wip/some-thing", False),
        ("a missing type/ prefix is rejected", "quick-fix", False),
        ("an UPPERCASE description is rejected", "feat/Quick-Fix", False),
        ("an underscore description is rejected", "feat/snake_case", False),
        ("a detached HEAD is rejected loudly", "HEAD", False),
    ]:
        problems = git_check.branch_problems(branch, policy)
        check(f"branch_problems: {label}", (problems == []) is ok,
              failures)

    # --- commit convention: Conventional-Commit shape, declared type/scope, 72-char cap ---
    for label, subject, ok in [
        ("a conventional subject is clean", "feat(commands): ship the thing", True),
        ("a scopeless conventional subject is clean", "docs: fix a typo", True),
        ("a merge commit is exempt", "Merge branch 'x' into main", True),
        ("a non-conventional subject is rejected", "fixed some stuff", False),
        ("an undeclared type is rejected", "yolo(commands): ship it", False),
        ("an undeclared scope is rejected", "feat(warpdrive): engage", False),
        ("an over-72-char subject is rejected",
         "feat(commands): " + "x" * 70, False),
    ]:
        problems = git_check.commit_problems(subject, policy)
        check(f"commit_problems: {label}", (problems == []) is ok, failures)

    # --- the CLI overrides: pure inputs, deterministic verdicts. open_pr_count is patched out
    #     so the cases stay hermetic on a machine with an authenticated gh (no network, no
    #     dependence on how many PRs happen to be open) ---
    real_count = git_check.open_pr_count
    git_check.open_pr_count = lambda repo, counts="authored": 1
    try:
        rc = git_check.main(["--branch", "feat/good-branch",
                             "--message", "feat(tools): a fine subject"])
        check("CLI exits 0 on a clean branch + subject", rc == 0, failures)
        rc = git_check.main(["--branch", "bad branch name", "--message", "nope"])
        check("CLI exits 1 on violations", rc == 1, failures)
        rc = git_check.main(["--branch", "bad branch name", "--message", "nope", "--advisory"])
        check("CLI --advisory reports but exits 0 (the local pre-flight mode)", rc == 0, failures)
        git_check.open_pr_count = lambda repo, counts="authored": 3
        rc = git_check.main(["--branch", "feat/good-branch",
                             "--message", "feat(tools): a fine subject"])
        check("CLI exits 1 when more than one PR is open (one-PR-at-a-time)", rc == 1, failures)
    finally:
        git_check.open_pr_count = real_count

    # --- the gate registry: git-policy is data, external, with the tool as its runs ---
    import phase_runner  # noqa: E402
    wf = phase_runner.load_workflow()
    gate = next((g for g in (wf.get("gates") or [])
                 if isinstance(g, dict) and g.get("id") == "git-policy"), None)
    check("the git-policy gate is registered in workflow.yaml", gate is not None, failures)
    if gate:
        check("git-policy is wired external (it reads git/gh state, not the manifest)",
              gate.get("wired") == "external", failures)
        check("git-policy runs git_check.py", "git_check.py" in str(gate.get("runs")), failures)
        check("git-policy is cross-cutting (required_for [])",
              gate.get("required_for") == [], failures)

    if failures:
        print("test-git-check: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} git-policy invariant(s) broken.")
        return 1
    print("test-git-check: OK — the git.yaml policy is evaluated (branch naming, commit "
          "convention, advisory/gating split) and registered as the git-policy gate (#250).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
