#!/usr/bin/env python3
"""Issue #153 — Phase 5 must open with a "do you already have a spec?" branch, not always co-author.
Pins the provenance question (asked first, import|coauthor), the import-and-validate protocol prose,
the manifest field, and the ADR record, so the branch can't silently regress back to a single
co-authoring path. Dependency-free (stdlib + the sibling YAML loader).

    python .eados-core/tools/tests/test_spec_provenance.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ORCH = os.path.join(os.path.dirname(TOOLS), "orchestrator")
DOCS = os.path.join(os.path.dirname(TOOLS), "docs")
sys.path.insert(0, TOOLS)
import render   # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    raw = read(os.path.join(ORCH, "questionnaire.yaml"))
    q = render.load_yaml(raw)

    # --- full-parse guard (#153 discovery): the hand-rolled loader used to silently TRUNCATE this
    # file at the first multi-line quoted scalar / multi-line flow list (Q4.7), so phases 4-5 were
    # partly invisible to every consumer while data-file-validity still passed. The file is now kept
    # within the loader's supported subset; this pins that (and the PyYAML differential, where
    # available) so a future edit can't silently reintroduce the truncation. -----------------------
    phases = q.get("phases", []) or []
    check("questionnaire parses ALL 6 phases (no silent truncation)", len(phases) == 6, failures)
    p4 = next((p for p in phases if p.get("id") == 4), {})
    check("phase 4 parses through Q4.8 (the old truncation point)",
          any(qq.get("id") == "Q4.8" for qq in (p4.get("questions") or []) if isinstance(qq, dict)),
          failures)
    check("phase 4 keeps both follow_ups", len(p4.get("follow_ups") or []) == 2, failures)
    try:
        import yaml   # the render-smoke CI job installs it; elsewhere this is best-effort
        check("hand-rolled parse matches PyYAML exactly (questionnaire differential)",
              yaml.safe_load(raw) == q, failures)
    except ImportError:
        pass

    phase5 = next((p for p in phases if p.get("id") == 5), {})
    questions = phase5.get("questions", []) or []
    ids = [qq.get("id") for qq in questions if isinstance(qq, dict)]
    q50 = next((qq for qq in questions if isinstance(qq, dict) and qq.get("id") == "Q5.0"), None)

    # --- the questionnaire branch -------------------------------------------
    check("Phase 5 has a Q5.0 provenance question", q50 is not None, failures)
    if q50:
        check("Q5.0 is asked FIRST (before Q5.1)",
              ids.index("Q5.0") == 0 and "Q5.1" in ids and ids.index("Q5.0") < ids.index("Q5.1"),
              failures)
        check("Q5.0 offers import + coauthor",
              set(q50.get("choices") or []) == {"import", "coauthor"}, failures)
        check("Q5.0 defaults to coauthor (no behavioural change unless a spec exists)",
              q50.get("default") == "coauthor", failures)
        check("Q5.0 records spec.provenance", "spec.provenance" in (q50.get("sets") or []), failures)

    # --- the interview protocol prose (whitespace-normalized: prose wraps) ---
    interview = " ".join(read(os.path.join(ORCH, "interview.md")).split())
    check("interview.md Phase 5 opens with the provenance question", "Q5.0 — Provenance" in interview, failures)
    check("interview.md describes import-and-validate", "import & validate" in interview, failures)
    check("interview.md describes the gap audit", "gap audit" in interview.lower(), failures)
    check("interview.md keeps the co-author path (b)", "build it together" in interview.lower(), failures)

    # --- manifest + reference carry the field -------------------------------
    tmpl = read(os.path.join(ORCH, "project.yaml.template"))
    check("project.yaml.template spec carries provenance", "provenance:" in tmpl, failures)
    ref = render.load_yaml(read(os.path.join(ORCH, "examples", "reference.yaml")))
    check("reference manifest records spec.provenance",
          (ref.get("spec") or {}).get("provenance") in ("coauthor", "import"), failures)

    # --- ADR-0002 (interview-driven intake) notes the branch ----------------
    adr = read(os.path.join(DOCS, "adr", "0002-interview-driven-intake.md"))
    check("ADR-0002 records the import-and-validate provenance branch",
          "import-and-validate" in adr or "provenance branch" in adr, failures)

    if failures:
        print("test-spec-provenance: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} spec-provenance invariant(s) broken.")
        return 1
    print("test-spec-provenance: OK - Phase 5 opens with import|coauthor (asked first, default "
          "coauthor); import-and-validate + gap-audit documented; manifest + ADR record it (#153).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
