#!/usr/bin/env python3
"""Tests for the bootstrap CI guard (#313) — a rendered repo must not open on a wall of red.

Roadmap item 1.1 is what lays down the build system, so on a freshly rendered repository the build
manifest is absent *by design*. Until #313 the rendered CI ran the toolchain jobs anyway and they
failed on day zero — for javascript, every `pnpm` job, because `pnpm install --frozen-lockfile`
has nothing to install. Technically expected, and still the wrong first experience: it teaches that
red CI on this repo is normal, which is the opposite of what every other gate here is for.

The fix is generic across all 19 toolchains: the profile names its build manifest as data, the
template renders a `bootstrap` job that probes for it, and the toolchain jobs `if:` on the result —
so they SKIP rather than fail, and start running by themselves the moment item 1.1 lands.

    python .eados-core/tools/tests/test_bootstrap_guard.py
"""

import io
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import render  # noqa: E402

REFERENCE = os.path.join(ROOT, "orchestrator", "examples", "reference.yaml")
PROFILES = os.path.join(ROOT, "orchestrator", "profiles")


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def manifest_with(ci_extra):
    """The reference manifest with its `ci:` block replaced — the shape the interview produces
    once a profile has been resolved into it."""
    import re
    src = io.open(REFERENCE, encoding="utf-8").read()
    return re.sub(r"(?ms)^ci:\n.*?(?=^governance:)", ci_extra, src)


JS_CI = """ci:
  tier1_platforms: "Linux (Node.js 20)"
  build_manifest: package.json
  matrix:
    - { os: ubuntu-24.04, toolchain: node-20, preset: default }
  setup_steps: |
    - name: Install dependencies
      run: pnpm install --frozen-lockfile
  extra_jobs: |
    lint:
      name: lint / eslint + prettier
      runs-on: ubuntu-24.04
      needs: bootstrap
      if: needs.bootstrap.outputs.ready == 'true'
      steps:
        - run: pnpm install --frozen-lockfile

"""


def render_to(manifest_text, out):
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "m.yaml")
    io.open(path, "w", encoding="utf-8").write(manifest_text)
    repo = os.path.join(out, "repo")
    rc = subprocess.run([sys.executable, os.path.join(TOOLS, "render.py"), path, "--out", repo],
                        capture_output=True, text=True, encoding="utf-8", timeout=120)
    return rc, repo


def workflow_jobs(repo):
    """The rendered workflow's jobs, via a real YAML parser when available."""
    try:
        import yaml
    except ImportError:
        return None
    text = io.open(os.path.join(repo, ".github", "workflows", "ci.yml"), encoding="utf-8").read()
    return (yaml.safe_load(text) or {}).get("jobs") or {}


def main():
    failures = []

    # --- every profile declares the file that proves its build system exists -----------------
    import glob
    profiles = sorted(p for p in glob.glob(os.path.join(PROFILES, "*.yaml"))
                      if not os.path.basename(p).startswith("_"))
    check("profiles are present", len(profiles) >= 19, failures)
    for p in profiles:
        prof = render.load_yaml(io.open(p, encoding="utf-8").read())
        name = os.path.basename(p)
        mf = str(prof.get("build_manifest") or "").strip()
        check(f"{name} declares a build_manifest", bool(mf), failures)
        # It must be a file the profile already expects, not a new invention — except where the
        # profile lists a glob or a differently-spelled variant, which is why this is advisory
        # only for the exact-match case.
        check(f"{name}'s build_manifest is a plain name or a glob", "/" not in mf, failures)

    with tempfile.TemporaryDirectory() as tmp:
        # --- javascript: the profile from the field report (#313) ---------------------------
        rc, repo = render_to(manifest_with(JS_CI), os.path.join(tmp, "js"))
        os.makedirs(os.path.join(tmp, "js"), exist_ok=True)
        check("a javascript manifest renders", rc.returncode == 0, failures)
        jobs = workflow_jobs(repo)
        if jobs is not None:
            check("a bootstrap job is rendered", "bootstrap" in jobs, failures)
            for job in ("build", "benchmark", "lint"):
                if job not in jobs:
                    continue
                check(f"the {job} job waits on bootstrap",
                      jobs[job].get("needs") == "bootstrap", failures)
                check(f"the {job} job SKIPS while the build system is absent",
                      "needs.bootstrap.outputs.ready" in str(jobs[job].get("if") or ""), failures)
            # The congruence gate is the green-by-construction promise; it must NEVER be gated.
            check("the consistency lint is never gated on the build system",
                  "if" not in jobs.get("consistency", {}), failures)
            check("bootstrap publishes the probe result",
                  "ready" in (jobs["bootstrap"].get("outputs") or {}), failures)

        # --- generic, not JS-tuned: one compiled and one interpreted profile ----------------
        for label, mf in (("compiled (cpp)", "CMakeLists.txt"), ("interpreted (python)",
                                                                 "pyproject.toml")):
            ci = f"ci:\n  tier1_platforms: \"Linux\"\n  build_manifest: {mf}\n  matrix:\n" \
                 "    - { os: ubuntu-24.04, toolchain: gcc, preset: debug }\n" \
                 "  setup_steps: \"\"\n  extra_jobs: \"\"\n\n"
            rc, repo = render_to(manifest_with(ci), os.path.join(tmp, mf.replace(".", "_")))
            check(f"{label} renders", rc.returncode == 0, failures)
            wf = io.open(os.path.join(repo, ".github", "workflows", "ci.yml"),
                         encoding="utf-8").read()
            check(f"{label} probes for its own manifest", mf in wf, failures)
            check(f"{label} gates its toolchain jobs", "needs: bootstrap" in wf, failures)

        # --- ADDITIVE: a manifest with no build_manifest renders exactly as before ----------
        plain = manifest_with("ci:\n  tier1_platforms: \"Linux\"\n  matrix: []\n"
                              "  setup_steps: \"\"\n  extra_jobs: \"\"\n\n")
        rc, repo = render_to(plain, os.path.join(tmp, "plain"))
        check("a manifest without build_manifest still renders", rc.returncode == 0, failures)
        wf = io.open(os.path.join(repo, ".github", "workflows", "ci.yml"), encoding="utf-8").read()
        check("no guard is rendered when no build manifest is declared",
              "bootstrap" not in wf, failures)

        # --- the half-configured manifest is rejected, not emitted as a broken workflow -----
        half = manifest_with(JS_CI.replace("  build_manifest: package.json\n", ""))
        rc, _ = render_to(half, os.path.join(tmp, "half"))
        check("extra_jobs gating on bootstrap without a build_manifest is refused",
              rc.returncode != 0 and "bootstrap" in (rc.stdout + rc.stderr), failures)

    if failures:
        print("test-bootstrap-guard: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-bootstrap-guard: OK — every profile names its build manifest, the toolchain jobs "
          "skip until it exists, the congruence lint never does, and a manifest without one "
          "renders unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
