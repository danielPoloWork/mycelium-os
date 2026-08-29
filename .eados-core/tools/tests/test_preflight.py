#!/usr/bin/env python3
"""Issue #154 — environment preflight. Proves preflight.py detects missing/unauthenticated tools,
degrades cleanly on partial environments, and emits OS-specific hints. All dependencies (which /
run / version / platform) are injected, so the logic is exercised without touching the real box.
A behavioural tail runs the CLI to confirm it never tracebacks. Dependency-free.

    python .eados-core/tools/tests/test_preflight.py
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TOOLS))
sys.path.insert(0, TOOLS)
import preflight   # noqa: E402


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def all_present(name):
    return f"/usr/bin/{name}"


def main():
    P = preflight
    failures = []

    # --- python floor -------------------------------------------------------
    below = P.check_python(version_info=(3, 6, 0), floor=(3, 8), platform="linux")
    check("python below floor -> not ok", not below["ok"], failures)
    check("python below floor -> carries a hint", bool(below["hint"]), failures)
    at = P.check_python(version_info=(3, 12, 1), floor=(3, 8), platform="linux")
    check("python at/above floor -> ok", at["ok"], failures)
    check("python ok -> required", at["required"], failures)

    # --- tool present / missing + OS-specific hints -------------------------
    present = P.check_tool("git", which=lambda n: "/usr/bin/git", platform="linux")
    check("git present -> ok", present["ok"], failures)
    check("git present -> detail is the resolved path", present["detail"] == "/usr/bin/git", failures)

    miss_mac = P.check_tool("git", which=lambda n: None, platform="darwin")
    check("git missing -> not ok", not miss_mac["ok"], failures)
    check("git missing (darwin) -> brew hint", "brew" in miss_mac["hint"], failures)
    miss_win = P.check_tool("git", which=lambda n: None, platform="win32")
    check("git missing (win32) -> winget hint", "winget" in miss_win["hint"], failures)
    miss_lin = P.check_tool("gh", which=lambda n: None, platform="linux")
    check("gh missing (linux) -> apt/cli.github hint",
          "apt" in miss_lin["hint"] or "cli.github.com" in miss_lin["hint"], failures)
    # per-OS hints are actually distinct (not one string reused)
    check("git hints differ across OSes", miss_mac["hint"] != miss_win["hint"], failures)

    # --- gh auth ------------------------------------------------------------
    authed = P.check_gh_auth(run=lambda cmd: (0, "Logged in to github.com"), platform="linux")
    check("gh authed -> ok", authed["ok"], failures)
    unauth = P.check_gh_auth(run=lambda cmd: (1, "not logged in"), platform="linux")
    check("gh unauth -> not ok", not unauth["ok"], failures)
    check("gh unauth -> `gh auth login` hint", "gh auth login" in unauth["hint"], failures)

    # --- interaction contract presence (advisory, #280) ---------------------
    present = P.check_interaction_contract(root="/repo", exists=lambda p: True)
    check("contract present -> ok", present["ok"], failures)
    check("contract check is ALWAYS advisory (never required)", not present["required"], failures)
    check("contract present -> detail points at AGENTS.md §10",
          "AGENTS.md §10" in present["detail"], failures)
    absent = P.check_interaction_contract(root="/repo", exists=lambda p: False)
    check("contract absent -> not ok", not absent["ok"], failures)
    check("contract absent -> still advisory (never required)", not absent["required"], failures)
    check("contract absent -> a restore hint, not silence", "interaction.yaml" in absent["hint"], failures)
    check("the probed path is the interaction spec under the given root",
          P.INTERACTION_SPEC.endswith(os.path.join("interaction", "interaction.yaml")), failures)

    # --- composition: everything present + authed --------------------------
    good = dict(which=all_present, run=lambda cmd: (0, ""), version_info=(3, 12, 0), platform="linux")
    checks, healthy = P.preflight(**good)
    check("all present + authed -> healthy", healthy, failures)
    check("healthy run -> no failing required check",
          all(c["ok"] for c in checks if c["required"]), failures)
    check("the interaction-contract check rides along in the composed checks",
          any(c["name"] == "interaction-contract" for c in checks), failures)

    # a MISSING interaction contract is advisory: it never flips the toolchain verdict --------
    checks, healthy = P.preflight(exists=lambda p: False, **good)
    ic = [c for c in checks if c["name"] == "interaction-contract"][0]
    check("missing contract -> the check reports not-ok", not ic["ok"], failures)
    check("missing contract -> healthy is UNCHANGED (advisory, not a gate)", healthy, failures)

    # --- git missing -> unhealthy; report names git with a usable hint ------
    def no_git(n):
        return None if n == "git" else f"/usr/bin/{n}"
    checks, healthy = P.preflight(which=no_git, run=lambda cmd: (0, ""),
                                  version_info=(3, 12, 0), platform="win32")
    check("git missing -> unhealthy", not healthy, failures)
    report = "\n".join(P.format_report(checks))
    check("report names git", "git:" in report, failures)
    check("report carries the win32 git hint",
          "winget" in report or "git-scm" in report, failures)
    check("format_report never tracebacks (produced lines)", bool(report), failures)

    # --- gh missing -----------------------------------------------------------
    def no_gh(n):
        return None if n == "gh" else f"/usr/bin/{n}"
    # required by default -> unhealthy, and auth is skipped (not crashed)
    checks, healthy = P.preflight(require_gh=True, which=no_gh, run=lambda cmd: (0, ""),
                                  version_info=(3, 12, 0), platform="linux")
    check("gh missing + required -> unhealthy", not healthy, failures)
    auth = [c for c in checks if c["name"] == "gh-auth"][0]
    check("gh missing -> auth check skipped (not required)",
          auth["skipped"] and not auth["required"], failures)
    # advisory (--no-gh) -> a box with only git is healthy
    checks, healthy = P.preflight(require_gh=False, which=no_gh, run=lambda cmd: (0, ""),
                                  version_info=(3, 12, 0), platform="linux")
    check("gh missing but advisory -> healthy (partial env tolerated)", healthy, failures)

    # --- gh present but UNauthenticated -> unhealthy ------------------------
    checks, healthy = P.preflight(which=all_present, run=lambda cmd: (1, "not logged in"),
                                  version_info=(3, 12, 0), platform="linux")
    check("gh present but unauth -> unhealthy", not healthy, failures)

    # --- behavioural: the CLI runs and never tracebacks --------------------
    proc = subprocess.run([sys.executable, os.path.join(TOOLS, "preflight.py"), "--no-gh"],
                          cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = proc.stdout.decode("utf-8", "replace")
    check("CLI prints its header", "EADOS preflight" in out, failures)
    check("CLI never tracebacks", "Traceback (most recent call last)" not in out, failures)
    check("CLI exit code is 0/1 (a clean verdict, not a crash)",
          proc.returncode in (0, 1), failures)
    helprun = subprocess.run([sys.executable, os.path.join(TOOLS, "preflight.py"), "--help"],
                             cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    check("--help exits 0", helprun.returncode == 0, failures)

    if failures:
        print("test-preflight: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} preflight invariant(s) broken.")
        return 1
    print("test-preflight: OK - detects missing/unauth python/git/gh, degrades on partial envs, "
          "emits OS-specific hints (#154).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
