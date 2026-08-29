#!/usr/bin/env python3
"""`git_check` must judge a generated repo by ITS contract, not the factory's (#358).

`GIT_POLICY` was hardcoded and `main()` exposed no way to change it, so after `scaffold` handed
governance to a generated repo's own `AGENTS.md` — the two-contracts rule — this tool still
evaluated that repo's commits against **EADOS's** Conventional-Commit scope list. On the consumer
that reported it, the lists overlapped in **2 of 13** entries, so it was wrong in both directions:

  * loud   — 11 of the project's own scopes rejected (`docs(security):` on a valid commit);
  * quiet  — 19 of the factory's accepted, so `fix(profiles):` sails through a Java library that
             has no profiles. Nobody notices a check that passes, which makes this the worse half.

So the assertions below run against a **real render**, not a hand-built fixture. That is the point:
a fixture is written by whoever wrote the tool and encodes the same assumptions, while a rendered
repo carries the *project's* contract — the only artifact that can contradict them. This defect was
found in the field, not in CI, for exactly that reason (see #359).

    python .eados-core/tools/tests/test_git_policy_scope.py
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
REPO_ROOT = os.path.dirname(ROOT)
REFERENCE = os.path.join(ROOT, "orchestrator", "examples", "reference.yaml")
sys.path.insert(0, TOOLS)
import git_check   # noqa: E402
import render      # noqa: E402


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def run(args):
    proc = subprocess.run([sys.executable, os.path.join(TOOLS, "git_check.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", timeout=120)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def main():
    failures = []

    with open(REFERENCE, encoding="utf-8") as fh:
        manifest = render.load_yaml(fh.read())
    project_scopes = [str(s) for s in ((manifest.get("governance") or {}).get("scopes") or [])]
    factory = git_check.load_policy()
    factory_scopes = [str(s) for s in ((factory.get("commit") or {}).get("scopes") or [])]

    # The premise, asserted rather than assumed: if the two lists ever converged, every assertion
    # below would pass for the wrong reason.
    only_project = [s for s in project_scopes if s not in factory_scopes]
    only_factory = [s for s in factory_scopes if s not in project_scopes]
    check(f"the project and factory scope lists genuinely differ ({only_project} / {only_factory})",
          only_project and only_factory, failures)

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "rendered")
        rc = subprocess.run([sys.executable, os.path.join(TOOLS, "render.py"), REFERENCE,
                             "--out", out], capture_output=True, text=True, timeout=180)
        check(f"the reference manifest renders ({rc.stderr[-200:] if rc.returncode else ''})",
              rc.returncode == 0, failures)
        if rc.returncode != 0:
            print("test-git-policy-scope: FAIL\n  render failed")
            return 1

        # --- the rendered repo carries its own policy, and it is the manifest's --------------
        rendered = os.path.join(out, git_check.PROJECT_POLICY)
        check("a generated repo ships docs/workflow/git-policy.yaml", os.path.exists(rendered),
              failures)
        policy = git_check.load_policy(rendered)
        check(f"...whose scopes are the MANIFEST's ({(policy.get('commit') or {}).get('scopes')})",
              [str(s) for s in ((policy.get("commit") or {}).get("scopes") or [])]
              == project_scopes, failures)
        check("...and whose branch types are the Conventional Commit vocabulary, in lockstep "
              "with the factory spec",
              [str(t) for t in ((policy.get("branch_naming") or {}).get("types") or [])]
              == [str(t) for t in ((factory.get("branch_naming") or {}).get("types") or [])],
              failures)
        check("...parsed by the shipped loader without a hand-rolled reader",
              isinstance(policy.get("commit"), dict), failures)

        # --- discovery: a consumer repo resolves to ITS policy, not the vendored factory's ----
        path, origin = git_check.resolve_policy(out)
        check(f"discovery picks the project's policy ({origin})",
              path == rendered and "own" in origin, failures)
        path, origin = git_check.resolve_policy(REPO_ROOT)
        check(f"...and the factory's only in the factory ({origin})",
              path == git_check.GIT_POLICY and "factory" in origin, failures)
        path, origin = git_check.resolve_policy(tmp)
        check("...and NOTHING in a repo that is neither — an ungated fallback is the defect",
              path is None, failures)
        path, _ = git_check.resolve_policy(out, explicit=git_check.GIT_POLICY)
        check("--policy always wins", path == git_check.GIT_POLICY, failures)

        # --- both directions of the original defect, through the real CLI --------------------
        good = project_scopes[0]
        rc, txt = run(["--repo", out, "--branch", "docs/x", "--message", f"docs({good}): ok"])
        check(f"THE LOUD HALF: a project scope '{good}' is accepted (was rejected)\n{txt}",
              "is not a declared scope" not in txt, failures)
        check("...and the readout names which policy it used",
              "docs/workflow/git-policy.yaml" in txt, failures)

        # The old behaviour, pinned as the trap it was: judging this repo by the FACTORY's policy
        # is one `--policy` away, and it rejects the project's own valid commit. Asserting it here
        # keeps the defect demonstrable after the code that caused it is gone — the same reason
        # test_run_records_committable pins the naive .gitignore form.
        rc, txt = run(["--repo", out, "--branch", "docs/x", "--message", f"docs({good}): ok",
                       "--policy", git_check.GIT_POLICY])
        check(f"THE DEFECT, pinned: judged by the factory's policy, the project's own scope "
              f"'{good}' is rejected\n{txt}", "is not a declared scope" in txt and rc != 0,
              failures)

        bad = only_factory[0]
        rc, txt = run(["--repo", out, "--branch", "fix/x", "--message", f"fix({bad}): sneaks in"])
        check(f"THE QUIET HALF: a factory-only scope '{bad}' is REJECTED (was accepted) — the "
              f"half nobody notices\n{txt}", "is not a declared scope" in txt and rc != 0, failures)

        # --- a repo generated before this shipped: narrower, and it says so -------------------
        legacy = os.path.join(tmp, "legacy")
        os.makedirs(legacy)
        rc, txt = run(["--repo", legacy, "--branch", "fix/x", "--message", "fix(whatever): ok",
                       "--advisory"])
        check(f"a policy-less repo does not fail on a scope it never declared\n{txt}",
              "is not a declared scope" not in txt, failures)
        check("...and does not silently borrow the factory's list either",
              "policy: NONE" in txt, failures)
        check("...stating exactly what it did NOT check (L-0006)",
              "[PARTIAL]" in txt and "NOT checked" in txt and "SCOPES" in txt, failures)
        check("...and how to fix it", "git-policy.yaml" in txt, failures)
        # What survives must still survive: the universal half is not thrown away with the rest.
        rc, txt = run(["--repo", legacy, "--branch", "nonsense-branch",
                       "--message", "just a sentence with no type", "--advisory"])
        check(f"...while branch shape and commit convention are still enforced\n{txt}",
              "does not match" in txt and "Conventional-Commit shaped" in txt, failures)
        rc, txt = run(["--repo", legacy, "--branch", "banana/x", "--message", "banana: nope",
                       "--advisory"])
        check(f"...including the type vocabulary\n{txt}",
              "is not a declared type" in txt, failures)

    if failures:
        print("test-git-policy-scope: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-git-policy-scope: OK — a rendered repo carries its own git policy and is judged by "
          "it (both directions of #358 asserted against a real render), the factory's applies only "
          "in the factory, and a repo with neither is checked more narrowly and told so.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
