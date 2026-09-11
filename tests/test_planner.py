# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The planner (roadmap 5.11, spec 04 §2, ADR-0083).

The claims under test, in the order they matter:

**The plan narrows; the configuration decides.** A plan may withhold a leg the
configuration enabled and may never enable one it disabled. This is the rule that
lets a router be added to a query path whose every default was set by
measurement, and it is asserted directly rather than trusted.

**The rules are spec 04 §2's, and they are deterministic.** Identifier-like
tokens and quoted phrases ask for the symbol leg; the relationship phrasings and
`--related` ask for the graph leg; anything else is a natural-language question.

**Routing is reported.** Spec 04 §2 requires `explain` to carry the chosen plan
and the rule that chose it, on the CLI and over MCP.

**The shipped ranking is untouched.** Both derived legs are off by default, so a
default search plans the same legs it always ran.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from mycelium.build import build
from mycelium.config import RetrievalConfig
from mycelium.planner import GENERATORS, GRAPH, LEXICAL, SYMBOL, VECTOR, plan_query
from mycelium.retrieval import retrieval_identity, search
from mycelium.store import SqliteStore

CORPUS = {
    "knowledge/policy.md": (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5P01\n---\n\n"
        "# RetryPolicy\n\nThe retry policy bounds how often a delivery is "
        "attempted. See [[transport]].\n\n```python\nclass RetryPolicy:\n"
        "    attempts = 5\n```\n"
    ),
    "knowledge/transport.md": (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5P02\n---\n\n"
        "# Transport\n\nDelivery is attempted over the transport, which reads "
        "the policy before each attempt.\n"
    ),
}
"""Two documents, one link, one fenced definition — enough for every leg to have
something to reach for, and small enough to build per module."""

# ---------------------------------------------------------------------------
# The rules (spec 04 §2's table)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "rule"),
    [
        ("SqliteStore", "identifier"),
        ("uv.lock", "identifier"),
        ("what is in pyproject.toml", "identifier"),
        ('"an exact phrase"', "identifier"),
        ("what does the determinism gate depend on", "relationship"),
        ("which documents are related to this one", "relationship"),
        ("what uses the build cache", "relationship"),
        ("WHAT DEPENDS ON the store", "relationship"),
        ("how do I report a security vulnerability", "natural-language"),
        ("why does chunking not use overlap", "natural-language"),
        ("", "natural-language"),
    ],
)
def test_a_query_matches_the_rule_spec_04_2_gives_it(query: str, rule: str) -> None:
    assert plan_query(query).rules == (rule,)


def test_the_caller_can_say_a_question_is_a_relationship_question() -> None:
    """`--related` is spec 04 §2's other half of the relationship cell, and the
    reliable half: a phrase list reaches 3 of 22 judged relationship queries."""
    query = "can an agent keep querying while a build is running"
    assert plan_query(query).rules == ("natural-language",)
    assert plan_query(query, related=True).rules == ("relationship",)
    assert plan_query(query, related=True).asks_for(GRAPH)


def test_signals_are_independent_rather_than_first_match_wins() -> None:
    """A query that names an identifier *and* asks a relationship question keeps
    both legs. First-match-wins would drop one silently (ADR-0083)."""
    plan = plan_query("what depends on pyproject.toml")
    assert plan.rules == ("identifier", "relationship")
    assert plan.generators == frozenset({LEXICAL, VECTOR, SYMBOL, GRAPH})


def test_every_plan_asks_for_the_lexical_leg_and_only_known_generators() -> None:
    """Lexical is the floor below which retrieval cannot fall, and a plan that
    named a leg the query path does not have would route into nothing."""
    for query in ("SqliteStore", "what depends on x", "an ordinary question", ""):
        plan = plan_query(query)
        assert plan.asks_for(LEXICAL)
        assert plan.generators <= set(GENERATORS)
        assert plan.rules and plan.why


def test_a_plan_is_a_pure_function_of_its_inputs() -> None:
    query = "what depends on the store"
    assert plan_query(query) == plan_query(query)
    assert plan_query(query, related=True) == plan_query(query, related=False), (
        "a query the phrasing rule already routes is routed the same way when the "
        "caller says so too - the signals agree rather than accumulate"
    )
    ordinary = "how the store works"
    assert plan_query(ordinary, related=True) != plan_query(ordinary, related=False)


# ---------------------------------------------------------------------------
# The narrowing rule
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory) -> Iterator[SqliteStore]:
    """Built once: every test here only reads."""
    root = Path(tmp_path_factory.mktemp("planner")) / "repo"
    for relative, text in CORPUS.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    build(root)
    with SqliteStore.open(root, read_only=True) as opened:
        yield opened


def test_a_plan_never_enables_a_leg_the_configuration_disabled(store: SqliteStore) -> None:
    """The load-bearing rule: a regex must not be able to overturn a verdict
    three gates decided (ADR-0017, ADR-0075, ADR-0080)."""
    outcome = search(store, "what depends on the retry policy", config=RetrievalConfig())
    assert plan_query("what depends on the retry policy").asks_for(GRAPH)
    assert GRAPH not in outcome.legs
    assert VECTOR not in outcome.legs

    outcome = search(store, "RetryPolicy", config=RetrievalConfig())
    assert plan_query("RetryPolicy").asks_for(SYMBOL)
    assert SYMBOL not in outcome.legs


def test_a_plan_withholds_a_leg_the_configuration_enabled(store: SqliteStore) -> None:
    """The half the configuration cannot do for itself: the flag permits the leg,
    and the query decides whether it is the kind that wants it."""
    enabled = RetrievalConfig(graph_expansion=True)
    ordinary = search(store, "how do I configure retries", config=enabled)
    assert GRAPH not in ordinary.legs
    assert any("graph leg not planned" in note for note in ordinary.notes)

    asked = search(store, "how do I configure retries", config=enabled, related=True)
    assert any("graph leg" in note and "not planned" not in note for note in asked.notes)


def test_the_symbol_leg_is_withheld_from_a_query_that_names_nothing(store: SqliteStore) -> None:
    enabled = RetrievalConfig(symbol_lookup=True)
    outcome = search(store, "how does the policy work", config=enabled)
    assert SYMBOL not in outcome.legs
    assert any("symbol leg not planned" in note for note in outcome.notes)


def test_the_shipped_default_plans_the_legs_it_always_ran(store: SqliteStore) -> None:
    """Both derived legs are off by default, so routing cannot move the shipped
    ranking — which is why this change re-blesses no baseline."""
    for query in ("RetryPolicy", "what depends on the store", "an ordinary question"):
        outcome = search(store, query, config=RetrievalConfig())
        assert outcome.legs == (LEXICAL,)


# ---------------------------------------------------------------------------
# Reporting (spec 04 §2's own obligation)
# ---------------------------------------------------------------------------


def test_the_outcome_reports_the_plan_and_the_rule_that_chose_it(store: SqliteStore) -> None:
    outcome = search(store, "RetryPolicy", config=RetrievalConfig())
    explained = outcome.explain()
    assert explained["plan"] == outcome.plan.as_dict()
    plan = explained["plan"]
    assert isinstance(plan, dict)
    assert plan["rules"] == ["identifier"]
    assert "RetryPolicy" in str(plan["why"])
    assert sorted(plan["generators"]) == plan["generators"]


def test_the_routing_rules_are_part_of_the_rankings_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`retrieval_identity` dates gate G2's verdict, and the phrasings decide
    whether the graph leg runs — so a verdict measured under one set of them is
    not about another (ADR-0064's rule, ADR-0083)."""
    from mycelium import planner, retrieval

    before = retrieval_identity()
    monkeypatch.setattr(retrieval, "RELATIONSHIP_PHRASES", (*planner.RELATIONSHIP_PHRASES, "x"))
    assert retrieval_identity() != before
