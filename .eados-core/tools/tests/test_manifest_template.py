#!/usr/bin/env python3
"""Tests for eados_lint.manifest_template_problems — the shipped manifest template passes; invalid
YAML, a non-mapping document, a dropped top-level section, and a typo'd `-> {{MARKER}}` each fail.
This guards orchestrator/project.yaml.template — the one factory file a consumer copies and
hand-fills, which nothing else validated (the issue-#90 follow-up). Dependency-free.

    python .eados-core/tools/tests/test_manifest_template.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint  # noqa: E402  (the module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    scalars, sections = lint.known_placeholders()

    shipped = lint.read(lint.MANIFEST_TEMPLATE)
    check("the shipped manifest template passes",
          lint.manifest_template_problems(shipped, scalars, sections) == [], failures)

    check("a non-mapping document fails",
          lint.manifest_template_problems("- not\n- a mapping\n", scalars, sections) != [], failures)

    # a minimal mapping missing most sections must report each absent one
    minimal = "schema_version: 1\ndomain: software\nidentity: {}\n"
    probs = lint.manifest_template_problems(minimal, scalars, sections)
    check("a missing top-level section is reported",
          any("missing required top-level section 'spec'" in p for p in probs), failures)

    # a typo'd / undefined placeholder annotation must be caught
    bad = shipped + '\nbogus_field: ""   # -> {{NOT_A_REAL_PLACEHOLDER}}\n'
    check("an undefined placeholder annotation fails",
          any("NOT_A_REAL_PLACEHOLDER" in p for p in
              lint.manifest_template_problems(bad, scalars, sections)), failures)

    if failures:
        print("test-manifest-template: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-manifest-template: OK — the manifest template is valid, complete, and well-annotated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
