#!/usr/bin/env python3
"""Tests for the agent-registry self-lint check (#202) — eados_lint.agent_registry_problems.

The registry (agent/README.md) is the catalogue side of the persona != authority split
(RFC-0001 §4). The check used to be ONE-WAY — it failed a persona file missing from the index, but
a dead index link (a persona renamed or deleted) stayed green, unlike its sibling hygiene checks
(workflow-safety, gate-coverage). These pin the now-bidirectional pure helper off an in-memory
index + file set, and confirm that links which ESCAPE agent/ (../, http(s)://, absolute) are never
probed on disk. Dependency-free (runs in the self-lint job).

    python .eados-core/tools/tests/test_agent_registry.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint  # noqa: E402  (the module under test)

# An index with two personas (one nested overlay), plus the real-world non-persona links that must
# be IGNORED: two `../`-escaping README links, an http link, an absolute link, and the index's own
# README.md self-reference.
INDEX = (
    "| [`enterprise-architect`](enterprise-architect.md) | the orchestrator |\n"
    "| [`domains/game/product-manager`](domains/game/product-manager.md) | game overlay |\n"
    "See [`../config/agents/`](../config/README.md) and "
    "[`../learning/lessons.yaml`](../learning/README.md).\n"
    "External [`docs`](https://example.com/guide.md), absolute [`x`](/etc/x.md), "
    "and the index itself [`README`](README.md).\n"
)
PERSONAS = {"enterprise-architect.md", "domains/game/product-manager.md"}


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    P = lint.agent_registry_problems

    # --- happy path: the index and the persona set agree both ways; escaping links are ignored ---
    check("a consistent index + file set has no problems", P(INDEX, PERSONAS) == [], failures)

    # --- forward (the pre-existing direction): a persona on disk missing from the index fails ---
    fwd = P(INDEX, PERSONAS | {"release-manager.md"})
    check("an unlisted persona is flagged (forward)",
          any("release-manager.md" in p and "not listed" in p for p in fwd), failures)

    # --- reverse (the #202 direction): a dead index link (persona deleted/renamed) fails ---
    rev = P(INDEX, {"enterprise-architect.md"})   # domains/game/product-manager.md no longer exists
    check("a dead index link is flagged (reverse)",
          any("domains/game/product-manager.md" in p and "does not exist" in p for p in rev),
          failures)

    # --- the caveat from the issue: links escaping agent/ must NOT be probed as personas ---
    escaping = (
        "[`../config/README.md`](../config/README.md)\n"
        "[`../learning/README.md`](../learning/README.md)\n"
        "[`nested/../up.md`](nested/../up.md)\n"
        "[`ext`](https://x/y.md)\n[`abs`](/z.md)\n[`self`](README.md)\n"
    )
    check("../-escaping, http(s), absolute, and README self-links are excluded from the probe",
          P(escaping, set()) == [], failures)

    # --- the link extractor keeps only the persona-relative .md links ---
    links = lint._persona_relative_links(INDEX)
    check("the extractor keeps the persona-relative links", links == PERSONAS, failures)

    # --- on-disk: the shipped agent/README.md is consistent both directions on the current tree ---
    collected = []
    lint.check_agent_registry(lambda _name, msg: collected.append(msg))
    check(f"the shipped agent/README.md is consistent both ways (got {collected})",
          collected == [], failures)

    if failures:
        print("test-agent-registry: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-agent-registry: OK — the registry check is bidirectional; escaping links are "
          "ignored; the shipped index is consistent both ways.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
