#!/usr/bin/env python3
"""Tests for project-root discovery in the reporting tools (#347).

`doctor.py` and `eados.py` defaulted `--root` to **the manifest's own directory**. The prescribed
manifest location is `orchestrator/project.yaml` while `ROADMAP.md` and `links.yaml` live at the
**repo root**, so on a correctly generated repo they looked in `orchestrator/`, found neither, and
reported them absent. Both lookups are `isfile`-guarded, so the miss was silent: `/eados status`
described a roadmap that exists as missing, and `roadmap-covers-rfcs` / `traceability-lint`
degraded to `needs-input` for a reason with nothing to do with the project.

The case that matters is **the manifest one level down** — the shipped layout, and the one that was
broken. A test with the manifest beside the roadmap would have passed throughout.

    python .eados-core/tools/tests/test_root_discovery.py
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
ROADMAP = ("# ROADMAP\n\n## Milestone 1 - Foundation\n\nImplements RFC-0001.\n\n- [ ] 1.1 thing\n")
STATE = ("delivery_state:\n  phase: plan\n"
         "  refs: { rfcs: ['RFC-0001'], milestones: ['M1'], prs: [], releases: [] }\n\n")


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def consumer_layout(base, marker=".eados-core", manifest_subdir="orchestrator"):
    """The layout the factory actually renders: a root marker + ROADMAP.md at the root, and the
    manifest one level down."""
    os.makedirs(os.path.join(base, marker), exist_ok=True)
    mdir = os.path.join(base, manifest_subdir) if manifest_subdir else base
    os.makedirs(mdir, exist_ok=True)
    io.open(os.path.join(base, "ROADMAP.md"), "w", encoding="utf-8").write(ROADMAP)
    manifest = os.path.join(mdir, "project.yaml")
    io.open(manifest, "w", encoding="utf-8").write(
        STATE + io.open(REFERENCE, encoding="utf-8").read())
    return manifest


def run(tool, *args):
    out = subprocess.run([sys.executable, os.path.join(TOOLS, tool), *args],
                         capture_output=True, text=True, encoding="utf-8", timeout=120)
    return out.returncode, (out.stdout or "") + (out.stderr or "")


def main():
    failures = []

    with tempfile.TemporaryDirectory() as tmp:
        # --- project_root, the helper --------------------------------------------------------
        base = os.path.join(tmp, "repo")
        manifest = consumer_layout(base)
        check("a manifest one level down resolves to the repo root",
              render.project_root(manifest) == os.path.realpath(base)
              or render.project_root(manifest) == base, failures)

        flat = os.path.join(tmp, "flat")
        m_flat = consumer_layout(flat, manifest_subdir="")
        check("a manifest AT the root still resolves to the root",
              os.path.samefile(render.project_root(m_flat), flat), failures)

        deep = os.path.join(tmp, "repo", "orchestrator", "nested")
        os.makedirs(deep, exist_ok=True)
        m_deep = os.path.join(deep, "project.yaml")
        io.open(m_deep, "w", encoding="utf-8").write("schema_version: 1\n")
        check("discovery ascends more than one level",
              os.path.samefile(render.project_root(m_deep), base), failures)

        # `.git` is a root marker too — a repo that keeps its manifest elsewhere.
        gitonly = os.path.join(tmp, "gitrepo")
        m_git = consumer_layout(gitonly, marker=".git")
        check(".git alone identifies the root",
              os.path.samefile(render.project_root(m_git), gitonly), failures)

        # No marker anywhere: fall back to the manifest's dir — the previous behaviour, and the
        # right answer for a manifest that belongs to no project.
        orphan = os.path.join(tmp, "orphan")
        os.makedirs(orphan)
        m_orphan = os.path.join(orphan, "project.yaml")
        io.open(m_orphan, "w", encoding="utf-8").write("schema_version: 1\n")
        check("no marker anywhere falls back to the manifest's own directory",
              os.path.samefile(render.project_root(m_orphan), orphan), failures)

        # --- the tools, end to end: the artifact must be FOUND, not reported absent -----------
        rc, out = run("doctor.py", manifest)
        check("doctor no longer reports an existing ROADMAP as missing",
              "no ROADMAP.md found" not in out, failures)
        check("doctor resolves roadmap coverage from the repo root",
              "roadmap-covers-rfcs: OK" in out, failures)

        rc, out = run("eados.py", "plan", manifest)
        check("the roadmap-covers-rfcs gate no longer degrades to needs-input",
              "[needs-input] roadmap-covers-rfcs" not in out, failures)
        check("…it evaluates OK instead", "[OK] roadmap-covers-rfcs" in out, failures)

        # --- an explicit --root still wins ---------------------------------------------------
        empty = os.path.join(tmp, "empty")
        os.makedirs(empty)
        rc, out = run("doctor.py", manifest, "--root", empty)
        check("an explicit --root overrides discovery",
              "no ROADMAP.md found" in out, failures)

    if failures:
        print("test-root-discovery: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-root-discovery: OK — the shipped layout (manifest one level down) resolves to the "
          "repo root, discovery ascends and falls back honestly, and an explicit --root still wins.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
