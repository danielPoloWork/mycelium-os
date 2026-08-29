#!/usr/bin/env python3
"""Tests for route_advice (M16 16.2) — the routing-policy evaluator core, on an in-memory fixture
spec AND the real shipped `os/routing/routing.yaml`. Exercises monotonic escalation (floor, raises,
order-independence), the loud rejection of a spec that breaks its own `_schema.md` invariants
(unknown tier/effort/flag, a host missing a tier), host/catalog resolution, effort-alias
normalization, and the advisory boundary. The `gh` shell is not touched. Dependency-free.

    python .eados-core/tools/tests/test_route_advice.py
"""

import contextlib
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import route_advice as ra        # noqa: E402  (the module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def fixture_spec():
    """A minimal well-formed spec, structurally parallel to the shipped instance."""
    return {
        "version": 1,
        "tiers": ["fast", "standard", "frontier-reasoning"],
        "efforts": ["low", "medium", "high", "extra", "max"],
        "flags": {"sets-pattern": "first of its class", "decision-heavy": "the decision is the deliverable"},
        "defaults": {"tier": "fast", "effort": "low"},
        "protected": ["label:security"],
        "selection": {"objective": "quality-first", "prefer": ["lowest_cost"]},
        "rules": [
            {"id": "sev-med", "when": ["label:severity:medium"],
             "min_tier": "standard", "min_effort": "medium", "why": "significant gap"},
            {"id": "sev-high", "when": ["label:severity:high"],
             "min_tier": "standard", "min_effort": "high", "why": "core guarantee"},
            {"id": "adr", "when": ["label:adr"],
             "min_tier": "frontier-reasoning", "min_effort": "high", "why": "decision-heavy by definition"},
            {"id": "pattern", "when": ["flag:sets-pattern"],
             "min_tier": "frontier-reasoning", "min_effort": "high", "why": "fixes the template"},
            {"id": "foundational", "when": ["flag:decision-heavy", "label:severity:high"],
             "min_tier": "frontier-reasoning", "min_effort": "max", "why": "most expensive artifact"},
        ],
        # Schema v2 (ADR-0024): providers say what exists and what it CLEARS; hosts say what they
        # reach. The fixture keeps the same resolved names as the v1 fixture did, so every
        # assertion below still reads against the values it was written for.
        "catalog": {
            "as_of": "2026-07-09",
            "providers": [
                {"id": "vendor-a", "models": [
                    {"id": "fable-5", "name": "Fable 5", "meets_tier": "frontier-reasoning",
                     "assessed": True},
                    {"id": "opus-4-8", "name": "Opus 4.8", "meets_tier": "standard",
                     "assessed": True},
                    {"id": "sonnet-5", "name": "Sonnet 5", "meets_tier": "fast", "assessed": True},
                    # Unassessed: reachable, but it must never be selected for any tier.
                    {"id": "unproven", "name": "Unproven", "assessed": False},
                ]},
                {"id": "vendor-b", "models": [
                    {"id": "x-large", "name": "X-large", "meets_tier": "frontier-reasoning",
                     "assessed": True},
                    {"id": "x-mid", "name": "X-mid", "meets_tier": "standard", "assessed": True},
                    {"id": "x-small", "name": "X-small", "meets_tier": "fast", "assessed": True},
                ]},
            ],
            "hosts": [
                {"id": "claude-code", "providers": ["vendor-a"],
                 "effort_aliases": {"ultracode": "max"}},
                {"id": "other-host", "providers": ["vendor-b"]},
            ],
        },
        "examples": {"verdicts": ["fast", "standard", "frontier-reasoning"], "cases": []},
    }


def main():
    failures = []
    spec = fixture_spec()

    # --- the fixture and the SHIPPED spec both satisfy the _schema invariants ---
    check("fixture spec is invariant-clean", ra.spec_problems(spec) == [], failures)
    shipped = ra.load_routing()          # raises (test fails loudly) if the shipped spec broke
    check("shipped routing.yaml loads under loud rejection", isinstance(shipped, dict), failures)

    # --- monotonic escalation: floor, single raise, max-of-matches, order-independence ---
    adv = ra.advise([], spec)
    check("no signals -> the floor (fast/low)",
          (adv["tier"], adv["effort"]) == ("fast", "low"), failures)
    # 19.4: no host resolved -> no model name. The tier/effort half is unaffected.
    check("advise without a host yields no model (no silent default)",
          adv["model"] is None and adv["host"] is None, failures)
    check("advise WITH a host names that host's model",
          ra.advise([], spec, host="claude-code")["model"] == "Sonnet 5", failures)
    check("no-match advice reports the floor", adv["matched"] == [], failures)

    adv = ra.advise(ra.signals_for(["severity:medium"], [], spec), spec)
    check("severity:medium -> standard/medium",
          (adv["tier"], adv["effort"]) == ("standard", "medium"), failures)

    adv = ra.advise(ra.signals_for(["adr", "severity:high"], [], spec), spec)
    check("adr + severity:high -> max of matches (frontier-reasoning/high)",
          (adv["tier"], adv["effort"]) == ("frontier-reasoning", "high"), failures)
    check("both rules are reported as matched",
          {m["id"] for m in adv["matched"]} == {"sev-high", "adr"}, failures)

    fwd = ra.advise(ra.signals_for(["adr", "severity:high"], ["decision-heavy"], spec), spec)
    rev = ra.advise(list(reversed(ra.signals_for(["adr", "severity:high"], ["decision-heavy"], spec))), spec)
    check("decision-heavy + severity:high -> the foundational max", fwd["effort"] == "max", failures)
    check("signal order never changes the advice",
          (fwd["tier"], fwd["effort"]) == (rev["tier"], rev["effort"]), failures)

    adv = ra.advise(ra.signals_for([], ["sets-pattern"], spec), spec)
    check("sets-pattern alone -> frontier-reasoning/high",
          (adv["tier"], adv["effort"]) == ("frontier-reasoning", "high"), failures)

    adv = ra.advise(ra.signals_for(["documentation", "severity:low"], [], spec), spec)
    check("unknown labels match nothing and stay on the floor",
          (adv["tier"], adv["effort"]) == ("fast", "low"), failures)

    check("advice states the advisory boundary", "advisory" in adv["boundary"], failures)
    check("advice carries the catalog date", adv["catalog_as_of"] == "2026-07-09", failures)

    # --- loud rejection: signals ---
    try:
        ra.signals_for([], ["sets-patern"], spec)   # typo'd flag
        failures.append("a typo'd asserted flag must be rejected")
    except ValueError:
        pass

    # --- loud rejection: a spec that breaks its own invariants ---
    def broken(mutate):
        s = fixture_spec()
        mutate(s)
        return ra.spec_problems(s)

    def broken_with(base, mutate):
        """`broken`, but starting from an already-extended spec rather than the bare fixture."""
        import copy
        s = copy.deepcopy(base)
        mutate(s)
        return ra.spec_problems(s)

    check("a rule with an unknown min_tier is a problem",
          broken(lambda s: s["rules"][0].update(min_tier="huge")), failures)
    check("a rule with an unknown min_effort is a problem",
          broken(lambda s: s["rules"][0].update(min_effort="extreme")), failures)
    check("a rule referencing an undeclared flag is a problem",
          broken(lambda s: s["rules"][0].update(when=["flag:nope"])), failures)
    check("a malformed signal is a problem",
          broken(lambda s: s["rules"][0].update(when=["severity:high"])), failures)
    check("bad defaults are a problem",
          broken(lambda s: s["defaults"].update(tier="huge")), failures)
    # --- schema v2 referential integrity (ADR-0024 D1/D6) ---
    check("a host reaching an unknown provider is a problem",
          broken(lambda s: s["catalog"]["hosts"][0].update(providers=["ghost-vendor"])), failures)
    check("a host that reaches nothing is a problem",
          broken(lambda s: s["catalog"]["hosts"][0].update(providers=[])), failures)
    check("a model claiming an unknown tier is a problem",
          broken(lambda s: s["catalog"]["providers"][0]["models"][0].update(meets_tier="huge")),
          failures)
    check("an assessed model with no meets_tier is a problem",
          broken(lambda s: s["catalog"]["providers"][0]["models"][0].pop("meets_tier")), failures)
    # The #326 guard: an unverified capability claim must be rejected, not quietly trusted.
    check("an UNASSESSED model claiming a tier is a problem",
          broken(lambda s: s["catalog"]["providers"][0]["models"][3].update(
              meets_tier="frontier-reasoning")), failures)
    check("a model with an unknown max_effort is a problem",
          broken(lambda s: s["catalog"]["providers"][0]["models"][0].update(max_effort="extreme")),
          failures)
    check("an unknown selection criterion is a problem",
          broken(lambda s: s.update(selection={"prefer": ["fastest"]})), failures)
    check("a protected signal referencing an undeclared flag is a problem",
          broken(lambda s: s.update(protected=["flag:nope"])), failures)
    # Both carry the cost invariant, and both fail OPEN when absent — so absence must be a problem.
    check("a missing `protected` is a problem", broken(lambda s: s.pop("protected")), failures)
    check("a missing `selection` is a problem", broken(lambda s: s.pop("selection")), failures)
    check("an alias to an unknown effort is a problem",
          broken(lambda s: s["catalog"]["hosts"][0]["effort_aliases"].update(mega="extreme")), failures)
    check("an examples verdict outside `tiers` is a problem",
          broken(lambda s: s["examples"]["verdicts"].append("huge")), failures)
    check("a missing catalog date is a problem",
          broken(lambda s: s["catalog"].pop("as_of")), failures)
    check("a rule that can raise nothing is a problem",
          broken(lambda s: [s["rules"][0].pop("min_tier"), s["rules"][0].pop("min_effort")]), failures)

    # --- 19.3 phase 2: SELECTION (ADR-0024 D2/D3) ------------------------------------------
    tier_rank = {t: i for i, t in enumerate(spec["tiers"])}

    # Cheapest-that-clears: the floor admits every tier at or above it, and with no cost recorded
    # the tier ladder decides — so the answer is the LEAST capable model that still clears it.
    adv = ra.advise([], spec, host="claude-code")                 # floor = fast/low
    check("selection takes the least capable model that clears the floor",
          adv["model"] == "Sonnet 5" and adv["provider"] == "vendor-a", failures)
    check("the runners-up that also cleared are reported",
          [a["model"] for a in adv["alternatives"]] == ["Opus 4.8", "Fable 5"], failures)

    # Recorded costs take over from the ladder — but only among models that ALREADY clear.
    costed = fixture_spec()
    for m, c in zip(costed["catalog"]["providers"][0]["models"], (1, 9, 5)):
        m["relative_cost"] = c                                    # fable=1, opus=9, sonnet=5
    adv = ra.advise([], costed, host="claude-code")
    check("with full cost data the cheapest clearing model wins, not the lowest tier",
          adv["model"] == "Fable 5" and adv["relative_cost"] == 1, failures)
    # Partial cost data must NOT rank: a recorded 9 must not outrank an unknown.
    partial = fixture_spec()
    partial["catalog"]["providers"][0]["models"][1]["relative_cost"] = 9
    check("partial cost data falls back to the ladder rather than ranking unfairly",
          ra.advise([], partial, host="claude-code")["model"] == "Sonnet 5", failures)

    # THE invariant: no signal combination may resolve a model below its own floor.
    every_label = ["severity:medium", "severity:high", "adr", "security"]
    every_flag = ["sets-pattern", "decision-heavy"]
    combos = []
    for i in range(1 << len(every_label)):
        for j in range(1 << len(every_flag)):
            combos.append(([l for k, l in enumerate(every_label) if i >> k & 1],
                           [f for k, f in enumerate(every_flag) if j >> k & 1]))
    below = []
    for labels, flags in combos:
        a = ra.advise(ra.signals_for(labels, flags, spec), spec, host="claude-code")
        if a["model"] is None:
            continue
        got = next((m for p in spec["catalog"]["providers"] for m in p["models"]
                    if m.get("name") == a["model"]), None)
        if got is None or tier_rank[got["meets_tier"]] < tier_rank[a["tier"]]:
            below.append((labels, flags, a["tier"], a["model"]))
    check(f"no signal combination resolves below its floor ({len(combos)} combinations)",
          not below, failures)
    check("every alternative offered also clears the floor",
          all(tier_rank[alt["meets_tier"]] >= tier_rank[a["tier"]]
              for labels, flags in combos
              for a in [ra.advise(ra.signals_for(labels, flags, spec), spec, host="claude-code")]
              for alt in a["alternatives"]), failures)

    # Protected signals are surfaced so the guarantee is visible, not merely true.
    prot = fixture_spec()
    prot["protected"] = ["label:adr"]
    adv = ra.advise(ra.signals_for(["adr"], [], prot), prot, host="claude-code")
    check("a protected signal is reported on the advice",
          adv["protected"] == ["label:adr"], failures)

    # An unassessed model is reachable but never selectable — the #326 guard, at resolution time.
    only_unproven = fixture_spec()
    only_unproven["catalog"]["providers"][0]["models"] = [
        {"id": "unproven", "name": "Unproven", "assessed": False}]
    adv = ra.advise([], only_unproven, host="claude-code")
    check("an unassessed model is never selected", adv["model"] is None, failures)
    check("an unresolvable model states WHY, and keeps the tier/effort advice",
          adv["unresolved_reason"] and adv["tier"] == "fast" and adv["effort"] == "low", failures)
    check("the unresolved reason names the floor and the host",
          "fast/low" in adv["unresolved_reason"] and "claude-code" in adv["unresolved_reason"],
          failures)

    # An effort ceiling excludes a model that cannot be driven that hard.
    capped = fixture_spec()
    capped["catalog"]["providers"][0]["models"][0]["max_effort"] = "low"   # Fable 5 capped
    adv = ra.advise(ra.signals_for(["adr", "severity:high"], ["decision-heavy"], capped), capped,
                    host="claude-code")
    check("a model whose max_effort is below the floor is not a candidate",
          adv["model"] is None and adv["effort"] == "max", failures)

    # Determinism: reordering the catalog must not change the answer.
    shuffled = fixture_spec()
    shuffled["catalog"]["providers"][0]["models"].reverse()
    check("reordering the catalog does not change the resolved model",
          ra.advise([], shuffled, host="claude-code")["model"]
          == ra.advise([], spec, host="claude-code")["model"], failures)

    # --- 19.4 host detection: the precedence ladder (ADR-0024 D4) ---------------------------
    det = fixture_spec()
    det["catalog"]["hosts"][0]["detect"] = [{"env": "FIXTURE_CLAUDE"},
                                            {"env": "FIXTURE_AGENT", "matches": "^cc-"}]
    det["catalog"]["hosts"][1]["detect"] = [{"env": "FIXTURE_OTHER"}]

    r = ra.resolve_host(det, environ={"FIXTURE_CLAUDE": "1"})
    check("evidence resolves the host", r["host"] == "claude-code" and r["source"] == "evidence",
          failures)
    check("the evidence names what was actually observed",
          "FIXTURE_CLAUDE" in r["evidence"], failures)
    r = ra.resolve_host(det, environ={"FIXTURE_AGENT": "cc-2"})
    check("a value-matching marker resolves", r["host"] == "claude-code", failures)
    check("a marker whose value does NOT match is not a hit",
          ra.resolve_host(det, environ={"FIXTURE_AGENT": "other"})["host"] is None, failures)

    # THE removal: no environment, no flag, no manifest -> unresolved, never hosts[0].
    r = ra.resolve_host(det, environ={})
    check("an empty environment resolves to UNRESOLVED, never the first catalog host",
          r["host"] is None and r["source"] == "unresolved", failures)
    check("_host_entry has no default — None means unresolved, not 'the first host'",
          ra._host_entry(det, None) is None, failures)

    # Ambiguity is stated, not settled by picking one.
    r = ra.resolve_host(det, environ={"FIXTURE_CLAUDE": "1", "FIXTURE_OTHER": "1"})
    check("two matching hosts resolve to UNRESOLVED", r["host"] is None, failures)
    check("ambiguity names both candidates",
          "claude-code" in r["evidence"] and "other-host" in r["evidence"], failures)

    # Precedence: flag beats manifest beats evidence.
    env_both = {"FIXTURE_CLAUDE": "1"}
    check("explicit beats manifest and evidence",
          ra.resolve_host(det, explicit="other-host", manifest_host="claude-code",
                          environ=env_both)["host"] == "other-host", failures)
    check("manifest beats evidence",
          ra.resolve_host(det, manifest_host="other-host", environ=env_both)["host"]
          == "other-host", failures)
    try:
        ra.resolve_host(det, explicit="not-a-host")
        failures.append("a named host that does not exist must be rejected loudly")
    except ValueError:
        pass

    # An unresolved host keeps the whole tier/effort recommendation — only the NAME is lost.
    adv = ra.advise(ra.signals_for(["adr"], [], det), det, host=None)
    check("unresolved host still yields tier and effort",
          (adv["tier"], adv["effort"]) == ("frontier-reasoning", "high"), failures)
    check("unresolved host yields no model, and says why",
          adv["model"] is None and adv["host"] is None and adv["unresolved_reason"], failures)
    check("the reason points at the two explicit rungs",
          "--host" in adv["unresolved_reason"] and "routing.host" in adv["unresolved_reason"],
          failures)

    # --- 19.7 per-step routing: a third signal kind that can only ever RAISE ----------------
    stepped = fixture_spec()
    stepped["steps"] = {"design": "decide the shape", "test": "exercise it"}
    stepped["rules"].append({"id": "step-design", "when": ["step:design"],
                             "min_tier": "standard", "min_effort": "high", "why": "shape"})
    check("a step signal is accepted by the spec validator",
          ra.spec_problems(stepped) == [], failures)
    check("an undeclared step in a rule is a problem",
          broken_with(stepped, lambda s: s["rules"][-1].update(when=["step:nope"])), failures)
    try:
        ra.signals_for([], [], stepped, step="desgin")
        failures.append("a typo'd step must be rejected loudly, like a typo'd flag")
    except ValueError:
        pass

    # The point of per-step: one item, different steps, different routes.
    low = ["severity:low"]
    d = ra.advise(ra.signals_for(low, [], stepped, step="design"), stepped, host="claude-code")
    t = ra.advise(ra.signals_for(low, [], stepped, step="test"), stepped, host="claude-code")
    check("the design step of a cheap item earns more than its test step",
          (d["tier"], d["effort"]) == ("standard", "high")
          and (t["tier"], t["effort"]) == ("fast", "low"), failures)

    # THE invariant: a step may raise, never lower. Checked over every step against the no-step
    # baseline, for a protected item and a trivial one alike — a protected floor must survive even
    # the most mechanical step, which is where a "this step is cheap" shortcut would bite.
    tier_rank2 = {t_: i for i, t_ in enumerate(stepped["tiers"])}
    effort_rank2 = {e: i for i, e in enumerate(stepped["efforts"])}
    for labels in (["security", "severity:high"], ["severity:low"], []):
        base = ra.advise(ra.signals_for(labels, [], stepped), stepped, host="claude-code")
        for step in stepped["steps"]:
            a = ra.advise(ra.signals_for(labels, [], stepped, step=step), stepped,
                          host="claude-code")
            if (tier_rank2[a["tier"]] < tier_rank2[base["tier"]]
                    or effort_rank2[a["effort"]] < effort_rank2[base["effort"]]):
                failures.append(f"step '{step}' LOWERED the route for {labels}: "
                                f"{base['tier']}/{base['effort']} -> {a['tier']}/{a['effort']}")

    # The shipped policy declares the full step vocabulary and routes it.
    check("the shipped spec declares a step vocabulary",
          set(shipped.get("steps") or {}) >= {"design", "implement", "test", "review", "optimize"},
          failures)
    sec = ["security", "severity:high"]
    base = ra.advise(ra.signals_for(sec, [], shipped), shipped, host="claude-code")
    for step in shipped["steps"]:
        a = ra.advise(ra.signals_for(sec, [], shipped, step=step), shipped, host="claude-code")
        if (a["tier"], a["effort"]) != (base["tier"], base["effort"]):
            failures.append(f"shipped: a protected item changed route on step '{step}'")

    # --- host + effort-alias resolution ---
    adv = ra.advise([], spec, host="other-host")
    check("an explicit host resolves its own catalog", adv["model"] == "X-small", failures)
    try:
        ra.advise([], spec, host="unknown-host")
        failures.append("an unknown host must be rejected")
    except ValueError:
        pass
    # An alias is HOST vocabulary, so it needs a host — with none resolved there is nothing to
    # map it through, and 19.4 removed the silent default that used to supply one.
    check("a host alias maps to the OS scale (ultracode -> max)",
          ra.normalize_effort("ultracode", spec, host="claude-code") == "max", failures)
    try:
        ra.normalize_effort("ultracode", spec)
        failures.append("a host alias must not resolve without a host (no silent default)")
    except ValueError:
        pass
    check("an OS-scale effort passes through", ra.normalize_effort("high", spec) == "high", failures)
    try:
        ra.normalize_effort("mega", spec)
        failures.append("an unknown effort word must be rejected")
    except ValueError:
        pass

    # --- the shipped spec routes the ratified M16 anchor cases (plan-doc backfill table) ---
    adv = ra.advise(ra.signals_for(["adr", "severity:high"], ["decision-heavy"], shipped),
                    shipped, host="claude-code")
    check("shipped spec: the foundational ADR routes to frontier-reasoning/max",
          (adv["tier"], adv["effort"]) == ("frontier-reasoning", "max"), failures)
    adv = ra.advise(ra.signals_for(["documentation", "severity:low"], [], shipped),
                    shipped, host="claude-code")
    check("shipped spec: a small doc fix stays on the floor",
          (adv["tier"], adv["effort"]) == (shipped["defaults"]["tier"], shipped["defaults"]["effort"]),
          failures)
    adv = ra.advise(ra.signals_for(["security", "severity:medium"], [], shipped),
                    shipped, host="claude-code")
    check("shipped spec: the security surface routes to frontier-reasoning",
          adv["tier"] == "frontier-reasoning", failures)

    # --- formatting: the surfaces print what the human needs to overrule ---
    text = ra.format_advice(adv, heading="#241  audit sub-mode")
    check("formatted advice carries the heading", "#241" in text, failures)
    check("formatted advice names tier, effort, and model",
          all(s in text for s in ["tier=", "effort=", adv["model"]]), failures)
    check("formatted advice states the advisory boundary", "advisory" in text, failures)

    # --- the route checkpoint (#297): tier_of_model normalization ---
    check("model matches its own catalog name", ra.tier_of_model("Opus 4.8", spec, host="claude-code") == "standard", failures)
    check("normalization tolerates id form (claude-opus-4-8)",
          ra.tier_of_model("claude-opus-4-8", spec, host="claude-code") == "standard", failures)
    check("frontier model resolves", ra.tier_of_model("Fable 5", spec, host="claude-code") == "frontier-reasoning", failures)
    check("an off-catalog model resolves to no tier", ra.tier_of_model("gpt-4", spec, host="claude-code") is None, failures)
    check("an empty model resolves to no tier", ra.tier_of_model("", spec, host="claude-code") is None, failures)
    check("tier_of_model honors the host", ra.tier_of_model("X-mid", spec, host="other-host") == "standard",
          failures)

    # --- check_route: ok / mismatch (below+above) / unknown-model ---
    std = ra.advise(ra.signals_for(["severity:medium"], [], spec), spec,
                    host="claude-code")   # standard/medium
    ok = ra.check_route(std, "Opus 4.8", spec, host="claude-code")
    check("check_route OK when session tier == routed tier", ok["status"] == "ok", failures)
    check("OK carries no direction", ok["direction"] is None, failures)

    below = ra.check_route(std, "Sonnet 5", spec, host="claude-code")                          # fast < standard
    check("check_route flags a below-route mismatch",
          below["status"] == "mismatch" and below["direction"] == "below", failures)
    check("mismatch reports the session's own tier", below["current_tier"] == "fast", failures)

    front = ra.advise(ra.signals_for(["adr"], [], spec), spec, host="claude-code")            # frontier-reasoning
    above = ra.check_route(front, "Opus 4.8", spec, host="claude-code")                       # standard < frontier
    check("check_route flags an above vs below correctly",
          above["status"] == "mismatch" and above["direction"] == "below", failures)
    over = ra.check_route(std, "Fable 5", spec, host="claude-code")                           # frontier > standard
    check("a session above the route reads 'above'",
          over["status"] == "mismatch" and over["direction"] == "above", failures)

    unknown = ra.check_route(std, "gpt-4", spec, host="claude-code")
    check("check_route degrades to unknown-model off-catalog", unknown["status"] == "unknown-model", failures)
    check("unknown-model carries no session tier", unknown["current_tier"] is None, failures)

    # --- format_check: the three verdicts, and the honest effort caveat everywhere ---
    ok_txt = ra.format_check(ok, heading="labels: severity:medium")
    check("OK verdict prints ROUTE-OK", "ROUTE-OK" in ok_txt, failures)
    mis_txt = ra.format_check(below)
    check("mismatch verdict prints ROUTE-MISMATCH", "ROUTE-MISMATCH" in mis_txt, failures)
    check("mismatch names the record_run bypass", "--route-mismatch" in mis_txt, failures)
    unk_txt = ra.format_check(unknown, host="claude-code")
    check("unknown verdict prints ROUTE-CHECK (cannot compare)",
          "ROUTE-CHECK" in unk_txt and "cannot compare" in unk_txt, failures)
    for label, txt in (("ok", ok_txt), ("mismatch", mis_txt), ("unknown", unk_txt)):
        check(f"{label} states effort is not verifiable", "not verifiable" in txt, failures)
        check(f"{label} states the advisory boundary", "advisory" in txt.lower(), failures)

    # --- the CLI --check path: always exit 0, whatever the verdict ---
    #
    # These two cases must keep BEING an OK and a mismatch. Hardcoding model names here made them
    # decay silently every time the catalog moved (#326): 'Sonnet 5' rose from fast to standard and
    # the mismatch case became a second OK, then 'Opus 4.8' left the catalog entirely and the OK
    # case became an unknown-model. Both stayed green while testing nothing. So: derive the models
    # from the live catalog, and assert the VERDICT rather than only the exit code — a future
    # reshuffle turns these red instead of quiet.
    # The CLI resolves its own host through the 19.4 ladder, which is ENVIRONMENT-dependent: on a
    # developer box it detects claude-code, on a CI runner it resolves to nothing and there are no
    # models to compare against. This test is about the --check verdicts, not about detection
    # (which has its own cases above), so it pins the host on both sides.
    _live = ra.load_routing()
    _host = "claude-code"
    live_models = ra.models_by_tier(_live, _host)
    verdicts = {}
    for slot in ("standard", "fast"):                    # standard == the floor, fast == below it
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            verdicts[slot] = (ra.main(["--labels", "severity:medium", "--check", "--host", _host,
                                       "--current-model", live_models[slot]]), buf.getvalue())
    check("--check OK exits 0", verdicts["standard"][0] == 0, failures)
    check("--check OK actually reports a match (not a silently-passing unknown-model)",
          "ROUTE-OK" in verdicts["standard"][1], failures)
    check("--check MISMATCH still exits 0 (advisory, never a gate)", verdicts["fast"][0] == 0, failures)
    check("--check MISMATCH actually reports a mismatch (not a silently-passing OK)",
          "ROUTE-MISMATCH" in verdicts["fast"][1], failures)
    check("--check unknown-model still exits 0",
          ra.main(["--labels", "severity:medium", "--check", "--current-model", "gpt-4"]) == 0, failures)
    check("--check without --current-model is a usage error (exit 2)",
          ra.main(["--labels", "severity:medium", "--check"]) == 2, failures)
    check("--check with --milestone is refused (exit 2)",
          ra.main(["--milestone", "M18", "--check", "--current-model", "Opus 4.8"]) == 2, failures)

    if failures:
        print("\ntest-route-advice: FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("test-route-advice: OK — monotonic escalation, loud spec rejection, catalog/alias "
          "resolution, and the advisory boundary all hold (M16 16.2).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
