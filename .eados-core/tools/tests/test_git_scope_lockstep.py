#!/usr/bin/env python3
"""The commit-scope vocabulary has one source of truth, and the contract must match it (#365).

`os/git/git.yaml` declared **21** scopes; `AGENTS.md` §6 listed **8**; `main` used **52**. Three
surfaces, three answers, and the one an agent reads first was the most wrong — the worst direction
for a contract to be stale in. Nothing watched, because `git-policy` is advisory and reports into a
void (the same silence behind #363's 178 subject-length violations).

Modelled on `interaction-lockstep` (#279): data is the source of truth, prose may elaborate but
never omit. **Two-way**, because a one-way check validates half a relationship and reports it as
whole (L-0009) — prose that outlives its data sends an agent to a scope `git_check` will reject.

    python .eados-core/tools/tests/test_git_scope_lockstep.py
"""

import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
REPO_ROOT = os.path.dirname(ROOT)
REFERENCE = os.path.join(ROOT, "orchestrator", "examples", "reference.yaml")
sys.path.insert(0, TOOLS)
import eados_lint as lint   # noqa: E402
import git_check            # noqa: E402
import render               # noqa: E402

PROSE = ("- Conventional Commits for messages. Scopes for this repo:\n"
         "  `alpha`, `beta`, `gamma`.\n"
         "  <!-- the `git-scope-lockstep` gate holds this against `os/git/git.yaml` -->\n")


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- the pure check, both directions -----------------------------------------------------
    check("a matching pair is congruent",
          lint.git_scope_lockstep_problems(["alpha", "beta", "gamma"], PROSE) == [], failures)

    missing = lint.git_scope_lockstep_problems(["alpha", "beta", "gamma", "delta"], PROSE)
    check(f"a scope in the data but not the prose fails ({missing})",
          len(missing) == 1 and "omits" in missing[0] and "delta" in missing[0], failures)

    extra = lint.git_scope_lockstep_problems(["alpha", "beta"], PROSE)
    check(f"THE OTHER DIRECTION: a scope in the prose but not the data fails too ({extra})",
          len(extra) == 1 and "does not declare" in extra[0] and "gamma" in extra[0], failures)

    check("a contract that states no vocabulary at all fails",
          lint.git_scope_lockstep_problems(["alpha"], "no list here") != [], failures)
    check("...and so does a spec that declares none",
          lint.git_scope_lockstep_problems([], PROSE) != [], failures)

    # The bug the first version of this gate had: a looser capture swept up every backticked token
    # near the list — including the gate's own name in the note beneath it — so it failed on the
    # tree that introduced it. Pinned, because "match the structure, not a span between delimiters"
    # is the property, and a rewrite would quietly lose it.
    noisy = PROSE + ("- **`git.yaml` is the source of truth** and `git_check` reads it; see "
                     "`docs/workflow` and `main`.\n")
    check("prose ABOUT the list is not mistaken for the list",
          lint.git_scope_lockstep_problems(["alpha", "beta", "gamma"], noisy) == [], failures)

    # --- the real tree ------------------------------------------------------------------------
    spec = render.load_yaml(lint.read(os.path.join(ROOT, "orchestrator", "os", "git", "git.yaml")))
    declared = [str(s) for s in ((spec.get("commit") or {}).get("scopes") or [])]
    contract = lint.read(os.path.join(REPO_ROOT, "AGENTS.md"))
    check(f"the shipped tree is congruent ({len(declared)} scopes)",
          lint.git_scope_lockstep_problems(declared, contract) == [], failures)
    check("...and it is a real vocabulary, not an empty one that passes vacuously",
          len(declared) >= 30, failures)

    # Proven to bite on the REAL contract, not only on a fixture.
    broken = contract.replace(f"`{declared[-1]}`.", ".")
    check(f"dropping '{declared[-1]}' from the real AGENTS.md fails the gate",
          lint.git_scope_lockstep_problems(declared, broken) != [], failures)

    # --- the vocabulary must cover what people actually write --------------------------------
    log = subprocess.run(["git", "log", "--format=%s", "--no-merges"], cwd=REPO_ROOT,
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=120)
    if log.returncode == 0:
        used = [m.group(1) for m in
                (re.match(r"^[a-z]+\(([^)]+)\)!?: ", s) for s in log.stdout.split("\n")) if m]
        if used:
            covered = sum(1 for u in used if u in declared)
            pct = covered / len(used) * 100
            # Not a hard threshold on history (it is immutable and full of pre-fix commits) — a
            # floor that catches the vocabulary being gutted. 57% before this change, 87% after.
            check(f"the vocabulary covers most of what `main` actually uses ({pct:.0f}%)",
                  pct >= 80, failures)

    # --- the generated contract needs no rule: it renders from the manifest -------------------
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "rendered")
        rc = subprocess.run([sys.executable, os.path.join(TOOLS, "render.py"), REFERENCE,
                             "--out", out], capture_output=True, text=True, timeout=180)
        check("the reference manifest renders", rc.returncode == 0, failures)
        if rc.returncode == 0:
            with open(REFERENCE, encoding="utf-8") as fh:
                manifest_scopes = [str(s) for s in
                                   ((render.load_yaml(fh.read()).get("governance") or {})
                                    .get("scopes") or [])]
            agents = lint.read(os.path.join(out, "AGENTS.md"))
            policy = git_check.load_policy(os.path.join(out, git_check.PROJECT_POLICY))
            check("a generated repo's contract and policy agree by construction — both render "
                  "from the manifest, which is why only the FACTORY drifted",
                  lint.git_scope_lockstep_problems(manifest_scopes, agents) == []
                  and [str(s) for s in ((policy.get("commit") or {}).get("scopes") or [])]
                  == manifest_scopes, failures)

    if failures:
        print("test-git-scope-lockstep: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-git-scope-lockstep: OK — the contract and the data agree, the gate bites in BOTH "
          "directions (on the real AGENTS.md, not just a fixture), prose about the list is not "
          "mistaken for the list, the vocabulary covers what `main` actually writes, and a "
          "generated repo stays congruent by construction.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
