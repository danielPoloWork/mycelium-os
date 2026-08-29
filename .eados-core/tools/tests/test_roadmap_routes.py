#!/usr/bin/env python3
"""Unit tests for the scaffold routing surface (#306, ADR-0023).

Pins the render-side half of os/routing template parity: `routed_item` (the {text, signals[]}
object form gains a derived advisory route; plain strings pass through untouched), the
`ROUTE_*` legend scalars (`routing_scalars` — catalog values asserted AGAINST the spec, never
literal model names, so a catalog refresh never edits this file), `milestone_item_problems`
(malformed objects and inert signals rejected loudly; legacy manifests acquire no routing
dependency), the `build_context` wiring, and an end-to-end ROADMAP.md.tmpl render off the
reference manifest — the acceptance surface of #306. Dependency-free.

    python .eados-core/tools/tests/test_roadmap_routes.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import render  # noqa: E402  (the module under test)

ROOT = os.path.dirname(TOOLS)
REFERENCE = os.path.join(ROOT, "orchestrator", "examples", "reference.yaml")
ROADMAP_TMPL = os.path.join(ROOT, "templates", "ROADMAP.md.tmpl")


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def _broken_loader():
    raise ValueError("simulated unreadable routing spec")


def main():
    # issue #128: force UTF-8 stdio — failure labels may echo the em-dash route notation
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    failures = []
    routing = render._load_routing()

    # --- routed_item: the per-item derivation --------------------------------
    check("legacy string passes through untouched",
          render.routed_item("2.1 Plain item", routing) == "2.1 Plain item", failures)
    check("adr signal earns frontier-reasoning / extra",
          render.routed_item({"text": "3.2 Record the ADR", "signals": ["adr"]}, routing)
          == "3.2 Record the ADR — route: frontier-reasoning / extra (adr)", failures)
    check("severity:medium earns standard / medium",
          render.routed_item({"text": "4.1 Fix gap", "signals": ["severity:medium"]}, routing)
          == "4.1 Fix gap — route: standard / medium (severity:medium)", failures)
    check("object with no signals renders the explicit floor",
          render.routed_item({"text": "4.2 Docs"}, routing)
          == "4.2 Docs — route: fast / low", failures)
    check("only-raise: max over floor and every match",
          render.routed_item({"text": "4.3 X", "signals": ["security", "severity:medium"]},
                             routing)
          == "4.3 X — route: frontier-reasoning / extra (security, severity:medium)", failures)
    check("foundational pair escalates effort to max",
          render.routed_item({"text": "4.4 Y", "signals": ["decision-heavy", "severity:high"]},
                             routing).endswith(
              "— route: frontier-reasoning / max (decision-heavy, severity:high)"), failures)

    # --- routing_scalars: the legend ------------------------------------------
    sc = render.routing_scalars(routing)
    check("ROUTE_TIERS is the spec ladder, cheapest first",
          sc["ROUTE_TIERS"] == "fast → standard → frontier-reasoning", failures)
    check("ROUTE_EFFORTS is the spec ladder, lowest first",
          sc["ROUTE_EFFORTS"] == " → ".join(routing["efforts"]), failures)
    check("ROUTE_FLOOR is the defaults pair", sc["ROUTE_FLOOR"] == "fast / low", failures)
    check("ROUTE_CATALOG_AS_OF mirrors the spec's dated catalog",
          sc["ROUTE_CATALOG_AS_OF"] == str((routing.get("catalog") or {}).get("as_of")),
          failures)
    # Catalog content asserted against the SPEC's values (a catalog refresh must not edit this
    # test): every host appears, and each tier maps to that host's current model name.
    import route_advice as _ra   # schema v2: the tier→model map is PROJECTED, not stored per host
    for host in (routing.get("catalog") or {}).get("hosts") or []:
        hid = host["id"]
        check(f"ROUTE_CATALOG names host {hid}",
              f"**{hid}**" in sc["ROUTE_CATALOG"], failures)
        projected = _ra.models_by_tier(routing, hid)
        for tier in routing["tiers"]:
            # A tier with no assessed reachable model renders "—" (ADR-0024 D6), which is a value
            # this assertion must accept rather than a gap it should paper over.
            check(f"ROUTE_CATALOG maps {hid}/{tier} to its catalog value",
                  f"{tier} → {projected.get(tier) or '—'}" in sc["ROUTE_CATALOG"], failures)

    # --- milestone_item_problems: loud validation -----------------------------
    clean = {"milestones": [{"items": ["2.1 ok", {"text": "2.2 ok", "signals": ["adr"]}]}],
             "milestone1_items": [{"text": "1.6 extra"}]}
    check("both forms validate clean", render.milestone_item_problems(clean) == [], failures)

    probs = render.milestone_item_problems(
        {"milestones": [{"items": [{"text": "", "signals": "adr", "oops": 1}]}],
         "milestone1_items": "not-a-list"})
    check("empty text rejected", any(".text is missing" in p for p in probs), failures)
    check("non-list signals rejected",
          any(".signals must be a list" in p for p in probs), failures)
    check("unknown item key rejected",
          any(".oops is not a recognized key" in p for p in probs), failures)
    check("non-list milestone1_items rejected",
          any("spec.milestone1_items must be a list" in p for p in probs), failures)

    probs = render.milestone_item_problems(
        {"milestones": [{"items": [{"text": "2.1 t", "signals": ["set-pattern"]}]}]})
    check("inert signal rejected loudly (the sets-pattern typo class)",
          any("'set-pattern'" in p and "inert" in p for p in probs), failures)
    check("inert-signal message teaches the known vocabulary",
          any("sets-pattern" in p and "security" in p for p in probs), failures)
    check("empty signal entry rejected",
          any("empty or non-string" in p for p in
              render.milestone_item_problems(
                  {"milestones": [{"items": [{"text": "2.1 t", "signals": [""]}]}]})), failures)

    # --- unreadable routing spec: loud where needed, inert where not ----------
    orig = render._load_routing
    render._load_routing = _broken_loader
    try:
        probs = render.milestone_item_problems(clean)
        check("object items + unreadable spec name the real cause",
              any("os/routing" in p and "unreadable" in p for p in probs), failures)
        check("legacy-only manifests acquire no routing dependency",
              render.milestone_item_problems(
                  {"milestones": [{"items": ["2.1 plain"]}]}) == [], failures)
        scalars, _f, sections = render.build_context(
            {"spec": {"milestones": [{"items": [{"text": "2.1 t"}]}]}})
        check("degraded build_context leaves ROUTE_* absent (unresolved-placeholder backstop)",
              "ROUTE_FLOOR" not in scalars, failures)
        check("degraded build_context leaves object items raw (validation names the cause)",
              isinstance(sections["EACH_MILESTONE"][0]["items"][0], dict), failures)
    finally:
        render._load_routing = orig

    # --- build_context wiring --------------------------------------------------
    scalars, _f, sections = render.build_context(
        {"spec": {"milestones": [{"number": 2, "items": ["2.1 plain",
                                                         {"text": "2.2 t", "signals": ["adr"]}]}],
                  "milestone1_items": [{"text": "1.6 extra"}]}})
    check("build_context exposes the legend scalars", scalars["ROUTE_FLOOR"] == "fast / low",
          failures)
    check("build_context keeps legacy items verbatim",
          sections["EACH_MILESTONE"][0]["items"][0] == "2.1 plain", failures)
    check("build_context suffixes object items",
          sections["EACH_MILESTONE"][0]["items"][1]
          == "2.2 t — route: frontier-reasoning / extra (adr)", failures)
    check("build_context routes milestone1_items too",
          sections["EACH_MILESTONE1_ITEM"][0] == "1.6 extra — route: fast / low", failures)

    # --- end-to-end: the reference manifest through ROADMAP.md.tmpl (#306 acceptance) ---
    with open(REFERENCE, encoding="utf-8") as handle:
        manifest = render.load_yaml(handle.read())
    scalars, flags, sections = render.build_context(manifest)
    check("reference manifest validates clean",
          render.validate_manifest(manifest, scalars) == [], failures)
    with open(ROADMAP_TMPL, encoding="utf-8") as handle:
        tmpl = handle.read()
    errs = []
    out = render.render(tmpl, scalars, flags, sections, None, "ROADMAP.md.tmpl", errs)
    check("ROADMAP renders with no unresolved placeholders", errs == [], failures)
    check("legend section rendered", "## Model & effort routing (advisory)" in out, failures)
    check("legend carries the dated catalog snapshot",
          sc["ROUTE_CATALOG"] in out and sc["ROUTE_CATALOG_AS_OF"] in out, failures)
    check("signalled item carries its derived route",
          "- [ ] 2.1 Add the thread-safe allocation path (lock-free free-list or sharded "
          "locks) — route: frontier-reasoning / high (sets-pattern)" in out, failures)
    check("object item without signals carries the explicit floor",
          "- [ ] 3.1 Add the reproducible allocation/deallocation benchmarks — route: fast / low"
          in out, failures)
    check("plain-string item renders unchanged (no route suffix)",
          "- [ ] 2.2 Wire TSan into CI and add the multi-threaded stress test\n" in out
          and "2.2 Wire TSan into CI and add the multi-threaded stress test — route" not in out,
          failures)

    if failures:
        print("test-roadmap-routes: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} routing-surface behaviour(s) wrong.")
        return 1
    print("test-roadmap-routes: OK — routed items, legend scalars, loud validation, and the "
          "rendered ROADMAP all hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
