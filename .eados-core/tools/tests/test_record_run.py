#!/usr/bin/env python3
"""Tests for record_run (#172) — the mechanized run recorder behind generate.md Step 9.

Pure-core fixtures: overrides derive from interview provenance against template defaults
(defaulted sections and no-default fields never produce entries); the failure/lesson/rubric
channels validate; the emitted YAML round-trips through the hand-rolled loader; the REAL
reference.yaml produces a schema-valid record end-to-end via the CLI; and autotune consumes
the extended records unchanged (the acceptance that closes the loop). Dependency-free.

    python .eados-core/tools/tests/test_record_run.py
"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import record_run as rr  # noqa: E402  (the module under test)
import autotune  # noqa: E402  (the consumer the records must feed)
import render  # noqa: E402  (round-trip loader)

RECORD_RUN_PY = os.path.join(TOOLS, "record_run.py")
REFERENCE = os.path.join(ROOT, "orchestrator", "examples", "reference.yaml")

# Synthetic template defaults + a manifest that overrides some of them.
TEMPLATE = {
    "domain": "software",
    "identity": {"project_kind": "library", "project_name": ""},
    "ownership": {"license_id": "MIT", "default_branch": "main", "year": "2026"},
    "toolchain": {"coverage_target": 80, "linter": ""},
    "governance": {"capabilities": {"bench": False, "public_api": True}},
    "i18n": {"default_lang": "en"},
}
MANIFEST = {
    "domain": "game",                                     # asked, differs -> override
    "identity": {"project_kind": "library",               # asked, equal -> no entry
                 "project_name": "acme", "project_slug": "acme"},
    "ownership": {"license_id": "Apache-2.0",             # asked, differs -> override
                  "default_branch": "main", "year": "2026"},
    "toolchain": {"coverage_target": 90,                  # asked, differs -> override
                  "linter": "ruff"},                      # no template default -> no entry
    "governance": {"capabilities": {"bench": True,        # asked, differs -> override
                                    "public_api": True}},
    "i18n": {"default_lang": "it"},                       # DEFAULTED section -> never an entry
    "language": {"lang": "python"},
    "interview": {"questionnaire_version": 1,
                  "provenance": {"domain": "asked", "identity": "asked", "ownership": "asked",
                                 "toolchain": "asked", "governance": "asked",
                                 "i18n": "defaulted"}},
}
KNOWN = {"L-0001", "L-0002"}


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- derive_overrides: the mechanical rule, edge by edge ---
    keys = {ov["key"]: ov for ov in rr.derive_overrides(MANIFEST, TEMPLATE)}
    check("asked + differs -> override (license_id)",
          keys.get("ownership.license_id", {}).get("chosen") == "Apache-2.0", failures)
    check("asked + differs -> override (coverage_target int)",
          keys.get("toolchain.coverage_target", {}).get("default") == 80, failures)
    check("asked + differs -> override (bool capability)",
          keys.get("governance.capabilities.bench", {}).get("chosen") is True, failures)
    check("top-level scalar (domain) participates",
          keys.get("domain", {}).get("default") == "software", failures)
    check("asked + equal -> no entry", "identity.project_kind" not in keys, failures)
    check("no template default -> no entry", "toolchain.linter" not in keys, failures)
    check("defaulted section -> never an entry", "i18n.default_lang" not in keys, failures)
    check("no provenance at all -> no overrides",
          rr.derive_overrides({"ownership": {"license_id": "X"}}, TEMPLATE) == [], failures)

    # --- build_run_record: channels + validation ---
    rec, probs = rr.build_run_record(MANIFEST, TEMPLATE, KNOWN, "2026-07-05",
                                     lessons=["L-0001"], rubric=["spec_measurability=2"])
    check("a clean record has no problems", probs == [], failures)
    check("record carries slug/lang/kind/outcome",
          (rec["slug"], rec["lang"], rec["kind"], rec["outcome"])
          == ("acme", "python", "library", "ok"), failures)
    check("lessons and rubric land in the record",
          rec["lessons_applied"] == ["L-0001"] and rec["rubric"] == {"spec_measurability": 2},
          failures)

    def problems(**kw):
        return rr.build_run_record(MANIFEST, TEMPLATE, KNOWN, "2026-07-05", **kw)[1]

    check("a failure without --outcome failed is rejected",
          any("outcome failed" in p for p in problems(failures=["ci-bootstrap=red matrix"])),
          failures)
    check("a failed run with a failure channel is clean",
          problems(outcome="failed", failures=["ci-bootstrap=red matrix"]) == [], failures)
    check("a malformed --failure is rejected",
          any("GATE=MESSAGE" in p for p in problems(outcome="failed", failures=["oops"])),
          failures)
    check("an unknown lesson id is rejected",
          any("not in learning/lessons.yaml" in p for p in problems(lessons=["L-9999"])),
          failures)
    check("a malformed lesson id is rejected",
          any("L-NNNN" in p for p in problems(lessons=["lesson-1"])), failures)
    check("an unknown rubric dimension is rejected",
          any("rubric" in p for p in problems(rubric=["vibes=2"])), failures)
    check("an out-of-range rubric score is rejected",
          any("0, 1, or 2" in p for p in problems(rubric=["spec_measurability=5"])), failures)
    check("a manifest without provenance is rejected",
          any("provenance" in p
              for p in rr.build_run_record({"identity": {"project_slug": "x"}}, TEMPLATE,
                                           KNOWN, "2026-07-05")[1]), failures)
    check("known_lesson_ids reads the ledger's '- id:' heads textually",
          rr.known_lesson_ids("- id: L-0001\n  rule: x\n- id: L-0002\n")
          == {"L-0001", "L-0002"}, failures)

    # --- emission round-trips through the hand-rolled loader (multi-word messages too) ---
    rec2, _ = rr.build_run_record(MANIFEST, TEMPLATE, KNOWN, "2026-07-05", outcome="failed",
                                  failures=['ci-bootstrap=msvc job red: LNK2019 "unresolved"'],
                                  lessons=["L-0002"], rubric=["profile_fidelity=1"])
    loaded = render.load_yaml(rr.emit_record_yaml(rec2))
    check("round-trip: scalars survive",
          (loaded["slug"], loaded["date"], loaded["outcome"]) == ("acme", "2026-07-05", "failed"),
          failures)
    check("round-trip: overrides survive with values",
          any(ov.get("key") == "ownership.license_id" and ov.get("chosen") == "Apache-2.0"
              for ov in loaded["overrides"]), failures)
    check("round-trip: the failure channel survives quoting",
          loaded["failures"][0]["gate"] == "ci-bootstrap"
          and 'LNK2019 "unresolved"' in loaded["failures"][0]["message"], failures)
    check("round-trip: lessons + rubric survive",
          loaded["lessons_applied"] == ["L-0002"] and loaded["rubric"] == {"profile_fidelity": 1},
          failures)

    # --- #201: provenance_gaps names sections present in the manifest but missing from a partial
    #     provenance block — the recorder warns on them (a partial block derives no override there) ---
    check("provenance_gaps flags a present section missing from a partial block (language)",
          rr.provenance_gaps(MANIFEST) == ["language"], failures)
    complete = {**MANIFEST, "interview": {"questionnaire_version": 1, "provenance": {
        "domain": "asked", "identity": "asked", "ownership": "asked", "toolchain": "asked",
        "governance": "asked", "i18n": "defaulted", "language": "asked"}}}
    check("provenance_gaps is empty when every section is recorded",
          rr.provenance_gaps(complete) == [], failures)
    check("provenance_gaps is empty (no warning) when there is no provenance block",
          rr.provenance_gaps({"identity": {}}) == [], failures)

    # --- #215: a record is phase-tagged (default scaffold; migrate/audit for real-user-code work),
    #     and a sensitive override key redacts its chosen value before it hits the committed ledger ---
    rec_r, probs_r = rr.build_run_record(MANIFEST, TEMPLATE, KNOWN, "2026-07-05", phase="migrate")
    check("build_run_record tags the phase", rec_r.get("phase") == "migrate" and probs_r == [],
          failures)
    check("the default phase is scaffold",
          rr.build_run_record(MANIFEST, TEMPLATE, KNOWN, "2026-07-05")[0]["phase"] == "scaffold",
          failures)
    check("an unknown phase is rejected",
          any("phase must be" in p
              for p in rr.build_run_record(MANIFEST, TEMPLATE, KNOWN, "2026-07-05", phase="bogus")[1]),
          failures)
    check("emit writes the phase line", "phase:" in rr.emit_record_yaml(rec_r), failures)

    # --- #297: an accepted route mismatch — parsed, emitted only when present, round-trips ---
    rec_m, probs_m = rr.build_run_record(MANIFEST, TEMPLATE, KNOWN, "2026-07-05",
                                         route_mismatch="frontier-reasoning/high=standard")
    check("build_run_record records the accepted mismatch",
          rec_m.get("route_mismatch") == {"routed": "frontier-reasoning/high", "session": "standard"}
          and probs_m == [], failures)
    loaded_m = render.load_yaml(rr.emit_record_yaml(rec_m))
    check("round-trip: the route_mismatch block survives",
          loaded_m.get("route_mismatch") == {"routed": "frontier-reasoning/high", "session": "standard"},
          failures)
    check("route_mismatch is omitted when the flag is absent (records stay byte-identical)",
          "route_mismatch" not in rr.emit_record_yaml(rec_r), failures)
    check("route_mismatch defaults to empty in the record dict",
          rr.build_run_record(MANIFEST, TEMPLATE, KNOWN, "2026-07-05")[0]["route_mismatch"] == {},
          failures)
    check("a malformed route mismatch (no '=') is a problem",
          any("ROUTED=SESSION" in p for p in rr.build_run_record(
              MANIFEST, TEMPLATE, KNOWN, "2026-07-05", route_mismatch="frontier-reasoning")[1]),
          failures)
    check("a route mismatch with an empty side is a problem",
          any("ROUTED=SESSION" in p for p in rr.build_run_record(
              MANIFEST, TEMPLATE, KNOWN, "2026-07-05", route_mismatch="standard=")[1]), failures)
    r_ok, _ = rr.parse_route_mismatch("standard/medium=fast")
    check("parse_route_mismatch trims and splits",
          r_ok == {"routed": "standard/medium", "session": "fast"}, failures)
    check("a sensitive override key redacts its chosen value (host/url/registry/token/...)",
          rr.redact_overrides([{"key": "ci.registry_url", "default": "d", "chosen": "internal:5000"}])
          == [{"key": "ci.registry_url", "default": "d", "chosen": "<redacted>"}], failures)
    check("a normal override key keeps its chosen value",
          rr.redact_overrides([{"key": "toolchain.linter", "default": "flake8", "chosen": "ruff"}])
          == [{"key": "toolchain.linter", "default": "flake8", "chosen": "ruff"}], failures)

    # --- acceptance: ONE command produces a schema-valid record from reference.yaml ---
    proc = subprocess.run([sys.executable, RECORD_RUN_PY, REFERENCE, "--dry-run",
                           "--date", "2026-07-05", "--lesson", "L-0001",
                           "--rubric", "spec_measurability=2"],
                          capture_output=True, text=True, encoding="utf-8")
    check(f"CLI --dry-run on reference.yaml exits 0 (got {proc.returncode}: "
          f"{(proc.stderr or proc.stdout)[:120]})", proc.returncode == 0, failures)
    ref_rec = render.load_yaml(proc.stdout) if proc.returncode == 0 else {}
    check("reference record carries the real slug/lang/kind",
          (ref_rec.get("slug"), ref_rec.get("lang"), ref_rec.get("kind"))
          == ("memorypool", "cpp", "library"), failures)
    check("reference record derives the genuine bench override",
          any(ov.get("key") == "governance.capabilities.bench"
              for ov in ref_rec.get("overrides", [])), failures)

    # --- acceptance: autotune consumes the extended records unchanged ---
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("2026-07-04-a.yaml", "2026-07-05-b.yaml"):
            with open(os.path.join(tmp, name), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(rr.emit_record_yaml(rec))     # extended keys included
        runs_before, argv_before = autotune.RUNS, sys.argv
        out = io.StringIO()
        try:
            autotune.RUNS, sys.argv = tmp, ["autotune.py", "--threshold", "2"]
            with contextlib.redirect_stdout(out):
                code = autotune.main()
        finally:
            autotune.RUNS, sys.argv = runs_before, argv_before
        check("autotune runs green over recorder output", code == 0, failures)
        check("autotune mines the recorder's overrides (extended keys ignored)",
              "ownership.license_id" in out.getvalue()
              and "Apache-2.0" in out.getvalue(), failures)

    if failures:
        print("test-record-run: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-record-run: OK — overrides derive from provenance, channels validate, records "
          "round-trip, and autotune consumes them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
