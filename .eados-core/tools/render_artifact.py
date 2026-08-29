#!/usr/bin/env python3
"""EADOS single-artifact render (roadmap 6.3 / G2) — render ONE template and place it via the
migrate sandbox.

`render.py` renders the *whole* repo from a manifest. The brownfield `migrate` procedure
([`commands/migrate.md`](../orchestrator/commands/migrate.md)) instead adds **one missing
artifact at a time** — "render the missing artifact → `sandbox.safe_write`" — but no tool performed
that single-artifact step. This is it: it renders one template with the manifest context (reusing
`render.py`'s engine and the same `placeholders` + `validate_manifest` gates, so a single artifact
is byte-identical to its counterpart in a full render) and writes it into the target repo through
`tools/sandbox.py` (contained, never `.git`, additive by default).

Dependency-free (stdlib + the sibling `render` / `sandbox` tools).

    python .eados-core/tools/render_artifact.py <template> <manifest> <target-repo> [--as REL] [--overwrite]
    # e.g. add AGENTS.md to a repo being migrated:
    python .eados-core/tools/render_artifact.py AGENTS.md.tmpl project.yaml ../their-repo
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render   # noqa: E402  — the rendering engine + manifest gates (one source of truth)
import sandbox  # noqa: E402  — the migrate write-containment guard (ADR-0007 principle)


def template_abspath(template_rel):
    """Resolve `template_rel` under `templates/`, refusing a path that escapes it or is missing —
    the template arg must name a shipped template, not an arbitrary file to read."""
    tmpl_root = os.path.realpath(render.TEMPLATES)
    src = os.path.realpath(os.path.join(tmpl_root, str(template_rel).replace("/", os.sep)))
    try:
        inside = src == tmpl_root or os.path.commonpath([tmpl_root, src]) == tmpl_root
    except ValueError:                       # different drives on Windows -> outside
        inside = False
    if not inside:
        raise ValueError(f"template path escapes templates/: {template_rel!r}")
    if not os.path.isfile(src):
        raise ValueError(f"no such template under templates/: {template_rel!r}")
    return src


def render_one(template_rel, manifest, as_rel=None):
    """Render the single template `template_rel` with `manifest`'s context; return (out_rel, text).

    Applies the *same* gates as the whole-repo render — `validate_manifest` and the unresolved-
    placeholder check — so a per-artifact render can never silently produce a hollow or half-
    substituted file. `out_rel` defaults to the template's natural output path (`out_relpath`,
    e.g. `.tmpl` stripped); `as_rel` overrides it. Raises ValueError on any problem."""
    scalars, flags, sections = render.build_context(manifest)
    problems = render.validate_manifest(manifest, scalars)
    if problems:
        raise ValueError("manifest validation failed:\n  " + "\n  ".join(sorted(set(problems))))
    with open(template_abspath(template_rel), encoding="utf-8") as handle:
        text = handle.read()
    errors = []
    rendered = render.render(text, scalars, flags, sections, None, str(template_rel), errors)
    if errors:
        raise ValueError("unresolved placeholders:\n  " + "\n  ".join(sorted(set(errors))))
    out_rel = as_rel or render.out_relpath(str(template_rel), scalars["PROJECT_SLUG"])
    return out_rel, rendered


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(
        description="Render ONE EADOS template with a manifest and place it into a target repo "
                    "via the migrate sandbox.")
    ap.add_argument("template", help="template path under templates/ (e.g. AGENTS.md.tmpl)")
    ap.add_argument("manifest", help="path to a filled project.yaml")
    ap.add_argument("target", help="the target repository root to write the artifact into")
    ap.add_argument("--as", dest="as_rel", metavar="REL",
                    help="output path within the target (default: the template's natural path)")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace an existing file (default: additive — refuse to clobber)")
    args = ap.parse_args(argv)

    try:
        with open(args.manifest, encoding="utf-8") as handle:
            manifest = render.load_yaml(handle.read())
        out_rel, text = render_one(args.template, manifest, args.as_rel)
        sandbox.safe_write(args.target, out_rel, text, overwrite=args.overwrite)
    except (ValueError, sandbox.SandboxError, OSError) as exc:
        print(f"render-artifact: FAIL — {exc}", file=sys.stderr)
        return 1
    print(f"render-artifact: OK — {args.template} -> {out_rel} (in {args.target})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
