#!/usr/bin/env python3
"""Tests for the EADOS phase runner — the legal-transition checker is correct, pure, and the
workflow spec is internally consistent. Dependency-free (runnable in the self-lint job).

    python .eados-core/tools/tests/test_phase_runner.py
"""

import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import phase_runner as pr  # noqa: E402  (the module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    wf = pr.load_workflow()

    # --- current_phase: defaults to init; reads delivery_state when present ---
    check("current_phase default init", pr.current_phase({}) == "init", failures)
    check("current_phase reads delivery_state",
          pr.current_phase({"delivery_state": {"phase": "plan"}}) == "plan", failures)
    check("current_phase tolerates malformed delivery_state",
          pr.current_phase({"delivery_state": "oops"}) == "init", failures)

    # --- legal_transitions: the entry phase forks (#247, ADR-0021) — the ordinary pipeline edge
    #     plus the two brownfield adoption edges, all human-gated ---
    init = pr.legal_transitions(wf, "init")
    by_to = {t.get("to"): t for t in init}
    check("init -> {design, audit, migrate} (the adoption fork, ADR-0021)",
          set(by_to) == {"design", "audit", "migrate"}, failures)
    check("init -> design stays first in declared order (the greenfield default)",
          init and init[0].get("to") == "design", failures)
    check("init -> design is human-gated", by_to.get("design", {}).get("human_gate") is True,
          failures)
    check("init -> design gate is manifest-valid",
          by_to.get("design", {}).get("entry_gates") == ["manifest-valid"], failures)
    for target in ("audit", "migrate"):
        t = by_to.get(target, {})
        check(f"init -> {target} is human-gated (it changes committed direction)",
              t.get("human_gate") is True, failures)
        check(f"init -> {target} is gated on manifest-valid + adoption-recorded",
              t.get("entry_gates") == ["manifest-valid", "adoption-recorded"], failures)

    # --- plan is a fork: forward to scaffold + resumable back to design ---
    plan = {t.get("to") for t in pr.legal_transitions(wf, "plan")}
    check("plan -> {scaffold, design}", plan == {"scaffold", "design"}, failures)

    # --- scaffold -> audit is automatic (not human-gated; the gates are mechanical) ---
    sc = pr.legal_transitions(wf, "scaffold")
    check("scaffold -> audit, not human-gated",
          sc and sc[0].get("to") == "audit" and not sc[0].get("human_gate"), failures)

    # --- migrate is terminal (renamed from refactor, ADR-0020 / #236) ---
    check("migrate is terminal", pr.legal_transitions(wf, "migrate") == [], failures)

    # --- an unknown phase yields no transitions (report() flags it; the function is total) ---
    check("unknown phase -> no transitions", pr.legal_transitions(wf, "bogus") == [], failures)

    # --- workflow integrity: every transition endpoint is a declared state ---
    states = set(pr.state_ids(wf))
    for t in wf.get("transitions") or []:
        check(f"transition from '{t.get('from')}' is a declared state",
              t.get("from") in states, failures)
        check(f"transition to '{t.get('to')}' is a declared state",
              t.get("to") in states, failures)

    # --- #165: domain overlays are applied by apply_overlay, data-driven from the registry ---
    check("manifest_domain defaults to software", pr.manifest_domain({}) == "software", failures)
    check("manifest_domain reads the top-level scalar",
          pr.manifest_domain({"domain": "game"}) == "game", failures)

    # --- #214: the optimistic-concurrency counter reads 0 when absent/malformed, else its value ---
    check("manifest_rev defaults to 0 (legacy/unlocked)", pr.manifest_rev({}) == 0, failures)
    check("manifest_rev reads the counter", pr.manifest_rev({"manifest_rev": 5}) == 5, failures)
    check("manifest_rev treats a negative/non-int value as 0",
          pr.manifest_rev({"manifest_rev": -1}) == 0 and pr.manifest_rev({"manifest_rev": "x"}) == 0,
          failures)
    merged = pr.apply_overlay(wf, "game")
    check("game overlay appends asset-pipeline-review as a human-owner state",
          any(isinstance(s, dict) and s.get("id") == "asset-pipeline-review"
              and s.get("role") == "human-owner" for s in merged.get("states") or []), failures)
    sc_m = pr.legal_transitions(merged, "scaffold")
    check("game overlay gates scaffold -> audit with hardware-budget",
          sc_m and "hardware-budget" in (sc_m[0].get("entry_gates") or []), failures)
    check("the applied overlay is recorded for the doctor",
          (merged.get("applied_overlay") or {}).get("domain") == "game", failures)
    check("the base workflow object is not mutated",
          "hardware-budget" not in (pr.legal_transitions(wf, "scaffold")[0].get("entry_gates") or [])
          and "asset-pipeline-review" not in pr.state_ids(wf), failures)
    web = pr.apply_overlay(wf, "web")
    check("web overlay gates the audit entry with both web gates",
          all(g in (pr.legal_transitions(web, "scaffold")[0].get("entry_gates") or [])
              for g in ("accessibility-review", "web-vitals-budget")), failures)
    check("software is a pass-through (same object, byte-identical machine)",
          pr.apply_overlay(wf, "software") is wf, failures)
    check("an unknown domain is a pass-through", pr.apply_overlay(wf, "quantum") is wf, failures)

    # --- propose_transition: legal vs illegal, and the emitted checkpoint (M2-C) ---
    legal = pr.propose_transition(wf, "init", "design")
    check("propose init->design is legal", legal is not None, failures)
    check("propose init->scaffold is illegal (skips the pipeline)",
          pr.propose_transition(wf, "init", "scaffold") is None, failures)
    check("propose plan->design is legal (resumable)",
          pr.propose_transition(wf, "plan", "design") is not None, failures)
    cp = pr.emit_checkpoint("init", legal)
    check("checkpoint records from/to", cp["from"] == "init" and cp["to"] == "design", failures)
    check("checkpoint carries the entry gates", cp["gates"] == ["manifest-valid"], failures)

    # --- #199: the checkpoint now carries evidence — a date, and a confirmed_by on a human-gated
    #     move (a <owner> placeholder the human fills). A non-human-gated move carries none. ---
    cp_h = pr.emit_checkpoint("init", legal, at="2026-07-06")
    check("enriched checkpoint records the transition date", cp_h.get("at") == "2026-07-06", failures)
    check("a human-gated checkpoint carries a confirmed_by placeholder",
          cp_h.get("confirmed_by") == "<owner>", failures)
    auto = pr.emit_checkpoint("scaffold", pr.propose_transition(wf, "scaffold", "audit"))
    check("a non-human-gated checkpoint carries no confirmed_by", "confirmed_by" not in auto, failures)

    # --- #213: emit_checkpoint records LIVE gate_results when the caller evaluated them, and omits
    #     the key when it did not (so an un-evaluated checkpoint stays unchanged) ---
    cp_gr = pr.emit_checkpoint("init", legal, gate_results={"manifest-valid": "OK"})
    check("emit_checkpoint records gate_results when provided",
          cp_gr.get("gate_results") == {"manifest-valid": "OK"}, failures)
    check("emit_checkpoint omits gate_results when none are provided", "gate_results" not in cp,
          failures)

    # --- #199: checkpoint_chain_problems — a legal contiguous chain ending at the current phase is
    #     clean; a phase-skip, illegal edge, broken chain, missing confirmed_by, a failing
    #     gate_result, and phase != chain-end are each rejected (the honor-system gap is closed) ---
    def ds(phase, cps):
        return {"delivery_state": {"phase": phase, "checkpoints": cps}}
    # #250: a human-gated checkpoint must also RECORD gate_results covering its entry gates
    legal_chain = [{"from": "init", "to": "design", "confirmed_by": "owner",
                    "gate_results": {"manifest-valid": "OK"}},
                   {"from": "design", "to": "plan", "confirmed_by": "owner",
                    "gate_results": {"rfc-approved": "OK"}}]
    check("a legal contiguous chain ending at the current phase is clean",
          pr.checkpoint_chain_problems(ds("plan", legal_chain), wf) == [], failures)
    check("a legacy manifest with no delivery_state is exempt",
          pr.checkpoint_chain_problems({"identity": {}}, wf) == [], failures)
    check("an init phase with no checkpoints is fine",
          pr.checkpoint_chain_problems(ds("init", []), wf) == [], failures)
    check("phase: scaffold with no checkpoints is a rejected phase-skip",
          any("no checkpoints" in p for p in pr.checkpoint_chain_problems(ds("scaffold", []), wf)),
          failures)
    check("an illegal edge (init -> scaffold) is rejected",
          any("not a legal transition" in p for p in pr.checkpoint_chain_problems(
              ds("scaffold", [{"from": "init", "to": "scaffold", "confirmed_by": "o"}]), wf)), failures)
    check("a non-contiguous chain is rejected",
          any("not contiguous" in p for p in pr.checkpoint_chain_problems(
              ds("scaffold", [{"from": "init", "to": "design", "confirmed_by": "o"},
                              {"from": "plan", "to": "scaffold", "confirmed_by": "o"}]), wf)), failures)
    check("a human-gated move without confirmed_by is rejected",
          any("confirmed_by" in p for p in pr.checkpoint_chain_problems(
              ds("design", [{"from": "init", "to": "design"}]), wf)), failures)
    check("a phase that is not the chain's end is rejected",
          any("ends at" in p for p in pr.checkpoint_chain_problems(ds("scaffold", legal_chain), wf)),
          failures)
    check("a recorded failing gate_result is rejected",
          any("may not be taken" in p for p in pr.checkpoint_chain_problems(
              ds("design", [{"from": "init", "to": "design", "confirmed_by": "o",
                             "gate_results": {"manifest-valid": "FAIL"}}]), wf)), failures)

    # --- ADR-0020 / #236: `refactor` is a deprecated alias of the renamed `migrate` phase. A legacy
    #     manifest still recording it keeps working — canonicalized in current_phase and the chain
    #     check, and surfaced by legacy_phase_aliases for the CLI deprecation warning. ---
    check("canonical_phase maps the deprecated refactor alias to migrate",
          pr.canonical_phase("refactor") == "migrate", failures)
    check("canonical_phase leaves a canonical phase unchanged",
          pr.canonical_phase("audit") == "audit", failures)
    check("current_phase canonicalizes a legacy refactor manifest to migrate",
          pr.current_phase({"delivery_state": {"phase": "refactor"}}) == "migrate", failures)
    legacy_migrate_chain = [
        {"from": "init", "to": "design", "confirmed_by": "o",
         "gate_results": {"manifest-valid": "OK"}},
        {"from": "design", "to": "plan", "confirmed_by": "o",
         "gate_results": {"rfc-approved": "OK"}},
        {"from": "plan", "to": "scaffold", "confirmed_by": "o",
         "gate_results": {"roadmap-covers-rfcs": "OK"}},
        {"from": "scaffold", "to": "audit"},
        {"from": "audit", "to": "refactor", "confirmed_by": "o",
         "gate_results": {"risk-register-present": "manual",
                          "traceability-lint": "OK"}}]
    check("a legacy chain into `refactor` validates against the renamed `migrate` state",
          pr.checkpoint_chain_problems(ds("refactor", legacy_migrate_chain), wf) == [], failures)
    check("legacy_phase_aliases surfaces the deprecated phase for a warning",
          pr.legacy_phase_aliases(ds("refactor", legacy_migrate_chain)) == ["refactor"], failures)
    canonical_migrate_chain = legacy_migrate_chain[:-1] + [
        {"from": "audit", "to": "migrate", "confirmed_by": "o"}]
    check("legacy_phase_aliases is empty for a canonical manifest",
          pr.legacy_phase_aliases(ds("migrate", canonical_migrate_chain)) == [], failures)

    # --- #213: report_propose evaluates the transition's gates LIVE via an INJECTED evaluator
    #     (so the engine needs no eados import) and records the marks in the emitted checkpoint's
    #     gate_results; a not-OK/manual mark warns NOT READY; no evaluator = no gate_results ---
    with tempfile.TemporaryDirectory() as d:
        mpath = os.path.join(d, "project.yaml")
        with open(mpath, "w", encoding="utf-8") as fh:
            fh.write("delivery_state:\n  phase: init\n  checkpoints: []\n"
                     "  refs: { rfcs: [], milestones: [] }\n")
        out = io.StringIO()
        rc = pr.report_propose(mpath, "design", out=out,
                               evaluate=lambda gates, m, ctx: {g: "OK" for g in gates})
        text = out.getvalue()
        check("report_propose exits 0 for a legal move", rc == 0, failures)
        check("the emitted checkpoint records the live gate_results",
              "gate_results: { manifest-valid: OK }" in text, failures)
        check("an all-OK move prints no NOT READY", "NOT READY" not in text, failures)

        out2 = io.StringIO()
        pr.report_propose(mpath, "design", out=out2,
                          evaluate=lambda gates, m, ctx: {g: "needs-input" for g in gates})
        check("a not-OK/manual gate marks the move NOT READY",
              "NOT READY" in out2.getvalue() and "manifest-valid=needs-input" in out2.getvalue(),
              failures)

        out3 = io.StringIO()
        pr.report_propose(mpath, "design", out=out3)   # no evaluator injected
        check("without an evaluator the checkpoint carries no gate_results (unchanged behavior)",
              "gate_results" not in out3.getvalue(), failures)

    # --- #214: report_propose surfaces the read rev, bumps it in the emit, and --expect-rev refuses
    #     a stale write (another session moved the manifest since it was read) ---
    with tempfile.TemporaryDirectory() as d:
        mpath = os.path.join(d, "project.yaml")
        with open(mpath, "w", encoding="utf-8") as fh:
            fh.write("manifest_rev: 2\ndelivery_state:\n  phase: init\n  checkpoints: []\n"
                     "  refs: { rfcs: [], milestones: [] }\n")
        out = io.StringIO()
        rc = pr.report_propose(mpath, "design", out=out, expect_rev=2)
        text = out.getvalue()
        check("a matching --expect-rev proceeds (exit 0)", rc == 0, failures)
        check("report_propose surfaces the read rev", "read at manifest_rev 2" in text, failures)
        check("the emit bumps manifest_rev to rev+1", "manifest_rev: 3" in text, failures)
        out2 = io.StringIO()
        rc2 = pr.report_propose(mpath, "design", out=out2, expect_rev=1)
        check("a stale --expect-rev is refused (CONFLICT, exit 1)",
              rc2 == 1 and "CONFLICT" in out2.getvalue(), failures)
        legacy = os.path.join(d, "legacy.yaml")
        with open(legacy, "w", encoding="utf-8") as fh:
            fh.write("delivery_state:\n  phase: init\n  checkpoints: []\n"
                     "  refs: { rfcs: [], milestones: [] }\n")
        out3b = io.StringIO()
        check("a legacy manifest (no manifest_rev) reads as rev 0 and matches --expect-rev 0",
              pr.report_propose(legacy, "design", out=out3b, expect_rev=0) == 0, failures)

    # --- #221: runtime invariants re-grounded at a phase boundary, DERIVED from the specs (never a
    #     hardcoded rule). The acting role comes from the workflow, the terminal decider + ownership
    #     from authority, one-PR + who-merges from git; a fake authority terminus flows through. ---
    authority, gitspec = pr.load_authority(), pr.load_git()
    check("terminal_decider reads the authority escalation terminus (human-owner)",
          pr.terminal_decider(authority) == "human-owner", failures)
    check("phase_role reads the workflow state->role map",
          pr.phase_role(wf, "design") == "tech-lead"
          and pr.phase_role(wf, "init") == "enterprise-architect", failures)

    t_hd = pr.propose_transition(wf, "init", "design")            # a human-gated move
    inv = pr.phase_invariants(wf, authority, gitspec, "design", t_hd)
    joined = " | ".join(inv)
    check("preamble names the target phase's owning role (workflow + authority)", "tech-lead" in joined,
          failures)
    check("preamble flags a human-gated move as human-gated",
          any("human-gated" in ln for ln in inv), failures)
    check("preamble derives the terminal gate from authority (human-owner)", "human-owner" in joined,
          failures)
    check("preamble derives one-PR + human-merge from the git spec",
          any("one PR at a time" in ln and "merges" in ln for ln in inv), failures)
    check("preamble cites English-on-disk (AGENTS.md §2)", "AGENTS.md" in joined, failures)

    t_auto = pr.propose_transition(wf, "scaffold", "audit")       # a non-human-gated move
    inv_auto = pr.phase_invariants(wf, authority, gitspec, "audit", t_auto)
    check("a non-human-gated move is framed automatic, not human-gated",
          any("automatic" in ln for ln in inv_auto)
          and not any("is human-gated" in ln for ln in inv_auto), failures)

    fake_auth = {"roles": [], "escalation": [{"level": 1, "decider": "council-of-elders"}]}
    check("the terminal-gate line is DERIVED (a fake authority terminus flows through, nothing hardcoded)",
          any("council-of-elders" in ln
              for ln in pr.phase_invariants(wf, fake_auth, gitspec, "design", t_hd)), failures)

    # --- #280: the re-grounding preamble re-reads the interaction contract (the ADR-0022 *re-ground*
    #     tier), DERIVED — the confidence vocabulary comes from the spec, never a hardcoded string. ---
    interaction = pr.load_interaction()
    inv_ix = pr.phase_invariants(wf, authority, gitspec, "design", t_hd, interaction)
    check("with the interaction spec, the preamble re-reads the interaction contract (AGENTS.md §10)",
          any("interaction contract" in ln and "AGENTS.md §10" in ln for ln in inv_ix), failures)
    check("the interaction line carries the confidence tags DERIVED from the spec",
          any("certain" in ln and "guessing" in ln
              for ln in inv_ix if "interaction contract" in ln), failures)
    check("without the interaction spec, the interaction line is dropped (degrades, never crashes)",
          not any("interaction contract" in ln for ln in inv), failures)
    fake_ix = {"confidence": {"levels": ["sure", "hunch"]}}
    check("the confidence vocabulary is DERIVED (a fake spec's levels flow through)",
          any("sure/hunch" in ln
              for ln in pr.phase_invariants(wf, authority, gitspec, "design", t_hd, fake_ix)), failures)

    # --- #297: the preamble also re-states the advisory model-routing posture, DERIVED — the tiers
    #     come from the spec, and it never tells the agent to switch its own session model. ---
    routing = pr.load_routing()
    inv_rt = pr.phase_invariants(wf, authority, gitspec, "design", t_hd, interaction, routing)
    check("with the routing spec, the preamble re-states the routing posture (ADR-0017)",
          any("model routing" in ln and "ADR-0017" in ln for ln in inv_rt), failures)
    check("the routing line names the checkpoint and forbids a session switch",
          any("route_advice.py --check" in ln and "never switch the session model" in ln
              for ln in inv_rt if "model routing" in ln), failures)
    check("without the routing spec, the routing line is dropped (degrades, never crashes)",
          not any("model routing" in ln for ln in inv), failures)
    fake_rt = {"tiers": ["cheap", "pricey"]}
    check("the tier vocabulary is DERIVED (a fake spec's tiers flow through)",
          any("cheap/pricey" in ln for ln in
              pr.phase_invariants(wf, authority, gitspec, "design", t_hd, interaction, fake_rt)), failures)

    # --- #221: the long-run reminder fires only past the checkpoint-depth threshold ---
    check("long_run_reminder is empty below the threshold",
          pr.long_run_reminder({"delivery_state": {"checkpoints": []}}, authority, gitspec) == [], failures)
    deep = {"delivery_state": {"checkpoints": [{"from": "init", "to": "design"},
                                               {"from": "design", "to": "plan"},
                                               {"from": "plan", "to": "scaffold"}]}}
    rem = pr.long_run_reminder(deep, authority, gitspec)
    check("long_run_reminder fires at/above the threshold", len(rem) >= 1, failures)
    check("the reminder re-states the human terminal gate",
          any("terminal gate" in ln for ln in rem), failures)

    # --- #221: report() and report_propose() actually emit the re-grounding block ---
    with tempfile.TemporaryDirectory() as d:
        mpath = os.path.join(d, "project.yaml")
        with open(mpath, "w", encoding="utf-8") as fh:
            fh.write("delivery_state:\n  phase: init\n  checkpoints: []\n"
                     "  refs: { rfcs: [], milestones: [] }\n")
        rout = io.StringIO()
        pr.report(mpath, out=rout)
        check("report() emits the runtime-invariants block, derived from the specs",
              "runtime invariants" in rout.getvalue() and "human-owner" in rout.getvalue(), failures)
        check("report() re-reads the interaction contract in the preamble (#280)",
              "interaction contract" in rout.getvalue() and "AGENTS.md §10" in rout.getvalue(), failures)
        check("report() re-states the model-routing posture in the preamble (#297)",
              "model routing" in rout.getvalue() and "route_advice.py --check" in rout.getvalue(),
              failures)
        pout = io.StringIO()
        pr.report_propose(mpath, "design", out=pout)
        check("report_propose() emits the re-grounding preamble for the proposed move",
              "runtime invariants" in pout.getvalue() and "tech-lead" in pout.getvalue(), failures)
        check("report_propose() re-reads the interaction contract in the preamble (#280)",
              "interaction contract" in pout.getvalue(), failures)
        check("report_propose() re-states the model-routing posture (#297)",
              "model routing" in pout.getvalue(), failures)

    if failures:
        print("test-phase-runner: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-phase-runner: OK — legal transitions, terminal phase, and workflow integrity hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
