#!/usr/bin/env python3
"""Tests for the interaction-lockstep gate (eados_lint check #21, M17 17.3 / #279) — the
interaction policy is data (os/interaction/interaction.yaml); 17.2 rendered it into the two agent
contracts. This gate keeps prose and data congruent: every banned opener and every confidence tag
the spec declares must be present in EACH rendered surface. Pure-function tests on
interaction_lockstep_problems() with in-memory fixtures — a congruent pair is clean, and every kind
of drift (a dropped banned phrase, a dropped confidence tag, in either surface) is caught.
Dependency-free.

    python .eados-core/tools/tests/test_interaction_lockstep.py
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


def spec():
    """A minimal interaction policy carrying two lockstep vocabularies."""
    return {
        "confidence": {"levels": ["certain", "likely", "guessing"]},
        "sycophancy": {"banned_openers": ["Great question", "You're absolutely right", "Absolutely"]},
    }


def surface(openers, levels):
    """A rendered contract surface that carries the given openers + confidence tags (plus prose)."""
    body = "The counterpart to the persona. Tag load-bearing claims.\n"
    body += " ".join(f'*"{o}"*' for o in openers) + "\n"
    body += " ".join(f"`{v}`" for v in levels) + "\n"
    return body


def main():
    failures = []

    s = spec()
    openers = s["sycophancy"]["banned_openers"]
    levels = s["confidence"]["levels"]
    congruent = surface(openers, levels)

    check("a congruent surface has no lockstep problems",
          el.interaction_lockstep_problems(s, [("AGENTS.md", congruent),
                                               ("tmpl", congruent)]) == [], failures)

    def caught(surfaces, needle):
        return any(needle in prob for prob in el.interaction_lockstep_problems(s, surfaces))

    # A dropped banned opener in a surface fails — data is the source of truth.
    check("a surface omitting a banned opener is caught",
          caught([("AGENTS.md", surface(openers[:-1], levels))], "Absolutely"), failures)
    # A dropped confidence tag in a surface fails.
    check("a surface omitting a confidence tag is caught",
          caught([("AGENTS.md", surface(openers, levels[:-1]))], "guessing"), failures)
    # Drift is reported per surface — the second surface is checked too, not just the first.
    check("drift in the SECOND surface is caught (not only the first)",
          caught([("AGENTS.md", congruent), ("tmpl", surface(openers[:-1], levels))],
                 "tmpl"), failures)
    # The apostrophe phrase must match verbatim — a straight-vs-curly mismatch would drift.
    check("a straight-apostrophe opener is matched verbatim",
          el.interaction_lockstep_problems(
              {"sycophancy": {"banned_openers": ["You're absolutely right"]},
               "confidence": {"levels": ["certain"]}},
              [("s", "prefix You're absolutely right `certain` suffix")]) == [], failures)

    # Robustness: a missing/unparseable spec is deferred to the completeness gates, not double-reported.
    check("a None interaction spec yields no problems (deferred to os-spec-completeness)",
          el.interaction_lockstep_problems(None, [("AGENTS.md", congruent)]) == [], failures)
    # A spec with neither vocabulary is itself a problem — nothing to lock the surfaces to.
    check("an empty spec (no vocabularies) is flagged",
          any("no banned_openers or confidence.levels" in prob
              for prob in el.interaction_lockstep_problems({}, [("AGENTS.md", congruent)])), failures)

    # The on-disk contract: the real spec + the two committed surfaces are actually in lockstep, so
    # a green suite here is not just an artifact of the fixtures (mirrors the live-render assertions
    # elsewhere in the suite).
    live_spec = el._load_spec("interaction")
    live_surfaces = []
    for label, path in (("AGENTS.md", os.path.join(el.REPO_ROOT, "AGENTS.md")),
                        ("tmpl", os.path.join(el.TEMPLATES, "AGENTS.md.tmpl"))):
        if os.path.exists(path):
            live_surfaces.append((label, el.read(path)))
    if isinstance(live_spec, dict) and live_surfaces:
        check("the real interaction spec and the committed contract surfaces are in lockstep",
              el.interaction_lockstep_problems(live_spec, live_surfaces) == [], failures)

    if failures:
        print("test-interaction-lockstep: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-interaction-lockstep: OK -- the contract surfaces carry every banned phrase + "
          "confidence tag; every drift is caught.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
