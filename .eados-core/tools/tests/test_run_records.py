#!/usr/bin/env python3
"""Tests for the run-record schema gate (#175) — eados_lint.check_run_records.

The learning loop must be inside the enforcement perimeter: once run records have a real schema
(#172), a malformed record silently poisons the auto-tuner and the lesson audit. These pin the
pure validator (`run_record_problems`) edge by edge, prove the empty-dir state stays green, and —
the key acceptance — that a record emitted by `record_run.py`'s own emitter validates clean
(schema parity between the writer and the gate). Dependency-free.

    python .eados-core/tools/tests/test_run_records.py
"""

import contextlib
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint    # noqa: E402  (the module under test)
import record_run as rr      # noqa: E402  (the schema authority + emitter)
import render                # noqa: E402  (round-trip loader)

VALID = {
    "slug": "acme", "date": "2026-07-05", "lang": "python", "kind": "library", "outcome": "ok",
    "overrides": [{"key": "ownership.license_id", "default": "MIT", "chosen": "Apache-2.0"}],
    "lessons_applied": ["L-0001"], "failures": [], "rubric": {"spec_measurability": 2},
}


def _problems(mutate=None):
    rec = {k: (v[:] if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
           for k, v in VALID.items()}
    if mutate:
        mutate(rec)
    return lint.run_record_problems([("learning/runs/r.yaml", rec)])


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- the happy path ---
    check("a well-formed record has no problems", _problems() == [], failures)
    check("the empty-dir state is trivially green", lint.run_record_problems([]) == [], failures)

    # --- required keys / vocab / shapes bite ---
    for key in lint.RUN_RECORD_REQUIRED:
        check(f"a missing required key '{key}' is flagged",
              any(f"'{key}'" in p for p in _problems(lambda r, k=key: r.pop(k))), failures)
    check("an empty required value is flagged",
          any("slug" in p for p in _problems(lambda r: r.update(slug="  "))), failures)
    check("a bad outcome vocabulary is flagged",
          any("outcome" in p for p in _problems(lambda r: r.update(outcome="maybe"))), failures)
    check("a malformed date is flagged",
          any("YYYY-MM-DD" in p for p in _problems(lambda r: r.update(date="July 5"))), failures)
    # #215: `phase` is an optional tag — a known phase passes, absence passes (legacy), a bogus one bites.
    check("a valid phase passes", _problems(lambda r: r.update(phase="migrate")) == [], failures)
    check("no phase passes (legacy record)", _problems(lambda r: r.pop("phase", None)) == [], failures)
    check("a bogus phase is flagged",
          any("phase" in p for p in _problems(lambda r: r.update(phase="bogus"))), failures)
    check("a non-mapping record is flagged",
          lint.run_record_problems([("r.yaml", ["not", "a", "map"])]) != [], failures)

    # --- overrides ---
    check("overrides must be a list",
          any("overrides must be a list" in p for p in _problems(lambda r: r.update(overrides={}))),
          failures)
    check("an override missing a triple key is flagged",
          any("key, default, chosen" in p
              for p in _problems(lambda r: r.update(overrides=[{"key": "x", "default": 1}]))),
          failures)
    check("an override with an empty key is flagged",
          any("empty key" in p
              for p in _problems(lambda r: r.update(
                  overrides=[{"key": "", "default": 1, "chosen": 2}]))), failures)

    # --- failures + the outcome-consistency rule ---
    check("a failure without outcome=failed is flagged",
          any("must be 'failed'" in p
              for p in _problems(lambda r: r.update(
                  failures=[{"gate": "ci-bootstrap", "message": "red"}]))), failures)
    check("a well-shaped failure on a failed run is clean",
          _problems(lambda r: r.update(outcome="failed",
                                       failures=[{"gate": "ci-bootstrap", "message": "red"}])) == [],
          failures)
    check("a failure missing 'message' is flagged",
          any("gate, message" in p
              for p in _problems(lambda r: r.update(outcome="failed",
                                                    failures=[{"gate": "x"}]))), failures)

    # --- lessons_applied + rubric ---
    check("a non-L-NNNN lesson id is flagged",
          any("L-NNNN" in p for p in _problems(lambda r: r.update(lessons_applied=["oops"]))),
          failures)
    check("an unknown rubric dimension is flagged",
          any("ten eval/rubric.md" in p for p in _problems(lambda r: r.update(rubric={"vibes": 2}))),
          failures)
    check("an out-of-range rubric score is flagged",
          any("0, 1, or 2" in p
              for p in _problems(lambda r: r.update(rubric={"spec_measurability": 5}))), failures)

    # --- schema parity: record_run's own emitter round-trips through the gate clean ---
    rec, probs = rr.build_run_record(
        {"identity": {"project_slug": "memorypool", "project_kind": "library"},
         "language": {"lang": "cpp"},
         "interview": {"provenance": {"identity": "asked"}}},
        {"identity": {"project_kind": "library"}}, {"L-0001"}, "2026-07-05",
        outcome="failed", failures=["ci-bootstrap=matrix red on windows"],
        lessons=["L-0001"], rubric=["spec_measurability=2"])
    check("the emitter produces a clean record to validate", probs == [], failures)
    emitted = render.load_yaml(rr.emit_record_yaml(rec))
    check("a record_run-emitted record validates clean against the gate (schema parity)",
          lint.run_record_problems([("learning/runs/emitted.yaml", emitted)]) == [], failures)

    # --- #197: a same-day re-run is disambiguated by a filename suffix, never a falsified date ---
    #     resolve_dest is the pure filename authority: base name first, then the lowest free -N.
    with tempfile.TemporaryDirectory() as d:
        p1 = rr.resolve_dest(d, "2026-07-05", "acme")
        check("first same-day record takes the base name",
              os.path.basename(p1) == "2026-07-05-acme.yaml", failures)
        open(p1, "w").close()
        p2 = rr.resolve_dest(d, "2026-07-05", "acme")
        check("second same-day record gets the -2 suffix",
              os.path.basename(p2) == "2026-07-05-acme-2.yaml", failures)
        open(p2, "w").close()
        p3 = rr.resolve_dest(d, "2026-07-05", "acme")
        check("third same-day record gets the -3 suffix",
              os.path.basename(p3) == "2026-07-05-acme-3.yaml", failures)
        check("a different real date is never suffixed by a prior day's records",
              os.path.basename(rr.resolve_dest(d, "2026-07-06", "acme")) == "2026-07-06-acme.yaml",
              failures)

    # end-to-end: two same-day record_run invocations for the same slug both succeed, land in
    # DISTINCT files, and the second's date: is the true run date — never bumped to disambiguate.
    with tempfile.TemporaryDirectory() as d:
        manifest = os.path.join(d, "project.yaml")
        with open(manifest, "w", encoding="utf-8") as fh:
            fh.write("identity: { project_slug: acme, project_kind: library }\n"
                     "language: { lang: python }\n"
                     "interview: { provenance: { identity: asked } }\n")
        saved_runs = rr.RUNS_DIR
        rr.RUNS_DIR = d
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                rc1 = rr.main([manifest, "--date", "2026-07-05"])
                rc2 = rr.main([manifest, "--date", "2026-07-05"])
        finally:
            rr.RUNS_DIR = saved_runs
        check("both same-day runs exit 0", rc1 == 0 and rc2 == 0, failures)
        first = os.path.join(d, "2026-07-05-acme.yaml")
        second = os.path.join(d, "2026-07-05-acme-2.yaml")
        check("the two same-day runs wrote two distinct files",
              os.path.isfile(first) and os.path.isfile(second), failures)
        if os.path.isfile(second):
            rec2 = render.load_yaml(open(second, encoding="utf-8").read())
            check("the second record's date: is the true run date, not a falsified one",
                  rec2.get("date") == "2026-07-05", failures)

    # --- gate-coverage: runs/** is now COVERED, not allow-listed, and not stale ---
    cov = dict(lint.GATE_COVERAGE)
    allow = dict(lint.GATE_ALLOWLIST)
    check("learning/runs/** is registered as a covered (validated) class",
          ".eados-core/learning/runs/**" in cov, failures)
    check("learning/runs/** is no longer prose in the allowlist",
          ".eados-core/learning/runs/**" not in allow, failures)
    check("the runs README is still covered by the runs/** pattern (not orphaned)",
          lint.gate_coverage_problems([".eados-core/learning/runs/README.md"]) == [], failures)

    if failures:
        print("test-run-records: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-run-records: OK — the schema gate bites on malformed records, the empty-dir state "
          "stays green, and record_run's emitter is schema-parity clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
