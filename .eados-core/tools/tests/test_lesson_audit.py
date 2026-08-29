#!/usr/bin/env python3
"""Tests for lesson_audit (#173) — the learning-loop watchdog behind generate.md's Recall/Record.

Pure-core fixtures: a seeded repeat failure reports a regression naming the lesson id (in scope
only); an unused lesson is flagged dead only after enough *applicable* runs; a dimension scoring
low in the majority of runs yields a trend proposal. The textual ledger parser is pinned against
the REAL lessons.yaml, and a main() integration proves the report is report-only (exit 0) over
records emitted by record_run's own loader-safe emitter. Dependency-free.

    python .eados-core/tools/tests/test_lesson_audit.py
"""

import contextlib
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import lesson_audit as la  # noqa: E402  (the module under test)
import record_run as rr    # noqa: E402  (the canonical loader-safe emitter)

REAL_LESSONS = os.path.join(ROOT, "learning", "lessons.yaml")

# A lesson whose rule carries distinctive keywords (placeholder / indentation / block), a
# language-scoped lesson, and a global one no run will ever apply (the dead-weight candidate).
LESSONS = [
    {"id": "L-0001", "scope": "global",
     "rule": "A placeholder that injects a multi-line block must carry the target indentation."},
    {"id": "L-0002", "scope": "lang:cpp",
     "rule": "Sanitizers map to the toolchain's real equivalents before the skeleton compiles."},
    {"id": "L-0009", "scope": "global",
     "rule": "An entirely unrelated maxim about documentation freshness and changelog cadence."},
]


def _record(**over):
    base = {"slug": "proj", "date": "2026-07-05", "lang": "python", "kind": "library",
            "outcome": "ok", "overrides": [], "lessons_applied": [], "failures": [], "rubric": {}}
    base.update(over)
    return rr.emit_record_yaml(base)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- keyword extraction: substance survives, noise and short tokens drop ---
    kw = la.keywords("A placeholder must carry the block indentation to that column")
    check("keywords keep substantive terms",
          {"placeholder", "carry", "block", "indentation", "column"} <= kw, failures)
    check("keywords drop stopwords and short tokens",
          not ({"must", "that", "the"} & kw), failures)

    # --- scope_applies: global everywhere, lang/kind match their field ---
    check("global scope applies to any run", la.scope_applies("global", "cpp", "cli"), failures)
    check("lang scope matches its language",
          la.scope_applies("lang:cpp", "cpp", "cli")
          and not la.scope_applies("lang:cpp", "python", "cli"), failures)
    check("kind scope matches its kind",
          la.scope_applies("kind:library", "cpp", "library")
          and not la.scope_applies("kind:library", "cpp", "cli"), failures)

    # --- regression detection: a repeat failure names the covered lesson, in scope only ---
    failing = {"slug": "webapp", "date": "2026-07-06", "lang": "python", "kind": "service",
               "outcome": "failed",
               "failures": [{"gate": "render", "message": "placeholder dropped the block "
                                                          "indentation at column zero"}]}
    regs = la.regressions(LESSONS, [failing])
    hit = {r["lesson"] for r in regs}
    check("a repeat failure reports the covered global lesson (L-0001)", "L-0001" in hit, failures)
    check("an out-of-scope lesson does not match (L-0002 is lang:cpp, run is python)",
          "L-0002" not in hit, failures)
    check("an unrelated lesson does not match (L-0009)", "L-0009" not in hit, failures)
    check("the regression carries the shared keywords",
          any("indentation" in r["shared"] for r in regs if r["lesson"] == "L-0001"), failures)
    check("a clean (no-failure) run produces no regression",
          la.regressions(LESSONS, [{"lang": "python", "kind": "library", "failures": []}]) == [],
          failures)

    # --- dead-lesson report: flagged only after enough APPLICABLE runs, never applied ---
    runs = [{"lang": "python", "kind": "library", "lessons_applied": ["L-0001"]},
            {"lang": "python", "kind": "library", "lessons_applied": ["L-0001"]}]
    dead_ids = {d["lesson"] for d in la.dead_lessons(LESSONS, runs, threshold=2)}
    check("an applied lesson is not dead (L-0001)", "L-0001" not in dead_ids, failures)
    check("a global lesson never applied across 2 runs is dead (L-0009)",
          "L-0009" in dead_ids, failures)
    check("a lang:cpp lesson is NOT dead when no cpp run exists (missing signal, not dead weight)",
          "L-0002" not in dead_ids, failures)
    check("below threshold, nothing is called dead",
          la.dead_lessons(LESSONS, runs[:1], threshold=2) == [], failures)

    # --- rubric trending: a dimension low in the majority proposes a lesson ---
    trend_runs = [{"rubric": {"profile_fidelity": 1, "spec_measurability": 2}},
                  {"rubric": {"profile_fidelity": 0, "spec_measurability": 2}},
                  {"rubric": {"profile_fidelity": 2, "spec_measurability": 2}}]
    dims = {t["dimension"] for t in la.rubric_trends(trend_runs, threshold=2)}
    check("a dimension low in the majority trends (profile_fidelity 2/3)",
          "profile_fidelity" in dims, failures)
    check("a consistently-solid dimension does not trend (spec_measurability)",
          "spec_measurability" not in dims, failures)
    check("a single low score below threshold does not trend",
          la.rubric_trends(trend_runs[:1], threshold=2) == [], failures)

    # --- the textual ledger parser is pinned against the REAL ledger ---
    with open(REAL_LESSONS, encoding="utf-8") as fh:
        real = la.parse_lessons(fh.read())
    real_ids = {le["id"] for le in real}
    check("parse_lessons reads the real ledger entries",
          {"L-0001", "L-0002"} <= real_ids, failures)
    check("parse_lessons captures each lesson's rule text",
          all(le.get("rule") for le in real), failures)

    # --- main() integration: report-only over real emitter output, exits 0 ---
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "2026-07-06-webapp.yaml"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_record(slug="webapp", outcome="failed",
                             failures=[{"gate": "render",
                                        "message": "placeholder dropped the block indentation"}],
                             rubric={"profile_fidelity": 1}))
        with open(os.path.join(tmp, "2026-07-07-lib.yaml"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_record(slug="lib", rubric={"profile_fidelity": 0}))
        ledger = os.path.join(tmp, "lessons.yaml")
        with open(ledger, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("- id: L-0001\n  scope: global\n  rule: A placeholder that injects a "
                     "multi-line block must carry the target indentation.\n")
        runs_before, lessons_before, argv = la.RUNS, la.LESSONS_PATH, sys.argv
        out = io.StringIO()
        try:
            la.RUNS, la.LESSONS_PATH, sys.argv = tmp, ledger, ["lesson_audit.py", "--threshold", "2"]
            with contextlib.redirect_stdout(out):
                code = la.main()
        finally:
            la.RUNS, la.LESSONS_PATH, sys.argv = runs_before, lessons_before, argv
        text = out.getvalue()
        check("main() exits 0 (report-only posture)", code == 0, failures)
        check("main() surfaces the regression against L-0001",
              "REGRESSION against L-0001" in text, failures)
        check("main() surfaces the low profile_fidelity trend",
              "profile_fidelity" in text, failures)

    # --- an empty runs dir is a clean no-op ---
    with tempfile.TemporaryDirectory() as tmp:
        runs_before, argv = la.RUNS, sys.argv
        out = io.StringIO()
        try:
            la.RUNS, sys.argv = tmp, ["lesson_audit.py"]
            with contextlib.redirect_stdout(out):
                code = la.main()
        finally:
            la.RUNS, sys.argv = runs_before, argv
        check("no records is a clean exit-0 no-op",
              code == 0 and "no run records yet" in out.getvalue(), failures)

    # --- #198: a malformed record must not abort the audit — the valid record is still analyzed,
    #     the bad file is named on stderr, and the tool exits 0 (report-only degrades per file) ---
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "2026-07-06-ok.yaml"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_record(slug="ok"))
        with open(os.path.join(tmp, "bad.yaml"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("note: >\n  folded body the loader rejects\n")
        runs_before, argv = la.RUNS, sys.argv
        out, err = io.StringIO(), io.StringIO()
        try:
            la.RUNS, sys.argv = tmp, ["lesson_audit.py"]
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = la.main()
        finally:
            la.RUNS, sys.argv = runs_before, argv
        check("a malformed record does not abort lesson_audit (exit 0)", code == 0, failures)
        check("the valid record is still analyzed despite the bad file",
              "1 run record(s)" in out.getvalue(), failures)
        check("the malformed record is named on stderr, not a traceback",
              "skipping bad.yaml" in err.getvalue(), failures)

    if failures:
        print("test-lesson-audit: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-lesson-audit: OK — regressions name the covered lesson, dead lessons need "
          "applicable runs, low dimensions trend, and the report changes nothing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
