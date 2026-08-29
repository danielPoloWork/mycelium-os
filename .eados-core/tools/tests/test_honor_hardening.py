#!/usr/bin/env python3
"""Issue #250 — the honor-system hardening's OTHER three fronts (git_check has its own test):

  * **gate_results persistence** — a human-gated checkpoint must RECORD gate_results covering
    its entry gates (an absent block was the honor system); the divergence re-run flags a
    recorded OK whose ctx-free gate now FAILs (the manifest changed after the move);
  * **traceability-lint evaluator** — the documented gate finally evaluates in-process:
    skipped with no RFC roots, needs-input on withheld roadmap/links (fail-closed under
    --strict), FAIL on a dangling edge, OK on a whole graph;
  * **uniform action record** — the four authoring phases (design/plan/audit/migrate) each
    instruct the same phase-tagged record_run step, so the audit trail is homogeneous.

Dependency-free.

    python .eados-core/tools/tests/test_honor_hardening.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
EADOS = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import eados         # noqa: E402
import phase_runner  # noqa: E402


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def ds(phase, cps, extra=None):
    manifest = {"delivery_state": {"phase": phase, "checkpoints": cps}}
    manifest.update(extra or {})
    return manifest


def main():
    failures = []
    wf = phase_runner.load_workflow()

    # --- 1. gate_results persistence: recorded evidence is REQUIRED on human-gated moves ---
    bare = [{"from": "init", "to": "design", "confirmed_by": "owner"}]
    problems = phase_runner.checkpoint_chain_problems(ds("design", bare), wf)
    check("a human-gated checkpoint WITHOUT gate_results is rejected (#250)",
          any("must record gate_results" in p for p in problems), failures)
    check("the rejection names the missing gate",
          any("manifest-valid" in p for p in problems), failures)
    partial = [{"from": "init", "to": "audit", "confirmed_by": "owner",
                "gate_results": {"manifest-valid": "OK"}}]
    problems = phase_runner.checkpoint_chain_problems(
        ds("audit", partial, {"adoption": {"goals": ["audit"]}}), wf)
    check("PARTIAL coverage is rejected too — every entry gate needs a mark",
          any("adoption-recorded" in p and "must record" in p for p in problems), failures)
    covered = [{"from": "init", "to": "design", "confirmed_by": "owner",
                "gate_results": {"manifest-valid": "OK"}}]
    check("a covered human-gated checkpoint is clean",
          phase_runner.checkpoint_chain_problems(ds("design", covered), wf) == [], failures)
    auto = [{"from": "scaffold", "to": "audit"}]
    check("a NON-human-gated checkpoint needs no gate_results (unchanged)",
          not any("must record" in p for p in phase_runner.checkpoint_chain_problems(
              ds("audit", [dict(covered[0]),
                           {"from": "design", "to": "plan", "confirmed_by": "o",
                            "gate_results": {"rfc-approved": "OK"}},
                           {"from": "plan", "to": "scaffold", "confirmed_by": "o",
                            "gate_results": {"roadmap-covers-rfcs": "OK"}},
                           auto[0]]), wf)), failures)

    # --- 1b. divergence: a recorded OK whose ctx-free gate now FAILs is stale, not evidence ---
    diverged = ds("audit", [{"from": "init", "to": "audit", "confirmed_by": "owner",
                             "gate_results": {"manifest-valid": "OK",
                                              "adoption-recorded": "OK"}}],
                  {"adoption": {"goals": ["not-a-goal"]}})   # malformed NOW -> evaluator FAILs
    problems = phase_runner.checkpoint_chain_problems(diverged, wf)
    check("a recorded OK whose gate now FAILs is flagged as divergence (#250)",
          any("now FAILs" in p and "adoption-recorded" in p for p in problems), failures)
    intact = ds("audit", [{"from": "init", "to": "audit", "confirmed_by": "owner",
                           "gate_results": {"manifest-valid": "OK",
                                            "adoption-recorded": "OK"}}],
                {"adoption": {"goals": ["audit"], "gap_map_ref": "x",
                              "provenance": {"goals": "asked"}}})
    check("a recorded OK whose gate still holds is clean",
          phase_runner.checkpoint_chain_problems(intact, wf) == [], failures)
    deleted = ds("audit", [{"from": "init", "to": "audit", "confirmed_by": "owner",
                            "gate_results": {"manifest-valid": "OK",
                                             "adoption-recorded": "OK"}}])   # no adoption block
    problems = phase_runner.checkpoint_chain_problems(deleted, wf)
    check("a recorded OK whose subject was REMOVED is flagged (skipped-divergence, #250)",
          any("now skipped" in p and "adoption-recorded" in p for p in problems), failures)

    # --- 2. the traceability-lint evaluator: the documented gate finally evaluates ---
    ev = eados.GATE_EVALUATORS.get("traceability-lint")
    check("eados.py registers the traceability-lint evaluator", ev is not None, failures)
    refs = {"delivery_state": {"refs": {"rfcs": ["RFC-0001"]}}}
    # the RFC id must appear in the milestone's BODY (covering_milestones parses section bodies)
    roadmap = "## Milestone 1 — Bootstrap\ncovers RFC-0001\n"
    check("no RFC roots -> skipped", ev({}, {})[0] == "skipped", failures)
    check("a withheld roadmap -> needs-input",
          ev(refs, {"roadmap_text": None, "links": []})[0] == "needs-input", failures)
    check("withheld links -> needs-input (fail-closed: omission must not pass)",
          ev(refs, {"roadmap_text": roadmap, "links": None})[0] == "needs-input", failures)
    mark, detail = ev(refs, {"roadmap_text": roadmap, "links": []})
    check("a dangling edge (RFC with no PR) -> FAIL", mark == "FAIL" and "rfc-no-pr" in detail,
          failures)
    whole = [{"pr": 1, "rfc": "RFC-0001", "milestone": "1", "commit": "abc", "release": ""}]
    check("a whole graph -> OK",
          ev(refs, {"roadmap_text": roadmap, "links": whole})[0] == "OK", failures)
    gate = next((g for g in (wf.get("gates") or [])
                 if isinstance(g, dict) and g.get("id") == "traceability-lint"), None)
    check("workflow.yaml wires traceability-lint in-process (the bijection holds)",
          gate is not None and gate.get("wired") == "in-process", failures)

    # --- 3. the uniform action record: all four authoring phases instruct the same step ---
    for phase in ("design", "plan", "audit", "migrate"):
        proc = read(EADOS, "orchestrator", "commands", f"{phase}.md")
        check(f"{phase}.md instructs the phase-tagged run record (record_run --phase {phase})",
              f"record_run.py <manifest> --phase {phase}" in proc, failures)

    if failures:
        print("test-honor-hardening: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} honor-system invariant(s) broken.")
        return 1
    print("test-honor-hardening: OK — gate_results are required evidence (+ divergence), the "
          "traceability gate evaluates in-process, and every authoring phase records the same "
          "audit trail (#250).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
