#!/usr/bin/env python3
"""Tests for eados — the thin phase orchestrator (roadmap 6.5 / G3). Dependency-free.

    python .eados-core/tools/tests/test_eados.py
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados  # noqa: E402  (the module under test)
import phase_runner  # noqa: E402

ROADMAP = (
    "# Roadmap — fixture\n"
    "## Milestone 1 — Bootstrap\n"
    "- [ ] 1.1 implement the sample feature per RFC-0001\n"
)
RFC_OK = (
    "# RFC-0001\n\n## Context\nx\n\n## Decision\ny\n\n## Alternatives\nz\n\n"
    "## Consequences\nw\n\n## Approval\napproved-by: tech-lead (2026-06-27)\n"
)
# A minimal manifest that passes validate_manifest (so manifest-valid is OK). The spec block
# is the minimum the #170 substance floor accepts.
SPEC_FLOOR = {
    "objective": "A demo library.",
    "functional_reqs": ["do one thing"],
    "verification": "unit tests",
    "milestones": [{"number": 2, "title": "Harden", "goal": "Stable API",
                    "items": ["2.1 freeze the API"]}],
}

# The canonical pipeline hops (from, to, human_gated, entry_gates) — used to synthesize the legal
# checkpoint chain #199 requires (a manifest at a non-init phase must record how it got there),
# with the gate marks #250 requires on every human-gated hop (recorded evidence, not honor).
_PIPELINE = [("init", "design", True, ("manifest-valid",)),
             ("design", "plan", True, ("rfc-approved",)),
             ("plan", "scaffold", True, ("roadmap-covers-rfcs",)),
             ("scaffold", "audit", False, ()),
             ("audit", "migrate", True, ("risk-register-present", "traceability-lint"))]
_ORDER = ["init", "design", "plan", "scaffold", "audit", "migrate"]


def _chain_to(phase):
    """A legal, contiguous checkpoint chain from init up to `phase` (empty at init), with a
    `confirmed_by` AND recorded `gate_results` on every human-gated hop — the evidence
    delivery-state-consistency (#199) and the #250 honor-system closure want."""
    chain = []
    for frm, to, human, gates in _PIPELINE:
        if _ORDER.index(to) > _ORDER.index(phase):
            break
        cp = {"from": frm, "to": to, "at": "2026-07-01"}
        if human:
            cp["confirmed_by"] = "owner"
            cp["gate_results"] = {g: "OK" for g in gates}
        chain.append(cp)
    return chain


def manifest_yaml(phase, domain=None, budgets=None):
    """A raw manifest string at `phase` carrying the legal checkpoint chain (#199). `budgets`
    (a list of (axis, target) tuples) records spec.nfr_budgets — a domain with hard axes needs
    them to clear the in-process nfr-budgets gate (#249)."""
    lines = [
        "identity:", "  project_name: Demo", "  project_slug: demo", "  project_kind: library",
        "ownership:", "  owner: me", "  license_id: MIT", "  default_branch: main",
        "language:", "  lang: cpp", "  group_path: it/x",
        "spec:", "  objective: A demo library.", "  functional_reqs: [do one thing]",
        "  verification: unit tests", "  milestones:",
        '    - { number: 2, title: Harden, goal: Stable API, items: ["2.1 freeze the API"] }',
    ]
    if budgets:
        lines.append("  nfr_budgets:")
        for axis, target in budgets:
            lines.append(f"    - {{ axis: {axis}, target: {target} }}")
    lines += ["delivery_state:", f"  phase: {phase}"]
    chain = _chain_to(phase)
    if chain:
        lines.append("  checkpoints:")
        for cp in chain:
            # block style for readability (the flow form report_propose emits parses equally —
            # yamlmini's flow parser is depth-aware; #250)
            lines.append(f'    - from: {cp["from"]}')
            lines.append(f'      to: {cp["to"]}')
            lines.append(f'      at: "{cp["at"]}"')
            if "confirmed_by" in cp:
                lines.append(f'      confirmed_by: {cp["confirmed_by"]}')
                marks = ", ".join(f"{g}: OK" for g in cp["gate_results"])
                lines.append(f'      gate_results: {{ {marks} }}')
    lines += ["  refs:", "    rfcs:", "      - RFC-0001", "    milestones:", '      - "1"']
    if domain:
        lines.append(f"domain: {domain}")
    return "\n".join(lines) + "\n"


def manifest_at(phase, rfcs=("RFC-0001",)):
    return {
        "identity": {"project_name": "Demo", "project_slug": "demo", "project_kind": "library"},
        "ownership": {"owner": "me", "license_id": "MIT", "default_branch": "main"},
        "language": {"lang": "cpp", "group_path": "it/x"},
        "spec": dict(SPEC_FLOOR),
        "delivery_state": {"phase": phase, "checkpoints": _chain_to(phase),
                           "refs": {"rfcs": list(rfcs), "milestones": ["1"]}},
    }


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def has(lines, needle):
    return any(needle in ln for ln in lines)


def main():
    failures = []
    wf = phase_runner.load_workflow()

    # --- plan: gates are data-driven from workflow (manifest-valid + roadmap-covers-rfcs) ---
    lines, ok = eados.run_phase("plan", manifest_at("plan"), wf, ROADMAP)
    check("plan runs manifest-valid (from plan->design)", has(lines, "[OK] manifest-valid"), failures)
    check("plan runs roadmap-covers-rfcs (from plan->scaffold)",
          has(lines, "[OK] roadmap-covers-rfcs"), failures)
    check("plan lists the legal moves", has(lines, "-> scaffold") and has(lines, "-> design"),
          failures)
    check("plan points at its procedure", has(lines, "commands/plan.md"), failures)
    check("a covered, valid plan is ok", ok, failures)

    # --- an uncovered RFC fails the gate ---
    lines, ok = eados.run_phase("plan", manifest_at("plan", rfcs=("RFC-9999",)), wf, ROADMAP)
    check("an uncovered RFC FAILs roadmap-covers-rfcs", has(lines, "[FAIL] roadmap-covers-rfcs"),
          failures)
    check("a failed gate makes the phase not ok", not ok, failures)

    # --- design: rfc-approved is evaluable only with --rfc ---
    lines, ok = eados.run_phase("design", manifest_at("design"), wf, None, RFC_OK)
    check("design with an approved RFC passes rfc-approved", has(lines, "[OK] rfc-approved"), failures)
    check("design with a good RFC is ok", ok, failures)
    lines, ok = eados.run_phase("design", manifest_at("design"), wf, None, None)
    check("design with recorded RFC refs but no --rfc is needs-input (not skipped)",
          has(lines, "[needs-input] rfc-approved"), failures)
    check("needs-input does not fail the phase without --strict", ok, failures)
    # #200: under --strict a needs-input gate (a checkable input was withheld) fails the phase, but
    # a genuinely not-applicable skipped gate still passes — the gate can't be satisfied by omission.
    _l, ok_strict = eados.run_phase("design", manifest_at("design"), wf, None, None, strict=True)
    check("needs-input FAILs the phase under --strict", not ok_strict, failures)
    lines, ok = eados.run_phase("design", manifest_at("design", rfcs=()), wf, None, None, strict=True)
    check("no recorded RFC refs is skipped (not applicable) and passes even under --strict",
          has(lines, "[skipped] rfc-approved") and ok, failures)

    # --- scaffold: its gates need a rendered repo -> [manual], nothing fails ---
    lines, ok = eados.run_phase("scaffold", manifest_at("scaffold"), wf)
    check("scaffold's render-time gates are manual",
          has(lines, "[manual] consistency-lint") and has(lines, "[manual] self-review"), failures)
    check("scaffold is ok (nothing auto-failed)", ok, failures)

    # --- #165: a game project's overlay gate surfaces as [manual] on the scaffold exit ---
    lines, ok = eados.run_phase("scaffold", manifest_at("scaffold"),
                                phase_runner.apply_overlay(wf, "game"))
    check("game overlay: [manual] hardware-budget gates scaffold",
          has(lines, "[manual] hardware-budget"), failures)
    check("game overlay: scaffold stays ok (manual never auto-fails)", ok, failures)

    # --- init: manifest-valid OK; an invalid manifest FAILs it ---
    lines, ok = eados.run_phase("init", manifest_at("init"), wf)
    check("init runs manifest-valid OK", has(lines, "[OK] manifest-valid") and ok, failures)
    lines, ok = eados.run_phase("init", {"identity": {"project_name": "x"}}, wf)
    check("an invalid manifest FAILs manifest-valid", has(lines, "[FAIL] manifest-valid") and not ok,
          failures)

    # --- #213: evaluate_gates is the shared marks-only resolver behind run_phase AND the checkpoint's
    #     live gate_results — an in-process gate is evaluated, an external one is `manual` ---
    marks = eados.evaluate_gates(["manifest-valid", "consistency-lint"], manifest_at("init"), {})
    check("evaluate_gates evaluates an in-process gate (manifest-valid OK on a valid manifest)",
          marks.get("manifest-valid") == "OK", failures)
    check("evaluate_gates marks an external gate as manual (run by the procedure / CI)",
          marks.get("consistency-lint") == "manual", failures)

    # --- an undeclared phase errors ---
    lines, ok = eados.run_phase("bogus", manifest_at("init"), wf)
    check("an undeclared phase is rejected", has(lines, "not a declared workflow state") and not ok,
          failures)

    # --- CLI smoke: a phase and `status` over real files, with exit codes ---
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "project.yaml"), "w", encoding="utf-8") as h:
            h.write(manifest_yaml("plan"))
        with open(os.path.join(d, "ROADMAP.md"), "w", encoding="utf-8") as h:
            h.write(ROADMAP)
        eados_py = os.path.join(TOOLS, "eados.py")
        manifest = os.path.join(d, "project.yaml")

        def run(*a):
            p = subprocess.run([sys.executable, eados_py, *a], capture_output=True, text=True,
                               encoding="utf-8", env=env)
            return p.returncode, (p.stdout or "") + (p.stderr or "")

        rc, out = run("plan", manifest)
        check("CLI `eados.py plan` exits 0 on a covered project", rc == 0, failures)
        check("CLI plan reports roadmap-covers-rfcs OK", "roadmap-covers-rfcs" in out, failures)
        rc, out = run("status", manifest)
        check("CLI `eados.py status` runs the doctor (exit 0)",
              rc == 0 and "phase: plan" in out, failures)
        # #165: the CLI reads the manifest's domain and applies its overlay end-to-end.
        # #249: a game manifest carries its four hard-axis budgets — without them the in-process
        # nfr-budgets gate (now on the overlay) correctly FAILs the scaffold exit.
        game = os.path.join(d, "game.yaml")
        with open(game, "w", encoding="utf-8") as h:
            h.write(manifest_yaml("scaffold", domain="game",
                                  budgets=[("framerate", 60), ("memory", 512),
                                           ("gpu", 2000), ("load_time", 30)]))
        rc, out = run("scaffold", game)
        check("CLI applies the manifest's domain overlay ([manual] hardware-budget)",
              rc == 0 and "[manual] hardware-budget" in out, failures)
        check("CLI evaluates the nfr-budgets gate in-process ([OK], #249)",
              "[OK] nfr-budgets" in out, failures)
        # ...and a game manifest WITHOUT budgets fails the same exit (the enforcement, #249)
        bare = os.path.join(d, "game-bare.yaml")
        with open(bare, "w", encoding="utf-8") as h:
            h.write(manifest_yaml("scaffold", domain="game"))
        rc, out = run("scaffold", bare)
        check("CLI FAILs a game manifest with no recorded budgets (rc 1, #249)",
              rc == 1 and "[FAIL] nfr-budgets" in out, failures)
        rc, out = run("status", game)
        check("CLI status surfaces the applied overlay",
              rc == 0 and "domain: game" in out and "asset-pipeline-review" in out, failures)

    if failures:
        print("test-eados: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-eados: OK -- phase gates run data-driven from workflow; failures gate; status "
          "delegates to the doctor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
