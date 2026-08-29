#!/usr/bin/env python3
"""Tests for the routing-delegation self-lint check (#255, M16 16.4) —
eados_lint.routing_delegation_problems.

The advisory routing policy (16.1-16.3) is *applied* — not merely printed — in exactly one place:
`orchestrator/os/routing/delegation.md`, the delegation hook. This check keeps that doc honest and
wired: it must be pointed at from commands/README.md and os/routing/_schema.md, must resolve routes
through route_advice.py, must document the advisory-only fallback, and must account for EVERY
catalog host (applied or advisory-only) so a host added to the catalog cannot ship without a stated
delegation posture. These pin the pure helper off in-memory fixtures plus the live factory tree.
Dependency-free.

    python .eados-core/tools/tests/test_routing_delegation.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint  # noqa: E402  (the module under test)

REPO_ROOT = os.path.dirname(lint.ROOT)

# A well-formed delegation doc: names the evaluator, documents the advisory fallback, and lists
# both catalog hosts of the SPEC fixture below.
DELEGATION_OK = (
    "# The delegation routing hook\n"
    "Resolve via route_advice.py and pass model + effort with the delegation.\n"
    "| **claude-code** | anthropic | yes | **applied** |\n"
    "| **codex** | openai | not today | **advisory-only** |\n"
)
README_OK = "See [`../os/routing/delegation.md`](../os/routing/delegation.md) for the hook."
SCHEMA_OK = "The applied path is specified in [`delegation.md`](./delegation.md)."
SPEC = {"catalog": {"hosts": [{"id": "claude-code"}, {"id": "codex"}]}}


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    P = lint.routing_delegation_problems

    # --- happy path: wired, evaluator-named, fallback documented, every host accounted for ---
    check("a fully wired delegation doc is clean",
          P(DELEGATION_OK, README_OK, SCHEMA_OK, SPEC) == [], failures)

    # --- README does not point at delegation.md ---
    r = P(DELEGATION_OK, "no pointer here", SCHEMA_OK, SPEC)
    check("an unreferenced doc (README) is flagged",
          any("README.md does not point at" in p for p in r), failures)

    # --- _schema.md does not reference delegation.md ---
    s = P(DELEGATION_OK, README_OK, "no reference", SPEC)
    check("an unreferenced doc (schema) is flagged",
          any("_schema.md does not reference delegation.md" in p for p in s), failures)

    # --- the doc restates the policy instead of delegating to the evaluator ---
    noeval = P("applied vs advisory-only for claude-code and codex", README_OK, SCHEMA_OK, SPEC)
    check("a doc that never names route_advice.py is flagged",
          any("does not name route_advice.py" in p for p in noeval), failures)

    # --- the advisory-only fallback is undocumented ---
    nofb = P("route_advice.py for claude-code and codex, all applied", README_OK, SCHEMA_OK, SPEC)
    check("a doc with no advisory fallback is flagged",
          any("documents no advisory-only fallback" in p for p in nofb), failures)

    # --- a catalog host missing from the matrix (the anti-rot property) ---
    three = {"catalog": {"hosts": [{"id": "claude-code"}, {"id": "codex"},
                                    {"id": "nowhere-host"}]}}
    miss = P(DELEGATION_OK, README_OK, SCHEMA_OK, three)
    check("a catalog host absent from the matrix is flagged",
          any("no matrix ROW for catalog host 'nowhere-host'" in p for p in miss), failures)

    # --- #327: the REVERSE direction, which the one-way check could not see at all ---
    ghost = DELEGATION_OK + "| **cursor** | anthropic | not today | **advisory-only** |\n"
    rev = P(ghost, README_OK, SCHEMA_OK, SPEC)
    check("a matrix row for a host the catalog does not have is flagged",
          any("declares a delegation posture for 'cursor'" in p for p in rev), failures)
    check("the two directions carry distinguishable messages",
          all("no matrix ROW" not in p for p in rev), failures)

    # --- rows are read STRUCTURALLY: a host named in prose is not a declaration ---
    # This is exactly what left the old substring test unable to notice a DELETED row: the shipped
    # delegation.md legitimately says things like "Run the same relay on codex or gemini…", so the
    # host's name was present in the file whether or not it had a row.
    prose_only = ("# The delegation routing hook\n"
                  "Resolve via route_advice.py; the advisory-only fallback applies.\n"
                  "| **claude-code** | anthropic | yes | **applied** |\n"
                  "Run the same relay on codex and it degrades to advisory-only.\n")
    pr = P(prose_only, README_OK, SCHEMA_OK, SPEC)
    check("a host named only in prose does not count as a declared row",
          any("no matrix ROW for catalog host 'codex'" in p for p in pr), failures)
    check("matrix_hosts reads rows, not prose",
          set(lint.matrix_hosts(prose_only)) == {"claude-code"}, failures)

    # --- the posture IS the point of the row, so a row without one is a hole ---
    nopost = ("# hook\nroute_advice.py; advisory-only fallback documented.\n"
              "| **claude-code** | anthropic | yes | **applied** |\n"
              "| **codex** | openai | not today | tbd |\n")
    check("a matrix row stating neither posture is flagged",
          any("states neither 'applied' nor 'advisory-only'" in p
              for p in P(nopost, README_OK, SCHEMA_OK, SPEC)), failures)
    check("posture parsing distinguishes applied from advisory-only",
          lint.matrix_hosts(DELEGATION_OK) == {"claude-code": "applied", "codex": "advisory-only"},
          failures)

    # --- a None/parse-failed spec degrades quietly (data-file-validity owns that failure) ---
    check("a missing spec does not crash the host loop",
          P(DELEGATION_OK, README_OK, SCHEMA_OK, None) == [], failures)

    # --- live invariant: the factory's own delegation doc is present and wired ---
    collected = []
    lint.check_routing_delegation(lambda _name, msg: collected.append(msg))
    check(f"the shipped delegation hook is wired and host-complete (got {collected})",
          collected == [], failures)

    if failures:
        print("test-routing-delegation: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-routing-delegation: OK — the delegation hook doc must be wired from README + "
          "schema, name the evaluator, document the advisory fallback, and account for every "
          "catalog host; the live tree satisfies all of it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
