#!/usr/bin/env python3
"""Tests for the generated-repo provenance stamp (#319).

EADOS has shipped a dozen minor versions, several carrying security fixes, and a generated
repository recorded **nothing** about which factory produced it. ADR-0003 is right that a
generated repo must never be re-rendered on a factory change — but *"do not re-render"* is not
*"do not tell them what changed"*, and neither is possible without knowing where they started.

The load-bearing property is durability: a repo whose manifest RECORDS a version must keep saying
that version after the factory moves on. A stamp that silently re-derives to "today" is worse than
none, because it reads like provenance while being a clock.

    python .eados-core/tools/tests/test_provenance_stamp.py
"""

import io
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import render  # noqa: E402

REFERENCE = os.path.join(ROOT, "orchestrator", "examples", "reference.yaml")
RECORDED = ("generated_by:\n"
            "  eados_version: \"2.9.0\"\n"
            "  eados_commit: abc1234\n"
            "  rendered_at: \"2026-01-15\"\n\n")


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def render_to(manifest_text, out):
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "m.yaml")
    io.open(path, "w", encoding="utf-8").write(manifest_text)
    repo = os.path.join(out, "repo")
    rc = subprocess.run([sys.executable, os.path.join(TOOLS, "render.py"), path, "--out", repo],
                        capture_output=True, text=True, encoding="utf-8", timeout=120)
    return rc, repo


def main():
    failures = []
    base = io.open(REFERENCE, encoding="utf-8").read()

    # --- derived: version from the CHANGELOG, which the version-lockstep gate already governs ---
    prov = render.factory_provenance()
    check("a version is derived, not hand-maintained",
          re.fullmatch(r"\d+\.\d+\.\d+", prov["eados_version"] or "") is not None, failures)
    check("a date is stamped", re.fullmatch(r"\d{4}-\d{2}-\d{2}", prov["rendered_at"] or "")
          is not None, failures)
    changelog = io.open(os.path.join(os.path.dirname(ROOT), "CHANGELOG.md"), encoding="utf-8").read()
    check("the derived version IS the CHANGELOG's latest release",
          prov["eados_version"] == re.findall(r"(?m)^##\s*\[(\d+\.\d+\.\d+)\]", changelog)[0],
          failures)

    # --- THE property: a recorded stamp wins over the running factory, forever -----------------
    recorded = render.factory_provenance({"generated_by": {"eados_version": "2.9.0",
                                                           "eados_commit": "abc1234",
                                                           "rendered_at": "2026-01-15"}})
    check("a recorded stamp is not overwritten by the running factory",
          recorded["eados_version"] == "2.9.0" and recorded["eados_commit"] == "abc1234", failures)
    check("a recorded stamp differs from the derived one (the test is meaningful)",
          recorded["eados_version"] != prov["eados_version"], failures)

    # An empty/garbage block must not be trusted as a recording — it falls back to derived.
    for bad in ({}, {"eados_version": ""}, {"eados_version": None}):
        got = render.factory_provenance({"generated_by": bad})
        check(f"an empty recorded block falls back to derived ({bad!r})",
              got["eados_version"] == prov["eados_version"], failures)

    # --- the line states what is unknown rather than omitting it ------------------------------
    blank = render.provenance_line({"eados_version": "", "eados_commit": "", "rendered_at": ""})
    check("an unknown version is said, not silently dropped",
          "unrecorded" in blank, failures)
    check("a missing commit is simply absent, not rendered as empty parens",
          "()" not in render.provenance_line({"eados_version": "1.0.0", "eados_commit": "",
                                              "rendered_at": "2026-01-01"}), failures)

    with tempfile.TemporaryDirectory() as tmp:
        # --- the generated contract carries the stamp ------------------------------------------
        rc, repo = render_to(base, os.path.join(tmp, "plain"))
        check("a manifest without the block still renders (additive)", rc.returncode == 0, failures)
        agents = io.open(os.path.join(repo, "AGENTS.md"), encoding="utf-8").read()
        check("the generated contract carries the provenance",
              "Provenance:" in agents and prov["eados_version"] in agents, failures)
        check("the contract explains why the stamp exists rather than just printing it",
              "ADR-0003" in agents, failures)

        # --- durability end to end: a v2.9.0 repo re-rendered by today's factory stays v2.9.0 ---
        rc, repo = render_to(RECORDED + base, os.path.join(tmp, "stamped"))
        check("a manifest WITH the block renders", rc.returncode == 0, failures)
        agents = io.open(os.path.join(repo, "AGENTS.md"), encoding="utf-8").read()
        check("the recorded version reaches the generated contract", "2.9.0" in agents, failures)
        check("today's factory version does NOT leak into a stamped repo",
              prov["eados_version"] not in agents, failures)

        # --- --check stays side-effect-free: it must not stamp anything ------------------------
        mpath = os.path.join(tmp, "check.yaml")
        io.open(mpath, "w", encoding="utf-8").write(base)
        before = io.open(mpath, encoding="utf-8").read()
        rc = subprocess.run([sys.executable, os.path.join(TOOLS, "render.py"), mpath, "--check"],
                            capture_output=True, text=True, encoding="utf-8", timeout=120)
        check("--check succeeds", rc.returncode == 0, failures)
        check("--check writes nothing back to the manifest",
              io.open(mpath, encoding="utf-8").read() == before, failures)
        check("--check creates no repo next to the manifest",
              sorted(os.listdir(tmp)) == sorted(["plain", "stamped", "check.yaml"]), failures)

    if failures:
        print("test-provenance-stamp: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-provenance-stamp: OK — the stamp is derived from the CHANGELOG, a recorded one "
          "survives a newer factory, an unknown is stated rather than dropped, and --check stays "
          "side-effect-free.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
