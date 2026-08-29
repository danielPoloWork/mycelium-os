#!/usr/bin/env python3
"""The commit-subject cap is policy data, and counts only what the author wrote (#363).

Two defects, one of them the kind that hides in plain sight for 255 commits:

  * **The cap was code.** `_SUBJECT_MAX = 72` sat in `git_check.py` while every other part of the
    commit convention lived in `os/git/git.yaml`. In an OS whose stated invariant is that knowledge
    is data, the single numeric threshold of the policy was a module constant — and a generated repo
    could not change it without editing a vendored tool.
  * **It counted characters nobody wrote.** Squash-merge appends ` (#PR)`. A PR title written exactly
    to the cap therefore failed the moment it merged — a reported violation with no author.

And the number itself was wrong for this repository: **178 of 255** commits on `main` broke 72, the
median subject being 80. A rule at 30% compliance is a decision about the rule, not a backlog. The
regression fixtures below are real merged subjects from that history.

    python .eados-core/tools/tests/test_subject_cap.py
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
REFERENCE = os.path.join(ROOT, "orchestrator", "examples", "reference.yaml")
sys.path.insert(0, TOOLS)
import git_check   # noqa: E402

# Real subjects from `main`. Each was under the cap as written and over it once merged.
MERGED = [
    "fix(git): bot PRs no longer break a generated repo's own policy (#350) (#362)",
    "feat(render): stamp the EADOS version that generated a repository (#319) (#349)",
    "fix(tools): apply YAML's real key rule instead of a charset guess (#316) (#335)",
]


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    policy = git_check.load_policy()
    cap = (policy.get("commit") or {}).get("subject_max")

    # --- the cap is data, and the tool reads it ---------------------------------------------
    check(f"os/git/git.yaml declares commit.subject_max ({cap})", isinstance(cap, int), failures)
    check("...and the in-code fallback agrees with it, so a policy-less repo is judged by the "
          "same number rather than a stricter historical one",
          git_check._SUBJECT_MAX == cap, failures)

    long_subject = "fix(tools): " + "x" * 200
    for declared, expect_fail in ((10, True), (400, False)):
        problems = git_check.commit_problems(
            long_subject, {"commit": {"convention": "conventional-commits",
                                      "subject_max": declared}})
        over = [p for p in problems if "caps it at" in p]
        check(f"a policy cap of {declared} is honoured (fail={expect_fail})",
              bool(over) == expect_fail, failures)
        if over:
            check(f"...and the message names the declared cap, not a constant",
                  str(declared) in over[0] and "commit.subject_max" in over[0], failures)
    # An absent cap must not mean "no limit" — a policy that forgot the key still gets a rule.
    problems = git_check.commit_problems(
        long_subject, {"commit": {"convention": "conventional-commits"}})
    check("an absent cap falls back to the default rather than disabling the check",
          any("caps it at" in p for p in problems), failures)

    # --- it counts only what the author wrote -----------------------------------------------
    check("a trailing squash reference is stripped",
          git_check.authored_subject("fix(x): y (#362)") == "fix(x): y", failures)
    check("...exactly one — the `(#350)` the author typed survives, the merge's `(#362)` does not",
          git_check.authored_subject("fix(x): y (#350) (#362)") == "fix(x): y (#350)", failures)
    check("a reference that is not trailing is untouched",
          git_check.authored_subject("fix(x): closes (#350) properly")
          == "fix(x): closes (#350) properly", failures)
    check("a subject with no reference is unchanged",
          git_check.authored_subject("fix(x): y") == "fix(x): y", failures)

    for subject in MERGED:
        authored = git_check.authored_subject(subject)
        check(f"REGRESSION: a real merged subject is measured as written "
              f"({len(subject)} -> {len(authored)})", len(authored) < len(subject), failures)
        problems = git_check.commit_problems(subject, policy)
        check(f"...and passes: {subject}", not any("caps it at" in p for p in problems), failures)

    # The rule must still bite on a subject the author genuinely wrote too long.
    over = "fix(tools): " + "x" * 90 + " (#999)"
    problems = git_check.commit_problems(over, policy)
    hits = [p for p in problems if "caps it at" in p]
    check("a genuinely over-long subject still fails", len(hits) == 1, failures)
    if hits:
        check(f"...stating BOTH lengths, so nobody re-derives why the numbers differ\n  {hits[0]}",
              "squash-merge appended" in hits[0] and str(len(over)) in hits[0], failures)

    # --- a generated repo inherits the cap as its own data ----------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "rendered")
        rc = subprocess.run([sys.executable, os.path.join(TOOLS, "render.py"), REFERENCE,
                             "--out", out], capture_output=True, text=True, timeout=180)
        check("the reference manifest renders", rc.returncode == 0, failures)
        if rc.returncode == 0:
            rendered = git_check.load_policy(os.path.join(out, git_check.PROJECT_POLICY))
            check("a generated repo's git-policy.yaml carries the cap",
                  (rendered.get("commit") or {}).get("subject_max") == cap, failures)
            with open(os.path.join(out, "AGENTS.md"), encoding="utf-8") as fh:
                agents = fh.read()
            check(f"...and its contract states the SAME number rather than a stale literal",
                  f"≤{cap} chars" in agents, failures)

    # --- this repo now states the rule for ITSELF, not only in the template ------------------
    with open(os.path.join(os.path.dirname(ROOT), "AGENTS.md"), encoding="utf-8") as fh:
        own = fh.read()
    check("EADOS's own AGENTS.md states the cap — it used to ask projects to keep a rule it had "
          "never written down for itself", f"{cap} characters" in own or f"≤ {cap}" in own,
          failures)

    if failures:
        print("test-subject-cap: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-subject-cap: OK — the cap is policy data the tool reads (and cannot be disabled by "
          "omitting it), only the authored part of a merged subject is measured, real merged "
          "subjects from `main` pass, an over-long one still fails with both lengths named, and a "
          "generated repo inherits the same number in its policy and its contract.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
