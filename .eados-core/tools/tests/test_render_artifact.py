#!/usr/bin/env python3
"""Tests for render_artifact — the single-artifact render path (render one template -> sandbox)
for the migrate phase (roadmap 6.3 / G2). Dependency-free.

    python .eados-core/tools/tests/test_render_artifact.py
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import render_artifact as ra  # noqa: E402  (the module under test)
import render  # noqa: E402
import sandbox  # noqa: E402

REFERENCE = os.path.join(render.ROOT, "orchestrator", "examples", "reference.yaml")


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def raises(exc_types, fn, *a, **k):
    try:
        fn(*a, **k)
        return False
    except exc_types:
        return True


def main():
    failures = []
    manifest = render.load_yaml(open(REFERENCE, encoding="utf-8").read())
    scalars, _flags, _sections = render.build_context(manifest)
    slug, name = scalars["PROJECT_SLUG"], scalars["PROJECT_NAME"]

    # --- render one artifact (no write) with the real reference manifest ---
    out_rel, text = ra.render_one("AGENTS.md.tmpl", manifest)
    check("AGENTS.md.tmpl renders to AGENTS.md", out_rel == "AGENTS.md", failures)
    check("the rendered artifact carries the manifest's project name", name and name in text,
          failures)
    check("no unresolved {{PLACEHOLDER}} survives (render gate held)",
          "{{" not in text.replace("${{", ""), failures)

    # out_rel reuses render.out_relpath, so a single artifact is named like its full-render twin.
    spec_rel, _ = ra.render_one("docs/specs/01_spec.md.tmpl", manifest)
    check("the spec template maps to its slug-named output",
          spec_rel == f"docs/specs/01_spec_{slug}.md", failures)

    # --- place it into a target via the sandbox; the migration is additive ---
    with tempfile.TemporaryDirectory() as target:
        dest = sandbox.safe_write(target, out_rel, text)
        check("the artifact lands at target/AGENTS.md",
              os.path.isfile(os.path.join(target, "AGENTS.md")) and
              os.path.realpath(dest) == os.path.realpath(os.path.join(target, "AGENTS.md")),
              failures)
        check("a second write without --overwrite is refused (additive)",
              raises(sandbox.SandboxError, sandbox.safe_write, target, out_rel, text), failures)
        check("--overwrite replaces it",
              sandbox.safe_write(target, out_rel, text, overwrite=True) is not None, failures)

    # --- the gates hold per-artifact ---
    check("an invalid manifest is rejected (validate_manifest, per-artifact)",
          raises(ValueError, ra.render_one, "AGENTS.md.tmpl", {"identity": {"project_name": "x"}}),
          failures)
    check("a template path escaping templates/ is refused",
          raises(ValueError, ra.template_abspath, "../tools/render.py"), failures)
    check("a missing template errors cleanly",
          raises(ValueError, ra.render_one, "does-not-exist.md.tmpl", manifest), failures)

    # --- an --as that would escape the target is caught by the sandbox, not silently written ---
    esc_rel, esc_text = ra.render_one("AGENTS.md.tmpl", manifest, "../escaped.md")
    check("a traversal --as is produced verbatim but...", esc_rel == "../escaped.md", failures)
    with tempfile.TemporaryDirectory() as target:
        check("...the sandbox refuses to write it outside the target",
              raises(sandbox.SandboxError, sandbox.safe_write, target, esc_rel, esc_text), failures)

    if failures:
        print("test-render-artifact: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-render-artifact: OK -- one template renders with the manifest gates and lands via "
          "the sandbox; escapes and clobbers are refused.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
