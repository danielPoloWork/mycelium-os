#!/usr/bin/env python3
"""EADOS end-to-end phase-flow smoke (roadmap 6.1 / G4).

The per-tool unit tests (`test_rfc_check`, `test_traceability`, `test_risk_score`,
`test_phase_runner`, ...) each exercise *one* tool in isolation, with hand-built strings. They
cannot catch a bug at the **seams between tools** — the integration the delivery pipeline depends
on: that a single coherent fixture project flows through `design -> plan -> audit` with every gate
agreeing on the *same* RFC ids, milestone, and links, and that the phase runner's view of the
state machine matches what `workflow.yaml` declares.

This smoke threads ONE fixture project (manifest + RFC + ROADMAP + links) through the real phase
tool chain by invoking each tool's **actual CLI** via subprocess — exactly how an agent (or CI)
runs a phase — and asserts:

  * the gate tools **pass** on the good fixture (the artifacts a real phase produces satisfy them);
  * each gate **fails** (non-zero exit) on a deliberately broken fixture (the gate truly gates —
    a smoke that only walks the happy path proves nothing);
  * for **every** transition declared in `workflow.yaml`, `phase_runner --propose` reports it LEGAL
    and lists that transition's entry gates, and an *undeclared* move is rejected ILLEGAL — the
    flow is data-driven from the spec, so it follows the workflow without a hardcoded copy;
  * every entry gate names a registered gate whose backing tool exists on disk — tying the
    workflow spec to the real toolchain (a renamed tool or typo'd gate id breaks the flow but
    passes every unit test).

Dependency-free (stdlib + the sibling renderer's YAML loader), so it runs in the self-lint job.

    python .eados-core/tools/tests/test_phase_smoke.py
"""

import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)                      # .eados-core/tools
ROOT = os.path.dirname(TOOLS)                      # .eados-core
sys.path.insert(0, TOOLS)
import render  # noqa: E402  — the hand-rolled, dependency-free YAML loader (sibling tool)

WORKFLOW = os.path.join(ROOT, "orchestrator", "os", "workflow", "workflow.yaml")

# --- the coherent fixture project: every artifact references the SAME RFC-0001 / Milestone 1 ----

RFC_OK = (
    "# RFC-0001 — Sample feature\n\n"
    "## Context\nWhy the change is needed.\n\n"
    "## Decision\nWe will implement the sample feature.\n\n"
    "## Alternatives\nWe considered doing nothing and an off-the-shelf option.\n\n"
    "## Consequences\nA small maintenance cost; a clearer pipeline.\n\n"
    "## Approval\napproved-by: tech-lead (2026-06-27)\n"
)

# Same RFC with the approval record removed — the design gate must reject it (not approved yet).
RFC_PENDING = (
    "# RFC-0001 — Sample feature\n\n"
    "## Context\nWhy the change is needed.\n\n"
    "## Decision\nWe will implement the sample feature.\n\n"
    "## Alternatives\nWe considered doing nothing and an off-the-shelf option.\n\n"
    "## Consequences\nA small maintenance cost; a clearer pipeline.\n"
)

ROADMAP = (
    "# Roadmap — fixture project\n\n"
    "## Milestone 1 — Bootstrap\n"
    "- [ ] 1.1 implement the sample feature per RFC-0001\n"
)

# A whole Git-side graph: the RFC traces to a PR, milestone, commit, and release.
LINKS_WHOLE = (
    "links:\n"
    "  - pr: 12\n"
    "    rfc: RFC-0001\n"
    "    milestone: \"1\"\n"
    "    commit: abc123\n"
    "    release: v0.1.0\n"
)

# A dangling graph: the only link carries no RFC (pr-no-rfc), so RFC-0001 traces to no PR
# (rfc-no-pr) — traceability-lint must fail.
LINKS_BROKEN = (
    "links:\n"
    "  - pr: 99\n"
    "    milestone: \"1\"\n"
    "    commit: def456\n"
)


def manifest_at(phase):
    """A minimal but realistic manifest parked at `phase` (what phase_runner reads)."""
    return (
        "schema_version: 1\n"
        "delivery_state:\n"
        f"  phase: {phase}\n"
        "  refs:\n"
        "    rfcs:\n"
        "      - RFC-0001\n"
        "    milestones:\n"
        "      - \"1\"\n"
    )


def run_tool(name, *args):
    """Invoke a real tool CLI the way an agent / CI does; return (returncode, combined output).

    The child is pinned to UTF-8 so output decodes identically on every platform (the tools emit
    em-dashes); assertions below only match ASCII substrings regardless."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    proc = subprocess.run(
        [sys.executable, os.path.join(TOOLS, name), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def expect(failures, label, rc, out, want_rc, *needles):
    """Record a failure (with a debuggable snippet) unless rc and every needle match."""
    if rc != want_rc or not all(n in out for n in needles):
        snippet = " | ".join(line for line in out.splitlines() if line.strip())[:240]
        failures.append(f"{label}  (rc={rc}, want {want_rc}; out: {snippet})")


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    workflow = render.load_yaml(open(WORKFLOW, encoding="utf-8").read())
    transitions = workflow.get("transitions") or []
    states = [s.get("id") for s in (workflow.get("states") or []) if isinstance(s, dict)]
    gates = {g.get("id"): g for g in (workflow.get("gates") or []) if isinstance(g, dict)}

    with tempfile.TemporaryDirectory() as tmp:
        def write(name, text):
            path = os.path.join(tmp, name)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            return path

        rfc_ok = write("0001-sample.md", RFC_OK)
        rfc_pending = write("0001-pending.md", RFC_PENDING)
        roadmap = write("ROADMAP.md", ROADMAP)
        links_whole = write("links-whole.yaml", LINKS_WHOLE)
        links_broken = write("links-broken.yaml", LINKS_BROKEN)

        def manifest(phase):
            return write("project.yaml", manifest_at(phase))

        # === design phase — the rfc-approved gate =================================================
        rc, out = run_tool("rfc_check.py", rfc_ok)
        expect(failures, "design: rfc_check passes the approved RFC", rc, out, 0, "OK")
        rc, out = run_tool("rfc_check.py", rfc_pending)
        expect(failures, "design: rfc_check rejects the un-approved RFC", rc, out, 1, "FAIL")

        rc, out = run_tool("phase_runner.py", manifest("design"))
        expect(failures, "design: phase_runner reports the legal next move", rc, out, 0,
               "current phase: design", "-> plan")
        rc, out = run_tool("phase_runner.py", manifest("design"), "--propose", "plan")
        expect(failures, "design: design -> plan is LEGAL", rc, out, 0, "LEGAL", "rfc-approved")

        # === #200: eados.py phase gates are fail-closed under --strict ============================
        # design records RFC refs but we pass no --rfc: rfc-approved is `needs-input` — it passes by
        # default, but FAILs under --strict (a checkable input was withheld, not "not applicable").
        rc, out = run_tool("eados.py", "design", manifest("design"))
        expect(failures, "eados design: needs-input passes without --strict", rc, out, 0,
               "[needs-input] rfc-approved")
        rc, out = run_tool("eados.py", "design", manifest("design"), "--strict")
        expect(failures, "eados design --strict: needs-input FAILs the phase", rc, out, 1,
               "[needs-input] rfc-approved")
        # a manifest with NO recorded refs is genuinely not-applicable: `skipped`, and it still
        # passes even under --strict (only a WITHHELD checkable input fails).
        no_refs = write("no-refs.yaml", "schema_version: 1\ndelivery_state:\n  phase: design\n"
                        "  refs:\n    rfcs: []\n    milestones: []\n")
        rc, out = run_tool("eados.py", "design", no_refs, "--strict")
        expect(failures, "eados design --strict: a skipped (no refs) gate still passes", rc, out, 0,
               "[skipped] rfc-approved")

        # === #213: --propose evaluates the transition's gates LIVE and records them in the checkpoint
        # design -> plan gates rfc-approved: with an approved RFC it is recorded OK; without --rfc it
        # is `needs-input` and the move is flagged NOT READY (the checkpoint chain would reject it).
        rc, out = run_tool("phase_runner.py", manifest("design"), "--propose", "plan",
                           "--rfc", rfc_ok)
        expect(failures, "propose evaluates rfc-approved live and records it OK", rc, out, 0,
               "gate results (live)", "gate_results: { rfc-approved: OK }")
        rc, out = run_tool("phase_runner.py", manifest("design"), "--propose", "plan")
        expect(failures, "propose without --rfc records needs-input and warns NOT READY", rc, out, 0,
               "gate_results: { rfc-approved: needs-input }", "NOT READY")

        # === plan phase — the roadmap-covers-rfcs gate ============================================
        rc, out = run_tool("traceability.py", roadmap, "RFC-0001")
        expect(failures, "plan: roadmap-covers-rfcs passes when the RFC is covered", rc, out, 0,
               "roadmap-covers-rfcs: OK")
        rc, out = run_tool("traceability.py", roadmap, "RFC-9999")
        expect(failures, "plan: roadmap-covers-rfcs fails an uncovered RFC", rc, out, 1, "FAIL")

        rc, out = run_tool("phase_runner.py", manifest("plan"), "--propose", "scaffold")
        expect(failures, "plan: plan -> scaffold is LEGAL", rc, out, 0, "LEGAL",
               "roadmap-covers-rfcs")

        # === audit phase — traceability-lint + risk score =========================================
        rc, out = run_tool("traceability.py", roadmap, "RFC-0001", "--links", links_whole)
        expect(failures, "audit: traceability-lint passes a whole graph", rc, out, 0,
               "traceability-lint: OK")
        rc, out = run_tool("traceability.py", roadmap, "RFC-0001", "--links", links_broken)
        expect(failures, "audit: traceability-lint fails a dangling graph", rc, out, 1,
               "traceability-lint: FAIL")

        rc, out = run_tool("risk_score.py", "tools/render.py", "--lines", "120")
        expect(failures, "audit: a security-surface change scores high -> gate REQUIRED", rc, out,
               0, "risk: high", "REQUIRED")
        rc, out = run_tool("risk_score.py", "README.md", "--lines", "10")
        expect(failures, "audit: a docs-only change scores low -> gate optional", rc, out, 0,
               "risk: low", "optional")

        rc, out = run_tool("phase_runner.py", manifest("audit"), "--propose", "migrate")
        expect(failures, "audit: audit -> migrate is LEGAL", rc, out, 0, "LEGAL",
               "risk-register-present")

        # === state machine — every declared transition is LEGAL, undeclared ones are not =========
        for t in transitions:
            frm, to = t.get("from"), t.get("to")
            rc, out = run_tool("phase_runner.py", manifest(frm), "--propose", to)
            expect(failures, f"transition {frm} -> {to} is LEGAL", rc, out, 0, "LEGAL")
            for gate in t.get("entry_gates") or []:
                check(f"transition {frm} -> {to} lists its gate '{gate}'", gate in out, failures)

        declared = {(t.get("from"), t.get("to")) for t in transitions}
        skip = ("design", "audit")   # a forward skip the spec deliberately does not allow
        check("the smoke's negative case is genuinely undeclared", skip not in declared, failures)
        rc, out = run_tool("phase_runner.py", manifest(skip[0]), "--propose", skip[1])
        expect(failures, "an undeclared transition is rejected ILLEGAL", rc, out, 1, "ILLEGAL")

        rc, out = run_tool("phase_runner.py", manifest("design"), "--propose", "nonsense")
        expect(failures, "a non-state target is rejected ILLEGAL", rc, out, 1, "ILLEGAL")

    # === the glue: every entry gate is registered and its backing tool exists on disk ============
    for t in transitions:
        for gate in t.get("entry_gates") or []:
            check(f"entry gate '{gate}' is in the gate registry", gate in gates, failures)
    for gid, g in gates.items():
        m = re.search(r"\.eados-core/tools/(\w+\.py)", g.get("runs") or "")
        if m:
            check(f"gate '{gid}' backing tool {m.group(1)} exists on disk",
                  os.path.exists(os.path.join(TOOLS, m.group(1))), failures)

    # A coherence guard: the phases the smoke walks are real workflow states.
    for phase in ("design", "plan", "scaffold", "audit", "migrate"):
        check(f"'{phase}' is a declared workflow state", phase in states, failures)

    if failures:
        print("test-phase-smoke: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-phase-smoke: OK -- design -> plan -> audit flows; every gate gates; "
          "the runner matches workflow.yaml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
