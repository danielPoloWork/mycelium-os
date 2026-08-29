#!/usr/bin/env python3
"""Issue #151 — architecture-style / design-pattern elicitation. Proves the structured style,
expected patterns, and pattern-discipline posture flow from the manifest through render into the
seeded docs/patterns/README.md catalogue (instead of it shipping empty). Covers the populated branch
(a style + patterns), the empty branch (a library — inverted sections, no orphan placeholders), and
the real reference manifest end-to-end. Dependency-free (stdlib + the sibling render module).

    python .eados-core/tools/tests/test_architecture_style.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
EADOS = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import render   # noqa: E402

PATTERNS_TMPL = os.path.join(EADOS, "templates", "docs", "patterns", "README.md.tmpl")
REFERENCE = os.path.join(EADOS, "orchestrator", "examples", "reference.yaml")


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def render_patterns(manifest):
    """Render the patterns catalogue template against a manifest; return (text, errors)."""
    scalars, flags, sections = render.build_context(manifest)
    with open(PATTERNS_TMPL, encoding="utf-8") as fh:
        tmpl = fh.read()
    errors = []
    out = render.render(tmpl, scalars, flags, sections, None, "patterns/README.md.tmpl", errors)
    return out, errors, (scalars, flags, sections)


def main():
    failures = []

    # --- populated: a committed style + patterns + enforced discipline -------
    styled = {"spec": {
        "architecture_style": "Hexagonal (Ports & Adapters)",
        "pattern_discipline": "enforced",
        "patterns": [
            {"name": "Repository", "why": "decouple the domain from persistence"},
            {"name": "Ports & Adapters", "why": "swap infrastructure without touching the core"},
        ],
    }}
    out, errors, (scalars, flags, sections) = render_patterns(styled)
    check("no unresolved placeholders on the populated render", not errors, failures)
    check("build_context exposes ARCHITECTURE_STYLE scalar",
          scalars.get("ARCHITECTURE_STYLE") == "Hexagonal (Ports & Adapters)", failures)
    check("IF_ARCHITECTURE_STYLE flag true when a style is set",
          flags.get("IF_ARCHITECTURE_STYLE") is True, failures)
    check("EACH_PATTERN section carries the patterns", len(sections.get("EACH_PATTERN", [])) == 2, failures)
    check("rendered catalogue names the committed style", "Hexagonal (Ports & Adapters)" in out, failures)
    check("rendered catalogue shows the discipline posture", "enforced" in out, failures)
    check("rendered catalogue seeds a Planned row for a named pattern",
          "Repository" in out and "Planned" in out, failures)
    check("rendered catalogue carries the pattern's rationale",
          "decouple the domain from persistence" in out, failures)
    check("populated render does NOT show the no-style fallback",
          "No single architectural style committed" not in out, failures)

    # --- empty: a library — no style, no patterns (inverted sections) --------
    lib = {"spec": {"architecture_style": "", "patterns": []}}
    out2, errors2, (sc2, fl2, _) = render_patterns(lib)
    check("no unresolved placeholders on the empty render", not errors2, failures)
    check("IF_ARCHITECTURE_STYLE flag false when no style", fl2.get("IF_ARCHITECTURE_STYLE") is False, failures)
    check("PATTERN_DISCIPLINE defaults to advisory", sc2.get("PATTERN_DISCIPLINE") == "advisory", failures)
    check("empty render shows the no-style fallback",
          "No single architectural style committed" in out2, failures)
    check("empty render keeps the filler table row (no seeded patterns)",
          "| — | —" in out2, failures)
    check("empty render leaves no literal {{ }} tokens", "{{" not in out2, failures)

    # --- the real reference manifest end-to-end -----------------------------
    with open(REFERENCE, encoding="utf-8") as fh:
        ref = render.load_yaml(fh.read())
    out3, errors3, _ = render_patterns(ref)
    check("reference render has no unresolved placeholders", not errors3, failures)
    check("reference catalogue seeds its named patterns (Object Pool)", "Object Pool" in out3, failures)
    check("reference catalogue seeds Free List too", "Free List" in out3, failures)

    if failures:
        print("test-architecture-style: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} architecture-style invariant(s) broken.")
        return 1
    print("test-architecture-style: OK - style/patterns/discipline flow manifest -> render -> seeded "
          "docs/patterns/README.md; empty (library) branch renders cleanly (#151).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
