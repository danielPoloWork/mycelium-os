#!/usr/bin/env python3
"""Issue #240 — optional API-contract stub (the design "api" fold). Proves a service/web project can
opt into `capabilities.api_spec` and the generator seeds `docs/api/README.md` (the OpenAPI/IDL
contract stub), while a project that leaves it off gets no `docs/api/` — the same opt-in,
skip-when-off mechanism as `capabilities.bench`. Unit-checks the build_context flag and renders both
an opted-in and the reference (off) manifest end-to-end via the real render CLI. Dependency-free.

    python .eados-core/tools/tests/test_api_spec.py
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

# A minimal-but-valid web service opting into the API-contract stub.
API_MANIFEST = """\
schema_version: 1
domain: web
identity:
  project_name: acme-api
  project_slug: acmeapi
  project_kind: service
ownership:
  owner: acme
  license_id: MIT
  default_branch: main
language:
  lang: java
  group_path: com/acme
governance:
  start_version: "0.0.0"
  capabilities:
    api_spec: true
spec:
  objective: A demo web service with a documented API contract.
  functional_reqs: [serve one endpoint]
  verification: unit tests in CI
  milestones:
    - { number: 2, title: Harden, goal: Production-ready, items: ["2.1 add auth"] }
"""


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- build_context wiring ----------------------------------------------
    _sc, flags, _sec = render.build_context(
        {"governance": {"capabilities": {"api_spec": True}}})
    check("IF_API_SPEC true when capabilities.api_spec", flags.get("IF_API_SPEC") is True, failures)

    with open(REFERENCE, encoding="utf-8") as fh:
        ref = render.load_yaml(fh.read())
    _s2, f2, _sec2 = render.build_context(ref)
    check("reference (library) has IF_API_SPEC false", f2.get("IF_API_SPEC") is False, failures)

    # --- end-to-end: opted-in seeds docs/api/, and it names the contract's four parts ------
    with tempfile.TemporaryDirectory() as d:
        man = os.path.join(d, "api.yaml")
        out = os.path.join(d, "out")
        with open(man, "w", encoding="utf-8") as fh:
            fh.write(API_MANIFEST)
        proc = subprocess.run([sys.executable, RENDER, man, "--out", out],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        rendered_ok = proc.returncode == 0
        check("api_spec manifest renders cleanly", rendered_ok, failures)
        if rendered_ok:
            api_readme = os.path.join(out, "docs", "api", "README.md")
            check("docs/api/README.md is seeded when api_spec is on",
                  os.path.isfile(api_readme), failures)
            text = open(api_readme, encoding="utf-8").read() if os.path.isfile(api_readme) else ""
            check("the stub renders the project name (placeholders resolved)",
                  "acme-api" in text and "{{" not in text, failures)
            for part in ("Operations", "Payloads", "Error model", "Versioning"):
                check(f"the stub states the '{part}' part of the contract", part in text, failures)
            # the generated AGENTS.md review table gains the API-contract row (IF_API_SPEC usage)
            agents = os.path.join(out, "AGENTS.md")
            agents_text = open(agents, encoding="utf-8").read() if os.path.isfile(agents) else ""
            check("generated AGENTS.md gains the API-contract review row",
                  "API contract" in agents_text and "docs/api/" in agents_text, failures)
        else:
            failures.append("render output: " + proc.stdout.decode("utf-8", "replace")[-500:])

    # --- end-to-end: the reference (api_spec off) seeds no docs/api/ -------------------------
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "out")
        proc = subprocess.run([sys.executable, RENDER, REFERENCE, "--out", out],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode == 0:
            check("reference render omits docs/api/ when api_spec is off",
                  not os.path.exists(os.path.join(out, "docs", "api")), failures)
            check("reference AGENTS.md has no API-contract row when off",
                  "API contract |" not in open(os.path.join(out, "AGENTS.md"), encoding="utf-8").read(),
                  failures)
        else:
            failures.append("reference render failed: " + proc.stdout.decode("utf-8", "replace")[-500:])

    if failures:
        print("test-api-spec: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} api-spec invariant(s) broken.")
        return 1
    print("test-api-spec: OK — a service/web project opts into docs/api/ (OpenAPI/IDL stub), the "
          "stub states operations/payloads/errors/versioning, and a project with it off gets none "
          "(#240).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
