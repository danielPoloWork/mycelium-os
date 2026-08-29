#!/usr/bin/env python3
"""EADOS preflight — verify the toolchain the pipeline assumes is present & authenticated (#154, M12).

The whole pipeline shells out to `python .eados-core/tools/*.py`, uses `git` for the bootstrap, and
drives an authenticated `gh` CLI for milestone seeding, PR drafting, and `derive_links` / `pr_review`.
Those were only ever *prose* prerequisites (README, walkthrough): nothing detected a missing or
unauthenticated tool, so a maintainer discovered the gap only when a step failed mid-run with a raw
error. This tool detects them up front and prints an OS-specific install/auth hint for anything
missing.

It reports; it changes nothing. It exits 0 when every *required* tool is present (and `gh`
authenticated) and **non-zero when a required tool is missing or unauthenticated**, so it doubles as
a pre-flight gate at the start of `init` (and before scaffold/bootstrap). Dependency-free (stdlib
only) — the one check that must run in a minimal environment. Partial environments degrade to clear
per-tool guidance, never a traceback.

It also surfaces, **advisory**, whether the interaction contract (the *how you communicate* spec,
ADR-0022) is present on disk — the section-presence half of the M17 17.4 runtime re-assertion
(#280). That note never moves the exit code; the toolchain verdict is unchanged.

Note: this is itself a *Python* tool, so it cannot help when Python is absent entirely — the guided
installer (`setup/setup.sh` / `setup.ps1`) carries that non-Python bootstrap hint.

    python .eados-core/tools/preflight.py [--no-gh]
"""

import os
import shutil
import subprocess
import sys

# The tools are plain stdlib and target the CI's 3.12; keep the advertised floor generous so a
# slightly older interpreter is a warning-with-a-hint, not a false alarm.
PYTHON_FLOOR = (3, 8)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .eados-core/
# The interaction contract's source of truth (ADR-0022). Preflight checks its PRESENCE only — the
# *section-presence* half of the runtime re-assertion (#280); the operative rules live in AGENTS.md
# §10 and self_check.py front-runs them. A plain os.path lookup keeps preflight dependency-free (it
# never parses YAML — it is the one check that must run in a minimal environment).
INTERACTION_SPEC = os.path.join("orchestrator", "os", "interaction", "interaction.yaml")

# OS-specific install / auth hints. Keyed by check name, then normalised platform
# (win32 / darwin / linux / other); "*" applies to every platform.
HINTS = {
    "python": {
        "win32":  "install Python — winget install Python.Python.3.12  (or https://www.python.org/downloads/)",
        "darwin": "install Python — brew install python@3.12  (or https://www.python.org/downloads/)",
        "linux":  "install Python — sudo apt install python3  |  sudo dnf install python3",
        "other":  "install Python — https://www.python.org/downloads/",
    },
    "git": {
        "win32":  "install Git — winget install Git.Git  (or https://git-scm.com/download/win)",
        "darwin": "install Git — brew install git  (or xcode-select --install)",
        "linux":  "install Git — sudo apt install git  |  sudo dnf install git",
        "other":  "install Git — https://git-scm.com/downloads",
    },
    "gh": {
        "win32":  "install the GitHub CLI — winget install GitHub.cli  (or https://cli.github.com/)",
        "darwin": "install the GitHub CLI — brew install gh  (or https://cli.github.com/)",
        "linux":  "install the GitHub CLI — sudo apt install gh  |  see https://cli.github.com/",
        "other":  "install the GitHub CLI — https://cli.github.com/",
    },
    "gh-auth": {
        "*": "authenticate — gh auth login",
    },
}


def normalize_platform(platform):
    """Map a raw sys.platform value onto the hint table's keys."""
    if platform.startswith("linux"):
        return "linux"
    if platform in ("win32", "cygwin", "msys"):
        return "win32"
    if platform == "darwin":
        return "darwin"
    return "other"


def hint_for(name, platform):
    table = HINTS.get(name, {})
    return table.get(normalize_platform(platform)) or table.get("*") or table.get("other") or ""


def _check(name, ok, required, detail, hint, skipped=False):
    return {"name": name, "ok": ok, "required": required,
            "detail": detail, "hint": hint, "skipped": skipped}


def check_python(version_info=None, floor=PYTHON_FLOOR, platform=None):
    """The running interpreter meets the version floor. (Python-missing-entirely is out of scope:
    this tool cannot run without it — that case belongs to the installer's non-Python check.)"""
    v = version_info if version_info is not None else sys.version_info
    platform = platform if platform is not None else sys.platform
    have = (v[0], v[1])
    ver = f"{v[0]}.{v[1]}.{v[2] if len(v) > 2 else 0}"
    if have >= tuple(floor):
        return _check("python", True, True, f"{ver} (>= {floor[0]}.{floor[1]})", "")
    return _check("python", False, True,
                  f"{ver} is below the {floor[0]}.{floor[1]} floor",
                  hint_for("python", platform))


def check_tool(name, required=True, which=None, platform=None):
    """A named executable resolves on PATH."""
    which = which if which is not None else shutil.which
    platform = platform if platform is not None else sys.platform
    path = which(name)
    if path:
        return _check(name, True, required, path, "")
    return _check(name, False, required, "not found on PATH", hint_for(name, platform))


def _default_run(cmd):
    """Run a probe command, returning (returncode, combined_output). Never raises — a missing
    binary or a timeout becomes a non-zero code so callers stay traceback-free."""
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=15, text=True)
        return proc.returncode, proc.stdout or ""
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)


def check_gh_auth(run=None, platform=None):
    """`gh` is authenticated (`gh auth status` exits 0). Callers invoke this only when `gh` exists."""
    run = run if run is not None else _default_run
    platform = platform if platform is not None else sys.platform
    rc, _out = run(["gh", "auth", "status"])
    if rc == 0:
        return _check("gh-auth", True, True, "authenticated", "")
    return _check("gh-auth", False, True, "not authenticated (`gh auth status` failed)",
                  hint_for("gh-auth", platform))


def check_interaction_contract(root=None, exists=None):
    """The interaction contract — how the agent communicates (calibrated confidence, no sycophancy,
    structured dissent, evidence-first pushback) — is present on disk before the run starts. This is
    the *section-presence* half of the runtime re-assertion (#280, ADR-0022 *re-ground* tier); the
    operative rules live in AGENTS.md §10 and the pre-PR checklist front-runs them (self_check.py).
    ADVISORY — never required: a run proceeds without it (older trees, the pure toolchain check), so
    it is a `note`, never a MISSING that fails the verdict. Presence-only, so it stays dependency-free
    (no YAML parse); `root`/`exists` are injectable for tests. Same `_check()` shape as the rest."""
    root = root if root is not None else ROOT
    exists = exists if exists is not None else os.path.exists
    if exists(os.path.join(root, INTERACTION_SPEC)):
        return _check("interaction-contract", True, False,
                      "present — calibrated confidence, no sycophancy, structured dissent (AGENTS.md §10)",
                      "")
    return _check("interaction-contract", False, False,
                  "not found — the how-you-communicate contract is absent (advisory)",
                  "restore orchestrator/os/interaction/interaction.yaml (ADR-0022); AGENTS.md §10 renders from it")


def preflight(*, require_gh=True, version_info=None, floor=PYTHON_FLOOR,
              which=None, run=None, platform=None, root=None, exists=None):
    """Compose the checks. Returns (checks, healthy): `healthy` is False iff a *required* check
    failed. `gh` (and thus its auth) drops to advisory when `require_gh` is False — the pure
    render path does not need it. The interaction-contract presence check is always advisory (it
    never moves `healthy`). All dependencies are injectable so the logic is unit-testable
    without touching the real environment."""
    which = which if which is not None else shutil.which
    platform = platform if platform is not None else sys.platform

    checks = [
        check_python(version_info=version_info, floor=floor, platform=platform),
        check_tool("git", required=True, which=which, platform=platform),
    ]
    gh = check_tool("gh", required=require_gh, which=which, platform=platform)
    checks.append(gh)
    if gh["ok"]:
        auth = check_gh_auth(run=run, platform=platform)
        auth["required"] = require_gh          # advisory when gh itself is advisory
        checks.append(auth)
    else:
        # Cannot probe auth without gh; record it as skipped (never required, never a crash).
        checks.append(_check("gh-auth", True, False, "skipped (gh not found)", "", skipped=True))

    # #280: advisory presence of the interaction contract — a note, never a gate (required=False).
    checks.append(check_interaction_contract(root=root, exists=exists))

    healthy = all(c["ok"] for c in checks if c["required"])
    return checks, healthy


def format_report(checks):
    """Render the checks as aligned report lines, with a hint under each failing one."""
    lines = []
    for c in checks:
        if c.get("skipped"):
            mark = "SKIP"
        elif c["ok"]:
            mark = "OK"
        else:
            mark = "MISSING" if c["required"] else "note"
        lines.append(f"[{mark:^7}] {c['name']}: {c['detail']}")
        if not c["ok"] and c["hint"]:
            lines.append(f"          → {c['hint']}")
    return lines


def main(argv=None):
    # issue #128: force UTF-8 stdio so the → arrows never mojibake or crash on cp1252 (Windows).
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(
        description="EADOS preflight - verify python/git/gh are present and gh authenticated.")
    ap.add_argument("--no-gh", action="store_true",
                    help="treat gh (and its auth) as advisory, not required (the pure render path)")
    args = ap.parse_args(argv)

    checks, healthy = preflight(require_gh=not args.no_gh)
    print("EADOS preflight - toolchain check")
    for line in format_report(checks):
        print(f"  {line}")
    if healthy:
        tail = "" if args.no_gh else " and gh authenticated"
        print(f"  OK - all required tools present{tail}.")
    else:
        print("  FAIL - install/authenticate the tools flagged above, then re-run.")
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
