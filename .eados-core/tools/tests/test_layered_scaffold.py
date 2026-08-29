#!/usr/bin/env python3
"""Issue #152 — optional layered package scaffold. Proves that a service/app/web project can opt into
a layered layout (capabilities.layered + spec.layers) and the generator lays the chosen packages down
under BOTH the main and test source roots, while a library keeps the flat shape. Unit-checks the
build_context wiring and the name-sanitisation, and renders a layered manifest end-to-end via the
real render CLI. Dependency-free (stdlib + the sibling render module).

    python .eados-core/tools/tests/test_layered_scaffold.py
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

# A minimal-but-valid layered manifest: a Java web service opting into a layered skeleton. Includes
# one deliberately unsafe layer name ("../evil") to prove name-sanitisation skips it.
LAYERED_MANIFEST = """\
schema_version: 1
domain: web
identity:
  project_name: acme-web
  project_slug: acmeweb
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
    layered: true
spec:
  objective: A layered demo web service.
  functional_reqs: [serve one endpoint]
  verification: unit tests in CI
  milestones:
    - { number: 2, title: Harden, goal: Production-ready, items: ["2.1 add auth"] }
  layers: [controller, service, repository, dto, mapper, "../evil"]
"""

GOOD_LAYERS = ["controller", "service", "repository", "dto", "mapper"]
SRC_MAIN = "src/main/java/com/acme/acmeweb"
SRC_TEST = "src/test/java/com/acme/acmeweb"


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- build_context wiring ----------------------------------------------
    layered = {"governance": {"capabilities": {"layered": True}},
               "spec": {"layers": GOOD_LAYERS}}
    _sc, flags, sections = render.build_context(layered)
    check("IF_LAYERED true when capabilities.layered", flags.get("IF_LAYERED") is True, failures)
    check("EACH_LAYER carries the layer names", sections.get("EACH_LAYER") == GOOD_LAYERS, failures)

    # a library (no capability) stays flat
    with open(REFERENCE, encoding="utf-8") as fh:
        ref = render.load_yaml(fh.read())
    _s2, f2, sec2 = render.build_context(ref)
    check("reference (library) has IF_LAYERED false", f2.get("IF_LAYERED") is False, failures)
    check("reference (library) has no layers", not sec2.get("EACH_LAYER"), failures)

    # --- end-to-end render of the layered manifest -------------------------
    with tempfile.TemporaryDirectory() as d:
        man = os.path.join(d, "layered.yaml")
        out = os.path.join(d, "out")
        with open(man, "w", encoding="utf-8") as fh:
            fh.write(LAYERED_MANIFEST)
        proc = subprocess.run([sys.executable, RENDER, man, "--out", out],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        rendered_ok = proc.returncode == 0
        check("layered manifest renders cleanly", rendered_ok, failures)
        if rendered_ok:
            for layer in GOOD_LAYERS:
                check(f"main layer package '{layer}' seeded",
                      os.path.isfile(os.path.join(out, SRC_MAIN, layer, ".gitkeep")), failures)
                check(f"test layer package '{layer}' mirrored",
                      os.path.isfile(os.path.join(out, SRC_TEST, layer, ".gitkeep")), failures)
            # name sanitisation: the unsafe entry created nothing, and nothing escaped the out dir
            escaped = os.path.exists(os.path.join(d, "evil")) or os.path.exists(os.path.join(d, "..", "evil"))
            check("unsafe layer name '../evil' created no directory / did not escape",
                  not escaped and "evil" not in os.listdir(os.path.join(out, SRC_MAIN)), failures)
            # the layout decision is recorded in the generated ADR-0002
            adr = os.path.join(out, "docs", "adr", "0002-adopt-cross-language-source-layout.md")
            adr_text = open(adr, encoding="utf-8").read() if os.path.isfile(adr) else ""
            check("ADR-0002 records the layered layout", "layered package skeleton" in adr_text, failures)
            check("ADR-0002 lists a chosen layer", "controller" in adr_text, failures)
        else:
            failures.append("render output: " + proc.stdout.decode("utf-8", "replace")[-500:])

    if failures:
        print("test-layered-scaffold: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} layered-scaffold invariant(s) broken.")
        return 1
    print("test-layered-scaffold: OK - service/app/web can opt into a layered skeleton (main+test), "
          "unsafe names are skipped, a library stays flat, ADR-0002 records it (#152).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
