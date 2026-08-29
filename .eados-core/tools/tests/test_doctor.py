#!/usr/bin/env python3
"""Tests for doctor — the `/eados status` read-only health readout (roadmap 6.4 / F1).
Dependency-free.

    python .eados-core/tools/tests/test_doctor.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import doctor  # noqa: E402  (the module under test)
import phase_runner  # noqa: E402

ROADMAP = (
    "# Roadmap — fixture\n"
    "## Milestone 1 — Bootstrap\n"
    "- [ ] 1.1 implement the sample feature per RFC-0001\n"
)
WHOLE = [{"pr": 12, "rfc": "RFC-0001", "milestone": "1", "commit": "abc123", "release": "v0.1.0"}]
BROKEN = [{"pr": 99, "milestone": "1", "commit": "def456"}]  # no rfc -> pr-no-rfc + rfc-no-pr


def manifest_at(phase, rfcs=("RFC-0001",)):
    return {"delivery_state": {"phase": phase, "refs": {"rfcs": list(rfcs), "milestones": ["1"]}}}


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def has(lines, needle):
    return any(needle in ln for ln in lines)


def main():
    failures = []
    wf = phase_runner.load_workflow()

    # --- a healthy plan-phase project: phase, legal move, covered RFC, whole graph ---
    lines, healthy = doctor.status_report(manifest_at("plan"), wf, ROADMAP, WHOLE)
    check("reports the current phase + role", has(lines, "phase: plan") and has(lines, "role:"),
          failures)
    check("lists the legal next transition (plan -> scaffold)", has(lines, "-> scaffold"), failures)
    check("shows its entry gate", has(lines, "roadmap-covers-rfcs"), failures)
    check("shows the recorded refs", has(lines, "RFC-0001"), failures)
    check("roadmap-covers-rfcs OK when covered", has(lines, "roadmap-covers-rfcs: OK"), failures)
    check("traceability-lint OK on a whole graph", has(lines, "traceability-lint: OK"), failures)
    check("a healthy project is healthy", healthy, failures)

    # --- an uncovered RFC -> FAIL + unhealthy ---
    lines, healthy = doctor.status_report(manifest_at("plan", rfcs=("RFC-9999",)), wf, ROADMAP, WHOLE)
    check("an uncovered RFC trips roadmap-covers-rfcs", has(lines, "roadmap-covers-rfcs: FAIL"),
          failures)
    check("an uncovered RFC is unhealthy (non-zero)", not healthy, failures)

    # --- a dangling traceability graph -> FAIL + unhealthy ---
    lines, healthy = doctor.status_report(manifest_at("plan"), wf, ROADMAP, BROKEN)
    check("a dangling graph trips traceability-lint", has(lines, "traceability-lint: FAIL"), failures)
    check("a dangling graph is unhealthy", not healthy, failures)

    # --- no delivery_state -> defaults to init, healthy, points at design ---
    lines, healthy = doctor.status_report({}, wf, None, None)
    check("a manifest with no delivery_state defaults to init", has(lines, "phase: init"), failures)
    check("init points at design", has(lines, "-> design"), failures)
    check("no roadmap -> coverage not checked", has(lines, "no ROADMAP.md found"), failures)
    check("a fresh manifest is healthy", healthy, failures)

    # --- #165: a game project's overlay is applied AND surfaced; software stays byte-identical ---
    merged = phase_runner.apply_overlay(wf, "game")
    lines, healthy = doctor.status_report(manifest_at("scaffold"), merged, None, None)
    check("game overlay: the domain line surfaces states + gates",
          has(lines, "domain: game") and has(lines, "+state asset-pipeline-review")
          and has(lines, "+gate hardware-budget"), failures)
    check("game overlay: hardware-budget gates the scaffold -> audit move",
          any("-> audit" in ln and "hardware-budget" in ln for ln in lines), failures)
    check("game overlay: an applied overlay stays healthy", healthy, failures)
    base_lines, _ = doctor.status_report(manifest_at("plan"), wf, ROADMAP, WHOLE)
    sw_lines, _ = doctor.status_report(
        manifest_at("plan"), phase_runner.apply_overlay(wf, "software"), ROADMAP, WHOLE)
    check("software status is byte-identical to the base machine", sw_lines == base_lines, failures)

    # --- an undeclared phase -> structural error, unhealthy ---
    lines, healthy = doctor.status_report(manifest_at("bogus"), wf, ROADMAP, WHOLE)
    check("an undeclared phase is flagged", has(lines, "not a declared workflow state"), failures)
    check("an undeclared phase is unhealthy", not healthy, failures)

    # --- refs present but no roadmap -> neutral (healthy), nothing to cover only if no rfcs ---
    lines, healthy = doctor.status_report(manifest_at("audit"), wf, None, None)
    check("audit -> migrate is shown", has(lines, "-> migrate"), failures)
    check("no roadmap stays healthy", healthy, failures)

    # --- M16 16.3 (#254): the advisory routing readout (pure; the gh shell is not touched) ---
    import route_advice
    spec = route_advice.load_routing()
    issues = [
        {"number": 1, "title": "ratify the ADR", "labels": ["adr", "severity:high"]},
        {"number": 2, "title": "fix a doc typo", "labels": ["documentation", "severity:low"]},
    ]
    rl = doctor.routing_lines(issues, spec)
    check("one advisory line per issue (+ the boundary line)", len(rl) == 3, failures)
    check("an ADR-labelled issue routes to frontier-reasoning",
          has(rl, "#1 -> frontier-reasoning/"), failures)
    check("a small doc fix stays on the floor",
          has(rl, f"#2 -> {spec['defaults']['tier']}/{spec['defaults']['effort']}"), failures)
    check("the advice names today's catalog model", has(rl, "("), failures)
    check("the advisory boundary is stated", has(rl, "advisory only"), failures)
    check("no issues -> no lines (nothing to advise)",
          doctor.routing_lines([], spec) == [], failures)

    if failures:
        print("test-doctor: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-doctor: OK -- phase, legal moves, refs, and traceability coverage report; problems "
          "mark it unhealthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
