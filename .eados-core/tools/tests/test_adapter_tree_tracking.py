#!/usr/bin/env python3
"""A generated repo does not commit its adapter tree — and still keeps its own commands (#372).

A generated repository ignores `.eados-core/` because *"it is not part of the project's own
source"*. `.claude/commands/eados/` was tracked anyway: the one piece of factory tooling landing in
a consumer's history as if it were theirs, decided by nobody.

Two facts settle it, and both are asserted below because both are invisible by inspection:

  1. **A committed adapter is a dangling pointer.** It names
     `.eados-core/orchestrator/commands/<cmd>.md`, a path the same `.gitignore` excludes. Whoever
     clones gets slash commands resolving to a missing file — worse than absence, because an absent
     command is obviously absent while a dangling one fails at the point of use.
  2. **Trees are per-host** (#375), so committing one imposes the author's host on the whole team.

The other half is the trap: "ignore the adapters" written carelessly swallows a team's **own**
commands. The exclusions are scoped to the EADOS subtree, and that is checked against real
`git check-ignore` rather than by reading the pattern.

    python .eados-core/tools/tests/test_adapter_tree_tracking.py
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
sys.path.insert(0, TOOLS)
import adapter_render   # noqa: E402
import route_advice     # noqa: E402


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def ignored(repo, rel):
    """Asked of real git, because a `.gitignore` pattern that LOOKS right and silently does nothing
    is the failure mode here (the same reason #353's test drives check-ignore)."""
    out = subprocess.run(["git", "check-ignore", "-q", rel], cwd=repo,
                         capture_output=True, timeout=60)
    return out.returncode == 0


def main():
    failures = []
    if not HAVE_GIT:
        print("test-adapter-tree-tracking: SKIP — git not on PATH")
        return 0

    spec = route_advice.load_routing()
    hosts = [h.get("id") for h in (spec.get("catalog") or {}).get("hosts") or []]

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "consumer")
        rc = subprocess.run([sys.executable, os.path.join(TOOLS, "render.py"), REFERENCE,
                             "--out", out], capture_output=True, text=True, timeout=240)
        check(f"the reference manifest renders ({rc.stderr[-200:] if rc.returncode else ''})",
              rc.returncode == 0, failures)
        if rc.returncode != 0:
            print("test-adapter-tree-tracking: FAIL\n  render failed")
            return 1
        subprocess.run(["git", "init", "-q", "."], cwd=out, capture_output=True, timeout=60)

        # --- every host's generated tree is excluded ----------------------------------------
        for host in hosts:
            block, files = adapter_render.plan(host, spec)
            if not files:
                continue
            rc2, _o = subprocess.run(
                [sys.executable, os.path.join(TOOLS, "adapter_render.py"), "--host", host,
                 "--out", out], capture_output=True, text=True, timeout=180).returncode, None
            check(f"{host}: the tree renders into the consumer", rc2 == 0, failures)
            for rel, _text in files:
                if not ignored(out, rel):
                    failures.append(f"{host}: {rel} is TRACKED — a generated, per-host tree must "
                                    f"not land in a consumer's history (#372)")
                    break

        # --- the reason, asserted: the target of a pointer is not committed ------------------
        check("the procedures an adapter points at are themselves excluded — which is why a "
              "committed adapter would dangle on a fresh clone",
              ignored(out, ".eados-core/orchestrator/commands/init.md"), failures)

        # --- THE TRAP: a team's own commands must survive ------------------------------------
        for rel in (".claude/commands/mine.md", ".gemini/commands/team.toml",
                    ".opencode/commands/deploy.md"):
            path = os.path.join(out, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()
            check(f"a project's OWN command survives the exclusion ({rel})",
                  not ignored(out, rel), failures)

        # --- and the contract says so, where the reader already is --------------------------
        with open(os.path.join(out, "AGENTS.md"), encoding="utf-8") as fh:
            agents = fh.read()
        check("the generated contract states the tree is not committed",
              "not committed" in agents, failures)
        check("...and how to generate your own", "adapter_render.py --host" in agents, failures)
        check("...and that nothing else depends on it",
              "the CLI works everywhere" in agents, failures)

    # --- the FACTORY is not a consumer: its own tree stays tracked -----------------------
    tracked = subprocess.run(["git", "ls-files", ".claude/commands/eados"],
                             cwd=os.path.dirname(ROOT), capture_output=True, text=True,
                             timeout=60).stdout.split()
    check(f"EADOS keeps its own adapter tree tracked and shipped ({len(tracked)} files) — the "
          "decision governs GENERATED repos, and conflating the two is what made this look like "
          "an inconsistency", len(tracked) >= 14, failures)

    # --- the installers do not imply the files will be committed -------------------------
    for name in ("setup.sh", "setup.ps1"):
        path = os.path.join(os.path.dirname(ROOT), "setup", name)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        check(f"{name}: says the adapter tree is not committed",
              "does not commit its adapter tree" in text, failures)

    if failures:
        print("test-adapter-tree-tracking: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-adapter-tree-tracking: OK — no host's generated tree lands in a consumer's history, "
          "a project's own commands still do, the contract says where to get yours, and the factory "
          "keeps its own tree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
