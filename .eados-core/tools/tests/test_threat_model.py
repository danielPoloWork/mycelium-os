#!/usr/bin/env python3
"""Issue #241 — the audit threat-modeling sub-mode's artifact. Proves every generated repo is
scaffolded with `docs/security/threat-model.md` (the STRIDE checklist the `/eados security`
sub-mode fills, owned by the security-auditor) + the `docs/security/README.md` surface — a
universal governed stub, like the bug ledger. Also pins the `os/risk/risk.yaml` `threat_model:`
data block the sub-mode reads (artifact path / method / owner role) so the command surface, the
persona, and the templates cannot drift apart. Dependency-free.

    python .eados-core/tools/tests/test_threat_model.py
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
EADOS = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import render   # noqa: E402

RENDER = os.path.join(TOOLS, "render.py")
REFERENCE = os.path.join(EADOS, "orchestrator", "examples", "reference.yaml")
RISK = os.path.join(EADOS, "orchestrator", "os", "risk", "risk.yaml")

STRIDE = ("Spoofing", "Tampering", "Repudiation", "Information disclosure",
          "Denial of service", "Elevation of privilege")


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- the risk spec's threat_model block: one source of truth for artifact/method/owner ---
    with open(RISK, encoding="utf-8") as fh:
        risk = render.load_yaml(fh.read())
    tm = risk.get("threat_model") if isinstance(risk, dict) else None
    check("risk.yaml declares a threat_model block", isinstance(tm, dict), failures)
    if isinstance(tm, dict):
        check("threat_model.artifact is the docs/security path",
              tm.get("artifact") == "docs/security/threat-model.md", failures)
        check("threat_model.method is STRIDE", tm.get("method") == "STRIDE", failures)
        check("threat_model.owner_role is the security-auditor",
              tm.get("owner_role") == "security-auditor", failures)

    # --- end-to-end: the reference render scaffolds the artifact (universal, like docs/bugs) ---
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "out")
        proc = subprocess.run([sys.executable, RENDER, REFERENCE, "--out", out],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        rendered_ok = proc.returncode == 0
        check("the reference manifest renders cleanly", rendered_ok, failures)
        if rendered_ok:
            artifact = os.path.join(out, "docs", "security", "threat-model.md")
            check("docs/security/threat-model.md is scaffolded", os.path.isfile(artifact), failures)
            text = open(artifact, encoding="utf-8").read() if os.path.isfile(artifact) else ""
            check("placeholders resolved (project name in, no {{ left)",
                  "pbr-cpp-memory-pool" in text and "{{" not in text, failures)
            for category in STRIDE:
                check(f"the STRIDE pass covers '{category}'", category in text, failures)
            check("the artifact names its owner (security-auditor)",
                  "security-auditor" in text, failures)
            readme = os.path.join(out, "docs", "security", "README.md")
            check("docs/security/README.md (the surface) is scaffolded",
                  os.path.isfile(readme), failures)
        else:
            failures.append("render output: " + proc.stdout.decode("utf-8", "replace")[-500:])

    if failures:
        print("test-threat-model: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} threat-model invariant(s) broken.")
        return 1
    print("test-threat-model: OK — every generated repo carries the STRIDE threat-model stub "
          "owned by the security-auditor, and risk.yaml's threat_model block pins the data (#241).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
