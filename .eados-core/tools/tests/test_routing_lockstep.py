#!/usr/bin/env python3
"""Tests for the two M19 19.5 gates (#326): `catalog-freshness` and `routing-model-lockstep`.

Both exist because of one incident. Model names lived in TWO homes — `os/routing/routing.yaml`'s
dated catalog and the READMEs' ranking prose — with nothing between them, and they drifted into
direct disagreement: for weeks the catalog routed every ADR, security and foundational-decision
unit of work to a model all three READMEs called *not benchmarked*, while the one they ranked
first sat a tier below. Every gate was green throughout.

So the point of these tests is not that the shipped tree passes — it is that a tree in the #326
state FAILS. A lockstep gate that cannot reproduce the drift it was written for is decoration.

    python .eados-core/tools/tests/test_routing_lockstep.py
"""

import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint    # noqa: E402  (the module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def spec(as_of="2026-07-27", budget=90, verified="2026-07-27"):
    return {"catalog": {
        "as_of": as_of, "max_age_days": budget,
        "providers": [
            {"id": "anthropic", "models": [
                {"id": "fable-5", "name": "Fable 5", "meets_tier": "frontier-reasoning",
                 "assessed": True, "verified": verified},
                {"id": "haiku-4-5", "name": "Haiku 4.5", "assessed": False},
            ]},
        ],
        "hosts": [{"id": "claude-code", "providers": ["anthropic"]}],
    }}


def main():
    failures = []
    today = datetime.date(2026, 7, 27)

    # --- catalog-freshness ---------------------------------------------------------------
    check("a fresh catalog passes", lint.catalog_freshness_problems(spec(), today) == [], failures)

    stale = lint.catalog_freshness_problems(spec(as_of="2026-01-01"), today)
    check("a catalog past its budget fails", stale != [], failures)
    check("the staleness message says what to DO, not just that a number was exceeded",
          any("re-verify" in p for p in stale), failures)
    check("the message names the age and the budget",
          any("207 days old" in p and "90-day" in p for p in stale), failures)

    check("a model verified longer ago than the budget is flagged",
          any("verified" in p for p in
              lint.catalog_freshness_problems(spec(verified="2026-01-01"), today)), failures)
    check("a non-ISO as_of is rejected",
          lint.catalog_freshness_problems(spec(as_of="July 2026"), today) != [], failures)
    check("a missing staleness budget is a problem — without it there is no gate",
          lint.catalog_freshness_problems(spec(budget=None), today) != [], failures)

    # --- routing-model-lockstep ----------------------------------------------------------
    CLAUSE = "not yet benchmarked"
    good = ("EADOS performs best with **Fable 5**.\n\n"
            "Other families are " + CLAUSE + " for EADOS.\n\n")
    check("prose that names every assessed model, outside the unassessed clause, passes",
          lint.model_lockstep_problems(spec(), [("README.md", good, CLAUSE)]) == [], failures)

    # Rule 1 — drift by omission: the catalog routes to a model the prose never mentions.
    silent = "EADOS works well.\n\nOther families are " + CLAUSE + " for EADOS.\n\n"
    probs = lint.model_lockstep_problems(spec(), [("README.md", silent, CLAUSE)])
    check("a catalog model the prose never names is drift", probs != [], failures)
    check("the omission names the model", any("Fable 5" in p for p in probs), failures)

    # Rule 2 — THE #326 REPRODUCTION. The catalog routes the most consequential work to Fable 5
    # while the prose lists Fable 5 among the models nobody has benchmarked. This exact tree was
    # live for weeks with every gate green; it must now be impossible.
    contradiction = ("EADOS performs best with **Opus 4.8**.\n\n"
                     "The rest of the family (including **Fable 5**) are " + CLAUSE + " for EADOS.\n\n")
    probs = lint.model_lockstep_problems(spec(), [("README.md", contradiction, CLAUSE)])
    check("#326 reproduced: an assessed model listed as NOT benchmarked fails", probs != [],
          failures)
    check("the contradiction is reported as a contradiction, naming the model",
          any("Fable 5" in p and "contradict" in p for p in probs), failures)

    # A surface with no unassessed clause at all is simply not subject to rule 2.
    check("a surface without the clause is not forced to have one",
          lint.model_lockstep_problems(
              spec(), [("USAGE.md", "Routing uses **Fable 5**.\n", CLAUSE)]) == [], failures)

    # An UNassessed model is not a routing target, so the prose may freely call it unbenchmarked.
    ok_unassessed = ("Best: **Fable 5**.\n\nAlso **Haiku 4.5** is " + CLAUSE + " for EADOS.\n\n")
    check("an unassessed model may be named in the unassessed clause",
          lint.model_lockstep_problems(spec(), [("README.md", ok_unassessed, CLAUSE)]) == [],
          failures)

    # --- the shipped tree, in all three languages ----------------------------------------
    shipped = lint._load_spec("routing")
    if isinstance(shipped, dict):
        surfaces = []
        for rel, clause in lint.README_SURFACES:
            path = (os.path.join(lint.REPO_ROOT, rel) if rel == "README.md"
                    else os.path.join(lint.ROOT, rel))
            if os.path.exists(path):
                surfaces.append((rel, lint.read(path), clause))
        check("all three README languages are covered", len(surfaces) == 3, failures)
        check("the shipped tree is in lockstep",
              lint.model_lockstep_problems(shipped, surfaces) == [], failures)
        check("the shipped catalog is within its own budget",
              lint.catalog_freshness_problems(shipped, datetime.date.today()) == [], failures)

    if failures:
        print("test-routing-lockstep: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-routing-lockstep: OK — the catalog stays fresh, the prose and the catalog cannot "
          "contradict each other, and the #326 tree fails as it always should have.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
