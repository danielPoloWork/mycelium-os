#!/usr/bin/env python3
"""Unit tests for the render() substitution engine itself (the Mustache subset).

The render-smoke proves the reference manifest renders cleanly end-to-end, but the engine's
branches — scalars, `#`/`^` flags, `EACH` over scalars vs dicts, the inverted-empty-list case,
unresolved-token errors, the `${{ }}` Actions carve-out, and multi-line block indentation —
were only ever exercised incidentally. This pins each one directly. Dependency-free.

    python .eados-core/tools/tests/test_render_engine.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import render  # noqa: E402  (the module under test)

SCALARS = {"NAME": "acme", "EMPTY": "", "BLOCK": "line1\nline2\n"}
FLAGS = {"IF_ON": True, "IF_OFF": False}
SECTIONS = {"EACH_D": [{"k": "a"}, {"k": "b"}], "EACH_S": ["x", "y"], "EACH_EMPTY": [],
            "EACH_M": [{"n": 1, "items": ["a", "b"]}, {"n": 2, "items": ["c"]}]}


def _r(tmpl, local=None):
    errs = []
    out = render.render(tmpl, SCALARS, FLAGS, SECTIONS, local, "t", errs)
    return out, errs


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    o, e = _r("Hi {{NAME}}")
    check("scalar substitution", o == "Hi acme" and not e, failures)

    o, e = _r("{{#IF_ON}}yes{{/IF_ON}}{{^IF_ON}}no{{/IF_ON}}")
    check("flag truthy + inverted", o == "yes", failures)
    o, e = _r("{{#IF_OFF}}yes{{/IF_OFF}}{{^IF_OFF}}no{{/IF_OFF}}")
    check("flag falsy + inverted", o == "no", failures)

    o, e = _r("{{#EACH_D}}[{{k}}]{{/EACH_D}}")
    check("EACH over dicts with field", o == "[a][b]" and not e, failures)
    o, e = _r("{{#EACH_S}}({{.}}){{/EACH_S}}")
    check("EACH over scalars with {{.}}", o == "(x)(y)" and not e, failures)

    o, e = _r("{{#EACH_EMPTY}}item{{/EACH_EMPTY}}{{^EACH_EMPTY}}none{{/EACH_EMPTY}}")
    check("empty EACH: # yields nothing, ^ yields body once", o == "none", failures)

    # Nested loop: a section whose name (lowercased) is a list FIELD of the current item
    # iterates that field — e.g. {{#ITEMS}} inside {{#EACH_MILESTONE}} over a milestone's items.
    o, e = _r("{{#EACH_M}}[{{n}}:{{#ITEMS}}{{.}}{{/ITEMS}}]{{/EACH_M}}")
    check("nested loop over the current item's list field",
          o == "[1:ab][2:c]" and not e, failures)

    o, e = _r("{{MISSING}}")
    check("unresolved UPPER placeholder -> error + blank",
          o == "" and any("unresolved placeholder" in x for x in e), failures)
    o, e = _r("{{#EACH_D}}{{missing}}{{/EACH_D}}")
    check("unresolved lower field in a dict loop -> error",
          any("unresolved field" in x for x in e), failures)

    o, e = _r("${{ github.sha }} and {{NAME}}")
    check("GitHub Actions ${{ }} left untouched",
          o == "${{ github.sha }} and acme" and not e, failures)

    # A multi-line scalar alone on an indented line indents its continuation lines to match.
    errs = []
    o = render.render("  {{BLOCK}}", SCALARS, FLAGS, SECTIONS, None, "t", errs)
    check("block_indent aligns continuation lines", o == "  line1\n  line2", failures)

    # errors threaded per-call: a fresh call does not inherit a prior call's errors.
    _r("{{MISSING}}")
    _, e2 = _r("{{NAME}}")
    check("render() is reentrant (errors not shared)", e2 == [], failures)

    if failures:
        print("test-render-engine: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} engine behaviour(s) wrong.")
        return 1
    print("test-render-engine: OK — scalars, flags, loops, errors, and indentation all hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
