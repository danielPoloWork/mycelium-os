#!/usr/bin/env python3
"""Tests for the cross-spec-consistency gate (eados_lint check #11) — referential integrity
ACROSS the delivery-OS specs. Pure-function tests on cross_spec_problems() with in-memory
fixtures: a complete clean spec set has no problems, and every kind of dangling cross-reference
(role / state / gate / overlay / level / domain / cross-cutting git gate / contribution decider +
disposition / interaction escalation ladder) is caught. Dependency-free.

    python .eados-core/tools/tests/test_cross_spec.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as el  # noqa: E402  (the module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def clean():
    """A minimal but COMPLETE spec set in which every cross-reference resolves."""
    authority = {
        "roles": [{"name": "tech-lead"}, {"name": "producer"}, {"name": "product-manager"},
                  {"name": "security-auditor"}, {"name": "enterprise-architect"}],
        "ownership_map": [{"glob": "src/**", "role": "tech-lead", "action": "approve"}],
        "escalation": [{"level": 1, "decider": "tech-lead"},
                       {"level": 2, "decider": "human-owner"}],   # terminal, not a role
    }
    workflow = {
        "states": [{"id": "design", "role": "tech-lead"}, {"id": "plan", "role": "producer"},
                   {"id": "scaffold", "role": "enterprise-architect"}],
        "transitions": [{"from": "design", "to": "plan", "entry_gates": ["rfc-approved"]},
                        {"from": "plan", "to": "scaffold", "entry_gates": ["roadmap-covers-rfcs"]}],
        "gates": [{"id": "rfc-approved", "required_for": ["plan"]},
                  {"id": "roadmap-covers-rfcs", "required_for": ["scaffold"]},
                  {"id": "hardware-budget", "required_for": []}],   # the game overlay's gate (#165)
        "domain_overlays": {"software": {}, "game": {"add_gates": ["hardware-budget"]}},
    }
    plan = {"roles": {"proposes": "product-manager", "sizes": "tech-lead",
                      "reconciles": "producer"}, "gate": "roadmap-covers-rfcs"}
    rfc = {"author_roles": ["tech-lead"], "reviewer_roles": ["enterprise-architect"],
           "approver_role": "tech-lead", "gate": "rfc-approved"}
    risk = {"levels": ["low", "medium", "high"], "mandatory_gate_level": "high",
            "domain_overrides": {"game": {"mandatory_gate_level": "high"}}}
    domains = {
        "software.yaml": {"domain": "software", "roles": ["tech-lead", "producer"],
                          "role_labels": {"product-manager": "product-manager"},
                          "workflow_overlay": "software"},
        "game.yaml": {"domain": "game", "roles": ["tech-lead"], "workflow_overlay": "game"},
    }
    return authority, workflow, plan, rfc, risk, domains


def main():
    failures = []

    check("a complete clean spec set has no cross-spec problems",
          el.cross_spec_problems(*clean()) == [], failures)

    def caught(mutate, needle):
        """True if mutating a fresh clean set produces a problem mentioning `needle`."""
        a, w, p, r, rk, d = clean()
        mutate(a, w, p, r, rk, d)
        return any(needle in prob for prob in el.cross_spec_problems(a, w, p, r, rk, d))

    # The three failure modes the review named explicitly.
    check("a misspelled plan negotiation role is caught (tech-led)",
          caught(lambda a, w, p, r, rk, d: p["roles"].__setitem__("sizes", "tech-led"),
                 "tech-led"), failures)
    check("a phantom gate in a transition is caught",
          caught(lambda a, w, p, r, rk, d: w["transitions"][0].__setitem__(
              "entry_gates", ["ghost-gate"]), "ghost-gate"), failures)
    check("a dangling domain workflow_overlay is caught",
          caught(lambda a, w, p, r, rk, d: d["game.yaml"].__setitem__(
              "workflow_overlay", "nope"), "nope"), failures)

    # Every other cross-reference kind.
    check("an unknown transition target state is caught",
          caught(lambda a, w, p, r, rk, d: w["transitions"][0].__setitem__("to", "limbo"),
                 "limbo"), failures)
    check("an unknown state-owner role is caught",
          caught(lambda a, w, p, r, rk, d: w["states"][0].__setitem__("role", "ghost-role"),
                 "ghost-role"), failures)
    check("an unknown gate.required_for state is caught",
          caught(lambda a, w, p, r, rk, d: w["gates"][0].__setitem__("required_for", ["nowhere"]),
                 "nowhere"), failures)
    check("an unknown ownership_map role is caught",
          caught(lambda a, w, p, r, rk, d: w and a["ownership_map"][0].__setitem__("role", "nobody"),
                 "nobody"), failures)
    check("an unknown escalation decider is caught",
          caught(lambda a, w, p, r, rk, d: a["escalation"][0].__setitem__("decider", "wizard"),
                 "wizard"), failures)
    check("an unknown rfc approver role is caught",
          caught(lambda a, w, p, r, rk, d: r.__setitem__("approver_role", "phantom"),
                 "phantom"), failures)
    check("an unknown risk gate level is caught",
          caught(lambda a, w, p, r, rk, d: rk.__setitem__("mandatory_gate_level", "spicy"),
                 "spicy"), failures)
    check("a domain role missing from the authority model is caught",
          caught(lambda a, w, p, r, rk, d: d["software.yaml"].__setitem__(
              "roles", ["tech-lead", "ghost"]), "ghost"), failures)

    # #165: an overlay add_gates id is a REFERENCE into the gate registry, never a definition.
    # With the registry entry present (clean()), using it in a transition is fine; a bare id
    # with no entry — the hole the audit found codified here as a feature — is now caught.
    a, w, p, r, rk, d = clean()
    w["transitions"][1]["entry_gates"] = ["hardware-budget"]   # registry-backed overlay gate
    check("a registry-backed overlay gate in a transition is accepted",
          el.cross_spec_problems(a, w, p, r, rk, d) == [], failures)
    check("an overlay add_gates id with no registry entry is caught",
          caught(lambda a, w, p, r, rk, d: w["domain_overlays"]["game"].__setitem__(
              "add_gates", ["phantom-budget"]), "phantom-budget"), failures)

    # 6.8: a cross-cutting (non-phase) gate referenced by git.yaml resolves to the gate registry —
    # the scope deferred from #62. traceability-lint is registered with required_for: [].
    a, w, p, r, rk, d = clean()
    w["gates"].append({"id": "traceability-lint", "required_for": []})
    check("a resolved cross-cutting git gate (traceability-lint) is accepted",
          el.cross_spec_problems(a, w, p, r, rk, d, {"traceability": {"gate": "traceability-lint"}})
          == [], failures)
    check("a typo'd cross-cutting git gate is caught",
          any("tracability-lint" in prob for prob in el.cross_spec_problems(
              a, w, p, r, rk, d, {"traceability": {"gate": "tracability-lint"}})), failures)
    check("git is optional — a None git yields no problems",
          el.cross_spec_problems(*clean(), None) == [], failures)

    # M8 8.5: the cross-cutting contribution-review gate referenced from git.pr.review_gate resolves.
    a, w, p, r, rk, d = clean()
    w["gates"].append({"id": "contribution-review", "required_for": []})
    check("a resolved git.pr.review_gate is accepted",
          el.cross_spec_problems(a, w, p, r, rk, d, {"pr": {"review_gate": "contribution-review"}})
          == [], failures)
    check("a typo'd git.pr.review_gate is caught",
          any("review_gate" in prob for prob in el.cross_spec_problems(
              a, w, p, r, rk, d, {"pr": {"review_gate": "contribution-revue"}})), failures)

    # M8 8.1: the inbound-contribution policy's escalation decider resolves to a role / the human
    # terminal, and its escalation disposition is one the policy itself declares.
    def contrib(decider="human-owner", disposition="needs-maintainer"):
        return {"escalation": {"on": "ext-touches-owned", "decider": decider,
                               "disposition": disposition},
                "dispositions": [{"id": "needs-maintainer"}, {"id": "close-with-thanks"}]}
    check("a clean contribution policy has no problems",
          el.cross_spec_problems(*clean(), None, contrib()) == [], failures)
    check("a role decider (not just the human terminal) resolves",
          el.cross_spec_problems(*clean(), None, contrib(decider="enterprise-architect")) == [],
          failures)
    check("an unknown contribution escalation decider is caught",
          any("decider" in prob for prob in
              el.cross_spec_problems(*clean(), None, contrib(decider="nobody-role"))), failures)
    check("an escalation disposition the policy does not declare is caught",
          any("disposition" in prob for prob in
              el.cross_spec_problems(*clean(), None, contrib(disposition="made-up"))), failures)
    check("contribution is optional — a None yields no problems",
          el.cross_spec_problems(*clean(), None, None) == [], failures)

    # M17 17.3 (#279): the interaction spec's conversation-external escalation pointer resolves to
    # the authority spec's escalation ladder (data ref, precedent: the git gate-ref above).
    ladder = {"dissent": {"escalation_ladder": "authority"}}
    check("a resolved interaction escalation_ladder is accepted",
          el.cross_spec_problems(*clean(), None, None, ladder) == [], failures)
    check("a typo'd interaction escalation_ladder is caught",
          any("escalation_ladder" in prob and "authoritee" in prob for prob in
              el.cross_spec_problems(*clean(), None, None,
                                     {"dissent": {"escalation_ladder": "authoritee"}})), failures)
    a, w, p, r, rk, d = clean()
    a["escalation"] = []   # the named spec exists but declares no ladder to resolve to
    check("escalation_ladder naming authority with no ladder is caught",
          any("no escalation ladder" in prob for prob in
              el.cross_spec_problems(a, w, p, r, rk, d, None, None, ladder)), failures)
    check("interaction is optional — a None yields no problems",
          el.cross_spec_problems(*clean(), None, None, None) == [], failures)
    check("interaction without the pointer yields no problems",
          el.cross_spec_problems(*clean(), None, None, {"dissent": {}}) == [], failures)

    # Robustness: a missing/unparseable core spec is left to os-spec-completeness, not double-reported.
    check("a None workflow yields no problems (deferred to os-spec-completeness)",
          el.cross_spec_problems(clean()[0], None) == [], failures)

    if failures:
        print("test-cross-spec: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-cross-spec: OK -- cross-spec references resolve; every dangling kind is caught.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
